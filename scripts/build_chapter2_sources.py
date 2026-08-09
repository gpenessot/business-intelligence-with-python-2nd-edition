"""Derive every example file used by chapter 2 from the book's dataset.

Chapter 2 teaches how to read data from many formats. Rather than inventing a
throwaway file per format, every example file is a projection of the running
dataset presented in section 1.7.1: same columns, same products, same
countries. The reader recognises the data from one format to the next.

Run ``scripts/prepare_dataset.py`` first: this script reuses the workbook it
downloads and the ``sales.csv`` it writes.

Files produced under ``data/``:

    raw/sales_fr.csv                  French-style export: ; separator, , decimal
    raw/monthly_reports/*.xlsx        one workbook per month of 2025
    raw/orders.json                   order lines as JSON records
    raw/customers.json                customers with nested sub-objects
    raw/products.xml                  product catalogue
    raw/sales.db                      SQLite database, one ``orders`` table
    processed/sales.parquet           the whole dataset in Parquet

Usage:
    uv run python scripts/build_chapter2_sources.py
"""

from __future__ import annotations

import json
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
SALES_CSV = RAW_DIR / "sales.csv"

# 2024 is the only complete year of the dataset: it starts in November 2023 and
# stops on 5 December 2025. The French export and the JSON extracts cover a
# single month of it, the way a business team would actually send them.
EXPORT_YEAR = 2024
EXPORT_MONTH = 12

STRING_COLUMNS = ["Invoice", "StockCode", "Description", "Country"]

# Column names normalised for the database. SQL identifiers with a space in
# them make every query awkward, and a real warehouse table would not have any.
DB_COLUMNS = {
    "Invoice": "invoice",
    "StockCode": "stock_code",
    "Description": "description",
    "Quantity": "quantity",
    "InvoiceDate": "invoice_date",
    "Price": "price",
    "Customer ID": "customer_id",
    "Country": "country",
}


def load_sales() -> pd.DataFrame:
    """Load the running dataset written by prepare_dataset.py."""
    if not SALES_CSV.exists():
        raise FileNotFoundError(
            f"{SALES_CSV} is missing. Run scripts/prepare_dataset.py first."
        )
    df = pd.read_csv(
        SALES_CSV,
        parse_dates=["InvoiceDate"],
        dtype={column: "string" for column in STRING_COLUMNS},
    )
    print(f"{SALES_CSV}: {len(df):,} rows")
    return df


def write_french_csv(df: pd.DataFrame) -> None:
    """Write one month as a French-style CSV: ; separator and , decimal."""
    month = df[
        (df["InvoiceDate"].dt.year == EXPORT_YEAR)
        & (df["InvoiceDate"].dt.month == EXPORT_MONTH)
    ]
    output = RAW_DIR / "sales_fr.csv"
    month.to_csv(output, index=False, sep=";", decimal=",")
    print(f"{output}: {len(month):,} rows")


def write_annual_workbook(df: pd.DataFrame) -> None:
    """Write one year as a workbook with a sheet per quarter.

    The source workbook of the dataset could not be used directly: it still
    holds the original 2009-2011 dates, which contradict the period announced
    in section 1.7.1.
    """
    year = df[df["InvoiceDate"].dt.year == EXPORT_YEAR].copy()
    year["quarter"] = year["InvoiceDate"].dt.quarter

    output = RAW_DIR / f"annual_report_{EXPORT_YEAR}.xlsx"
    with pd.ExcelWriter(output) as writer:
        for quarter, group in year.groupby("quarter"):
            group.drop(columns="quarter").to_excel(
                writer, sheet_name=f"Q{quarter}", index=False
            )
    print(f"{output}: {output.stat().st_size / 1e6:.1f} MB, 4 sheets")


def write_monthly_workbooks(df: pd.DataFrame) -> None:
    """Split one year into a workbook per month, as regional teams would send."""
    folder = RAW_DIR / "monthly_reports"
    folder.mkdir(parents=True, exist_ok=True)
    year = df[df["InvoiceDate"].dt.year == EXPORT_YEAR]

    for month, group in year.groupby(year["InvoiceDate"].dt.month):
        output = folder / f"sales_{EXPORT_YEAR}_{month:02d}.xlsx"
        group.to_excel(output, index=False, sheet_name="Sales")
    print(f"{folder}: {len(list(folder.glob('*.xlsx')))} workbooks")


