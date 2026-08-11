#!/usr/bin/env python3
"""Enable the 218x150 thumbnail size and build it for existing images.

The symptom
-----------
Every "Related articles" thumbnail on the site was a grey placeholder reading
"218 x 150 — Enable thumb from THEME PANEL + BLOCK SETTINGS". That is the
theme's own placeholder, not a broken image: the block asks for `td_218x150`
and no such file exists for any attachment.

The cause
---------
Newspaper registers its intermediate sizes from flags in the `td_011` option,
one per size. The working sizes read "yes"; `tds_thumb_td_218x150` was empty,
so `add_image_size` was never called for it, so WordPress never cut the crop.
Confirmed against the media library: of twenty recent images, all twenty had
td_80x60, td_100x70, td_150x0, td_300x0 and td_324x400, and none had
td_218x150.

Why two steps
-------------
Turning the flag on only affects uploads from that moment. WordPress cuts
intermediate sizes once, at upload, so the 500-odd images already in the
library stay without one until they are told to make the missing crop. That is
the second pass here, and it uses `wp_update_image_subsizes`, which generates
only the sizes that are absent and leaves the existing files alone.

Load
----
The regeneration runs in small batches with a pause between them. Cutting
every missing crop for the whole library in one request is how you exhaust
PHP-FPM on shared hosting, and the site staying up matters more than this
finishing quickly.

Usage:
    python3 fix_thumbnails.py                  # dry run: report, change nothing
    python3 fix_thumbnails.py --execute        # enable the size, then backfill
    python3 fix_thumbnails.py --execute --batch 5 --pause 3
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

import requests

from backfill_images import session, WP_URL

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("thumbnails")

CS = f"{WP_URL}/wp-json/code-snippets/v1/snippets"
H = {"Cache-Control": "no-cache"}
SNIPPET_NAME = "Avoltium thumbnail repair (used by fix_thumbnails.py)"

# The block that renders "Related articles" asks for these two. The retina
# variant is what a phone or a Mac actually loads, so enabling only the base
# size would leave the placeholder in place on exactly the devices most
# readers use.
WANTED = ["td_218x150", "td_218x150_retina"]

PHP = r"""
/**
 * Enable a Newspaper thumbnail size and build it for existing attachments.
 *
 * Installed by fix_thumbnails.py and safe to delete once that has run.
 */
