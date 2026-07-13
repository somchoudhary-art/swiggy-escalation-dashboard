"""
Data Collection Script
Collects Swiggy Food & Zomato posts from Twitter/X, Reddit, LinkedIn via Apify.
Period: April, May, June (current year)

Compatible with apify-client >= 1.6 (Run object API, not dict).
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
RAW_DIR  = BASE_DIR / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

YEAR       = date.today().year
START_DATE = f"{YEAR}-04-01"
END_DATE   = f"{YEAR}-06-30"

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

SWIGGY_EXCLUDE = [
    "instamart", "district", "genie", "dineout", "minis",
    "swiggy stores", "grocery",
]


def _run_actor(actor_id: str, run_input: dict) -> list:
    """
    Run an Apify actor and return items from its default dataset.
    Works with apify-client >= 1.6 where .call() returns a Run object.
    """
    run = client.actor(actor_id).call(run_input=run_input)
    # apify-client v1.x returns dict; v2.x returns Run object
    if isinstance(run, dict):
        dataset_id = run["defaultDatasetId"]
    else:
        dataset_id = run.default_dataset_id
    return list(client.dataset(dataset_id).iterate_items())


def save_raw(brand: str, platform: str, data: list):
    path = RAW_DIR / f"{brand}_{platform}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    log.info("Saved %d records → %s", len(data), path)


# ── Twitter / X ───────────────────────────────────────────────────────────────

def collect_twitter(brand: str, queries: list, max_per_query: int = 200) -> list:
    """
    Tries free-tier Twitter actors in order. Each actor has a different input schema.
    actor: twitter-scraper by apidojo is paid; use free alternatives.
    Verified free actors (July 2025):
      - quacker/twitter-url-scraper  (search URL → tweets)
      - shanes/twitter-scraper        (keyword search, free)
    """
    all_tweets = []

    for q in queries:
        log.info("[Twitter] %s | query: %s", brand, q)
        collected = False

        # Actor 1: quacker/twitter-url-scraper — build a Twitter search URL
        search_url = (
            f"https://twitter.com/search?q={q.replace(' ', '%20')}"
            f"%20since%3A{START_DATE}%20until%3A{END_DATE}&f=live"
        )
        try:
            items = _run_actor("quacker/twitter-url-scraper", {
                "startUrls": [{"url": search_url}],
                "maxItems": max_per_query,
            })
            if items:
                all_tweets.extend(items)
                log.info("  → %d tweets (quacker)", len(items))
                collected = True
        except Exception as e:
            log.warning("  quacker/twitter-url-scraper failed: %s", e)

        # Actor 2: shanes/twitter-scraper (keyword, free tier)
        if not collected:
            try:
                items = _run_actor("shanes/twitter-scraper", {
                    "searchTerms": [f"{q} since:{START_DATE} until:{END_DATE}"],
                    "maxItems": max_per_query,
                    "lang": "en",
                })
                if items:
                    all_tweets.extend(items)
                    log.info("  → %d tweets (shanes)", len(items))
                    collected = True
            except Exception as e:
                log.warning("  shanes/twitter-scraper failed: %s", e)

        # Actor 3: apidojo/twitter-user-scraper  (profile-based, free, last resort)
        if not collected:
            handle = "Swiggy" if brand == "swiggy" else "ZomatoIN"
            try:
                items = _run_actor("apidojo/twitter-user-scraper", {
                    "startUrls": [f"https://twitter.com/{handle}"],
                    "maxItems": max_per_query,
                })
                # Filter by date and keyword
                kw = brand
                items = [
                    i for i in items
                    if kw.lower() in str(i.get("text", "")).lower()
                    and _in_date_range(i.get("createdAt") or i.get("created_at"))
                ]
                if items:
                    all_tweets.extend(items)
                    log.info("  → %d tweets (profile fallback)", len(items))
                    collected = True
            except Exception as e:
                log.warning("  apidojo/twitter-user-scraper failed: %s", e)

        if not collected:
            log.warning("  All Twitter actors failed for query: %s", q)
        time.sleep(1)

    save_raw(brand, "twitter", all_tweets)
    return all_tweets


# ── Reddit ─────────────────────────────────────────────────────────────────────

def collect_reddit(brand: str, queries: list, max_per_query: int = 200) -> list:
    """
    Scrapes Reddit via trudax/reddit-scraper-lite.
    Strategy: target brand-specific subreddits directly (most reliable),
    then supplement with keyword search URLs.
    No date filter during collection — we accept last 12 months of real posts.
    """
    all_posts = []

    # Primary: scrape brand subreddits directly — most reliable source of real posts
    SUBREDDIT_URLS = {
        "swiggy": [
            "https://www.reddit.com/r/swiggy/",
            "https://www.reddit.com/r/india/search/?q=swiggy+food&sort=top&t=year",
            "https://www.reddit.com/r/bangalore/search/?q=swiggy&sort=top&t=year",
        ],
        "zomato": [
            "https://www.reddit.com/r/zomato/",
            "https://www.reddit.com/r/india/search/?q=zomato+food&sort=top&t=year",
            "https://www.reddit.com/r/mumbai/search/?q=zomato&sort=top&t=year",
        ],
    }

    for url in SUBREDDIT_URLS.get(brand, []):
        log.info("[Reddit] %s | url: %s", brand, url)
        try:
            items = _run_actor("trudax/reddit-scraper-lite", {
                "startUrls": [{"url": url}],
                "maxItems": max_per_query,
                "proxy": {"useApifyProxy": True},
            })
            all_posts.extend(items)
            log.info("  → %d posts", len(items))
        except Exception as e:
            log.warning("  subreddit scrape failed for %s: %s", url, e)
        time.sleep(2)

    # Supplement with keyword search (top posts, past year)
    for q in queries[:3]:
        search_url = f"https://www.reddit.com/search/?q={q.replace(' ', '+')}&sort=top&t=year"
        log.info("[Reddit] %s | search: %s", brand, q)
        try:
            items = _run_actor("trudax/reddit-scraper-lite", {
                "startUrls": [{"url": search_url}],
                "maxItems": 100,
                "proxy": {"useApifyProxy": True},
            })
            all_posts.extend(items)
            log.info("  → %d posts", len(items))
        except Exception as e:
            log.warning("  search scrape failed: %s", e)
        time.sleep(2)

    # Deduplicate by URL
    seen = set()
    deduped = []
    for p in all_posts:
        key = p.get("url") or p.get("id") or str(p)[:100]
        if key not in seen:
            seen.add(key)
            deduped.append(p)

    log.info("[Reddit] %s | total unique posts: %d", brand, len(deduped))
    save_raw(brand, "reddit", deduped)
    return deduped


# ── LinkedIn ──────────────────────────────────────────────────────────────────

def collect_linkedin(brand: str, queries: list, max_per_query: int = 100) -> list:
    """
    LinkedIn scraping. Tries multiple actors — all are rate-limited.
    We cap at 3 queries and accept partial data.
    """
    all_posts = []

    for q in queries[:3]:
        log.info("[LinkedIn] %s | query: %s", brand, q)

        # Actor 1: voyager/linkedin-post-search
        try:
            items = _run_actor("voyager/linkedin-post-search", {
                "keywords": q,
                "maxResults": max_per_query,
            })
            if items:
                all_posts.extend(items)
                log.info("  → %d posts (voyager)", len(items))
                time.sleep(3)
                continue
        except Exception as e:
            log.warning("  voyager/linkedin-post-search failed: %s", e)

        # Actor 2: dev_fusion/linkedin-post-scraper
        try:
            items = _run_actor("dev_fusion/linkedin-post-scraper", {
                "searchQuery": q,
                "maxResults": max_per_query,
            })
            if items:
                all_posts.extend(items)
                log.info("  → %d posts (dev_fusion)", len(items))
        except Exception as e:
            log.warning("  dev_fusion/linkedin-post-scraper failed: %s", e)

        time.sleep(3)

    save_raw(brand, "linkedin", all_posts)
    return all_posts


# ── Date range helper ─────────────────────────────────────────────────────────

def _in_date_range(ts) -> bool:
    if ts is None:
        return True
    try:
        if isinstance(ts, (int, float)):
            dt = datetime.utcfromtimestamp(ts)
        elif isinstance(ts, str):
            dt = None
            for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d",
                        "%a %b %d %H:%M:%S +0000 %Y"):
                try:
                    dt = datetime.strptime(ts[:len(fmt)], fmt)
                    break
                except ValueError:
                    continue
            if dt is None:
                return True
        else:
            return True
        return date(YEAR, 4, 1) <= dt.date() <= date(YEAR, 6, 30)
    except Exception:
        return True


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("=== Starting data collection | %s - %s ===", START_DATE, END_DATE)

    log.info("--- Swiggy Food ---")
    collect_twitter("swiggy", SWIGGY_QUERIES, max_per_query=300)
    collect_reddit("swiggy", SWIGGY_QUERIES[:6], max_per_query=200)
    collect_linkedin("swiggy", SWIGGY_QUERIES[:4], max_per_query=100)

    log.info("--- Zomato ---")
    collect_twitter("zomato", ZOMATO_QUERIES, max_per_query=300)
    collect_reddit("zomato", ZOMATO_QUERIES[:6], max_per_query=200)
    collect_linkedin("zomato", ZOMATO_QUERIES[:4], max_per_query=100)

    log.info("=== Data collection complete ===")
