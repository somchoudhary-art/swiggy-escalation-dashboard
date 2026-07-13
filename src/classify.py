"""
Classification Engine
- Rule-based keyword pre-classifier (fast, interpretable)
- LLM-based refinement for ambiguous posts
- Sentiment labelling
- Emerging topic detection via BERTopic
"""

import re
import logging
from pathlib import Path
import pandas as pd
import numpy as np

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
PROC_DIR = BASE_DIR / "data" / "processed"

# ── Bucket definitions ─────────────────────────────────────────────────────────
BUCKETS = {
    "A_Cancellation": [
        r"cancell?ed", r"cancell?ation", r"auto.cancel", r"order cancel",
        r"restaurant cancel", r"delivery cancel", r"cancel order",
    ],
    "B_AI_Bot": [
        r"bot loop", r"chatbot", r"ai support", r"automated response",
        r"no human", r"reach human", r"virtual assistant", r"bot response",
        r"automated", r"ai agent", r"swiggy ai", r"zomato ai",
    ],
    "C_Customer_Care": [
        r"customer (care|service|support|executive)", r"agent behav",
        r"rude (agent|executive|support)", r"no (callback|response|resolution)",
        r"slow support", r"escalat", r"poor support", r"support team",
        r"helpless", r"useless support",
    ],
    "D_Delay": [
        r"late deliver", r"delay(ed)?", r"took (too )?long", r"waiting",
        r"hours? (for|to get)", r"still waiting", r"not delivered yet",
        r"eta", r"overdue", r"delayed deliver",
    ],
    "E_Food_Quality": [
        r"wrong (item|order|food)", r"missing (item|food|order)",
        r"cold food", r"packaging", r"spill(ed)?", r"veg.non.veg",
        r"non.?veg.*veg", r"hair", r"insect", r"foreign (particle|object|material)",
        r"stale", r"taste", r"undercooked", r"overcooked", r"quantity",
        r"quality (issue|problem|bad)", r"bad food", r"not fresh",
        r"spoiled", r"rotten",
    ],
    "F_Delivery_Executive": [
        r"delivery (boy|guy|partner|executive|agent|person)",
        r"rude (deliver|rider|partner)", r"fake deliver", r"didn.t deliver",
        r"come outside", r"safety (concern|issue)", r"tamper",
        r"unprofessional", r"not delivering", r"rider behav",
    ],
    "G_Payment_Coupon": [
        r"payment fail", r"double (charge|debit)", r"refund",
        r"coupon (not applied|fail|issue)", r"cashback", r"wallet",
        r"money deducted", r"charged (twice|extra|again)", r"not refunded",
        r"promo (code|fail)", r"discount not applied",
    ],
    "H_Price_Fee": [
        r"platform fee", r"delivery (fee|charge)", r"surge (price|pricing|fee)",
        r"high (price|fee|charge)", r"hidden charge", r"rain (fee|surcharge)",
        r"extra fee", r"overcharging", r"price (hike|increase)",
    ],
}

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


def _compile(patterns: list):
    return re.compile("|".join(patterns), re.IGNORECASE)


COMPILED = {bucket: _compile(pats) for bucket, pats in BUCKETS.items()}


# ── Keyword classifier ─────────────────────────────────────────────────────────

def classify_text(text: str) -> tuple[str, float]:
    """
    Returns (bucket_key, confidence).
    confidence = 1.0 for single match, 0.8 for multi-match (take first).
    """
    if not isinstance(text, str) or not text.strip():
        return "I_Other", 0.5

    matches = {}
    for bucket, pattern in COMPILED.items():
        found = pattern.findall(text)
        if found:
            matches[bucket] = len(found)

    if not matches:
        return "I_Other", 0.5
    if len(matches) == 1:
        return list(matches.keys())[0], 1.0

    # Multiple matches: pick highest count; break ties by bucket order
    best = max(matches, key=lambda b: (matches[b], -list(BUCKETS).index(b)))
    conf = 0.8 if len(matches) > 1 else 1.0
    return best, conf


def classify_df(df: pd.DataFrame) -> pd.DataFrame:
    results = df["text"].apply(classify_text)
    df["bucket"]     = results.apply(lambda x: x[0])
    df["bucket_label"] = df["bucket"].map(BUCKET_LABELS)
    df["confidence"] = results.apply(lambda x: x[1])
    return df


# ── Sentiment ──────────────────────────────────────────────────────────────────

NEGATIVE_WORDS = re.compile(
    r"worst|terrible|horrible|awful|bad|poor|delay|cancel|refund|angry|"
    r"frustrated|useless|cheated|scam|fraud|disgusting|pathetic|incompetent|"
    r"disappointed|never (again|order|use)|waste|ruin|wrong|missing|cold|"
    r"rude|unprofessional|tamper|fake|stale|overcharge|hidden|surge|"
    r"no response|bot loop|chatbot|automated", re.IGNORECASE
)
POSITIVE_WORDS = re.compile(
    r"great|excellent|amazing|good|love|happy|satisfied|fast|quick|"
    r"on time|perfect|wonderful|appreciate|thank", re.IGNORECASE
)

