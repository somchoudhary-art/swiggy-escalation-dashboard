"""
Data Collection Script
Collects Swiggy Food & Zomato posts from Twitter/X, Reddit, LinkedIn via Apify
Period: April, May, June (current year)
"""

import os
import json
import time
import logging
from datetime import datetime, date
from pathlib import Path
from apify_client import ApifyClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

APIFY_TOKEN = os.getenv("APIFY_TOKEN", "apify_api_z0RRdE0g5a5gEgieJCj2wiEA6nlaTh4G0Yzs")
client = ApifyClient(APIFY_TOKEN)

BASE_DIR = Path(__file__).parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Date range: April 1 – June 30 of current year
YEAR = date.today().year
START_DATE = f"{YEAR}-04-01"
END_DATE   = f"{YEAR}-06-30"

# ── Search query sets ──────────────────────────────────────────────────────────
SWIGGY_QUERIES = [
    "swiggy food delivery complaint",
    "swiggy order cancelled",
    "swiggy delivery late",
    "swiggy food quality",
    "swiggy delivery executive",
    "swiggy refund",
    "swiggy customer support",
    "swiggy chatbot",
    "swiggy wrong order",
    "@swiggy",
]

ZOMATO_QUERIES = [
    "zomato food delivery complaint",
    "zomato order cancelled",
    "zomato delivery late",
    "zomato food quality",
    "zomato delivery executive",
    "zomato refund",
    "zomato customer support",
    "zomato chatbot",
    "@zomato",
]

# ── Exclusion keywords for Swiggy non-food businesses ────────────────────────
SWIGGY_EXCLUDE = [
    "instamart", "district", "genie", "dineout", "minis",
    "grocery", "swiggy stores",
]


def save_raw(brand: str, platform: str, data: list):
    path = RAW_DIR / f"{brand}_{platform}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    log.info("Saved %d records → %s", len(data), path)


# ── Twitter / X ───────────────────────────────────────────────────────────────
def collect_twitter(brand: str, queries: list, max_per_query: int = 200) -> list:
    """
    Uses apidojo/tweet-scraper (most reliable Twitter actor on Apify).
    Falls back to vbarbaresi/twitter-scraper if needed.
    """
    actor_id = "apidojo/tweet-scraper"
    all_tweets = []

    for q in queries:
        search_term = f"{q} since:{START_DATE} until:{END_DATE} lang:en"
        log.info("[Twitter] %s | query: %s", brand, q)
        try:
            run_input = {
                "searchTerms": [search_term],
                "maxTweets": max_per_query,
                "addUserInfo": True,
                "startUrls": [],
            }
            run = client.actor(actor_id).call(run_input=run_input, timeout_secs=180)
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            all_tweets.extend(items)
            log.info("  → %d tweets collected", len(items))
            time.sleep(2)
        except Exception as e:
            log.warning("  Twitter actor failed for query '%s': %s", q, e)
            # Try fallback actor
            try:
                run_input2 = {
                    "searchTerms": [q],
                    "startUrls": [],
                    "maxItems": max_per_query,
                    "since": START_DATE,
                    "until": END_DATE,
                }
                run2 = client.actor("vbarbaresi/twitter-scraper").call(
                    run_input=run_input2, timeout_secs=180
                )
                items2 = list(client.dataset(run2["defaultDatasetId"]).iterate_items())
                all_tweets.extend(items2)
                log.info("  → %d tweets (fallback)", len(items2))
            except Exception as e2:
                log.error("  Fallback also failed: %s", e2)

    save_raw(brand, "twitter", all_tweets)
    return all_tweets


# ── Reddit ─────────────────────────────────────────────────────────────────────
def collect_reddit(brand: str, queries: list, max_per_query: int = 200) -> list:
    """
    Uses trudax/reddit-scraper-lite (free, no API key needed).
    """
    actor_id = "trudax/reddit-scraper-lite"
    all_posts = []

    for q in queries:
        log.info("[Reddit] %s | query: %s", brand, q)
        try:
            run_input = {
                "searches": [{"query": q, "sort": "relevance"}],
                "maxComments": 0,
                "maxPosts": max_per_query,
                "maxCommunitiesCount": 0,
                "proxy": {"useApifyProxy": True},
            }
            run = client.actor(actor_id).call(run_input=run_input, timeout_secs=240)
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            # Filter by date
            filtered = [
                i for i in items
                if _in_date_range(i.get("createdAt") or i.get("created_utc"))
            ]
            all_posts.extend(filtered)
            log.info("  → %d posts (after date filter)", len(filtered))
            time.sleep(2)
        except Exception as e:
            log.warning("  Reddit actor failed: %s", e)

    save_raw(brand, "reddit", all_posts)
    return all_posts


# ── LinkedIn ──────────────────────────────────────────────────────────────────
def collect_linkedin(brand: str, queries: list, max_per_query: int = 100) -> list:
    """
    Uses voyager/linkedin-post-search (searches LinkedIn public posts).
    """
    actor_id = "voyager/linkedin-post-search"
    all_posts = []

    for q in queries[:5]:  # LinkedIn is rate-limited; fewer queries
        log.info("[LinkedIn] %s | query: %s", brand, q)
        try:
            run_input = {
                "keywords": q,
                "datePosted": "past-month",  # actor supports this filter
                "maxResults": max_per_query,
            }
            run = client.actor(actor_id).call(run_input=run_input, timeout_secs=300)
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            all_posts.extend(items)
            log.info("  → %d posts", len(items))
            time.sleep(3)
        except Exception as e:
            log.warning("  LinkedIn actor failed: %s", e)

    # Also try dev_fusion/linkedin-post-scraper as fallback
    if not all_posts:
        for q in queries[:3]:
            try:
                run_input = {"searchQuery": q, "maxResults": max_per_query}
                run = client.actor("dev_fusion/linkedin-post-scraper").call(
                    run_input=run_input, timeout_secs=300
                )
                items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
                all_posts.extend(items)
                log.info("  → %d posts (fallback)", len(items))
                time.sleep(3)
            except Exception as e2:
                log.error("  LinkedIn fallback failed: %s", e2)

    save_raw(brand, "linkedin", all_posts)
    return all_posts


# ── Date range helper ─────────────────────────────────────────────────────────
def _in_date_range(ts) -> bool:
    if ts is None:
        return True  # include if no date
    try:
        if isinstance(ts, (int, float)):
            dt = datetime.utcfromtimestamp(ts)
        elif isinstance(ts, str):
            for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(ts[:len(fmt)], fmt)
                    break
                except ValueError:
                    continue
            else:
                return True
        else:
            return True
        return date(YEAR, 4, 1) <= dt.date() <= date(YEAR, 6, 30)
    except Exception:
        return True


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("=== Starting data collection | %s – %s ===", START_DATE, END_DATE)

    # Swiggy
    log.info("--- Swiggy Food ---")
    collect_twitter("swiggy", SWIGGY_QUERIES, max_per_query=300)
    collect_reddit("swiggy", SWIGGY_QUERIES[:6], max_per_query=200)
    collect_linkedin("swiggy", SWIGGY_QUERIES[:4], max_per_query=100)

    # Zomato
    log.info("--- Zomato ---")
    collect_twitter("zomato", ZOMATO_QUERIES, max_per_query=300)
    collect_reddit("zomato", ZOMATO_QUERIES[:6], max_per_query=200)
    collect_linkedin("zomato", ZOMATO_QUERIES[:4], max_per_query=100)

    log.info("=== Data collection complete ===")
