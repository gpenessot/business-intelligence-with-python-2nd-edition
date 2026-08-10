"""Download the public A/B test dataset used by section 4.5.

Every other file of the book derives from Online Retail II. This one cannot:
a sales history records purchases, never a randomized experiment. Simulating
an A/B test would mean deciding the answer before running the analysis, which
is precisely what the section teaches not to do. So chapter 4 borrows a real
experiment instead, and says so.

    Source : https://www.kaggle.com/datasets/faviovaz/marketing-ab-testing
    Author : Favio Vazquez
    Content: 588 101 users of a display advertising campaign, split between a
             treatment group exposed to ads and a control group shown public
             service announcements at the same placements.

The download needs no Kaggle account.

Usage:
    uv run --with kagglehub python scripts/download_marketing_ab.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

import kagglehub
import pandas as pd

DATASET = "faviovaz/marketing-ab-testing"
SOURCE_NAME = "marketing_AB.csv"
TARGET = Path("data/raw/marketing_ab.csv")

EXPECTED_ROWS = 588_101
EXPECTED_COLUMNS = {"user id", "test group", "converted", "total ads",
                    "most ads day", "most ads hour"}


def main() -> None:
    cache_dir = Path(kagglehub.dataset_download(DATASET))
    source = cache_dir / SOURCE_NAME

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, TARGET)

    # Check we got the file the chapter was written against: a public dataset
    # can be re-uploaded, and every figure of section 4.5 depends on it.
    df = pd.read_csv(TARGET)
    missing = EXPECTED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"{TARGET}: missing expected columns {sorted(missing)}")
    if len(df) != EXPECTED_ROWS:
        raise ValueError(f"{TARGET}: expected {EXPECTED_ROWS:,} rows, got {len(df):,}")

    groups = df["test group"].value_counts().to_dict()
    print(f"{TARGET}: {len(df):,} users, groups {groups}")


if __name__ == "__main__":
    main()
