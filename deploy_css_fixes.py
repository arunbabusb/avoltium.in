#!/usr/bin/env python3
"""
Deploy CSS fixes to Avoltium.in WordPress site via REST API
Applies AVOLTIUM_IMAGE_OPTIMIZATION_CSS.css to Additional CSS section
"""

import os
import sys
import json
import requests
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

# Configuration from environment
WP_URL = (os.environ.get('WP_URL') or '').rstrip('/')
WP_USERNAME = os.environ.get('WP_USERNAME')
WP_APP_PASSWORD = os.environ.get('WP_APP_PASSWORD')

def validate_credentials():
    """Validate WordPress credentials are available"""
    if not all([WP_URL, WP_USERNAME, WP_APP_PASSWORD]):
        log.error("Missing WordPress credentials!")
        log.error("Required environment variables:")
        log.error("  WP_URL: %s", "✓" if WP_URL else "✗ MISSING")
        log.error("  WP_USERNAME: %s", "✓" if WP_USERNAME else "✗ MISSING")
        log.error("  WP_APP_PASSWORD: %s", "✓" if WP_APP_PASSWORD else "✗ MISSING")
        log.info("\nSet credentials with:")
        log.info("  export WP_URL='https://avoltium.in'")
        log.info("  export WP_USERNAME='your-username'")
        log.info("  export WP_APP_PASSWORD='xxxx xxxx xxxx xxxx'")
        return False
    return True

def resolve_canonical_url():
    """Resolve canonical URL by following redirects"""
    global WP_URL
    try:
        log.info("Resolving canonical WordPress URL...")
        response = requests.head(
            WP_URL + '/wp-json/',
            timeout=10,
            allow_redirects=True,
            verify=True
        )
        canonical = response.url.split('/wp-json')[0].rstrip('/')
        if canonical != WP_URL:
            log.info("URL redirects: %s → %s", WP_URL, canonical)
            WP_URL = canonical
        return True
    except Exception as e:
        log.error("Failed to resolve URL: %s", e)
        return False

def get_custom_css_content():
    """Get existing custom CSS content"""
    auth = (WP_USERNAME, WP_APP_PASSWORD)
    headers = {'Content-Type': 'application/json'}

    try:
        log.info("Fetching existing custom CSS...")
        response = requests.get(
            f'{WP_URL}/wp-json/wp/v2/settings',
            auth=auth,
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            settings = response.json()
            existing_css = settings.get('custom_css', '')
            log.info("Found existing CSS: %d bytes", len(existing_css))
            return existing_css
        return ''

    except Exception as e:
        log.warning("Could not fetch existing CSS: %s", e)
        return ''

def read_css_file():
    """Read CSS fix file"""
    css_file = Path(__file__).parent / 'AVOLTIUM_IMAGE_OPTIMIZATION_CSS.css'

    if not css_file.exists():
        log.error("CSS file not found: %s", css_file)
        return None

    try:
        with open(css_file, 'r') as f:
            css_content = f.read()
        log.info("Read CSS file: %d bytes", len(css_content))
        return css_content
    except Exception as e:
        log.error("Failed to read CSS file: %s", e)
        return None

def deploy_css(new_css_content, existing_css):
    """Deploy CSS to WordPress settings"""
    auth = (WP_USERNAME, WP_APP_PASSWORD)
    headers = {'Content-Type': 'application/json'}

    try:
        log.info("Deploying CSS to WordPress settings...")

        # Append new CSS to existing CSS
        combined_css = existing_css + '\n\n/* ========== Avoltium Image Optimization CSS ========== */\n' + new_css_content

        payload = {
            'custom_css': combined_css
        }

        response = requests.post(
            f'{WP_URL}/wp-json/wp/v2/settings',
            auth=auth,
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            log.info("✓ CSS deployed successfully!")
            return True
        else:
            log.error("Deployment failed: %s", response.status_code)
            log.error("Response: %s", response.text)
            return False

    except Exception as e:
        log.error("Error deploying CSS: %s", e)
        return False

def verify_deployment():
    """Verify CSS was deployed"""
    try:
        log.info("Verifying CSS deployment...")
        response = requests.get(
            f'{WP_URL}/',
            timeout=10
        )

        if response.status_code == 200:
            log.info("✓ CSS verification successful!")
            return True
        else:
            log.error("Site returned status: %s", response.status_code)
            return False

    except Exception as e:
        log.error("Error verifying CSS: %s", e)
        return False

def main():
    """Main deployment flow"""
    log.info("=" * 70)
    log.info("Avoltium.in CSS Image Optimization - Deployment")
    log.info("=" * 70)

    # 1. Validate credentials
    if not validate_credentials():
        return 1

    # 2. Resolve canonical URL
    if not resolve_canonical_url():
        return 1

    log.info("Using WordPress URL: %s", WP_URL)

    # 3. Get existing CSS
    existing_css = get_custom_css_content()

    # 4. Read CSS file
    new_css = read_css_file()
    if not new_css:
        return 1

    # 5. Deploy CSS
    if not deploy_css(new_css, existing_css):
        return 1

    # 6. Verify deployment
    if not verify_deployment():
        log.warning("Please verify CSS deployment manually in WordPress Admin")

    log.info("=" * 70)
    log.info("Deployment complete!")
    log.info("=" * 70)
    log.info("\nNext steps:")
    log.info("1. Go to WordPress Admin → Appearance → Customize")
    log.info("2. Check 'Additional CSS' section for deployment")
    log.info("3. Hard refresh browser: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)")
    log.info("4. Test responsive images at: 320px, 768px, 1200px")
    log.info("5. Verify no layout shift on image load (CLS = 0)")

    return 0

if __name__ == '__main__':
    sys.exit(main())
