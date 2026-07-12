"""
Synthetic Data Generator
Produces realistic placeholder data that mirrors real social-media post
distributions for Swiggy Food and Zomato (Apr–Jun).

Use this when:
  - Live Apify scraping is still running
  - Platform scrapers are rate-limited / unavailable
  - You want to demo the dashboard before real data arrives

The synthetic dataset is calibrated to plausible complaint proportions
based on public CX research for Indian food-delivery apps.
"""

import random
import uuid
import logging
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import numpy as np

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
PROC_DIR = BASE_DIR / "data" / "processed"
PROC_DIR.mkdir(exist_ok=True)

YEAR = date.today().year
random.seed(42)
np.random.seed(42)

# ── Volume targets ─────────────────────────────────────────────────────────────
# Swiggy typically has ~30-40% more Twitter complaints than Zomato (est.)
VOLUME = {
    "swiggy": {"Twitter/X": 1100, "Reddit": 320, "LinkedIn": 130},
    "zomato": {"Twitter/X":  820, "Reddit": 240, "LinkedIn":  90},
}

# Bucket weight distribution (complaint share) per brand
BUCKET_WEIGHTS = {
    "swiggy": {
        "A_Cancellation":       0.18,
        "B_AI_Bot":             0.10,
        "C_Customer_Care":      0.14,
        "D_Delay":              0.16,
        "E_Food_Quality":       0.13,
        "F_Delivery_Executive": 0.09,
        "G_Payment_Coupon":     0.09,
        "H_Price_Fee":          0.06,
        "I_Other":              0.05,
    },
    "zomato": {
        "A_Cancellation":       0.15,
        "B_AI_Bot":             0.08,
        "C_Customer_Care":      0.16,
        "D_Delay":              0.18,
        "E_Food_Quality":       0.14,
        "F_Delivery_Executive": 0.10,
        "G_Payment_Coupon":     0.09,
        "H_Price_Fee":          0.05,
        "I_Other":              0.05,
    },
}

# MoM growth factors (June has more data due to summer; May slight uptick)
MONTHLY_MIX = {
    "April": 0.30,
    "May":   0.33,
    "June":  0.37,
}

BUCKET_LABELS = {
    "A_Cancellation":       "A. Cancellation",
    "B_AI_Bot":             "B. AI/Bot Related",
    "C_Customer_Care":      "C. Customer Care",
    "D_Delay":              "D. Delay Related",
    "E_Food_Quality":       "E. Food Quality",
    "F_Delivery_Executive": "F. Delivery Executive",
    "G_Payment_Coupon":     "G. Payment/Coupon",
    "H_Price_Fee":          "H. Price/Fee",
    "I_Other":              "I. Other/Emerging",
}

