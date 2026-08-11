#!/usr/bin/env python3
"""Publish the single authoritative profile / consultancy page.

Why this page exists
--------------------
The site publishes technical articles and engineering calculators, but nothing
on it says who is behind them. For a reference site that is the difference
between "some blog about hydrogen" and "written by the engineer who led India's
first membrane-less alkaline electrolyzer to pilot with ONGC and BPCL". Every
calculator and every article borrows its authority from this page, so there
should be exactly one of it, kept current, rather than a PDF emailed around.

Everything here is drawn from the CV and nothing is embellished. Where the CV
gives a number — 60% CAPEX reduction, 99.9% purity, ~$135K saved at Xylem —
the number is reproduced as stated and attributed to the role it came from.
Invented credentials on a page whose whole job is credibility would be
self-defeating.

Contact details
---------------
The published address is the role address hello@avoltium.in, never the personal
one from the CV. A consultancy page needs a contact route, but a personal
address on a crawled page is harvested within days, cannot be recalled, and
ties the business to one individual's inbox forever.

The personal mobile is likewise not published, for the same reason. Pass
--include-phone to override that.

Styling
-------
Self-contained and scoped under .av-profile so it cannot leak into the theme,
mobile-first, and it does not depend on the theme being responsive — which
matters, because the theme currently ships 291 fixed pixel widths wider than a
phone screen.

Env: WP_URL, WP_USERNAME, WP_APP_PASSWORD
Usage:
    python publish_profile.py                # dry run, writes profile.html
    python publish_profile.py --execute
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("profile")

WP_URL = (os.environ.get("WP_URL") or "https://www.avoltium.in").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME") or ""
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD") or ""

SLUG = "about-us"
TITLE = "Arun Babu — Green Hydrogen & Mechanical Engineering Consultancy"
EMAIL = "hello@avoltium.in"
PHONE = "+91-7019597352"

PAGES_READ = f"{WP_URL}/wp-json/wp/v2/pages"
PAGES_WRITE = f"{WP_URL}/?rest_route=/wp/v2/pages"

CSS = """
<style>
.av-profile{--ink:#151b23;--muted:#5c6672;--rule:#e2e7ee;--accent:#0a6694;
  --soft:#f4f8fb;max-width:1080px;margin:0 auto;color:var(--ink);
  font-size:17px;line-height:1.65;-webkit-text-size-adjust:100%}
.av-profile *{box-sizing:border-box;max-width:100%}
.av-profile h2,.av-profile h3{line-height:1.25;margin:0 0 .4em}
.av-profile h2{font-size:clamp(1.35rem,4vw,1.9rem);margin-top:2.2rem}
.av-profile h3{font-size:clamp(1.05rem,3vw,1.2rem)}
.av-hero{background:var(--soft);border:1px solid var(--rule);border-radius:14px;
  padding:clamp(20px,4vw,38px)}
.av-hero h1{font-size:clamp(1.6rem,5.5vw,2.5rem);line-height:1.15;margin:0 0 .3em}
.av-kicker{color:var(--accent);font-weight:700;letter-spacing:.06em;
  text-transform:uppercase;font-size:.78rem;margin:0 0 .8em}
