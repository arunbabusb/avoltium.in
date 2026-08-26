# Avoltium.in Rules

## WordPress Integration
Whenever the user asks you to interact with the Avoltium website (e.g. create a post, publish an article, check the site), ALWAYS do the following:
1. Look for the `.env` file in the root of the Avoltium.in workspace.
2. Read `WP_URL`, `WP_USERNAME`, and `WP_APP_PASSWORD` from that file.
3. Use those credentials to authenticate with the WordPress REST API via HTTP Basic Auth.
4. You do not need to ask the user for permission or passwords again. You are fully authorized to use the WordPress REST API to fulfill their requests.

## Apify Integration
Whenever the user asks you to scrape websites (e.g. techjobs360.com) or use Apify actors, ALWAYS do the following:
1. Look for the `.env` file in the root of the Avoltium.in workspace.
2. Read `APIFY_API_KEY` from that file.
3. Use that key to authenticate with the Apify API.
4. You do not need to ask the user for permission or the API key again. You are fully authorized to use the Apify API to fulfill their requests.
