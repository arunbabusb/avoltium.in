# avoltium.in — AdSense "Low value content" remediation

Status as of 13 Aug 2026: **Needs attention — Low value content**, last updated
11 Aug 2026. `ads.txt` is authorised. The site is not serving ads and will not
serve any until the flag clears, so no amount of ad-placement work moves
revenue here. The flag is the whole problem.

## What the audit found

Measured against the live site:

| Signal | Finding | Verdict |
|---|---|---|
| Published posts | 51 | Adequate |
| Published pages | 15 | Adequate |
| Article depth (3 sampled) | 1,593 / 1,748 / 1,667 words | Good |
| Policy pages | Privacy, Terms, Disclaimer, About, Contact, Editorial standards, Corrections, Ownership & funding | Strong — better than most sites that pass |
| `robots.txt` | Present, sitemaps declared | Correct |
| `wp-sitemap.xml` | Present and populated | Correct |
| Ad units on page | 0 `<ins>` elements | Moot until approved |

So the usual causes — thin content, missing policy pages, no About/Contact,
blocked crawling — do **not** apply here. That narrows the likely triggers.

## Most likely triggers, in order

1. **News reposts.** A large share of recent posts are rewrites of press
   releases and industry news (`publish_news.py`, `news_sources.py`,
   `rewrite_content.py`). Reviewers treat rewritten wire copy as republished
   content regardless of word count. This is the single most probable cause.
2. **Originality-to-aggregation ratio.** The consulting and technical-insight
   articles are genuinely original; the news stream is not. If the news stream
   outnumbers the original work in the index, the site reads as an aggregator.
3. **Publication burst pattern.** Batches of posts sharing a single date
   (16 Mar, 07 Aug) read as bulk generation rather than an editorial calendar.
4. **Site-purpose clarity.** The homepage spans consulting, technical insights
   and news. A reviewer landing cold should be able to tell in one screen what
   original value the site provides.

## What to actually do

Ordered by impact per unit of effort. Steps 1–4 are content work only you can
do — I cannot make them from the repo, and no code change substitutes for them.

1. **Stop the automated news publishing until the flag clears.** Pause any cron
   running `publish_news.py`. Adding more rewritten wire copy while under
   review works directly against the appeal.
2. **Prune or de-index the weakest news reposts.** For each news post, ask: does
   this add analysis a reader cannot get from the source? If not, either add
   real analysis (your own read on what it means for India's H2 buildout) or set
   it `noindex`. Aim to have original analysis clearly outnumber reposts.
3. **Publish 5–8 genuinely original pieces** in the site's actual area of
   authority — electrolyzer sizing, LCOH modelling, water treatment,
   commissioning practice. The three calculators (`/lcoh-calculator/`,
   `/electrolyzer-calculator/`, `/water-consumption-treatment-calculator/`) are
   real differentiated assets; write the methodology articles that explain and
   link to them. This is the strongest possible signal of original value.
4. **Make the homepage state the site's purpose above the fold** — who runs it,
   what expertise it brings, why its analysis is worth reading. Link the
   ownership, editorial standards and corrections pages prominently; they are
   already written and they help.
5. **Then request review** in AdSense → Sites → avoltium.in. Reviews take
   roughly 2–4 weeks. Requesting a review before steps 1–4 are visibly done
   burns the cycle.

## Two things to verify in the AdSense UI

- **Loader host parameter.** The live page loads
  `adsbygoogle.js?client=ca-pub-8459363476525914&host=ca-host-pub-2644536267352236`.
  The `host=` parameter marks the request as coming through a host-partner
  account. If this is unintentional (it is added by some Site Kit
  configurations), reconnecting Site Kit to the standalone AdSense account
  removes it. Worth checking, but it is not the cause of the content flag.
- **Duplicate loader.** The page loads the AdSense script twice. Harmless while
  ads are off; remove one copy before approval so units are not double-requested.

## The honest summary

avoltium.in is closer to passing than the flag suggests — the depth, the policy
pages and the calculators are all above bar. The one thing dragging it under is
the automated news stream. Turn that off, tilt the ratio toward original
analysis, then appeal.