.av-lede{font-size:clamp(1rem,2.6vw,1.15rem);color:var(--muted);margin:0}
.av-stats{display:grid;gap:14px;margin:26px 0 0;padding:0;list-style:none;
  grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.av-stats li{background:#fff;border:1px solid var(--rule);border-radius:10px;
  padding:14px 16px}
.av-stats b{display:block;font-size:clamp(1.25rem,4vw,1.6rem);color:var(--accent);
  line-height:1.1}
.av-stats span{font-size:.85rem;color:var(--muted)}
.av-grid{display:grid;gap:18px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.av-card{border:1px solid var(--rule);border-radius:12px;padding:20px;background:#fff}
.av-card h3{margin-top:0}
.av-card p{margin:0;color:var(--muted);font-size:.95rem}
.av-role{border-left:3px solid var(--accent);padding:2px 0 2px 18px;margin:0 0 26px}
.av-role h3{margin:0}
.av-meta{color:var(--muted);font-size:.9rem;margin:.2em 0 .7em}
.av-role ul{margin:.4em 0 0;padding-left:1.1em}
.av-role li{margin-bottom:.35em}
.av-tools{display:flex;flex-wrap:wrap;gap:8px;padding:0;margin:.6em 0 0;list-style:none}
.av-tools li{background:var(--soft);border:1px solid var(--rule);border-radius:999px;
  padding:6px 13px;font-size:.85rem;white-space:nowrap}
.av-cta{background:var(--accent);color:#fff;border-radius:14px;
  padding:clamp(20px,4vw,34px);margin-top:2.4rem}
.av-cta h2{color:#fff;margin-top:0}
.av-cta p{color:#dbeaf3}
.av-btn{display:inline-block;background:#fff;color:var(--accent);font-weight:700;
  padding:13px 24px;border-radius:8px;text-decoration:none;margin-top:10px;
  min-height:44px;line-height:1.4}
@media (max-width:600px){
  .av-profile{font-size:16px}
  .av-role{padding-left:14px}
  .av-stats{grid-template-columns:repeat(auto-fit,minmax(130px,1fr))}
}
</style>
"""


def build_html(include_phone: bool = False) -> str:
    """The profile page markup. The phone number is opt-in."""
    contact = f'<a href="mailto:{EMAIL}">{EMAIL}</a>'
    if include_phone:
        contact += f' &nbsp;·&nbsp; <a href="tel:{PHONE.replace("-", "")}">{PHONE}</a>'

    return CSS + f"""
<div class="av-profile">

  <div class="av-hero">
    <p class="av-kicker">Engineering consultancy</p>
    <h1>Arun Babu</h1>
    <p class="av-lede">Mechanical and green hydrogen engineer with nearly 15 years in
    R&amp;D product development. Led India's first membrane-less alkaline electrolyzer
    from concept to pilot commissioning with ONGC and BPCL.</p>
    <ul class="av-stats">
      <li><b>15</b><span>years in engineering R&amp;D</span></li>
      <li><b>60%</b><span>CAPEX reduction vs PEM systems</span></li>
      <li><b>99.9%</b><span>hydrogen purity achieved</span></li>
      <li><b>$135K</b><span>manufacturing cost removed at Xylem</span></li>
    </ul>
  </div>

  <h2>What I work on</h2>
  <div class="av-grid">
    <div class="av-card">
      <h3>Green hydrogen systems</h3>
      <p>Electrolyzer development from concept through prototype, pilot and scale-up.
      Alkaline and membrane-less architectures, balance of plant, gas purity and
      cost-down engineering.</p>
    </div>
    <div class="av-card">
      <h3>Mechanical R&amp;D and product development</h3>
      <p>End-to-end lifecycle under Stage-Gate and Agile: concept design, CAD, FEA and
      CFD validation, DFM/DFA, VA/VE and pilot commissioning.</p>
    </div>
    <div class="av-card">
      <h3>Water and fluid systems</h3>
      <p>Treatment trains, chlorination and clarifier systems, hydraulic calculations,
      pumps and valves — from Xylem water technology and electrolyzer feedwater work.</p>
    </div>
    <div class="av-card">
      <h3>Engineering process and PLM</h3>
      <p>PLM/PDM workflow, CAD standards, BOM governance, ECN/ECO management, SAP ERP,
      and CMMI Level 3 / ISO 9001 process implementation.</p>
    </div>
  </div>

  <h2>Track record</h2>

  <div class="av-role">
    <h3>Project Lead, R&amp;D — Green Hydrogen</h3>
    <p class="av-meta">Newtrace Pvt. Ltd., Bengaluru · May 2022 – Sep 2025 · first non-founder engineer</p>
    <ul>
      <li>Led the full R&amp;D lifecycle for India's first membrane-less alkaline green
      hydrogen electrolyzer, from concept and CAD through pilot commissioning and validation.</li>
      <li>Took the membrane-less electrolyzer from concept to pilot for <strong>ONGC and BPCL</strong>.</li>
      <li>Delivered a <strong>60% CAPEX reduction versus PEM systems</strong> at
      <strong>99.9% hydrogen purity</strong>, using SolidWorks, FEA and CFD.</li>
      <li>Established PLM workflow, CAD standards and BOM governance across R&amp;D,
      manufacturing and supply chain.</li>
      <li>Contributed to national recognition under India's Green Hydrogen Mission (PLI Award).</li>
    </ul>
  </div>

  <div class="av-role">
    <h3>Senior Engineer — Water Technology</h3>
    <p class="av-meta">Xylem India, Chennai · May 2020 – Jan 2022</p>
    <ul>
      <li>Led VA/VE on chlorinator systems with simulation-driven design optimization,
      cutting manufacturing cost by <strong>~$135K</strong>.</li>
      <li>Drove design improvements for clarifier systems through structured design review.</li>
    </ul>
  </div>

  <div class="av-role">
    <h3>Technical Consultant — Engineering &amp; AI Workflows</h3>
    <p class="av-meta">Mercor AI, Remote · Oct 2025 – Present</p>
    <ul>
      <li>Designs prompt-engineering frameworks, AI evaluation methodology and technical
      rubrics for engineering-domain models.</li>
      <li>Engineering consulting and project management across renewable energy and
      industrial sectors.</li>
    </ul>
  </div>

  <h2>Tools and methods</h2>
  <ul class="av-tools">
    <li>SolidWorks</li><li>AutoCAD</li><li>Autodesk Inventor</li><li>FEA</li><li>CFD</li>
    <li>Hydraulic calculations</li><li>GD&amp;T</li><li>PLM / PDM</li><li>ECN / ECO</li>
    <li>BOM management</li><li>SAP ERP</li><li>Stage-Gate NPD</li><li>DFM / DFA</li>
    <li>VA / VE</li><li>CMMI Level 3</li><li>ISO 9001 QMS</li><li>Python</li>
  </ul>

  <h2>Engineering tools on this site</h2>
  <div class="av-grid">
    <div class="av-card">
      <h3><a href="/lcoh-calculator/">LCOH Calculator</a></h3>
      <p>Levelised cost of hydrogen against electricity price, utilisation and CAPEX.</p>
    </div>
    <div class="av-card">
      <h3><a href="/electrolyzer-calculator/">Electrolyzer Calculator</a></h3>
      <p>Stack sizing and output for a given duty.</p>
    </div>
    <div class="av-card">
      <h3><a href="/water-consumption-treatment-calculator/">Water Consumption &amp; Treatment</a></h3>
      <p>Feedwater demand and treatment duty for an electrolyser plant.</p>
    </div>
  </div>

  <div class="av-cta">
    <h2>Consultancy enquiries</h2>
    <p>Electrolyzer development, balance of plant, water treatment trains, mechanical
    R&amp;D and engineering process governance.</p>
    <p>{contact}</p>
    <a class="av-btn" href="mailto:{EMAIL}">Start a conversation</a>
  </div>

</div>
"""


def session() -> requests.Session:
    """A requests session carrying the WordPress application-password auth."""
    s = requests.Session()
    s.auth = (WP_USERNAME, WP_APP_PASSWORD)
    s.headers.update({"User-Agent": "avoltium-profile/1.0"})
    return s


class LookupFailed(RuntimeError):
    """The lookup itself failed, which is not the same as finding nothing."""


def find_page(s: requests.Session, slug: str):
    """The existing page with this slug, or None if there is none.

    Raises LookupFailed when the request errors. Returning None for both
    outcomes meant a transient 500 read as "no such page", and the caller
    published a second page on a slug that already had one.
    """
    try:
        r = s.get(PAGES_READ, params={"slug": slug, "status": "publish,draft"}, timeout=30)
        if r.status_code != 200:
            raise LookupFailed(f"/{slug}: HTTP {r.status_code}")
        items = r.json()
    except requests.RequestException as exc:
        # A timeout or a dropped connection is a failed lookup, not an absent
        # page, and it must reach main as one rather than as a traceback.
        raise LookupFailed(f"/{slug}: {type(exc).__name__}: {exc}") from exc
    except ValueError as exc:
        raise LookupFailed(f"/{slug}: response was not JSON ({exc})") from exc
    if not isinstance(items, list):
        raise LookupFailed(f"/{slug}: expected a list, got {type(items).__name__}")
    return items[0] if items else None


def main() -> int:
    """Publish the profile page. Dry run by default; writes the HTML to --out."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--slug", default=SLUG)
    ap.add_argument("--include-phone", action="store_true",
                    help="publish the mobile number too (off by default: once crawled "
                         "a phone number cannot be recalled)")
    ap.add_argument("--out", default="profile.html")
    ap.add_argument("--delete-page", type=int, default=0,
                    help="permanently delete this page id before publishing. Used to "
                         "remove the orphan /home-mobile/ (557): it is published but "
                         "nothing serves it — mobile visitors get the normal homepage — "
                         "so it only exists in the sitemap as duplicate content.")
    args = ap.parse_args()

    body = build_html(include_phone=args.include_phone)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(body)
    logger.info("Rendered %d chars -> %s (phone %s)",
                len(body), args.out, "included" if args.include_phone else "withheld")

    if not args.execute:
        logger.info("[DRY-RUN] nothing published. Re-run with --execute.")
        return 0
    if not (WP_USERNAME and WP_APP_PASSWORD):
        logger.error("Missing WP credentials in env")
        return 2

    s = session()

    if args.delete_page:
        # force=true skips the trash. Requested explicitly, and irreversible
        # without a database backup.
        r = s.delete(f"{PAGES_WRITE}/{args.delete_page}", params={"force": "true"}, timeout=60)
        if r.status_code in (200, 410):
            logger.info("Permanently deleted page id=%s", args.delete_page)
        else:
            logger.error("Delete of id=%s failed: HTTP %s — %s",
                         args.delete_page, r.status_code, r.text[:200])
            return 1

    try:
        existing = find_page(s, args.slug)
    except LookupFailed as exc:
        # Guessing "no page" here would publish a duplicate on a slug that
        # already has one, and WordPress would silently serve it as
        # /slug-2/ -- two pages competing for the same search result.
        logger.error("Could not check whether /%s already exists: %s", args.slug, exc)
        return 1
    payload = {"title": TITLE, "content": body, "status": "publish", "slug": args.slug}
    if existing:
        logger.info("Updating existing page id=%s", existing["id"])
        r = s.post(f"{PAGES_WRITE}/{existing['id']}", json=payload, timeout=60)
    else:
        logger.info("Creating /%s", args.slug)
        r = s.post(PAGES_WRITE, json=payload, timeout=60)

    if r.status_code not in (200, 201):
        logger.error("Publish failed: HTTP %s — %s", r.status_code, r.text[:300])
        return 1
    logger.info("DONE — %s", r.json().get("link", f"{WP_URL}/{args.slug}/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