def sentiment_label(text: str) -> str:
    if not isinstance(text, str):
        return "Neutral"
    neg = len(NEGATIVE_WORDS.findall(text))
    pos = len(POSITIVE_WORDS.findall(text))
    if neg > pos:
        return "Negative"
    if pos > neg:
        return "Positive"
    return "Neutral"


def add_sentiment(df: pd.DataFrame) -> pd.DataFrame:
    df["sentiment"] = df["text"].apply(sentiment_label)
    return df


# ── Is Complaint / Is Escalation flags ────────────────────────────────────────

COMPLAINT_PATTERN = re.compile(
    r"complaint|issue|problem|cancel|delay|refund|wrong|missing|rude|"
    r"tamper|fraud|scam|overcharge|not working|failed|not delivered|"
    r"poor|bad|terrible|worst|useless|angry|frustrated|disappointed",
    re.IGNORECASE
)

ESCALATION_PATTERN = re.compile(
    r"escalat|consumer court|legal|police|ncpr|twitter|social media|"
    r"going viral|complaint box|grievance|ombudsman|filing complaint|"
    r"taking action|no resolution|nobody helping|days? (later|ago) still",
    re.IGNORECASE
)


def add_complaint_flags(df: pd.DataFrame) -> pd.DataFrame:
    df["is_complaint"]  = df["text"].apply(
        lambda t: bool(COMPLAINT_PATTERN.search(t)) if isinstance(t, str) else False
    )
    df["is_escalation"] = df["text"].apply(
        lambda t: bool(ESCALATION_PATTERN.search(t)) if isinstance(t, str) else False
    )
    return df


# ── Emerging topic detection ───────────────────────────────────────────────────

def detect_emerging_topics(df: pd.DataFrame, n_topics: int = 10) -> pd.DataFrame:
    """
    Run BERTopic on the 'I_Other' bucket to surface new themes.
    Falls back to TF-IDF + KMeans if BERTopic is unavailable.
    """
    other_df = df[df["bucket"] == "I_Other"].copy()
    if len(other_df) < 20:
        log.info("Too few 'Other' posts for topic modeling (%d)", len(other_df))
        df["topic_label"] = ""
        return df

    docs = other_df["text"].fillna("").tolist()

    try:
        from bertopic import BERTopic
        topic_model = BERTopic(
            nr_topics=n_topics,
            calculate_probabilities=False,
            verbose=False,
        )
        topics, _ = topic_model.fit_transform(docs)
        topic_info = topic_model.get_topic_info()

        # Map topic id → label
        topic_map = {
            row["Topic"]: row["Name"]
            for _, row in topic_info.iterrows()
            if row["Topic"] != -1
        }
        other_df["topic_label"] = [topic_map.get(t, "misc") for t in topics]
        log.info("BERTopic: %d topics found", len(topic_map))

    except Exception as e:
        log.warning("BERTopic failed (%s); using TF-IDF KMeans fallback", e)
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.cluster import KMeans

            vec = TfidfVectorizer(max_features=500, stop_words="english", ngram_range=(1, 2))
            X = vec.fit_transform(docs)
            k = min(n_topics, len(docs) // 5 + 1)
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = km.fit_predict(X)

            # Get top terms per cluster
            terms = vec.get_feature_names_out()
            centers = km.cluster_centers_
            cluster_labels = {}
            for i in range(k):
                top_idx = centers[i].argsort()[-3:][::-1]
                cluster_labels[i] = "_".join(terms[j] for j in top_idx)

            other_df["topic_label"] = [cluster_labels.get(l, "misc") for l in labels]

        except Exception as e2:
            log.error("KMeans fallback also failed: %s", e2)
            other_df["topic_label"] = "misc"

    df = df.merge(
        other_df[["topic_label"]],
        left_index=True, right_index=True,
        how="left"
    )
    df["topic_label"] = df.get("topic_label", "").fillna("")
    return df


# ── Main pipeline ──────────────────────────────────────────────────────────────

def run_classification(df: pd.DataFrame) -> pd.DataFrame:
    log.info("Classifying %d posts...", len(df))
    df = classify_df(df)
    df = add_sentiment(df)
    df = add_complaint_flags(df)
    df = detect_emerging_topics(df)

    out = PROC_DIR / "classified.parquet"
    df.to_parquet(out, index=False)

    # Also save CSV (skip if file is locked by Excel)
    try:
        df.to_csv(PROC_DIR / "classified.csv", index=False, encoding="utf-8-sig")
    except PermissionError:
        log.warning("classified.csv is open — CSV save skipped; parquet is the source of truth")
    log.info("Classification done. Saved to %s", out)
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = pd.read_parquet(PROC_DIR / "unified_raw.parquet")
    classified = run_classification(df)
    print(classified.groupby(["brand", "bucket_label"]).size().to_string())
