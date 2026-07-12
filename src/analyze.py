"""
Analytics: generate all metrics, MoM trends, competitive comparison,
emerging issues, and representative post samples.
Saves results as JSON for the dashboard to consume.
"""

import json
import logging
from pathlib import Path
import pandas as pd
import numpy as np

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
PROC_DIR = BASE_DIR / "data" / "processed"
OUT_DIR  = BASE_DIR / "output"
OUT_DIR.mkdir(exist_ok=True)

MONTHS      = ["April", "May", "June"]
MONTH_ORDER = {"April": 1, "May": 2, "June": 3}

BUCKET_LABELS = {
    "A_Cancellation":      "A. Cancellation",
    "B_AI_Bot":            "B. AI/Bot Related",
    "C_Customer_Care":     "C. Customer Care",
    "D_Delay":             "D. Delay Related",
    "E_Food_Quality":      "E. Food Quality",
    "F_Delivery_Executive":"F. Delivery Executive",
    "G_Payment_Coupon":    "G. Payment/Coupon",
    "H_Price_Fee":         "H. Price/Fee",
    "I_Other":             "I. Other/Emerging",
}


def safe_pct_change(a, b):
    """% change from a to b; returns None if a==0."""
    if a == 0:
        return None
    return round((b - a) / a * 100, 1)


def platform_counts(df: pd.DataFrame) -> dict:
    """Absolute post counts by brand × platform."""
    result = {}
    for brand in ("swiggy", "zomato"):
        sub = df[df["brand"] == brand]
        result[brand] = sub.groupby("platform").size().to_dict()
    return result


def overall_kpis(df: pd.DataFrame) -> dict:
    kpis = {}
    for brand in ("swiggy", "zomato"):
        sub = df[df["brand"] == brand]
        kpis[brand] = {
            "total_posts":      int(len(sub)),
            "complaint_posts":  int(sub["is_complaint"].sum()),
            "escalation_posts": int(sub["is_escalation"].sum()),
            "negative_posts":   int((sub["sentiment"] == "Negative").sum()),
        }
    return kpis


def monthly_trend(df: pd.DataFrame) -> dict:
    """
    Per brand, per month: total, bucket counts, bucket %, MoM growth.
    """
    result = {}
    for brand in ("swiggy", "zomato"):
        sub = df[df["brand"] == brand]
        months_data = {}
        prev_total = None
        prev_bucket_counts = {}

        for month in MONTHS:
            m_df = sub[sub["month"] == month]
            total = len(m_df)
            bucket_counts = m_df.groupby("bucket_label").size().to_dict()
            bucket_pct = {
                k: round(v / total * 100, 1) if total > 0 else 0
                for k, v in bucket_counts.items()
            }

            mom_total = safe_pct_change(prev_total, total) if prev_total is not None else None
            mom_bucket = {
                k: safe_pct_change(prev_bucket_counts.get(k, 0), v)
                for k, v in bucket_counts.items()
            }

            months_data[month] = {
                "total":          total,
                "bucket_counts":  bucket_counts,
                "bucket_pct":     bucket_pct,
                "mom_total_pct":  mom_total,
                "mom_bucket_pct": mom_bucket,
                "complaints":     int(m_df["is_complaint"].sum()),
                "escalations":    int(m_df["is_escalation"].sum()),
                "sentiment_neg":  int((m_df["sentiment"] == "Negative").sum()),
            }
            prev_total = total
            prev_bucket_counts = bucket_counts

        # Biggest increase / decrease Apr→Jun
        apr = months_data.get("April", {}).get("bucket_counts", {})
        jun = months_data.get("June",  {}).get("bucket_counts", {})
        changes = {
            k: (jun.get(k, 0) - apr.get(k, 0))
            for k in set(list(apr.keys()) + list(jun.keys()))
        }
        biggest_increase = max(changes, key=changes.get, default=None)
        biggest_decrease = min(changes, key=changes.get, default=None)

        result[brand] = {
            "by_month":         months_data,
            "biggest_increase": biggest_increase,
            "biggest_decrease": biggest_decrease,
        }
    return result


def bucket_analysis(df: pd.DataFrame) -> dict:
    """
    For every bucket: absolute counts, share, trend, example posts.
    """
    result = {}
    for brand in ("swiggy", "zomato"):
        sub = df[df["brand"] == brand]
        total = len(sub)
        brand_result = {}

        for bucket_key, bucket_label in BUCKET_LABELS.items():
            b_df = sub[sub["bucket"] == bucket_key]
            count = len(b_df)
            share = round(count / total * 100, 1) if total > 0 else 0

            # Trend Apr → Jun
            trend = {
                m: int(len(b_df[b_df["month"] == m]))
                for m in MONTHS
            }

            # Examples: top 5 by engagement
            examples = (
                b_df.sort_values("engagement", ascending=False)
                .head(8)[["text", "platform", "date", "engagement", "sentiment", "url"]]
                .copy()
            )
            examples["date"] = examples["date"].astype(str)
            ex_list = examples.to_dict("records")

            brand_result[bucket_label] = {
                "count":   count,
                "share":   share,
                "trend":   trend,
                "examples": ex_list,
            }

        result[brand] = brand_result
    return result