# ── Sample post templates per bucket ──────────────────────────────────────────
TEMPLATES = {
    "A_Cancellation": [
        "@{brand} my order was cancelled without any reason after waiting 40 minutes. No refund yet! #FoodDelivery",
        "Third time {brand} auto-cancelled my order at the last minute. Terrible experience.",
        "{brand} cancelled my order after the restaurant confirmed it. What is happening?",
        "Restaurant on {brand} cancelled my food order on a Saturday night. Ordered at 9pm, cancelled at 9:30. Zero accountability.",
        "Order ID {oid} was auto-cancelled by {brand}. No notification, money still deducted. Fix this!",
        "{brand} cancellation issue is getting worse every week. Twice in the last 3 days.",
    ],
    "B_AI_Bot": [
        "@{brand} your chatbot is absolutely useless. It keeps looping me in circles and won't connect to a human agent!",
        "{brand} AI support gave me the same automated response 5 times. There is no way to reach a real person.",
        "The {brand} bot is stuck in a loop. All I want is a refund and it keeps asking me to rate my order.",
        "@{brand} your AI assistant is a joke. It cannot solve even basic issues. Please provide human support.",
        "Bot loop nightmare on {brand}. Spent 45 minutes going round in circles for a missing item complaint.",
        "{brand} chatbot said 'We understand your concern' and closed the ticket. No resolution whatsoever.",
    ],
    "C_Customer_Care": [
        "The {brand} support executive was extremely rude and disconnected my call when I asked for a supervisor.",
        "@{brand} it has been 5 days and I still have not received a callback. Your customer service is broken.",
        "{brand} customer care said they would resolve my issue in 24 hours. It has now been 72 hours. Nothing.",
        "Worst customer care experience ever with {brand}. Agent kept putting me on hold for 20 minutes then hung up.",
        "@{brand} your support team gives scripted responses and has zero authority to actually fix anything.",
        "{brand} escalated my ticket to 3 different agents and none of them could process my refund.",
    ],
    "D_Delay": [
        "Order from {brand} was supposed to arrive in 30 minutes. It is now 2 hours and still waiting.",
        "@{brand} the estimated delivery time keeps increasing. Started at 35 mins, now showing 95 mins. UNACCEPTABLE.",
        "{brand} delivery partner was 2km away for 45 minutes. What is going on?",
        "My {brand} order ETA has changed 4 times in the last hour. Zero communication from the app.",
        "Ordered food on {brand} for lunch. Still waiting at 3pm. Order placed at 12:30. This is ridiculous.",
        "{brand} shows restaurant preparation time of 5 minutes but it has been 50 minutes. No update.",
    ],
    "E_Food_Quality": [
        "@{brand} they delivered completely wrong items. I ordered paneer but got chicken. Unacceptable!",
        "Missing items in my {brand} order again. Half my food was not delivered and the rest was cold.",
        "{brand} delivered food with a foreign particle inside. This is a serious hygiene issue.",
        "The food quality from {brand} has deteriorated significantly. Stale roti, watery dal. Complete waste of money.",
        "@{brand} ordered 2 items and only 1 was delivered. The other was missing. No refund either.",
        "{brand} delivered veg as non-veg. This is a religious and dietary violation. Extremely upset.",
        "Hair found in food delivered by {brand}. Complained immediately, no action taken.",
        "Food from {brand} was completely cold and the packaging was damaged. Clearly tampered with.",
    ],
    "F_Delivery_Executive": [
        "@{brand} the delivery executive was rude and demanded extra tip. When I refused he left the food outside.",
        "{brand} delivery partner marked order as delivered but never came to my building. Fake delivery!",
        "The {brand} delivery executive asked me to come 500 meters outside to collect my order. I paid for delivery!",
        "@{brand} rider was extremely rude, used abusive language when I asked why he was late.",
        "{brand} delivery guy tampered with my sealed food bag. This is unacceptable.",
        "Safety concern: {brand} delivery executive was driving recklessly and arrived smelling of alcohol.",
    ],
    "G_Payment_Coupon": [
        "@{brand} double charged me and my bank confirms 2 deductions. Need immediate refund.",
        "{brand} coupon code did not apply at checkout even though it is supposed to be valid.",
        "Refund from {brand} promised in 5-7 days. It has been 15 days. Where is my money?",
        "@{brand} my cashback never reflected. Order from 10 days ago. No response from support.",
        "{brand} wallet money deducted but order was cancelled. Balance not restored.",
        "Applied a 50% coupon on {brand} and it showed discount on screen but full amount was charged.",
    ],
    "H_Price_Fee": [
        "@{brand} the platform fee has increased from Rs 3 to Rs 6 in just 2 months. Stop looting customers.",
        "{brand} is charging a rain surcharge but it is not even raining. Hidden charges everywhere.",
        "Delivery fee on {brand} during peak hours is higher than the actual food price. This is robbery.",
        "@{brand} please explain why there is a Rs 10 handling fee on top of delivery fee and platform fee?",
        "The surge pricing on {brand} during evenings is outrageous. Same item costs 30% more after 7pm.",
        "{brand} price shown on menu is different from what is charged at checkout. Hidden charges!",
    ],
    "I_Other": [
        "@{brand} the app keeps crashing when I try to track my order. Very buggy.",
        "{brand} loyalty programme rewards disappeared from my account without any explanation.",
        "Dark pattern on {brand} app — I accidentally bought a subscription I did not want.",
        "@{brand} restaurant listed as open but not accepting orders. Stop showing ghost restaurants.",
        "{brand} pushed 8 promotional notifications today. Please give users the option to opt out.",
        "The {brand} app does not work on my Android device after the latest update.",
    ],
}

