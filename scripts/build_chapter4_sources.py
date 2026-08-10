"""Derive the companion files used by chapter 4 from the book's dataset.

Chapter 4 needs three files the raw sales extract cannot provide, because a
sales history records what was bought, never what was merely looked at:

    data/raw/monthly_traffic.csv   visitors per month
    data/raw/marketing_spend.csv   acquisition spend per month and channel
    data/raw/web_events.csv        browsing events of one month

These three are **simulated**, and the book says so. They are not invented
freely either: every figure is anchored on the running dataset. The number of
visitors is deduced from the real number of buyers of each month, the spend
from the real number of new customers, and the browsing events end on the
real customer identifiers who really ordered in November 2025, on the day
they really ordered.

Two consistency rules the files must respect, and that the chapter relies on:

    1. The visitor count of November 2025 in monthly_traffic.csv is exactly
       the number of distinct visitors in web_events.csv. The monthly
       conversion rate of section 4.3.1.2 and the funnel of section 4.3.6
       therefore agree on that month.
    2. The funnel is not strictly nested. A small share of visitors skips a
       step, the way a visitor arriving from an ad lands directly on a
       product page. Without it, an open funnel and a closed funnel would
       give identical rates, and the caveat of section 4.3.6 would be empty.

The fourth file of the chapter, marketing_ab.csv, is NOT produced here: it is
a genuine public A/B test, downloaded by scripts/download_marketing_ab.py.

Run scripts/prepare_dataset.py first.

Usage:
    uv run python scripts/build_chapter4_sources.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RAW_DIR = Path("data/raw")
SALES_CSV = RAW_DIR / "sales.csv"

SEED = 42

# Month whose browsing events are simulated: the last complete month of the
# dataset, which stops on 5 December 2025.
EVENTS_MONTH = pd.Period("2025-11", freq="M")

# Visitors are deduced from buyers: visitors = buyers / conversion rate.
# The rate itself moves from month to month, the way a real one does.
CONVERSION_MIN, CONVERSION_MAX = 0.022, 0.032
EVENTS_MONTH_CONVERSION = 0.026

# Acquisition cost per new customer, drifting upward over the two years:
# paid channels get more expensive, which is the trend worth commenting on.
CAC_START, CAC_END = 170.0, 230.0
CAC_NOISE = 0.15

CHANNELS = {
    "Paid search": 0.42,
    "Social": 0.27,
    "Email": 0.12,
    "Affiliates": 0.19,
}

FUNNEL_STEPS = ["visit", "view_product", "add_to_cart", "purchase"]

# Share of visitors whose furthest step is each of the four. Tuned so the
# overall conversion lands on EVENTS_MONTH_CONVERSION.
STEP_SHARES = [0.30, 0.57, 0.101, 0.029]

# Probability that a visitor skips an intermediate step of their own path.
SKIP_RATE = 0.05


def load_sales() -> pd.DataFrame:
    """Load the running dataset, restricted to actual sales.

    Cancellations and accounting adjustments are dropped: a returned order
    was still a conversion, but it would distort every count below.
    """
    if not SALES_CSV.exists():
        raise FileNotFoundError(f"{SALES_CSV} is missing. Run scripts/prepare_dataset.py first.")
    df = pd.read_csv(
        SALES_CSV,
        parse_dates=["InvoiceDate"],
        dtype={"Invoice": "string", "StockCode": "string", "Customer ID": "string"},
    ).rename(columns=lambda c: c.lower().replace(" ", "_")).rename(
        columns={"stockcode": "stock_code", "invoicedate": "invoice_date"}
    )
    df = df.drop_duplicates(keep="first")
    return df[(df["quantity"] > 0) & (df["price"] > 0)]


def build_monthly_traffic(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Deduce a monthly visitor count from the real number of buyers."""
    buyers = (
        df.dropna(subset=["customer_id"])
        .assign(month=lambda d: d["invoice_date"].dt.to_period("M"))
        .groupby("month")["customer_id"].nunique()
    )

    rates = pd.Series(
        rng.uniform(CONVERSION_MIN, CONVERSION_MAX, size=len(buyers)), index=buyers.index
    )
    # Pin the events month so the funnel and the monthly rate agree on it.
    rates.loc[EVENTS_MONTH] = EVENTS_MONTH_CONVERSION

    visitors = (buyers / rates).round(-1).astype(int)
    return pd.DataFrame({"month": visitors.index.astype(str), "visitors": visitors.to_numpy()})