def competitive_analysis(df: pd.DataFrame) -> dict:
    sw = df[df["brand"] == "swiggy"]
    zm = df[df["brand"] == "zomato"]
    sw_total = max(len(sw), 1)
    zm_total = max(len(zm), 1)

    comparison = {}
    for bucket_key, bucket_label in BUCKET_LABELS.items():
        sw_cnt = int(len(sw[sw["bucket"] == bucket_key]))
        zm_cnt = int(len(zm[zm["bucket"] == bucket_key]))
        sw_share = round(sw_cnt / sw_total * 100, 1)
        zm_share = round(zm_cnt / zm_total * 100, 1)
        comparison[bucket_label] = {
            "swiggy_count": sw_cnt,
            "zomato_count": zm_cnt,
            "swiggy_share": sw_share,
            "zomato_share": zm_share,
            "diff_share":   round(sw_share - zm_share, 1),  # + means worse for Swiggy
        }

    # Higher for Swiggy (share diff > 2pp)
    higher_swiggy = [k for k, v in comparison.items() if v["diff_share"] > 2]
    higher_zomato = [k for k, v in comparison.items() if v["diff_share"] < -2]

    return {
        "by_bucket":     comparison,
        "higher_swiggy": higher_swiggy,
        "higher_zomato": higher_zomato,
    }


def emerging_issues(df: pd.DataFrame) -> list:
    """
    Surface fastest-growing topics from the 'I_Other' bucket +
    biggest MoM spikes across all buckets.
    """
    issues = []

    # 1. Topic model labels in I_Other
    other = df[df["bucket"] == "I_Other"]
    if "topic_label" in other.columns and not other.empty:
        topic_counts = other.groupby("topic_label").size().reset_index(name="count")
        topic_counts = topic_counts[topic_counts["topic_label"] != ""].sort_values(
            "count", ascending=False
        )
        for _, row in topic_counts.head(5).iterrows():
            t_df = other[other["topic_label"] == row["topic_label"]]
            apr_cnt = len(t_df[t_df["month"] == "April"])
            jun_cnt = len(t_df[t_df["month"] == "June"])
            growth = safe_pct_change(apr_cnt, jun_cnt)
            issues.append({
                "issue":      row["topic_label"],
                "type":       "New Topic",
                "total":      int(row["count"]),
                "apr_count":  apr_cnt,
                "jun_count":  jun_cnt,
                "growth_pct": growth,
                "brand":      "both",
                "samples":    t_df.sort_values("engagement", ascending=False)
                               .head(3)[["text", "platform", "date", "engagement"]]
                               .assign(date=lambda d: d["date"].astype(str))
                               .to_dict("records"),
            })

    # 2. Biggest MoM spikes (any bucket, either brand)
    for brand in ("swiggy", "zomato"):
        sub = df[df["brand"] == brand]
        for bucket_key, bucket_label in BUCKET_LABELS.items():
            b_df = sub[sub["bucket"] == bucket_key]
            may_cnt = len(b_df[b_df["month"] == "May"])
            jun_cnt = len(b_df[b_df["month"] == "June"])
            growth = safe_pct_change(may_cnt, jun_cnt)
            if growth and growth > 50 and jun_cnt >= 5:
                issues.append({
                    "issue":      f"{bucket_label} ({brand.title()})",
                    "type":       "Spike",
                    "total":      jun_cnt,
                    "apr_count":  len(b_df[b_df["month"] == "April"]),
                    "jun_count":  jun_cnt,
                    "growth_pct": growth,
                    "brand":      brand,
                    "samples":    [],
                })

    issues.sort(key=lambda x: x.get("growth_pct") or 0, reverse=True)
    return issues


def representative_posts(df: pd.DataFrame, n: int = 8) -> dict:
    """Top N posts per bucket per brand (sorted by engagement)."""
    result = {}
    for brand in ("swiggy", "zomato"):
        sub = df[df["brand"] == brand]
        brand_result = {}
        for bucket_key, bucket_label in BUCKET_LABELS.items():
            b_df = sub[sub["bucket"] == bucket_key]
            posts = (
                b_df.sort_values("engagement", ascending=False)
                .head(n)[["text", "platform", "date", "engagement", "sentiment", "url"]]
                .copy()
            )
            posts["date"] = posts["date"].astype(str)
            brand_result[bucket_label] = posts.to_dict("records")
        result[brand] = brand_result
    return result


def build_analytics(df: pd.DataFrame) -> dict:
    log.info("Building analytics for %d posts...", len(df))
    analytics = {
        "platform_counts": platform_counts(df),
        "kpis":            overall_kpis(df),
        "monthly_trend":   monthly_trend(df),
        "bucket_analysis": bucket_analysis(df),
        "competitive":     competitive_analysis(df),
        "emerging":        emerging_issues(df),
        "rep_posts":       representative_posts(df),
    }

    out = OUT_DIR / "analytics.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(analytics, f, ensure_ascii=False, indent=2, default=str)
    log.info("Analytics saved to %s", out)
    return analytics


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = pd.read_parquet(PROC_DIR / "classified.parquet")
    analytics = build_analytics(df)
    print("KPIs:", json.dumps(analytics["kpis"], indent=2))