def write_orders_json(df: pd.DataFrame) -> None:
    """Write one month of order lines as a list of JSON records."""
    month = df[
        (df["InvoiceDate"].dt.year == EXPORT_YEAR)
        & (df["InvoiceDate"].dt.month == EXPORT_MONTH)
    ]
    output = RAW_DIR / "orders.json"
    month.to_json(output, orient="records", date_format="iso", indent=2)
    print(f"{output}: {len(month):,} records")


def write_customers_json(df: pd.DataFrame) -> None:
    """Write a customer export with nested sub-objects, for json_normalize().

    APIs rarely return flat records: the shipping address and the activity
    summary come back as nested objects. This file reproduces that shape.
    """
    known = df.dropna(subset=["Customer ID"]).copy()
    known["revenue"] = known["Quantity"] * known["Price"]

    summary = known.groupby("Customer ID").agg(
        country=("Country", "first"),
        first_order=("InvoiceDate", "min"),
        last_order=("InvoiceDate", "max"),
        orders=("Invoice", "nunique"),
        total_spent=("revenue", "sum"),
    )

    customers = [
        {
            "customer_id": str(int(float(customer_id))),
            "address": {"country": row.country},
            "activity": {
                "first_order": row.first_order.date().isoformat(),
                "last_order": row.last_order.date().isoformat(),
                "orders": int(row.orders),
                "total_spent": round(float(row.total_spent), 2),
            },
        }
        for customer_id, row in summary.iterrows()
    ]

    output = RAW_DIR / "customers.json"
    output.write_text(json.dumps(customers, indent=2), encoding="utf-8")
    print(f"{output}: {len(customers):,} customers")


def write_products_xml(df: pd.DataFrame) -> None:
    """Write the product catalogue as XML, the format of legacy exports."""
    catalogue = (
        df.dropna(subset=["Description"])
        .groupby("StockCode")
        .agg(description=("Description", "first"), price=("Price", "median"))
        .reset_index()
    )

    root = ET.Element("catalog")
    for row in catalogue.itertuples(index=False):
        product = ET.SubElement(root, "product")
        ET.SubElement(product, "stock_code").text = str(row.StockCode)
        ET.SubElement(product, "description").text = str(row.description)
        ET.SubElement(product, "price").text = f"{row.price:.2f}"

    output = RAW_DIR / "products.xml"
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
    print(f"{output}: {len(catalogue):,} products")


def write_parquet(df: pd.DataFrame) -> None:
    """Write the whole dataset to Parquet, to compare size and read time."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    output = PROCESSED_DIR / "sales.parquet"
    df.to_parquet(output, index=False)

    csv_mb = SALES_CSV.stat().st_size / 1e6
    parquet_mb = output.stat().st_size / 1e6
    print(
        f"{output}: {parquet_mb:.1f} MB against {csv_mb:.1f} MB for the CSV "
        f"({csv_mb / parquet_mb:.1f} times smaller)"
    )


def write_sqlite(df: pd.DataFrame) -> None:
    """Load the dataset into a single-file SQLite database.

    Column names are normalised here: a SQL identifier with a space in it makes
    every query awkward, and no real warehouse table would carry one.
    """
    output = RAW_DIR / "sales.db"
    output.unlink(missing_ok=True)

    table = df.rename(columns=DB_COLUMNS)
    with sqlite3.connect(output) as connection:
        table.to_sql("orders", connection, index=False)
        connection.execute("CREATE INDEX idx_orders_date ON orders(invoice_date)")
    print(f"{output}: {output.stat().st_size / 1e6:.1f} MB")


def main() -> None:
    df = load_sales()
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    write_french_csv(df)
    write_annual_workbook(df)
    write_monthly_workbooks(df)
    write_orders_json(df)
    write_customers_json(df)
    write_products_xml(df)
    write_parquet(df)
    write_sqlite(df)


if __name__ == "__main__":
    main()
