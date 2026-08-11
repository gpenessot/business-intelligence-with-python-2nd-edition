"""Generate one day of new sales, the way a source system would deliver them.

The book's dataset stops on 5 December 2025. A real warehouse is never
finished: it receives a new batch every night. This script produces those
batches so chapter 5 can teach incremental loading on something that moves.

Each file has exactly the eight columns of ``data/raw/sales.csv``: it is the
same source, one day later, not a different dataset. Products, customers,
countries and price levels are drawn from the real history, so the figures
stay in the same range as the rest of the book.

Three things are deliberately planted in every batch, because a warehouse
that only ever receives well-behaved rows teaches nothing:

    late rows      a few lines dated one to three days earlier, the way a
                   shop that syncs late or a correction posted after the fact
    cancellations  invoices prefixed with C and negative quantities
    country moves  now and then, a returning customer appears with a new
                   country, which is what Slowly Changing Dimensions are for

The generator is **deterministic for a given date**: running it twice writes
byte-identical files. Section 5.10.5 relies on that to show that replaying a
day changes nothing in the warehouse.

Run ``scripts/prepare_dataset.py`` first.

Usage:
    uv run python scripts/generate_daily_delta.py                  # next day
    uv run python scripts/generate_daily_delta.py 2025-12-06
    uv run python scripts/generate_daily_delta.py 2025-12-06 --days 5
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

RAW_DIR = Path("data/raw")
INCOMING_DIR = Path("data/incoming")
SALES_CSV = RAW_DIR / "sales.csv"

# The history ends here; the first generated day is the one after.
HISTORY_LAST_DAY = date(2025, 12, 5)

# Lines per day, before the weekday effect. The real history averages
# about 1 400 lines per selling day.
LINES_PER_DAY = 1_400
WEEKDAY_FACTOR = {0: 1.05, 1: 1.10, 2: 1.05, 3: 1.15, 4: 0.95, 5: 0.55, 6: 0.75}

# The real history carries a median of 16 lines per invoice: this is a
# wholesaler, not a corner shop.
LINES_PER_INVOICE = (1, 33)

SHARE_LATE_ROWS = 0.03      # dated one to three days before the batch
SHARE_CANCELLATIONS = 0.02  # invoices prefixed with C
SHARE_NEW_CUSTOMERS = 0.04  # identifiers never seen before
SHARE_GUEST_LINES = 0.22    # no customer id at all, as in the history
SHARE_COUNTRY_MOVE = 0.02   # returning customer, new country
SHARE_NEW_PRODUCTS = 0.01   # references the catalogue has never sold

# New identifiers continue the ranges of the history rather than starting a
# visibly separate series: invoice numbers stop around 581 000, customer
# identifiers around 18 300. Each day gets its own slice so two batches can
# never mint the same invoice number.
FIRST_NEW_CUSTOMER_ID = 90_000
FIRST_NEW_INVOICE = 600_000
IDS_RESERVED_PER_DAY = 200

COLUMNS = ["Invoice", "StockCode", "Description", "Quantity",
           "InvoiceDate", "Price", "Customer ID", "Country"]


def load_reference() -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    """Extract the product catalogue, the customer base and country weights."""
    if not SALES_CSV.exists():
        raise FileNotFoundError(f"{SALES_CSV} is missing. Run scripts/prepare_dataset.py first.")

    df = pd.read_csv(
        SALES_CSV,
        parse_dates=["InvoiceDate"],
        dtype={"Invoice": "string", "StockCode": "string", "Description": "string",
               "Country": "string"},
    )
    sold = df[(df["Quantity"] > 0) & (df["Price"] > 0) & df["Description"].notna()]

    products = (
        sold.groupby("StockCode")
        .agg(Description=("Description", "first"),
             price=("Price", "median"),
             weight=("Quantity", "size"))
        .reset_index()
    )

    customers = (
        sold.dropna(subset=["Customer ID"])
        .groupby("Customer ID")
        .agg(Country=("Country", "last"), weight=("Invoice", "size"))
        .reset_index()
    )
    customers["Customer ID"] = customers["Customer ID"].astype("int64")

    countries = sold["Country"].value_counts(normalize=True)
    return products, customers, countries


def generate_day(day: date, products: pd.DataFrame, customers: pd.DataFrame,
                 countries: pd.Series) -> pd.DataFrame:
    """Build one day's batch of order lines."""
    # Seed derived from the date: the same day always yields the same file.
    rng = np.random.default_rng(int(day.strftime("%Y%m%d")))

    n_lines = int(LINES_PER_DAY * WEEKDAY_FACTOR[day.weekday()] * rng.uniform(0.85, 1.15))

    product_p = products["weight"] / products["weight"].sum()
    customer_p = customers["weight"] / customers["weight"].sum()

    rows: list[dict] = []
    day_index = (day - HISTORY_LAST_DAY).days
    invoice_seq = FIRST_NEW_INVOICE + day_index * IDS_RESERVED_PER_DAY
    new_customer_seq = FIRST_NEW_CUSTOMER_ID + day_index * IDS_RESERVED_PER_DAY

    while len(rows) < n_lines:
        invoice_seq += 1
        n_items = int(rng.integers(*LINES_PER_INVOICE))
        cancelled = rng.random() < SHARE_CANCELLATIONS
        invoice = f"C{invoice_seq}" if cancelled else str(invoice_seq)

        # Who is buying: a guest, a brand-new customer, or a returning one.
        draw = rng.random()
        if draw < SHARE_GUEST_LINES:
            customer_id, country = pd.NA, countries.index[rng.choice(len(countries), p=countries.to_numpy())]
        elif draw < SHARE_GUEST_LINES + SHARE_NEW_CUSTOMERS:
            new_customer_seq += 1
            customer_id = new_customer_seq
            country = countries.index[rng.choice(len(countries), p=countries.to_numpy())]
        else:
            idx = rng.choice(len(customers), p=customer_p.to_numpy())
            customer_id = int(customers.at[idx, "Customer ID"])
            country = customers.at[idx, "Country"]
            if rng.random() < SHARE_COUNTRY_MOVE:
                # The customer moved: same identifier, different country.
                country = countries.index[rng.choice(len(countries), p=countries.to_numpy())]

        # Most lines belong to the batch's day; a few arrive late.
        line_day = day
        if rng.random() < SHARE_LATE_ROWS:
            line_day = day - timedelta(days=int(rng.integers(1, 4)))
        timestamp = pd.Timestamp(line_day) + pd.Timedelta(
            hours=int(rng.integers(7, 20)), minutes=int(rng.integers(0, 60))
        )

        picks = rng.choice(len(products), size=n_items, p=product_p.to_numpy(), replace=False)
        for pick in picks:
            quantity = int(rng.choice([1, 2, 3, 4, 6, 8, 12, 24, 48],
                                      p=[.20, .14, .10, .10, .12, .09, .15, .07, .03]))
            price = round(float(products.at[pick, "price"]) * rng.uniform(0.95, 1.05), 2)
            stock_code = products.at[pick, "StockCode"]
            description = products.at[pick, "Description"]

            if rng.random() < SHARE_NEW_PRODUCTS:
                # A reference the catalogue has never sold: the product
                # dimension has to grow, not just the fact table.
                stock_code = f"N{day_index:03d}{rng.integers(100, 999)}"
                description = f"NEW SEASON {description}"

            rows.append({
                "Invoice": invoice,
                "StockCode": stock_code,
                "Description": description,
                "Quantity": -quantity if cancelled else quantity,
                "InvoiceDate": timestamp,
                "Price": price,
                "Customer ID": customer_id,
                "Country": country,
            })

    return pd.DataFrame(rows, columns=COLUMNS).sort_values("InvoiceDate").reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("start", nargs="?", default=None,
                        help="First day to generate, YYYY-MM-DD (default: the day after the history)")
    parser.add_argument("--days", type=int, default=1, help="Number of consecutive days")
    args = parser.parse_args()

    start = date.fromisoformat(args.start) if args.start else HISTORY_LAST_DAY + timedelta(days=1)

    products, customers, countries = load_reference()
    INCOMING_DIR.mkdir(parents=True, exist_ok=True)

    for offset in range(args.days):
        day = start + timedelta(days=offset)
        batch = generate_day(day, products, customers, countries)
        path = INCOMING_DIR / f"sales_{day:%Y-%m-%d}.csv"
        batch.to_csv(path, index=False)
        late = (batch["InvoiceDate"].dt.date < day).sum()
        cancels = batch["Invoice"].str.startswith("C").sum()
        print(f"{path}: {len(batch):,} lines, {batch['Invoice'].nunique()} invoices, "
              f"{late} late, {cancels} cancelled")


if __name__ == "__main__":
    main()