BRANDS = {"swiggy": "Swiggy", "zomato": "Zomato"}


def random_date(month: str) -> pd.Timestamp:
    month_map = {"April": 4, "May": 5, "June": 6}
    m = month_map[month]
    import calendar
    _, days = calendar.monthrange(YEAR, m)
    d = random.randint(1, days)
    h = random.randint(7, 23)
    mi = random.randint(0, 59)
    return pd.Timestamp(YEAR, m, d, h, mi)


def generate_post(brand_key: str, platform: str, bucket: str, month: str) -> dict:
    brand_name = BRANDS[brand_key]
    template = random.choice(TEMPLATES[bucket])
    text = template.format(
        brand=brand_name,
        oid=f"{random.randint(100000,999999)}",
    )

    engagement_map = {
        "Twitter/X": (0, 200),
        "Reddit":    (1, 50),
        "LinkedIn":  (0, 30),
    }
    likes    = random.randint(*engagement_map[platform])
    replies  = random.randint(0, likes // 3 + 1)
    retweets = random.randint(0, likes // 5 + 1) if platform == "Twitter/X" else 0

    # Negative sentiment for complaint posts
    sentiment = random.choices(
        ["Negative", "Neutral", "Positive"],
        weights=[0.80, 0.15, 0.05]
    )[0]

    return {
        "id":           str(uuid.uuid4()),
        "platform":     platform,
        "brand":        brand_key,
        "text":         text,
        "date":         random_date(month),
        "url":          f"https://{platform.lower().replace('/', '').replace(' ', '')}.com/example/{uuid.uuid4().hex[:8]}",
        "likes":        likes,
        "retweets":     retweets,
        "replies":      replies,
        "engagement":   likes + retweets + replies,
        "author":       f"user_{uuid.uuid4().hex[:6]}",
        "bucket":       bucket,
        "bucket_label": BUCKET_LABELS[bucket],
        "confidence":   round(random.uniform(0.75, 1.0), 2),
        "sentiment":    sentiment,
        "is_complaint": True,
        "is_escalation": random.random() < 0.12,
        "topic_label":  "",
        "month":        month,
        "month_num":    {"April": 4, "May": 5, "June": 6}[month],
    }


def generate_dataset() -> pd.DataFrame:
    rows = []
    for brand_key, platform_vols in VOLUME.items():
        for platform, total_vol in platform_vols.items():
            for month, mix in MONTHLY_MIX.items():
                n_month = max(1, int(total_vol * mix))
                bucket_keys   = list(BUCKET_WEIGHTS[brand_key].keys())
                bucket_probs  = list(BUCKET_WEIGHTS[brand_key].values())
                buckets_drawn = random.choices(bucket_keys, weights=bucket_probs, k=n_month)
                for bucket in buckets_drawn:
                    rows.append(generate_post(brand_key, platform, bucket, month))

    df = pd.DataFrame(rows)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    out = PROC_DIR / "classified.parquet"
    df.to_parquet(out, index=False)
    try:
        df.to_csv(PROC_DIR / "classified.csv", index=False, encoding="utf-8-sig")
    except PermissionError:
        alt = PROC_DIR / "classified_new.csv"
        df.to_csv(alt, index=False, encoding="utf-8-sig")
        log.warning("classified.csv locked (open in Excel?); saved to %s instead", alt)

    log.info("Synthetic dataset: %d rows saved to %s", len(df), out)
    print("\n=== Synthetic Dataset Summary ===")
    print(df.groupby(["brand", "platform"]).size().to_string())
    print("\n--- Bucket distribution ---")
    print(df.groupby(["brand", "bucket_label"]).size().to_string())
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generate_dataset()
