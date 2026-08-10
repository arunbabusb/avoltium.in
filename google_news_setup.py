#!/usr/bin/env python3
"""Ship the technical requirements for Google News: schema and a news sitemap.

Audited before writing: a news post on this site emitted **zero** JSON-LD —
no Article, no NewsArticle, no Organization — and there was no news sitemap at
any of the usual paths. Rank Math is installed but is not emitting article
schema on these posts. Both are prerequisites Google states outright, so this
is worth doing regardless of what happens to publishing volume.

What this installs (as a Code Snippet, since the theme is not ours to edit):

  1. NewsArticle JSON-LD on posts in a news category, Article elsewhere, plus
     Organization and a breadcrumb trail. Includes author, publisher, dates
     and the featured image, which are the fields Google actually reads.
  2. /news-sitemap.xml — the Google News format, which is a different document
     from a normal sitemap: only the last 48 hours, capped at 1000 URLs, with
     the news: namespace.
  3. A robots.txt line pointing at it.

Deliberately not included: anything that claims original reporting. Schema
markup asserting a byline and a date is fine because both are true. Markup
implying a newsroom that does not exist would be the same fabrication problem
as an invented citation, and Google's own guidance treats misrepresentation as
a policy violation rather than a technicality.

Usage:
    python3 google_news_setup.py            # dry run, prints the snippet
    python3 google_news_setup.py --execute
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time

import requests

from backfill_images import session, WP_URL

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("google-news")

CS = f"{WP_URL}/wp-json/code-snippets/v1/snippets"
H = {"Cache-Control": "no-cache"}
SNIPPET_NAME = "Avoltium Google News (schema + news sitemap)"

PHP = r"""
/**
 * Google News technical requirements: NewsArticle schema and a news sitemap.
 * Installed by google_news_setup.py — edit there, not here.
 */

// ---------------------------------------------------------------- schema ---
add_action('wp_head', function () {
    if (!is_singular('post')) return;
    global $post;

    $is_news = has_category(['industry-news', 'news', 'hydrogen-policy-market'], $post);
    $img     = get_the_post_thumbnail_url($post, 'full');
    $author  = get_the_author_meta('display_name', $post->post_author) ?: 'Avoltium';

    $publisher = [
        '@type' => 'Organization',
        'name'  => 'Avoltium',
        'url'   => home_url('/'),
        'logo'  => [
            '@type' => 'ImageObject',
            'url'   => get_site_icon_url(512) ?: home_url('/favicon.ico'),
        ],
    ];

    $article = [
        '@context'         => 'https://schema.org',
        '@type'            => $is_news ? 'NewsArticle' : 'Article',
        'mainEntityOfPage' => ['@type' => 'WebPage', '@id' => get_permalink($post)],
        'headline'         => wp_strip_all_tags(get_the_title($post)),
        'datePublished'    => get_the_date('c', $post),
        'dateModified'     => get_the_modified_date('c', $post),
        'author'           => ['@type' => 'Person', 'name' => $author,
                               'url'   => home_url('/about-us/')],
        'publisher'        => $publisher,
        'description'      => wp_strip_all_tags(get_the_excerpt($post)),
        'inLanguage'       => 'en',
        'isAccessibleForFree' => true,
    ];
    if ($img) {
        $article['image'] = ['@type' => 'ImageObject', 'url' => $img];
    }

    $crumbs = [[
        '@type' => 'ListItem', 'position' => 1,
        'name'  => 'Home', 'item' => home_url('/'),
    ]];
    $cats = get_the_category($post->ID);
    if ($cats) {
        $crumbs[] = ['@type' => 'ListItem', 'position' => 2,
                     'name' => $cats[0]->name, 'item' => get_category_link($cats[0]->term_id)];
    }
    $crumbs[] = ['@type' => 'ListItem', 'position' => count($crumbs) + 1,
                 'name' => wp_strip_all_tags(get_the_title($post))];

    $breadcrumb = ['@context' => 'https://schema.org',
                   '@type' => 'BreadcrumbList', 'itemListElement' => $crumbs];

    foreach ([$article, $breadcrumb] as $blob) {
        echo '<script type="application/ld+json">'
           . wp_json_encode($blob, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE)
           . '</script>' . "\n";
    }
}, 5);

