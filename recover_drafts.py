# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests",
#     "python-dotenv"
# ]
# ///
"""Publish drafts that the QC gate parked for a recoverable reason.

When `generate_article.py` finishes an article but the featured image fails,
the QC image rule is a BLOCKER, so the post is saved as a draft. The article
itself is fine — it is one image away from publishable — but nothing ever
went back for it. Post 1115 ("LCOH Deep Dive", 5 Aug 2026) sat that way.

This script finds those drafts, regenerates the missing image, re-runs the
full QC suite, and publishes only if every blocker is now clear. A draft
failing QC for any *other* reason is reported and left alone: thin content
and LaTeX in the body are editorial problems, not transient ones, and a
human should see them.
"""
import os
import sys

import requests
from dotenv import load_dotenv

import qc_check
import resilient
from generate_article import (
    TOPICS,
    fetch_contextual_image,
    make_excerpt,
    upload_image_to_wp,
)

load_dotenv()

WP_URL = os.environ.get("WP_URL", "https://www.avoltium.in").rstrip("/")
auth = (os.environ.get("WP_USERNAME"), os.environ.get("WP_APP_PASSWORD"))

# Only image blockers are auto-recoverable — they are the transient ones.
RECOVERABLE_BLOCKERS = ("no featured image", "featured image has no alt text")


def fetch_drafts() -> list[dict]:
    """Every draft post, newest first."""
    drafts, page = [], 1
    while True:
        res = resilient.request_with_retry(
            "GET",
            f"{WP_URL}/wp-json/wp/v2/posts",
            attempts=3,
            label="wp/drafts",
            params={"status": "draft", "per_page": 50, "page": page},
            auth=auth,
            timeout=30,
        )
        if res is None or res.status_code != 200:
            status = res.status_code if res is not None else "no response"
            print(f"ERROR: could not list drafts — {status}", flush=True)
            break

        batch = res.json()
        drafts.extend(batch)
        if len(batch) < 50:
            break
        page += 1

    return drafts


def fetch_media(media_id: int) -> dict | None:
    """Media record in the shape qc_check.check_image expects."""
    if not media_id:
        return None
    res = resilient.request_with_retry(
        "GET",
        f"{WP_URL}/wp-json/wp/v2/media/{media_id}",
        attempts=2,
        label=f"wp/media/{media_id}",
        auth=auth,
        timeout=30,
    )
    if res is None or res.status_code != 200:
        return None
    return res.json()


def topic_for(title: str) -> str:
    """Map a post title back to its TOPICS key for the image prompt.

    Dated review titles carry a suffix ("<topic>: August 2026 Engineering
    Review"), so a prefix match recovers the original topic. An unmatched
    title falls through to the generic prompt in fetch_contextual_image.
    """
    if title in TOPICS:
        return title
    for key in TOPICS:
        if title.startswith(key):
            return key
    return title


def recover(post: dict) -> bool:
    """Try to make one draft publishable. True when it went live."""
    post_id = post["id"]
    title = post["title"]["rendered"]
    content = post["content"]["rendered"]
    print(f"\n[{post_id}] {title[:70]}", flush=True)

    media = fetch_media(post.get("featured_media") or 0)
    issues = qc_check.check_post(title, content, media)
    fatal = qc_check.blockers(issues)

    if not fatal:
        print("  no blockers — publishing as-is.", flush=True)
        return publish(post_id, title, content, None)

    unrecoverable = [b for b in fatal if b not in RECOVERABLE_BLOCKERS]
    if unrecoverable:
        for b in unrecoverable:
            print(f"  BLOCKER (needs a human): {b}", flush=True)
        return False

    # Every remaining blocker is about the image, so build a new one.
    print(f"  recoverable: {', '.join(fatal)}", flush=True)
    topic = topic_for(title)
    image_bytes = fetch_contextual_image(topic)
    if not image_bytes:
        print("  image generation failed again — leaving as draft.", flush=True)
        return False

    media_id = upload_image_to_wp(image_bytes, topic)
    if not media_id:
        print("  image upload failed — leaving as draft.", flush=True)
        return False

    # Re-run the full suite against the repaired post rather than assuming
    # the new image cleared everything.
    recheck = qc_check.check_post(
        title,
        content,
        {"alt_text": topic, "media_details": {"width": 1200, "height": 675}},
    )
    still_fatal = qc_check.blockers(recheck)
    if still_fatal:
        for b in still_fatal:
            print(f"  BLOCKER after repair: {b}", flush=True)
        return False

    return publish(post_id, title, content, media_id)


def publish(post_id: int, title: str, content: str, media_id: int | None) -> bool:
    """Publish one held draft, attaching an excerpt and image where available."""
    payload = {"status": "publish"}
    if media_id:
        payload["featured_media"] = media_id
    if not (payload_excerpt := make_excerpt(content)):
        # An empty excerpt lets Google invent its own snippet — see §7 of
        # editorial_standards.md.
        print("  WARNING: could not derive an excerpt.", flush=True)
    else:
        payload["excerpt"] = payload_excerpt

    res = resilient.request_with_retry(
        "POST",
        f"{WP_URL}/wp-json/wp/v2/posts/{post_id}",
        attempts=3,
        label=f"wp/publish/{post_id}",
        headers={"Content-Type": "application/json"},
        auth=auth,
        json=payload,
        timeout=60,
    )
    if res is not None and res.status_code == 200:
        print(f"  PUBLISHED: {res.json().get('link', post_id)}", flush=True)
        return True

    status = res.status_code if res is not None else "no response"
    print(f"  publish failed — {status}", flush=True)
    return False


def main() -> int:
    """Publish the drafts that now pass QC; exit non-zero if any are still held."""
    drafts = fetch_drafts()
    if not drafts:
        print("No drafts pending. Nothing to recover.", flush=True)
        return 0

    print(f"{len(drafts)} draft(s) pending review.", flush=True)
    published = sum(1 for post in drafts if recover(post))
    remaining = len(drafts) - published

    print(f"\n{'=' * 60}")
    print(f"RESULT: {published} published, {remaining} still held as drafts")

    # Red run when something is still stuck, so a draft needing an editor is
    # visible in the Actions tab instead of passing silently.
    return 1 if remaining else 0


if __name__ == "__main__":
    sys.exit(main())
