# Why AdSense rejected the site again, and what this branch does about it

Measured against the live site on 11 August 2026: 51 published posts, 15
published pages, read through the WordPress REST API and by fetching pages
directly.

The previous rounds of work hardened the *publishing pipeline* — duplicate
detection in `news_sources.py`, selection tests, provenance and policy pages.
That work is sound, and the rules in it would have prevented the mess
described below. But it only governs what gets published *next*. Nothing ever
went back and cleaned up what was already live, and the live archive is the
only thing a reviewer reads. That is the gap this branch closes.

## What is actually on the site

### 1. Thirteen posts covering one event

India's first hydrogen train ran on 17 July 2026. Between 15 and 22 July the
site published thirteen posts about it:

| Date | Post |
| --- | --- |
| 07-15 | India set to launch its First Hydrogen Train under "Hydrogen for Heritage" |
| 07-15 | India's Hydrogen Train: Working, Advantages, Challenges |
| 07-16 | India's first hydrogen train signals a new era of green rail mobility |
| 07-16 | India's first hydrogen train set for July 17 launch: Route, features, FAQs |
| 07-16 | PM Modi to flag off India's first hydrogen-powered train |
| 07-17 | Why India's first hydrogen train is special |
| 07-17 | How does India's first hydrogen train work? The science behind the green engine |
| 07-17 | How India's first hydrogen-powered train works \| Explained |
| 07-17 | India launches first hydrogen-powered train built in the country |
| 07-19 | PM Modi Inaugurates India's First Hydrogen Train on Jind–Sonipat Route |
| 07-19 | India's First Hydrogen-Powered Train: Advancing Green Rail Mobility |
| 07-22 | Hydrogen rail signals clean energy leap |
| 07-22 | Hydrogen Trains: Fuel Cell Traction and Onboard Storage Explained |

Three separate "how it works" explainers, two Modi pieces, a preview and a
retrospective. Each one is a competent article on its own. Together they are
one press cycle spun out thirteen ways, which is exactly the pattern a policy
reviewer is scanning for.

Worth being clear about what this is *not*: they are not copied from each
other. Five-word phrase overlap between them is under 11%, no higher than
between unrelated posts on the site. They were written separately about one
subject. The problem is editorial judgement about what deserves its own post,
not plagiarism.

### 2. Thirty-seven posts link to a page that does not exist

Both article generators inject a "water treatment" link pointing at
`/water-consumption-calculator/`. The page is published at
`/water-consumption-treatment-calculator/`. The short slug has never existed,
so the link has 404'd since the first article that carried it — 46 occurrences
across 37 of the 51 posts.

`fix_articles.py` had a repair for this that made it worse: it rewrote
`/waterconsumptioncalculator/` to `/water-consumption-calculator/`, turning one
dead link into a different dead link.

Five more internal links lost their hyphens somewhere upstream
(`/2026/07/22/batteriesandhydrogencompetitorsorpartners/` and similar) and also
404. Total: 51 broken internal links. A reviewer clicking the highlighted
"water treatment" link in almost any article on the site lands on an error
page.

### 3. Ten posts display raw HTML to the reader

Wikimedia gives an image author as markup, not as a name. An early version of
the credit writer escaped that wholesale, so ten live pages carry a line that
reads, literally:

```
Featured Image Credit: <a href="//commons.wikimedia.org/wiki/User:Kyy0602"
title="User:Kyy0602">Scarlett Kang</a> / CC BY-SA 4.0 via Wikimedia Commons
```

Six of those ten also carry a *second*, correct credit lower down — and in
several cases the two name different photographs, because the featured image
was swapped later and only the new credit was rewritten. A credit naming the
wrong photographer is a licence problem, not only a cosmetic one.

### 4. Three theme demo pages are indexed

`/tds-checkout/`, `/tds-my-account/` and `/tds-login-register/` are tagDiv
Newspaper demo pages. They are in the sitemap. They contain no prose at all —
only the theme's generated CSS — and they advertise a shop and a member login
this site does not have.

## What this branch changes

