# Swiggy Food vs Zomato — Customer Escalation Intelligence Dashboard

> **Q2 2025 (April – June) | Sources: Twitter/X, Reddit, LinkedIn**
> Built by: CX & Strategy, Swiggy

---

## What This Project Does

This project scrapes social media posts mentioning **Swiggy Food** and **Zomato**, classifies them into 9 customer escalation categories, analyses trends across Q2 2025, and presents everything in:

1. **An interactive Streamlit web dashboard** (publicly hosted, shareable link)
2. **A ~25-page Word document** with detailed analysis, root causes, and recommendations

The goal is to answer: *Where are customers escalating? Is Swiggy worse than Zomato? What is growing fastest? What do we fix first?*

---

## Live Dashboard

Hosted on Streamlit Community Cloud — connected to this GitHub repo. Rebuilds automatically on every `git push`.

---

## Project Architecture

```
swiggy_escalation_dashboard/
│
├── src/                        # Python pipeline scripts
│   ├── collect_data.py         # Apify scraping (Twitter, Reddit, LinkedIn)
│   ├── preprocess.py           # Schema normalisation, dedup, date filter
│   ├── classify.py             # 9-bucket classifier + sentiment
│   ├── analyze.py              # All metrics → output/analytics.json
│   ├── generate_synthetic.py   # 2,695 synthetic posts (demo/dev mode)
│   ├── generate_docx.py        # Word report generator (python-docx)
│   ├── generate_pptx.py        # PowerPoint generator (python-pptx)
│   └── run_pipeline.py         # Master runner
│
├── dashboard/
│   └── app.py                  # Streamlit dashboard (7 tabs)
│
├── data/
│   ├── raw/                    # Raw Apify JSON output (gitignored)
│   └── processed/
│       ├── classified.parquet  # Full classified dataset (committed)
│       └── classified.csv      # Same data as CSV
│
├── output/
│   ├── analytics.json          # Pre-computed metrics (committed)
│   ├── Swiggy_Escalation_Intelligence_Q2_2025.docx
│   └── Swiggy_Escalation_Intelligence_Q2_2025.pptx
│
├── .streamlit/
│   └── config.toml             # Theme (Swiggy orange), headless mode
│
├── requirements.txt            # Dashboard dependencies only
└── README.md                   # This file
```

---

## Data Flow

```
Social Media (Twitter/X · Reddit · LinkedIn)
        │
        ▼  [Apify cloud scrapers]
data/raw/{brand}_{platform}.json
        │
        ▼  [src/preprocess.py]
        Unified DataFrame
        - Normalise schemas across 3 platforms
        - Apply Swiggy food-only filter
        - Filter Apr–Jun 2025 date range
        - Deduplicate by post ID
        │
        ▼  [src/classify.py]
data/processed/classified.parquet
        - 9-bucket keyword classification
        - Sentiment: Negative / Neutral / Positive
        - Flags: is_complaint, is_escalation
        - Emerging topic detection (TF-IDF KMeans)
        │
        ▼  [src/analyze.py]
output/analytics.json
        - KPIs per brand
        - Monthly trends (MoM%)
        - Bucket analysis
        - Competitive gap (Swiggy % vs Zomato %)
        - Emerging issues
        - Representative posts
        │
        ├──▶  dashboard/app.py         (Streamlit interactive dashboard)
        └──▶  src/generate_docx.py     (Word report)
```

---

## Escalation Taxonomy (9 Buckets)

| Bucket | Label | What it captures |
|---|---|---|
| A | Cancellation | Order cancelled by platform/restaurant, slow refund |
| B | AI/Bot Related | Bot loop, no human escalation path, auto-ticket close |
| C | Customer Care | Rude agents, no callback, scripted responses |
| D | Delay Related | ETA breach, no proactive notification, long wait |
| E | Food Quality | Wrong item, missing item, hygiene issues, cold food |
| F | Delivery Executive | Rude rider, fake delivery, tip demand |
| G | Payment/Coupon | Double charge, coupon failure, slow refund |
| H | Price/Fee | Platform fee hike, rain surcharge, hidden fees |
| I | Other/Emerging | App crash, ghost restaurants, dark patterns |

**Classification method:** Regex keyword matching. Each post is scanned against all 9 buckets; first match wins. Unmatched posts go to bucket I.

---

## Competitive Analysis Logic

For each bucket, the dashboard computes:

- **Swiggy share %** = (Swiggy posts in bucket) / (Total Swiggy posts) × 100
- **Zomato share %** = (Zomato posts in bucket) / (Total Zomato posts) × 100
- **Gap (pp)** = Swiggy share % − Zomato share %

A positive gap means Swiggy has a **proportionally higher** complaint rate in that bucket vs Zomato — this is the priority fix signal, not raw volume.

---

## Swiggy Food-Only Filter

Posts mentioning Swiggy are filtered to food delivery only. Posts that mention any of the following are excluded:

`instamart` · `district` · `genie` · `dineout` · `minis` · `swiggy stores` · `grocery`

This ensures the benchmark against Zomato (food-only platform) is fair.

---

## Data Sources

| Platform | Apify Actor | What it captures |
|---|---|---|
| Twitter/X | `apidojo/tweet-scraper` | @mentions, complaints, viral threads |
| Reddit | `trudax/reddit-scraper-lite` | r/india, r/bangalore, r/mumbai, r/delhi |
| LinkedIn | `voyager/linkedin-post-search` | Professional and observer posts |