add_action('rest_api_init', function () {
    register_rest_route('av/v1', '/thumbsize', [
        'methods' => 'POST',
        'permission_callback' => function () { return current_user_can('manage_options'); },
        'callback' => function ($req) {
            $sizes = (array) ($req->get_json_params()['sizes'] ?? []);
            $opt = get_option('td_011', []);
            if (!is_array($opt)) {
                return new WP_Error('bad_option', 'td_011 is not an array', ['status' => 500]);
            }
            $changed = [];
            foreach ($sizes as $s) {
                $key = 'tds_thumb_' . preg_replace('/[^a-z0-9_]/', '', (string) $s);
                // Only flip flags the theme already defines. Inventing a key
                // would write a setting the theme never reads.
                if (!array_key_exists($key, $opt)) { continue; }
                if ($opt[$key] !== 'yes') { $opt[$key] = 'yes'; $changed[] = $key; }
            }
            if ($changed) { update_option('td_011', $opt); }
            return ['changed' => $changed, 'registered' => get_intermediate_image_sizes()];
        },
    ]);

    register_rest_route('av/v1', '/regen', [
        'methods' => 'POST',
        'permission_callback' => function () { return current_user_can('manage_options'); },
        'callback' => function ($req) {
            // wp_update_image_subsizes and wp_get_missing_image_subsizes live in
            // wp-admin, which a REST request does not load. Without this the
            // route fatals on an undefined function and every batch returns 500.
            require_once ABSPATH . 'wp-admin/includes/image.php';
            require_once ABSPATH . 'wp-admin/includes/file.php';
            require_once ABSPATH . 'wp-admin/includes/media.php';

            $body   = $req->get_json_params();
            $offset = max(0, (int) ($body['offset'] ?? 0));
            $limit  = min(25, max(1, (int) ($body['limit'] ?? 10)));

            $ids = get_posts([
                'post_type'      => 'attachment',
                'post_mime_type' => 'image',
                'post_status'    => 'inherit',
                'posts_per_page' => $limit,
                'offset'         => $offset,
                'orderby'        => 'ID',
                'order'          => 'ASC',
                'fields'         => 'ids',
            ]);

            $built = [];
            $failed = [];
            foreach ($ids as $id) {
                // Generates only the sizes that are missing; existing files
                // are left untouched. Cheaper and safer than rebuilding the
                // whole set, which would also re-compress what is already there.
                $missing = wp_get_missing_image_subsizes($id);
                if (empty($missing)) { continue; }
                $res = wp_update_image_subsizes($id);
                if (is_wp_error($res)) {
                    $failed[] = ['id' => $id, 'why' => $res->get_error_message()];
                    continue;
                }
                $built[] = ['id' => $id, 'sizes' => array_keys($missing)];
            }
            return ['scanned' => count($ids), 'built' => $built, 'failed' => $failed];
        },
    ]);

    register_rest_route('av/v1', '/imgcount', [
        'methods' => 'GET',
        'permission_callback' => function () { return current_user_can('manage_options'); },
        'callback' => function () {
            $q = new WP_Query([
                'post_type' => 'attachment', 'post_mime_type' => 'image',
                'post_status' => 'inherit', 'posts_per_page' => 1, 'fields' => 'ids',
            ]);
            return ['total' => (int) $q->found_posts,
                    'registered' => get_intermediate_image_sizes()];
        },
    ]);
}, 20);
"""


def install_snippet(auth) -> None:
    """Install the size-flag and regeneration endpoints."""
    for _ in range(8):
        listing = requests.get(CS, auth=auth, timeout=60, headers=H,
                               params={"_ts": time.time()}).json()
        if isinstance(listing, list):
            break
        time.sleep(4)
    else:
        raise SystemExit("Code Snippets API did not return a list")

    existing = next((x for x in listing if x.get("name") == SNIPPET_NAME), None)
    payload = {"name": SNIPPET_NAME, "desc": "Enable and backfill a thumbnail size.",
               "code": PHP, "scope": "global", "priority": 10, "active": True}
    r = (requests.put(f"{CS}/{existing['id']}", auth=auth, json=payload, timeout=120, headers=H)
         if existing else
         requests.post(CS, auth=auth, json=payload, timeout=120, headers=H))
    if r.status_code not in (200, 201):
        raise SystemExit(f"snippet install failed: HTTP {r.status_code} — {r.text[:200]}")


def wait_for_route(auth) -> dict:
    """Block until the read route answers, and return what it reports."""
    for _ in range(10):
        time.sleep(4)
        r = requests.get(f"{WP_URL}/wp-json/av/v1/imgcount", auth=auth, timeout=60,
                         headers=H, params={"_ts": time.time()})
        if r.status_code == 200:
            return r.json()
    raise SystemExit("the repair endpoint never came up")


def main() -> int:
    """Enable the missing size, then cut it for every image already uploaded."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--batch", type=int, default=10,
                    help="attachments per request (max 25)")
    ap.add_argument("--pause", type=float, default=2.0,
                    help="seconds between batches, to spare the host")
    args = ap.parse_args()

    auth = session().auth

    if not args.execute:
        logger.info("[DRY-RUN] would enable %s and rebuild missing crops for every "
                    "image in the library. Re-run with --execute.", ", ".join(WANTED))
        logger.info("Installing the endpoint is itself a write, so this mode stops here.")
        return 0

    install_snippet(auth)
    before = wait_for_route(auth)
    total = before["total"]
    logger.info("%d image attachments; %d sizes registered before the change",
                total, len(before["registered"]))

    r = requests.post(f"{WP_URL}/wp-json/av/v1/thumbsize", auth=auth, timeout=120,
                      headers=H, json={"sizes": WANTED})
    if r.status_code != 200:
        raise SystemExit(f"could not enable the size: HTTP {r.status_code} — {r.text[:200]}")
    body = r.json()
    logger.info("enabled: %s", ", ".join(body["changed"]) or "(already on)")

    after = wait_for_route(auth)
    if "td_218x150" not in after["registered"]:
        raise SystemExit("td_218x150 is still not registered after enabling the flag — "
                         "stopping rather than regenerating against the old set.")
    logger.info("td_218x150 is now registered")

    built = failed = 0
    for offset in range(0, total, args.batch):
        r = requests.post(f"{WP_URL}/wp-json/av/v1/regen", auth=auth, timeout=300,
                          headers=H, json={"offset": offset, "limit": args.batch})
        if r.status_code != 200:
            logger.error("batch at %d failed: HTTP %s — %s", offset, r.status_code,
                         r.text[:160])
            failed += args.batch
            continue
        b = r.json()
        built += len(b["built"])
        failed += len(b["failed"])
        for f in b["failed"]:
            logger.error("  attachment %s: %s", f["id"], f["why"])
        logger.info("%4d/%-4d  built %d, failed %d", min(offset + args.batch, total),
                    total, built, failed)
        time.sleep(args.pause)

    logger.info("done — %d attachment(s) given missing crops, %d failed", built, failed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
