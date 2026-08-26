import urllib.request
import json
import base64

wp_url = "https://www.techjobs360.com"
user = "admin"
pwd = "vgPl O24r nMOq dRF7 GhBN i9l4"
auth_str = base64.b64encode(f"{user}:{pwd}".encode("utf-8")).decode("utf-8")

php_code = r"""/**
 * Plugin Name: TechJobs360 SEO Authority, Google Jobs Schema & Ad Revenue Engine
 * Description: Injects Google JobPosting & BreadcrumbList structured data, optimizes AdSense viewability and in-article placements, and injects high-relevance internal links for massive SEO crawl depth.
 * Version: 3.2.0
 * Author: TechJobs360 Elite
 */

if (!defined('ABSPATH')) exit;

// ============================================================
// 1. DYNAMIC GOOGLE FOR JOBS SCHEMA & BREADCRUMBS IN <HEAD>
// ============================================================
add_action('wp_head', 'tj360_inject_seo_head_schema', 1);
function tj360_inject_seo_head_schema(): void {
    if (!is_singular(['post', 'job_listing'])) return;
    global $post;
    if (!$post) return;

    $title = get_the_title($post->ID);
    
    // Resolve company name
    $comp = get_post_meta($post->ID, '_company_name', true) ?: get_post_meta($post->ID, 'fsp_employer', true);
    if (!$comp && strpos($title, ' at ') !== false) {
        $parts = explode(' at ', $title);
        $comp = trim(end($parts));
    }
    if (!$comp) $comp = 'TechJobs360 Verified Employer';

    // Resolve location
    $loc = get_post_meta($post->ID, '_job_location', true) ?: get_post_meta($post->ID, 'fsp_location', true);
    if (!$loc) $loc = 'India';

    // Clean description
    $clean_desc = wp_strip_all_tags($post->post_content);
    $clean_desc = preg_replace('/\{"@context":.*?\}/s', '', $clean_desc);
    $clean_desc = mb_substr(trim($clean_desc), 0, 2000);

    // Job Posting JSON-LD
    $job_schema = [
        '@context' => 'https://schema.org/',
        '@type' => 'JobPosting',
        'title' => $title,
        'description' => $clean_desc,
        'datePosted' => get_the_date('Y-m-d', $post->ID),
        'validThrough' => date('Y-m-d', strtotime('+90 days', strtotime(get_the_date('Y-m-d', $post->ID)))),
        'employmentType' => 'FULL_TIME',
        'hiringOrganization' => [
            '@type' => 'Organization',
            'name' => $comp,
            'sameAs' => home_url('/'),
        ],
        'jobLocation' => [
            '@type' => 'Place',
            'address' => [
                '@type' => 'PostalAddress',
                'addressLocality' => $loc,
                'addressCountry' => 'IN'
            ]
        ],
        'applicantLocationRequirements' => [
            '@type' => 'Country',
            'name' => 'India'
        ],
        'directApply' => true,
        'url' => get_permalink($post->ID)
    ];

    $thumb_id = get_post_thumbnail_id($post->ID);
    if ($thumb_id) {
        $logo_url = wp_get_attachment_image_url($thumb_id, 'full');
        if ($logo_url) {
            $job_schema['hiringOrganization']['logo'] = $logo_url;
            $job_schema['image'] = $logo_url;
        }
    }

    // Breadcrumb JSON-LD
    $breadcrumb_schema = [
        '@context' => 'https://schema.org',
        '@type' => 'BreadcrumbList',
        'itemListElement' => [
            [
                '@type' => 'ListItem',
                'position' => 1,
                'name' => 'Home',
                'item' => home_url('/')
            ],
            [
                '@type' => 'ListItem',
                'position' => 2,
                'name' => 'Tech Jobs',
                'item' => home_url('/jobs/')
            ],
            [
                '@type' => 'ListItem',
                'position' => 3,
                'name' => $comp . ' Jobs',
                'item' => home_url('/category/' . sanitize_title($comp) . '/')
            ],
            [
                '@type' => 'ListItem',
                'position' => 4,
                'name' => $title,
                'item' => get_permalink($post->ID)
            ]
        ]
    ];

    echo "\n<!-- TechJobs360 Google Rich Results Structured Data -->\n";
    echo '<script type="application/ld+json">' . json_encode($job_schema, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "</script>\n";
    echo '<script type="application/ld+json">' . json_encode($breadcrumb_schema, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "</script>\n";
}

// ============================================================
// 2. HIGH-CTR ADSENSE PLACEMENTS & VIEWABILITY INJECTION
// ============================================================
add_filter('the_content', 'tj360_inject_ads_and_internal_links', 25);
function tj360_inject_ads_and_internal_links($content) {
    if (!is_singular(['post', 'job_listing']) || is_admin()) return $content;
    global $post;
    if (!$post) return $content;

    $pub_id = 'ca-pub-8459363476525914';

    // Ad Unit 1: Top in-article banner (High viewability)
    $ad_top = '<div class="tj360-ad-slot tj360-ad-top" style="margin:20px 0;text-align:center;min-height:90px;background:#f8fafc;border-radius:10px;padding:12px;border:1px dashed #cbd5e1;">
        <span style="display:block;font-size:10px;letter-spacing:1px;color:#94a3b8;text-transform:uppercase;margin-bottom:6px;font-weight:700;">Advertisement</span>
        <ins class="adsbygoogle"
             style="display:block"
             data-ad-client="' . $pub_id . '"
             data-ad-format="auto"
             data-full-width-responsive="true"></ins>
        <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
    </div>';

    // Ad Unit 2: Bottom pre-apply action banner
    $ad_bottom = '<div class="tj360-ad-slot tj360-ad-bottom" style="margin:24px 0;text-align:center;min-height:90px;background:#f8fafc;border-radius:10px;padding:12px;border:1px dashed #cbd5e1;">
        <span style="display:block;font-size:10px;letter-spacing:1px;color:#94a3b8;text-transform:uppercase;margin-bottom:6px;font-weight:700;">Sponsored Opportunity</span>
        <ins class="adsbygoogle"
             style="display:block"
             data-ad-client="' . $pub_id . '"
             data-ad-format="rectangle,horizontal"
             data-full-width-responsive="true"></ins>
        <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
    </div>';

    // 3. Internal Linking Hub Box (SEO Authority Booster) with crisp Unicode HTML entities
    $comp = get_post_meta($post->ID, '_company_name', true) ?: get_post_meta($post->ID, 'fsp_employer', true);
    if (!$comp && strpos(get_the_title($post->ID), ' at ') !== false) {
        $parts = explode(' at ', get_the_title($post->ID));
        $comp = trim(end($parts));
    }
    $comp_slug = sanitize_title($comp ?: 'technology');

    $internal_links = '<div class="tj360-seo-hubs" style="margin:30px 0 20px;padding:20px;background:#f1f5f9;border-radius:12px;border-left:4px solid #2563eb;">
        <h4 style="margin:0 0 12px;font-size:16px;color:#1e293b;font-weight:700;display:flex;align-items:center;gap:8px;">
            <span>&#128640;</span> Explore More Top Tech Drives &amp; Off-Campus Jobs
        </h4>
        <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:10px;">
            <a href="' . home_url('/category/' . $comp_slug . '/') . '" style="background:#ffffff;color:#2563eb;padding:6px 14px;border-radius:20px;font-size:13px;font-weight:600;text-decoration:none;border:1px solid #bfdbfe;display:inline-flex;align-items:center;gap:6px;"><span>&#127970;</span> More ' . esc_html($comp) . ' Jobs</a>
            <a href="' . home_url('/jobs/') . '" style="background:#ffffff;color:#0f766e;padding:6px 14px;border-radius:20px;font-size:13px;font-weight:600;text-decoration:none;border:1px solid #99f6e4;display:inline-flex;align-items:center;gap:6px;"><span>&#9889;</span> All India Tech Drives</a>
            <a href="' . home_url('/category/software-engineer/') . '" style="background:#ffffff;color:#7c3aed;padding:6px 14px;border-radius:20px;font-size:13px;font-weight:600;text-decoration:none;border:1px solid #ddd6fe;display:inline-flex;align-items:center;gap:6px;"><span>&#128187;</span> Software Engineer Roles</a>
            <a href="' . home_url('/category/fresheres/') . '" style="background:#ffffff;color:#c026d3;padding:6px 14px;border-radius:20px;font-size:13px;font-weight:600;text-decoration:none;border:1px solid #f5d0fe;display:inline-flex;align-items:center;gap:6px;"><span>&#127891;</span> 2026 Batch Freshers</a>
            <a href="https://t.me/techjobs360" target="_blank" rel="noopener" style="background:#0284c7;color:#ffffff;padding:6px 14px;border-radius:20px;font-size:13px;font-weight:600;text-decoration:none;display:inline-flex;align-items:center;gap:6px;"><span>&#9992;&#xFE0F;</span> Join Telegram Alerts</a>
        </div>
    </div>';

    return $ad_top . $content . $ad_bottom . $internal_links;
}

// ============================================================
// 3. DNS PRECONNECT & LITESPEED CACHE OPTIMIZATIONS
// ============================================================
add_action('wp_head', 'tj360_speed_dns_prefetch', 0);
function tj360_speed_dns_prefetch(): void {
    echo '<link rel="preconnect" href="https://pagead2.googlesyndication.com" crossorigin>' . "\n";
    echo '<link rel="preconnect" href="https://googleads.g.doubleclick.net" crossorigin>' . "\n";
    echo '<link rel="dns-prefetch" href="https://pagead2.googlesyndication.com">' . "\n";
    echo '<link rel="dns-prefetch" href="https://api.indexnow.org">' . "\n";
}
"""

payload = json.dumps({"code": php_code, "active": True}).encode("utf-8")
req = urllib.request.Request(
    f"{wp_url}/wp-json/code-snippets/v1/snippets/206",
    data=payload,
    headers={
        "Authorization": f"Basic {auth_str}",
        "Content-Type": "application/json; charset=utf-8"
    },
    method="POST"
)

with urllib.request.urlopen(req) as res:
    data = json.loads(res.read().decode("utf-8"))
    print("SUCCESS! Snippet 206 updated and active:", data.get("active"))
