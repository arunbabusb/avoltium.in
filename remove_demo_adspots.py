#!/usr/bin/env python3
"""Remove the Newspaper demo ad banner from the tagDiv Cloud Templates.

What this is actually removing
------------------------------
A "The news you need — now available from your pocket" banner with App Store
and Google Play badges, advertising an app that does not exist, linking to
`href="#"`. It shipped with the theme's demo content.

Where it lives, since three earlier guesses were wrong. It is **not** a Theme
Panel ad spot — every slot in `td_011`'s `td_ads` is empty. It is not in any
option, and no post body mentions it. Searching for the filename finds only
the two media-library attachments themselves, because the block references the
image by attachment id:

    [td_block_ad_box spot_url="#" ... spot_img_all="48"]

That element sits in six tagDiv Cloud Templates — Single, Category, Author,
Search, Date and Tag — which is why the banner appears on articles and on
every archive page. Deleting the attachments would not help; the block would
just render a broken image.

Safety
------
`--backup` writes every tdb_templates row to JSON before anything changes, and
`--restore` puts them back from that file. The edit itself is the removal of a
self-closing shortcode with no children, so nothing around it is disturbed;
the regex stops at the first `]`, and the base64 in `tdc_css` contains none.

Usage:
    python3 remove_demo_adspots.py --backup            # write the backup only
    python3 remove_demo_adspots.py                     # dry run, shows the plan
    python3 remove_demo_adspots.py --execute
    python3 remove_demo_adspots.py --restore           # undo, from the backup
"""
from __future__ import annotations

import argparse
import json
import logging
import pathlib
import re
import sys
import time

import requests

from backfill_images import session, WP_URL

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("adspots")

CS = f"{WP_URL}/wp-json/code-snippets/v1/snippets"
H = {"Cache-Control": "no-cache"}
SNIPPET_NAME = "Avoltium template editor (used by remove_demo_adspots.py)"
BACKUP = pathlib.Path("tdb_templates_backup.json")

# Self-closing, no children, and no `]` can appear inside the attributes.
AD_BOX = re.compile(r"\[td_block_ad_box\b[^\]]*\]")

PHP = r"""
/**
 * Read and write tdb_templates post_content over REST.
 *
 * The templates are a custom post type that the WordPress REST API does not
 * expose, so there is no built-in endpoint to edit them through. Installed by
 * remove_demo_adspots.py and safe to delete once that has run.
 */
add_action('rest_api_init', function () {
    register_rest_route('av/v1', '/templates', [
        'methods'  => 'GET',
        'permission_callback' => function () { return current_user_can('manage_options'); },
        'callback' => function () {
            global $wpdb;
            $out = [];
            $ids = $wpdb->get_col("SELECT ID FROM {$wpdb->posts} WHERE post_type='tdb_templates'");
            foreach ($ids as $id) {
                $out[$id] = ['title' => get_the_title($id),
                             'content' => get_post_field('post_content', $id)];
            }
            return $out;
        },
    ]);
    register_rest_route('av/v1', '/templates', [
        'methods'  => 'POST',
        'permission_callback' => function () { return current_user_can('manage_options'); },
        'callback' => function ($req) {
            global $wpdb;
            $body = $req->get_json_params();
            $done = [];
            $failed = [];
            foreach (($body['templates'] ?? []) as $id => $content) {
                $id = (int) $id;
                if (get_post_type($id) !== 'tdb_templates') {
                    $failed[] = ['id' => $id, 'why' => 'not a tdb_templates row'];
                    continue;
                }
                // wp_update_post runs the content through kses for some roles
                // and would strip the shortcodes; write the column directly.
                // update() returns false on error and 0 when nothing changed;
                // only false is a failure, since a no-op means the row already
                // holds this exact content.
                $res = $wpdb->update($wpdb->posts, ['post_content' => $content], ['ID' => $id]);
                if ($res === false) {
                    $failed[] = ['id' => $id, 'why' => $wpdb->last_error ?: 'update failed'];
                    continue;
                }
                clean_post_cache($id);
                $done[] = $id;
            }
            // tagDiv compiles template CSS on save; drop it so it regenerates.
            delete_option('td_011_generated_css');
            return ['updated' => $done, 'failed' => $failed];
        },
    ]);
}, 20);
"""


def install_snippet(auth) -> None:
    """Install the read/write endpoint the templates are edited through."""
    for _ in range(8):
        listing = requests.get(CS, auth=auth, timeout=60, headers=H,
                               params={"_ts": time.time()}).json()
        if isinstance(listing, list):
            break
        time.sleep(4)
    else:
        raise SystemExit("Code Snippets API did not return a list")

    existing = next((x for x in listing if x.get("name") == SNIPPET_NAME), None)
    payload = {"name": SNIPPET_NAME, "desc": "Read/write tdb_templates over REST.",
               "code": PHP, "scope": "global", "priority": 10, "active": True}
    r = (requests.put(f"{CS}/{existing['id']}", auth=auth, json=payload, timeout=120, headers=H)
         if existing else
         requests.post(CS, auth=auth, json=payload, timeout=120, headers=H))
    if r.status_code not in (200, 201):
        raise SystemExit(f"snippet install failed: HTTP {r.status_code} — {r.text[:200]}")


