# TechJobs360 — Automated MNC Jobs Scraper

Automatically scrapes and publishes high-quality MNC tech jobs from LinkedIn to [techjobs360.com](https://www.techjobs360.com) — **3 times daily, fully automated via GitHub Actions**.

## How It Works

```
GitHub Actions (cron: 3x/day)
    ↓
techjobs360_pipeline.py
    ↓
LinkedIn Public Guest API (no login, no API key)
    ↓
MNC Filter (200+ reputed companies)
    ↓
India Location Filter
    ↓
WordPress REST API → techjobs360.com
```

## Features

- **No API key required** — uses LinkedIn's public job search API
- **MNC whitelist** — 200+ companies: Google, IBM, Amazon, Accenture, Wipro, TCS, Infosys, Cisco, Samsung, etc.
- **Full job descriptions** — complete details, apply links, seniority level, industry
- **India-only** — filters out US/UK/other country jobs automatically
- **Duplicate prevention** — never publishes the same job twice
- **3x daily** — runs at 6 AM, 12 PM, 6 PM IST

## Setup (One-Time)

### 1. Fork / Clone this repo to your GitHub account

### 2. Add GitHub Secrets
Go to **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Value |
|-------------|-------|
| `WP_URL` | `https://www.techjobs360.com` |
| `WP_USERNAME` | `admin` |
| `WP_APP_PASS` | Your WordPress Application Password |

### 3. Enable GitHub Actions
Go to **Actions** tab → click **"I understand my workflows, go ahead and enable them"**

### 4. Test manually
Go to **Actions → TechJobs360 — Daily MNC Jobs Scraper → Run workflow**

That's it! Jobs will publish automatically 3x per day.

## Manual Run

```bash
# Set credentials
export WP_URL="https://www.techjobs360.com"
export WP_USERNAME="admin"
export WP_APP_PASS="your-app-password"

# Run
python techjobs360_pipeline.py
```

## Companies Covered

MNCs, Indian IT Giants, Startups:
`Google • Microsoft • Amazon • IBM • Accenture • TCS • Infosys • Wipro • HCL • Cognizant • Cisco • Samsung • Oracle • SAP • Deloitte • Goldman Sachs • JP Morgan • Flipkart • Walmart • Adobe • Salesforce • and 180+ more`