// -------------------------------------------------------- news sitemap ---
add_action('init', function () {
    add_rewrite_rule('^news-sitemap\.xml$', 'index.php?av_news_sitemap=1', 'top');
});
add_filter('query_vars', function ($v) { $v[] = 'av_news_sitemap'; return $v; });

add_action('template_redirect', function () {
    if (!get_query_var('av_news_sitemap')) return;

    // Google News reads the last two days only, and caps a news sitemap at
    // 1000 URLs. Sending more is not rewarded and older entries are ignored.
    // Same category set the schema uses for NewsArticle. Listing a technical
    // explainer inside <news:news> while its markup says Article is a
    // contradiction Google reads as a malformed news sitemap.
    $posts = get_posts([
        'post_type'   => 'post',
        'post_status' => 'publish',
        'numberposts' => 1000,
        'date_query'  => [['after' => '48 hours ago']],
        'orderby'     => 'date',
        'order'       => 'DESC',
        'tax_query'   => [[
            'taxonomy' => 'category',
            'field'    => 'slug',
            'terms'    => ['industry-news', 'news', 'hydrogen-policy-market'],
        ]],
    ]);

    header('Content-Type: application/xml; charset=UTF-8');
    echo '<?xml version="1.0" encoding="UTF-8"?>' . "\n";
    echo '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
       . 'xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">' . "\n";
    foreach ($posts as $p) {
        echo "  <url>\n";
        echo '    <loc>' . esc_url(get_permalink($p)) . "</loc>\n";
        echo "    <news:news>\n";
        echo "      <news:publication>\n";
        echo "        <news:name>Avoltium</news:name>\n";
        echo "        <news:language>en</news:language>\n";
        echo "      </news:publication>\n";
        echo '      <news:publication_date>' . get_the_date('c', $p) . "</news:publication_date>\n";
        echo '      <news:title>' . esc_html(wp_strip_all_tags(get_the_title($p))) . "</news:title>\n";
        echo "    </news:news>\n";
        echo "  </url>\n";
    }
    echo '</urlset>';
    exit;
});

add_filter('robots_txt', function ($output) {
    return $output . "\nSitemap: " . home_url('/news-sitemap.xml') . "\n";
}, 20, 1);
"""


def snippets(auth):
    for _ in range(8):
        d = requests.get(CS, auth=auth, timeout=60, headers=H,
                         params={"_ts": time.time()}).json()
        if isinstance(d, list):
            return d
        time.sleep(4)
    raise SystemExit("Code Snippets API did not return a list")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    s = session()
    auth = s.auth
    if not args.execute:
        logger.info("[DRY-RUN] would install %r (%d chars of PHP)", SNIPPET_NAME, len(PHP))
        return 0

    m = next((x for x in snippets(auth) if x.get("name") == SNIPPET_NAME), None)
    payload = {"name": SNIPPET_NAME,
               "desc": "NewsArticle/Article JSON-LD, breadcrumbs, and /news-sitemap.xml.",
               "code": PHP, "scope": "global", "priority": 10, "active": True}
    r = (requests.put(f"{CS}/{m['id']}", auth=auth, json=payload, timeout=120, headers=H)
         if m else requests.post(CS, auth=auth, json=payload, timeout=120, headers=H))
    if r.status_code not in (200, 201):
        logger.error("install failed: HTTP %s — %s", r.status_code, r.text[:200])
        return 1
    sid = r.json().get("id")
    logger.info("snippet %s active", sid)

    # Rewrite rules only take effect once flushed.
    time.sleep(5)
    requests.post(f"{WP_URL}/wp-json/av/v1/purge", auth=auth, timeout=90, headers=H)
    logger.info("cache purged; permalinks may need one save in wp-admin if the "
                "sitemap 404s (rewrite rules flush on that action)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
