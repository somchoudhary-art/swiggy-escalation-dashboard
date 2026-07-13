"""
Preprocessing: normalise raw Apify output into a unified DataFrame.
Handles Twitter, Reddit, LinkedIn schema differences.
"""

import json
import re
import logging
from pathlib import Path
from datetime import datetime, date
import pandas as pd

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
RAW_DIR  = BASE_DIR / "data" / "raw"
PROC_DIR = BASE_DIR / "data" / "processed"
PROC_DIR.mkdir(exist_ok=True)

SWIGGY_EXCLUDE = [
    "instamart", "district", "genie", "dineout", "minis",
    "swiggy stores", "grocery",
]

YEAR = date.today().year
TODAY = date.today()


# ── Schema normalisers ─────────────────────────────────────────────────────────

def _parse_dt(v) -> pd.Timestamp | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        try:
            return pd.Timestamp.utcfromtimestamp(v).tz_localize(None)
        except Exception:
            return None
    if isinstance(v, str):
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d",
            "%a %b %d %H:%M:%S +0000 %Y",
        ):
            try:
                return pd.to_datetime(v, format=fmt, utc=True).tz_localize(None)
            except Exception:
                pass
        try:
            return pd.to_datetime(v, utc=True).tz_localize(None)
        except Exception:
            return None
    return None


def normalise_twitter(items: list, brand: str) -> pd.DataFrame:
    rows = []
    for it in items:
        text = it.get("text") or it.get("full_text") or it.get("rawContent") or ""
        rows.append({
            "id":         it.get("id") or it.get("id_str", ""),
            "platform":   "Twitter/X",
            "brand":      brand,
            "text":       text,
            "date":       _parse_dt(it.get("createdAt") or it.get("created_at")),
            "url":        it.get("url") or it.get("tweetUrl") or "",
            "likes":      it.get("likeCount") or it.get("favorite_count") or 0,
            "retweets":   it.get("retweetCount") or it.get("retweet_count") or 0,
            "replies":    it.get("replyCount") or 0,
            "engagement": (it.get("likeCount") or 0)
                          + (it.get("retweetCount") or 0)
                          + (it.get("replyCount") or 0),
            "author":     (it.get("author") or {}).get("userName")
                          or it.get("user", {}).get("screen_name", ""),
        })
    return pd.DataFrame(rows)


def normalise_reddit(items: list, brand: str) -> pd.DataFrame:
    rows = []
    for it in items:
        text = (it.get("body") or it.get("title") or it.get("selftext") or
                it.get("text") or "")
        title = it.get("title") or ""
        combined = f"{title} {text}".strip()
        rows.append({
            "id":         it.get("id", ""),
            "platform":   "Reddit",
            "brand":      brand,
            "text":       combined,
            "date":       _parse_dt(it.get("createdAt") or it.get("created_utc")),
            "url":        it.get("url") or it.get("permalink") or "",
            "likes":      it.get("score") or it.get("ups") or 0,
            "retweets":   0,
            "replies":    it.get("numComments") or it.get("num_comments") or 0,
            "engagement": (it.get("score") or 0) + (it.get("numComments") or 0),
            "author":     it.get("author") or "",
        })
    return pd.DataFrame(rows)


def normalise_linkedin(items: list, brand: str) -> pd.DataFrame:
    rows = []
    for it in items:
        text = (it.get("text") or it.get("commentary") or
                it.get("content") or it.get("body") or "")
        rows.append({
            "id":         it.get("id") or it.get("urn") or "",
            "platform":   "LinkedIn",
            "brand":      brand,
            "text":       text,
            "date":       _parse_dt(it.get("postedAt") or it.get("publishedAt")
                                    or it.get("date")),
            "url":        it.get("url") or it.get("postUrl") or "",
            "likes":      it.get("totalReactionCount") or it.get("likes") or 0,
            "retweets":   it.get("repostCount") or 0,
            "replies":    it.get("commentsCount") or it.get("comments") or 0,
            "engagement": (it.get("totalReactionCount") or 0)
                          + (it.get("commentsCount") or 0),
            "author":     (it.get("author") or {}).get("name") or
                          it.get("authorName") or "",
        })
    return pd.DataFrame(rows)


# ── Filtering ─────────────────────────────────────────────────────────────────

def filter_swiggy_food(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only Swiggy Food posts; exclude Instamart, District, etc."""
    if df.empty:
        return df
    text_lower = df["text"].str.lower()
    has_swiggy  = text_lower.str.contains("swiggy", na=False)
    # Exclude if ONLY about a non-food Swiggy vertical
    is_non_food = text_lower.apply(
        lambda t: any(kw in t for kw in SWIGGY_EXCLUDE)
                  and "food" not in t
                  and "delivery" not in t
                  and "order" not in t
    )
    return df[has_swiggy & ~is_non_food].reset_index(drop=True)


def filter_zomato(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    text_lower = df["text"].str.lower()
    return df[text_lower.str.contains("zomato", na=False)].reset_index(drop=True)


def filter_date_range(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "date" not in df.columns:
        return df
    # Accept Apr–Jun (primary window) plus current month so real scraped posts aren't dropped
    lo = pd.Timestamp(f"{YEAR}-04-01")
    hi = pd.Timestamp(TODAY.strftime("%Y-%m-%d") + " 23:59:59")
    has_date = df["date"].notna()
    in_range  = (df["date"] >= lo) & (df["date"] <= hi)
    return df[~has_date | in_range].reset_index(drop=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def load_raw(brand: str, platform: str) -> list:
    path = RAW_DIR / f"{brand}_{platform}.json"
    if not path.exists():
        log.warning("Raw file not found: %s", path)
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_unified_df() -> pd.DataFrame:
    frames = []
    for brand in ("swiggy", "zomato"):
        tw  = normalise_twitter(load_raw(brand, "twitter"),  brand)
        rd  = normalise_reddit(load_raw(brand, "reddit"),    brand)
        li  = normalise_linkedin(load_raw(brand, "linkedin"), brand)

        combined = pd.concat([tw, rd, li], ignore_index=True)

        if brand == "swiggy":
            combined = filter_swiggy_food(combined)
        else:
            combined = filter_zomato(combined)

        combined = filter_date_range(combined)
        frames.append(combined)

    non_empty = [f for f in frames if not f.empty]
    if not non_empty:
        log.warning("All raw files were empty — returning empty DataFrame")
        return pd.DataFrame()

    df = pd.concat(non_empty, ignore_index=True)

    if df.empty or "brand" not in df.columns:
        log.warning("No usable posts after filtering — returning empty DataFrame")
        return pd.DataFrame()

    # Deduplicate by (brand, platform, text similarity via first 200 chars)
    df["_dedup_key"] = df["brand"] + "|" + df["platform"] + "|" + df["text"].str[:200]
    df = df.drop_duplicates(subset="_dedup_key").drop(columns="_dedup_key")

    # Add month column — extend to cover real scraped posts beyond June
    MONTH_MAP = {1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",
                 7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"}
    df["month"] = df["date"].dt.month.map(MONTH_MAP).fillna("Unknown")
    df["month_num"] = df["date"].dt.month.fillna(0).astype(int)
    df["data_source"] = "real"

    out = PROC_DIR / "unified_raw.parquet"
    df.to_parquet(out, index=False)
    log.info("Unified dataset: %d rows → %s", len(df), out)
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = build_unified_df()
    print(df.groupby(["brand", "platform"]).size().to_string())
