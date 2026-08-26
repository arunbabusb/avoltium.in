"""
Targeted MNC Scraper to populate zero-count categories on TechJobs360
"""
import time
import techjobs360_pipeline as pipeline

def populate_empty_categories():
    print("=" * 60)
    print("🚀 Populating Empty MNC Categories on TechJobs360")
    print("=" * 60)

    pipeline.populate_existing_media()
    pipeline.populate_categories_cache()

    target_queries = [
        "software engineer TCS India",
        "software engineer Capgemini India",
        "software engineer Goldman Sachs India",
        "software engineer Oracle India",
        "software engineer SAP India",
        "software engineer JP Morgan India"
    ]

    published_total = 0

    for q in target_queries:
        print(f"\n[TARGET SEARCH] {q}...")
        ids = pipeline.search_linkedin_jobs(q, location="India", count=3)
        print(f"  Found {len(ids)} job IDs for '{q}'")
        for jid in ids:
            job = pipeline.get_linkedin_job_detail(jid)
            if not job:
                continue
            success = pipeline.publish_job(job)
            if success:
                published_total += 1
                print(f"  ✅ Published: {job.get('title')} at {job.get('company')}")
            time.sleep(1.5)

    print("\n" + "=" * 60)
    print(f"🎉 Complete! Published {published_total} targeted MNC jobs.")
    print("=" * 60)

if __name__ == "__main__":
    populate_empty_categories()
