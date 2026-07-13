"""
Master pipeline runner.

Usage:
  python src/run_pipeline.py             # 100% synthetic data (instant demo)
  python src/run_pipeline.py --live      # Reddit + LinkedIn real data +
                                         # synthetic Twitter (Apify Twitter = paid)
  python src/run_pipeline.py --skip-pptx # skip PowerPoint step
"""

import sys
import logging
import argparse
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))
PROC_DIR = BASE_DIR / "data" / "processed"


def step(label: str):
    log.info("=" * 60)
    log.info("STEP: %s", label)
    log.info("=" * 60)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true",
                        help="Scrape Reddit + LinkedIn live; Twitter = synthetic")
    parser.add_argument("--use-cached", action="store_true",
                        help="Skip Apify scraping — reprocess existing raw JSON files")
    parser.add_argument("--skip-pptx", action="store_true")
    args = parser.parse_args()

    import pandas as pd

    if args.live or args.use_cached:
        if args.live and not args.use_cached:
            # ── 1. Scrape Reddit (real) ───────────────────────────────────────
            step("1a. Scrape Reddit (real data via Apify)")
            from collect_data import collect_reddit, collect_linkedin
            from collect_data import SWIGGY_QUERIES, ZOMATO_QUERIES

            collect_reddit("swiggy", SWIGGY_QUERIES[:6], max_per_query=200)
            collect_reddit("zomato", ZOMATO_QUERIES[:6], max_per_query=200)

            # ── 2. Scrape LinkedIn (real) ─────────────────────────────────────
            step("1b. Scrape LinkedIn (real data via Apify)")
            collect_linkedin("swiggy", SWIGGY_QUERIES[:3], max_per_query=100)
            collect_linkedin("zomato", ZOMATO_QUERIES[:3], max_per_query=100)
        else:
            step("1. Using cached raw JSON files (no re-scrape)")

        # ── 3. Preprocess real data ────────────────────────────────────────────
        step("2. Preprocess real Reddit + LinkedIn data")
        from preprocess import build_unified_df
        real_df = build_unified_df()
        real_count = len(real_df)
        log.info("Real posts collected: %d", real_count)

        # ── 4. Classify real posts ─────────────────────────────────────────────
        if real_count > 0:
            step("3. Classify real posts")
            from classify import run_classification
            real_df = run_classification(real_df)
        else:
            log.warning("No real posts collected — will use 100%% synthetic")

        # ── 5. Synthetic Twitter to supplement ────────────────────────────────
        step("4. Generate synthetic Twitter data")
        from generate_synthetic import generate_twitter_only
        synth_twitter = generate_twitter_only()

        # ── 6. Merge ──────────────────────────────────────────────────────────
        step("5. Merge real (Reddit+LinkedIn) + synthetic (Twitter)")
        if real_count > 0:
            df = pd.concat([real_df, synth_twitter], ignore_index=True)
        else:
            log.warning("Falling back to full synthetic dataset")
            from generate_synthetic import generate_dataset
            df = generate_dataset()

        log.info("Final dataset: %d posts  (%d real, %d synthetic Twitter)",
                 len(df), real_count, len(synth_twitter))

        # Save merged classified dataset
        out_parquet = PROC_DIR / "classified.parquet"
        df.to_parquet(out_parquet, index=False)
        try:
            df.to_csv(PROC_DIR / "classified.csv", index=False, encoding="utf-8-sig")
        except PermissionError:
            df.to_csv(PROC_DIR / "classified_new.csv", index=False, encoding="utf-8-sig")
            log.warning("classified.csv locked; saved as classified_new.csv")
        log.info("Merged dataset saved: %s", out_parquet)

    else:
        # ── Full synthetic ─────────────────────────────────────────────────────
        step("1. Generate synthetic data (all platforms)")
        from generate_synthetic import generate_dataset
        df = generate_dataset()

    # ── Build analytics ────────────────────────────────────────────────────────
    step("Build analytics JSON")
    from analyze import build_analytics
    analytics = build_analytics(df)

    # ── Optional PPTX ─────────────────────────────────────────────────────────
    if not args.skip_pptx:
        step("Generate PowerPoint (optional)")
        try:
            from generate_pptx import generate_pptx
            generate_pptx(analytics)
        except Exception as e:
            log.warning("PowerPoint generation skipped: %s", e)

    # ── Generate Word doc ─────────────────────────────────────────────────────
    step("Generate Word report")
    try:
        from generate_docx import generate_docx
        generate_docx()
    except Exception as e:
        log.warning("Word doc generation skipped: %s", e)

    step("Done")
    log.info("Outputs: %s", BASE_DIR / "output")
    log.info("Launch:  streamlit run dashboard/app.py")


if __name__ == "__main__":
    main()