| Change | Effect |
| --- | --- |
| `prune_low_value.py` | Retires 11 of the 13 train posts and the 3 demo pages to draft |
| `fix_internal_links.py` | Repairs all 51 broken internal links |
| `fix_image_credits.py` | Repairs the 10 broken/stale credit blocks |
| `publish_image_credits.py` | `clean_caption()` so escaped markup can't be re-emitted |
| `generate_article.py`, `rewrite_content.py` | Correct calculator slug in the injected link |
| `fix_articles.py` | Stops "repairing" the link into a second dead URL |
| `citations.json` + `editorial_provenance.py` | Sources on 12 posts, references on 20 |
| `news_sources.py`, `publish_news.py` | New articles cite only checkable links |
| `test_site_cleanup.py` | 54 offline tests over all of the above |
| `.github/workflows/site_cleanup.yml` | Manual dispatch, dry run by default |

Two of the thirteen train posts are kept: `hydrogen-train` (the 1,745-word
explainer of fuel-cell traction, which is the kind of piece the rest of the
site is built on) and the Jind–Sonipat inauguration report. An explainer plus
a record of the event is what a publication covering this story would have.

Nothing is deleted. Retired posts move to `draft`, which drops them from the
sitemap and the index while leaving every word recoverable — from the
WordPress admin, or with `prune_low_value.py --restore <journal> --execute`.
Published post count goes from 51 to 40.

The retire list is an explicit, reviewed manifest rather than a similarity
threshold. Thresholds were tried and abandoned: every one that grouped the
thirteen train posts also grouped "Gasket and Sealing Technology" with
"Compressor Technologies", and the Rs 22 crore startup award with the Rs 797
crore jetty approval. Unpublishing a good article to satisfy a number is worse
than leaving a duplicate up. `--audit` reports candidate clusters so the list
can grow by someone reading it.

## How to run it

Dry run first, and read the output — every script logs each page it would
touch and why:

```
Actions → "Site cleanup (AdSense review)" → Run workflow   (execute unchecked)
```

Then re-run with **execute** checked. Order inside the workflow matters and is
already set: retire first, then repair links, so links are never "fixed" to
point at a post that is about to be unpublished.

Afterwards, submit the 14 retired URLs for removal in Search Console.

## What this does not fix

This is the part that matters most, and it is not a code problem.

**All 51 posts carry "Drafted with AI assistance."** Every one of them ends
with the same generic Further reading block — the same three or four
government and industry landing pages, labelled in the markup as "Background
on this subject. These are not citations for individual statements above."
Across the whole site, exactly one post links to a specific news source.
`hydrogen.energy.gov` appears in 40 posts; `mnre.gov.in`, `pib.gov.in` and
`niti.gov.in` in 26 each.

So an AdSense reviewer opening any article sees: AI-drafted, with a set of
decorative links to institutional home pages that support nothing in
particular. "Low value content" is the name for precisely that, and no script
changes it. The duplicate cluster and the broken links are what made the
judgement obvious and quick; they are worth fixing, and fixing them is not
sufficient.

### Citations: eight posts done, the rest still to do

The first item on this list used to read "backfill real citations." That work
has now started rather than being recommended. `citations.json` carries
verified primary sources for eight news posts, and
`editorial_provenance.py` renders them as a **Sources** section above Further
reading:

| Post | Source | Verified |
| --- | --- | --- |
| 30 KTPA to four refineries | The India Post / ANI, 11 Aug 2026 | Full SIGHT Mode-2B split: Panipat 10, Bina 5, Vizag 5, Numaligarh 10 KTPA |
| Paradip jetty | DD News (Prasar Bharati), 27 Feb 2026 | Rs 797.17 cr, 4 MTPA, Paradip Port Authority, 24 months |
| Ohmium / InSolare | Ohmium press release, 28 May 2026 | 4 MW, up to 700 t/yr, NLC India, Neyveli |
| Certification portal | Energetica India, 18 Jun 2026 | Launched by Pralhad Joshi at MNRE workshop; 3,000 MW/yr electrolyser incentives |
| Haryana policy | NewsOnAir (Prasar Bharati), 17 Mar 2026 | Chief Secretary Anurag Rastogi; IOCL Panipat 10,000 TPA due Dec 2026 |
| Rs 22 crore startups | Business Standard, 17 Jun 2026 | Rs 22 cr to nine startups under a Rs 100 cr call |
| Cu₃Pt catalyst | Phys.org on *Electrochimica Acta* (2026) | IMDEA Materials; Pt-level ORR at 25% of the platinum loading |
| IIT Kanpur CoE | IIT Kanpur / The Tribune, Jul 2026 | ECOGEN, sanctioned by UPNEDA under UP Green Hydrogen Policy 2024 |