def endpoint_available(auth) -> bool:
    """Whether the read route is already installed, without installing it."""
    r = requests.get(f"{WP_URL}/wp-json/av/v1/templates", auth=auth, timeout=60,
                     headers=H, params={"_ts": time.time()})
    return r.status_code == 200


def purge(auth) -> None:
    """Drop the page cache so the next read reflects what was just written."""
    requests.post(f"{WP_URL}/wp-json/av/v1/purge", auth=auth, timeout=90, headers=H)


def read_templates(auth) -> dict:
    """Every tdb_templates row as {id: {title, content}}."""
    for _ in range(8):
        time.sleep(5)
        r = requests.get(f"{WP_URL}/wp-json/av/v1/templates", auth=auth, timeout=120,
                         headers=H, params={"_ts": time.time()})
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict) and data and all("content" in v for v in data.values()):
                return data
    raise SystemExit("could not read the templates")


def write_templates(auth, updates: dict) -> list:
    """Write {id: content} back. Returns the ids WordPress reports it saved.

    Exits if any requested template did not save. A partial rewrite is the
    worst outcome available here — some templates carrying the banner and
    some not, with the run having reported success.
    """
    r = requests.post(f"{WP_URL}/wp-json/av/v1/templates", auth=auth, timeout=120,
                      headers=H, json={"templates": updates})
    if r.status_code != 200:
        raise SystemExit(f"write failed: HTTP {r.status_code} — {r.text[:200]}")
    body = r.json()
    updated, failed = body.get("updated", []), body.get("failed", [])
    missing = set(map(int, updates)) - set(map(int, updated))
    if failed or missing:
        raise SystemExit(f"only {len(updated)} of {len(updates)} template(s) saved — "
                         f"failed={failed} missing={sorted(missing)}. "
                         f"Run --restore to put the originals back.")
    return updated


def main() -> int:
    """Strip the demo ad box from every template that carries one."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--backup", action="store_true", help="write the backup and stop")
    ap.add_argument("--restore", action="store_true", help="put the backup back")
    args = ap.parse_args()

    auth = session().auth
    # Installing the endpoint is itself a write, so the modes documented as
    # non-mutating must not do it. Reading templates needs the GET route, so a
    # dry run uses it if it is already there and says so plainly if not.
    if args.execute or args.restore:
        install_snippet(auth)
        purge(auth)
    elif not endpoint_available(auth):
        logger.error("The read endpoint is not installed, and installing it would "
                     "write to the site — which this mode does not do. Re-run with "
                     "--execute, which installs it and removes the ad boxes.")
        return 2

    if args.restore:
        if not BACKUP.exists():
            logger.error("no %s to restore from", BACKUP)
            return 1
        saved = json.loads(BACKUP.read_text())
        updated = write_templates(auth, {k: v["content"] for k, v in saved.items()})
        purge(auth)
        logger.info("restored %d template(s) from %s", len(updated), BACKUP)
        return 0

    live = read_templates(auth)
    BACKUP.write_text(json.dumps(live, indent=2, ensure_ascii=False))
    logger.info("backed up %d template(s) -> %s (%d KB)",
                len(live), BACKUP, BACKUP.stat().st_size // 1024)
    if args.backup:
        return 0

    updates = {}
    for pid, t in sorted(live.items(), key=lambda kv: int(kv[0])):
        stripped = AD_BOX.sub("", t["content"])
        removed = len(AD_BOX.findall(t["content"]))
        if removed:
            logger.info("  %-5s %-46s -%d ad box(es), %d -> %d chars",
                        pid, re.sub(r"&#8211;", "-", t["title"])[:46], removed,
                        len(t["content"]), len(stripped))
            updates[pid] = stripped

    if not updates:
        logger.info("No demo ad box found. Nothing to do.")
        return 0
    if not args.execute:
        logger.info("[DRY-RUN] would rewrite %d template(s). Re-run with --execute.", len(updates))
        return 0

    updated = write_templates(auth, updates)
    purge(auth)
    logger.info("rewrote %d template(s): %s", len(updated), updated)

    # Prove it against the live page rather than trusting the write.
    time.sleep(6)
    page = requests.get(f"{WP_URL}/green-hydrogen-explained/", timeout=60, headers=H)
    if page.status_code != 200:
        # An error page contains no "custom-rec" either, which would read as a
        # clean result. Not being able to check is not the same as passing.
        logger.error("could not verify: the check page returned HTTP %s", page.status_code)
        return 1
    hits = page.text.count("custom-rec")
    logger.info("live single post now references custom-rec %d time(s)", hits)
    return 0 if hits == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
