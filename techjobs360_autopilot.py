"""
TechJobs360.com — 24/7 Continuous Autonomous Job & Discover Engine
====================================================================
Runs 24/7 on autopilot. Ingests fresh verified MNC & tech jobs, attaches high-res logos,
injects Schema.org NewsArticle & JobPosting for Google Discover & Google News,
pings IndexNow (Bing/Google/Yandex), and broadcasts to Telegram and social channels.

Usage:
    python techjobs360_autopilot.py --interval 3600
"""

import sys
import time
import argparse
from datetime import datetime

# Import core pipeline functions
import techjobs360_pipeline as pipeline

def run_autopilot_loop(interval_seconds=3600):
    print("=" * 70, flush=True)
    print(f"🚀 TechJobs360 24/7 Autopilot Engine Initialized at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"⏱️ Continuous Cycle Interval: {interval_seconds // 60} minutes", flush=True)
    print("=" * 70, flush=True)

    cycle_count = 1
    while True:
        try:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ▶️ Starting Autonomous Cycle #{cycle_count}...", flush=True)
            pipeline.run_pipeline()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Cycle #{cycle_count} completed successfully.", flush=True)
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Cycle #{cycle_count} encountered notice: {e}", flush=True)
        
        cycle_count += 1
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 💤 Sleeping for {interval_seconds // 60} minutes until next cycle...\n", flush=True)
        time.sleep(interval_seconds)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TechJobs360 24/7 Autopilot Engine")
    parser.add_argument("--interval", type=int, default=3600, help="Interval in seconds between cycles (default: 3600s / 1 hour)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.once:
        pipeline.run_pipeline()
    else:
        run_autopilot_loop(args.interval)