def build_marketing_spend(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Spread an acquisition budget over channels, month by month.

    The budget of a month is the number of customers actually acquired that
    month times a target cost per customer, which drifts upward.
    """
    first_order = df.dropna(subset=["customer_id"]).groupby("customer_id")["invoice_date"].min()
    new_customers = first_order.dt.to_period("M").value_counts().sort_index()

    target = np.linspace(CAC_START, CAC_END, len(new_customers))
    noise = rng.uniform(1 - CAC_NOISE, 1 + CAC_NOISE, size=len(new_customers))
    budget = new_customers.to_numpy() * target * noise

    rows = []
    for month, total in zip(new_customers.index, budget):
        # Channel mix wobbles a little every month, then is renormalized.
        weights = np.array(list(CHANNELS.values())) * rng.uniform(0.85, 1.15, size=len(CHANNELS))
        weights /= weights.sum()
        for channel, weight in zip(CHANNELS, weights):
            rows.append({"month": str(month), "channel": channel, "spend": round(total * weight, 2)})
    return pd.DataFrame(rows)


def build_web_events(df: pd.DataFrame, visitors: int, rng: np.random.Generator) -> pd.DataFrame:
    """Simulate one month of browsing events, ending on the real buyers.

    Buyers keep their real customer_id and their real order timestamp; the
    steps that precede the purchase are placed shortly before it. Visitors
    who never buy get a synthetic identifier.
    """
    month_sales = df[df["invoice_date"].dt.to_period("M") == EVENTS_MONTH]
    real_buyers = (
        month_sales.dropna(subset=["customer_id"])
        .groupby("customer_id")["invoice_date"].min()
    )
    n_buyers = len(real_buyers)

    # Furthest step reached by each visitor. Buyers are known, the rest is drawn.
    n_others = visitors - n_buyers
    shares = np.array(STEP_SHARES[:3], dtype=float)
    shares /= shares.sum()
    furthest = rng.choice([0, 1, 2], size=n_others, p=shares)

    user_ids = np.concatenate([
        real_buyers.index.to_numpy().astype(str),
        np.array([f"anon_{i:07d}" for i in range(n_others)]),
    ])
    furthest = np.concatenate([np.full(n_buyers, 3), furthest])

    # Timestamps: real order time for buyers, uniform in the month otherwise.
    month_start = EVENTS_MONTH.start_time
    month_span = (EVENTS_MONTH.end_time - month_start).total_seconds()
    last_ts = np.concatenate([
        real_buyers.to_numpy(),
        month_start.to_numpy() + (rng.uniform(0, month_span, n_others) * 1e9).astype("timedelta64[ns]"),
    ])

    records = []
    for user, far, end_ts in zip(user_ids, furthest, last_ts):
        # Walk back from the furthest step, a few minutes at a time.
        offsets = np.cumsum(rng.integers(2, 45, size=far + 1))
        for rank in range(far + 1):
            if rank < far and rng.random() < SKIP_RATE:
                continue  # visitor skipped this step
            ts = pd.Timestamp(end_ts) - pd.Timedelta(minutes=int(offsets[far - rank] - offsets[0]))
            records.append((user, FUNNEL_STEPS[rank], ts))

    events = pd.DataFrame(records, columns=["user_id", "event", "ts"])
    return events.sort_values("ts").reset_index(drop=True)


def main() -> None:
    rng = np.random.default_rng(SEED)
    df = load_sales()
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    traffic = build_monthly_traffic(df, rng)
    traffic.to_csv(RAW_DIR / "monthly_traffic.csv", index=False)
    print(f"{RAW_DIR / 'monthly_traffic.csv'}: {len(traffic)} months, "
          f"{traffic['visitors'].sum():,} visitors")

    spend = build_marketing_spend(df, rng)
    spend.to_csv(RAW_DIR / "marketing_spend.csv", index=False)
    print(f"{RAW_DIR / 'marketing_spend.csv'}: {len(spend)} rows, "
          f"{spend['spend'].sum():,.0f} GBP over {spend['month'].nunique()} months")

    visitors = int(traffic.loc[traffic["month"] == str(EVENTS_MONTH), "visitors"].iloc[0])
    events = build_web_events(df, visitors, rng)
    events.to_csv(RAW_DIR / "web_events.csv", index=False)
    print(f"{RAW_DIR / 'web_events.csv'}: {len(events):,} events, "
          f"{events['user_id'].nunique():,} visitors in {EVENTS_MONTH}")
    print(events.groupby("event")["user_id"].nunique().reindex(FUNNEL_STEPS).to_string())


if __name__ == "__main__":
    main()
