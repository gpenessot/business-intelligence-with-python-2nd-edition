"""Download and prepare the dataset used as the running example of the book.

The source is the *Online Retail II* dataset from the UCI Machine Learning
Repository: two years of transactions from a UK online retailer selling
all-occasion giftware, shipped across Europe.

    https://archive.ics.uci.edu/dataset/502/online+retail+ii
    Chen, D. (2019). Online Retail II. UCI Machine Learning Repository.
    Licence: Creative Commons Attribution 4.0 International (CC BY 4.0).

The script does as little as possible on purpose:

1. it downloads the source workbook once and caches it;
2. it concatenates the two yearly sheets;
3. it shifts every date by 5,110 days, so the period runs from November 2023
   to December 2025 instead of 2009 to 2011. The offset is a multiple of 7,
   so every transaction keeps its original day of the week, and the weekend
   patterns of the data stay intact;
4. it writes the result as-is to ``data/raw/sales.csv``;
5. it writes ``data/raw/sales_sample.csv``, a small already clean extract of
   valid 2024 order lines, used by the guided example of chapter 1.

Apart from that extract, nothing is cleaned. The duplicate rows, the missing customer ids, the returns
with a negative quantity and the cancelled invoices are the ones from the real
dataset: cleaning them up is the whole point of chapter 3.

Usage:
    uv run python scripts/prepare_dataset.py
"""

from __future__ import annotations

import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

SOURCE_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
CACHE_DIR = Path("data/source")
OUTPUT_DIR = Path("data/raw")
WORKBOOK_NAME = "online_retail_II.xlsx"

# 5,110 days is 14 years, rounded down to a whole number of weeks so that every
# date keeps its original day of the week.
DATE_OFFSET_DAYS = 5_110

# Size of the simplified extract used by the guided example of chapter 1.
SAMPLE_ROWS = 12_543


def download_source() -> Path:
    """Download the source workbook once and return its local path."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    workbook = CACHE_DIR / WORKBOOK_NAME
    if workbook.exists():
        print(f"Source workbook already downloaded: {workbook}")
        return workbook

    archive = CACHE_DIR / "online_retail_II.zip"
    print(f"Downloading {SOURCE_URL} (about 45 MB, this takes a moment)...")
    urllib.request.urlretrieve(SOURCE_URL, archive)
    with zipfile.ZipFile(archive) as zf:
        zf.extract(WORKBOOK_NAME, CACHE_DIR)
    archive.unlink()
    return workbook


def load_workbook(workbook: Path) -> pd.DataFrame:
    """Concatenate the two yearly sheets into a single DataFrame."""
    sheets = pd.ExcelFile(workbook)
    print(f"Sheets found: {sheets.sheet_names}")
    frames = [sheets.parse(name) for name in sheets.sheet_names]
    df = pd.concat(frames, ignore_index=True)

    # Invoice, StockCode and Description mix numbers and text in the source
    # file. Forcing them to text keeps the cancelled invoices (prefixed with a
    # C) readable instead of turning them into NaN.
    for column in ["Invoice", "StockCode", "Description", "Country"]:
        df[column] = df[column].astype("string")
    return df


def shift_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Move the period forward while keeping every day of the week intact."""
    df = df.copy()
    df["InvoiceDate"] = df["InvoiceDate"] + pd.Timedelta(days=DATE_OFFSET_DAYS)
    return df


def build_chapter1_extract(df: pd.DataFrame) -> pd.DataFrame:
    """Build the small, already clean extract used by chapter 1.

    Chapter 1 is a first contact with the data: the reader has not learned how
    to clean anything yet, so this extract keeps only valid 2024 order lines,
    drops the columns that are not needed and renames the remaining ones.
    """
    clean = df[
        (df["InvoiceDate"].dt.year == 2024)
        & (~df["Invoice"].str.startswith("C"))
        & (df["Quantity"] > 0)
        & (df["Price"] > 0)
        & df["Description"].notna()
    ].copy()

    clean = clean.rename(
        columns={
            "InvoiceDate": "order_date",
            "Description": "product_name",
            "Quantity": "quantity",
            "Price": "unit_price",
            "Country": "country",
        }
    )
    clean["order_date"] = clean["order_date"].dt.normalize()
    columns = ["order_date", "country", "product_name", "quantity", "unit_price"]
    clean = clean[columns].drop_duplicates()

    extract = clean.sample(n=SAMPLE_ROWS, random_state=42)
    return extract.sort_values("order_date").reset_index(drop=True)


def main() -> None:
    workbook = download_source()
    df = load_workbook(workbook)
    df = shift_dates(df)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / "sales.csv"
    df.to_csv(output, index=False)

    extract = build_chapter1_extract(df)
    extract_path = OUTPUT_DIR / "sales_sample.csv"
    extract.to_csv(extract_path, index=False)
    print(f"{extract_path}: {len(extract):,} rows, {extract.shape[1]} columns")

    print(f"\n{output}: {len(df):,} rows, {df.shape[1]} columns")
    print(f"Period: {df['InvoiceDate'].min().date()} -> {df['InvoiceDate'].max().date()}")
    print("\nQuality issues left in place, on purpose (chapter 3 fixes them):")
    print(f"  duplicate rows        : {df.duplicated().sum():,}")
    print(f"  missing customer id   : {df['Customer ID'].isna().sum():,}")
    print(f"  missing description   : {df['Description'].isna().sum():,}")
    print(f"  negative quantities   : {(df['Quantity'] < 0).sum():,}")
    print(f"  zero or negative price: {(df['Price'] <= 0).sum():,}")
    print(f"  cancelled invoices    : {df['Invoice'].str.startswith('C').sum():,}")


if __name__ == "__main__":
    main()