Each was checked by opening the source and confirming it carries the claim
the post is built on. Nothing was recorded from a search snippet. The rule
the file enforces on itself, and that the tests enforce on the file: no bare
domains, every source carries publisher and date, every entry records what
was verified and when.

**Three of the eight turned up a second problem.** The Paradip jetty was
announced 27 February and published here on 16 July; Haryana's policy was
announced 17 March and published 22 July; the Rs 22 crore award was announced
17 June and published 7 August. Those posts ran months-old announcements as
news. The datelines are now stated in the Sources block rather than left for
a reader to discover, but the underlying habit is worth stopping — it is
`news_sources.py`'s `max_age_hours` doing its job only for items that come
through the feed path.

Since then the backfill was finished: **12 posts carry reporting sources and
20 carry references** (standards and published datasets, rendered as a
separate list because they are a baseline, not reporting). Greenzo, the
SBICAPS report, BriHyNergy and the Kochi summit were added to the eight above.

**New articles are now cited automatically.** `publish_news.py` already
carried source URL, publisher and timestamp; two things were wrong with it and
are fixed. It linked Google News redirect URLs — the 11 August refinery post
cites "The Tribune" and links 668 characters of `news.google.com/rss/articles/`
whose payload is an opaque token that decodes to nothing. And a post carrying
a Source block then said underneath that nothing here cites any individual
statement. Now a citation is only offered where it leads somewhere checkable,
and the provenance note no longer contradicts it.

### Four posts that cannot be cited, and five whose titles do not match

Recorded in `citations.json` under `_UNCITABLE` and `_MISMATCHED`, with the
reason and a recommendation for each, because a silent gap looks like an
oversight and a plausible-but-wrong citation is worse than none:

- **Gujarat data centre policy** (15 July) calls the Viksit Gujarat policy
  "newly minted". It was notified 7 August — three weeks *after* this post ran
  — and the headline claim of "50%+ acceleration" traces to nothing published.
- **As told to Parliament** (21 July) is about women's share of the
  agricultural workforce, with a green ammonia aside attached.
- **Both roundups** aggregate many announcements with no single source.

And the pattern worth acting on: **26 of the 40 surviving posts carry a
water-treatment or feedstock-purity section, whatever the headline says.** One
template appears to have been applied across many titles. "Global Oil Markets
2026" mentions oil, OPEC, barrel or crude **twice** and electrolyzer or water
**34 times**; all four of its section headings are electrolyzer and water
treatment. The same holds for the drilling, offshore wind and compressor
posts, and "Building a Zero-Incident Safety Culture" is 423 words whose only
heading is "About this article".

That is the duplicate-content problem the hydrogen-train cluster made obvious,
in a form title-level checks do not catch — and it is probably closer to what
the reviewer actually saw than the train cluster was.

Remaining work, in order of impact:

1. **Fix the mismatched titles.** Five posts promise a subject their body does
   not deliver. Retitle each to what it argues, or retire it. This is a
   half-day of editing and it removes the strongest remaining signal.
2. **Publish something that is not derivable from a press release.** The
   engineering deep-dives (LCOH sensitivity, EDI vs mixed-bed polishing,
   gasket selection for alkaline stacks) are the strongest thing here and read
   like they came from someone who has done the work. More of those, fewer
   news rewrites. The calculators are a genuine differentiator; almost nothing
   currently links to them from the articles that discuss the same maths.
3. **Give the author a real identity.** The byline links to `/author/admin/`.
   A named author page with actual credentials, tied to the "Chief Engineer"
   byline already in use, is cheap and directly addresses reviewer questions
   about who is behind the site.
4. **Consider re-titling `balance-of-plant-bop-strategies-...-2`** (2 Aug).
   Its title promises pumps, cooling and instrumentation; the body is entirely
   about feedwater purity. Left alone here because retitling is an editorial
   call, not a cleanup one.
5. **Slow down.** One well-sourced post a week beats three a day. The pipeline
   defaults to three daily, which over a month rebuilds exactly the archive
   shape being cleaned up here.
