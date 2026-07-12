"""
Master pipeline runner.

Usage:
  python src/run_pipeline.py           # uses synthetic data (instant)
  python src/run_pipeline.py --live    # scrapes live data via Apify first
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


def step(label: str):
    log.info("=" * 60)
    log.info("STEP: %s", label)
    log.info("=" * 60)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true",
                        help="Collect live data via Apify before processing")
    parser.add_argument("--skip-pptx", action="store_true",
                        help="Skip PowerPoint generation")
    args = parser.parse_args()

    if args.live:
        step("1. Live data collection via Apify")
        from collect_data import (
            collect_twitter, collect_reddit, collect_linkedin,
            SWIGGY_QUERIES, ZOMATO_QUERIES,
        )
        collect_twitter("swiggy", SWIGGY_QUERIES, max_per_query=300)
        collect_reddit ("swiggy", SWIGGY_QUERIES[:6], max_per_query=200)
        collect_linkedin("swiggy", SWIGGY_QUERIES[:4], max_per_query=100)

        collect_twitter("zomato", ZOMATO_QUERIES, max_per_query=300)
        collect_reddit ("zomato", ZOMATO_QUERIES[:6], max_per_query=200)
        collect_linkedin("zomato", ZOMATO_QUERIES[:4], max_per_query=100)

        step("2. Preprocess live data")
        from preprocess import build_unified_df
        df = build_unified_df()

        step("3. Classify")
        from classify import run_classification
        df = run_classification(df)

    else:
        step("1. Generate synthetic data")
        from generate_synthetic import generate_dataset
        df = generate_dataset()

    step("4. Build analytics")
    from analyze import build_analytics
    analytics = build_analytics(df)

    if not args.skip_pptx:
        step("5. Generate PowerPoint")
        try:
            from generate_pptx import generate_pptx
            generate_pptx(analytics)
        except Exception as e:
            log.warning("PowerPoint generation failed: %s", e)

    step("6. Done")
    log.info("All outputs saved to: %s", BASE_DIR / "output")
    log.info("")
    log.info("Launch dashboard:  streamlit run dashboard/app.py")
    log.info("Open CSV:          data/processed/classified.csv")
    log.info("Open PPTX:         output/Swiggy_Escalation_Intelligence_Q2_2025.pptx")


if __name__ == "__main__":
    main()