**Fallback actors:**
- Twitter: `vbarbaresi/twitter-scraper`
- LinkedIn: `dev_fusion/linkedin-post-scraper`

---

## Running the Pipeline

### Prerequisites

```bash
# Python 3.12 (Windows path)
C:\Users\som.choudhary\AppData\Local\Programs\Python\Python312\python.exe

# Install all dependencies
pip install streamlit pandas numpy plotly pyarrow apify-client python-docx python-pptx scikit-learn
```

### Run with synthetic data (instant, for demo)

```bash
python src/run_pipeline.py
```

Generates 2,695 realistic synthetic posts calibrated to plausible complaint distributions. No Apify credits consumed.

### Run with live Apify data (real posts, ~1–2 hours)

```bash
python src/run_pipeline.py --live
```

Triggers all 6 Apify scrapers (Swiggy × 3 platforms + Zomato × 3 platforms), preprocesses, classifies, and rebuilds analytics.json.

### Launch dashboard locally

```bash
streamlit run dashboard/app.py
# Opens at http://localhost:8501
```

### Generate Word report

```bash
python src/generate_docx.py
# Saves to output/Swiggy_Escalation_Intelligence_Q2_2025.docx
```

### Push updated data to Streamlit Cloud

```bash
git add output/analytics.json data/processed/classified.parquet data/processed/classified.csv
git commit -m "Update with live Q2 2025 data"
git push origin main
# Streamlit Cloud auto-rebuilds within ~2 minutes
```

---

## Dashboard Tabs

| Tab | What it shows |
|---|---|
| Executive Summary | KPI cards, sentiment donut, radar chart (complaint share by bucket) |
| Monthly Trends | Grouped bar charts (Apr/May/Jun), heatmap, MoM% table |
| Bucket Analysis | Horizontal bar charts per brand, stacked trend, summary table |
| Competitive | Side-by-side count, share-gap bar chart, platform distribution |
| Emerging Issues | Fast-growing issue cards with sample posts |
| Posts | Filterable representative posts by brand + bucket |
| Raw Data | Full dataset with CSV download |

---

## Word Report Sections

1. Cover Page
2. Table of Contents
3. Executive Summary — key findings + biggest risks
4. Key Performance Indicators — full KPI table
5. Monthly Trends — per-brand breakdown + MoM%
6. Bucket Deep Dive (×9) — stats, root causes, recommendations, sample posts
7. Competitive Analysis — share gap table
8. Emerging Issues — fastest-growing complaint clusters
9. Sentiment Analysis
10. Representative Customer Voices
11. Root Cause Analysis — 5 structural root causes
12. Strategic Recommendations — P0/P1/P2 table with owners + timelines
13. Appendix — methodology, taxonomy, limitations

---

## Deployment (Streamlit Community Cloud)

1. Repo must be **public** on GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app
3. Select repo: `somchoudhary-art/swiggy-escalation-dashboard`
4. Main file path: `dashboard/app.py`
5. Click Deploy

**Important:**
- `requirements.txt` contains only the 5 packages needed by the dashboard (`streamlit`, `pandas`, `numpy`, `plotly`, `pyarrow`). Do NOT add `apify-client`, `python-docx`, `scikit-learn` — these are only for the pipeline, not the dashboard, and cause cloud build failures.
- `output/analytics.json` and `data/processed/classified.parquet` must be committed to git — Streamlit Cloud has no way to run the pipeline itself.
- `data/raw/` is gitignored (large files, not needed by dashboard).

---

## Apify Configuration

**Token:** `apify_api_z0RRdE0g5a5gEgieJCj2wiEA6nlaTh4G0Yzs`

**MCP Server** (configured in `~/.claude.json` for use from Claude Code):
```json
"apify-actors": {
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@apify/actors-mcp-server"],
  "env": { "APIFY_TOKEN": "apify_api_z0RRdE0g5a5gEgieJCj2wiEA6nlaTh4G0Yzs" }
}
```

---

## Key Design Decisions

| Decision | Reason |
|---|---|
| Pre-compute analytics.json | Dashboard loads instantly — no heavy computation at render time |
| Parquet for classified data | 5× faster read than CSV, smaller file size |
| Synthetic data generator | Dashboard fully demonstrable without live scraping or Apify credits |
| Keyword classifier (not ML) | Interpretable, debuggable, zero latency, no model hosting needed |
| Streamlit Community Cloud | Free, zero-config, deploys straight from GitHub |
| 5-package requirements.txt | Minimal footprint for cloud build; pipeline deps kept separate |
| `Path(__file__).resolve()` | Works on both Windows (local) and Linux (Streamlit Cloud) |

---

## Data Note

The default dataset is **synthetic** — generated by `src/generate_synthetic.py` using pre-written complaint templates. Volumes and bucket proportions are calibrated to plausible real-world distributions but are not scraped from actual social media.

To replace with real data: run `python src/run_pipeline.py --live` (requires Apify credits, ~1–2 hours).

---

## Tech Stack Summary

| Component | Technology | Version |
|---|---|---|
| Language | Python | 3.12 |
| Dashboard | Streamlit | ≥1.35 |
| Charts | Plotly | ≥5.18 |
| Data | Pandas + PyArrow | ≥2.0 / ≥14.0 |
| Scraping | Apify Client | ≥1.6 |
| Word report | python-docx | ≥1.0 |
| Classification | scikit-learn (TF-IDF) | ≥1.3 |
| Hosting | Streamlit Community Cloud | free tier |
| Version control | Git + GitHub | — |
