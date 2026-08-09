"""Derive the companion files used by chapter 3 from the book's dataset.

Chapter 3 needs two files that the raw dataset does not provide:

    data/raw/product_catalog.csv   purchase cost and supplier per product
    data/raw/budget_2025.xlsx      revenue target per category and month

Both are computed from the running dataset itself, so the figures stay
consistent with everything else in the book. Neither is invented from
scratch, and both keep the defects a real file would have: the catalogue
does not cover every product sold, and the budget is sometimes met,
sometimes missed.

The product categories used by the budget come from the rule-based
classification that chapter 3 builds as a guided example. They are
reproduced here so the file can be regenerated without running the chapter.

Run ``scripts/prepare_dataset.py`` first.

Usage:
    uv run python scripts/build_chapter3_sources.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RAW_DIR = Path("data/raw")
SALES_CSV = RAW_DIR / "sales.csv"

SEED = 42

# Share of products deliberately left out of the catalogue. A referential
# that covers every product sold does not exist in real life, and section
# 3.3.3.3 relies on those gaps to demonstrate the indicator parameter.
MISSING_PRODUCT_SHARE = 0.05

SUPPLIERS = [
    "Nordic Home",
    "PaperWorks",
    "Kitchen Classics",
    "Garden & Co",
    "Vintage Living",
]

# Ordered rules: the first pattern that matches wins. Same list as the
# guided example of chapter 3.
CATEGORY_RULES: list[tuple[str, str]] = [
    ("Shipping & fees", r"POSTAGE|CARRIAGE|^MANUAL$|AMAZON FEE|BANK CHARGES|^ADJUST"),
    ("Christmas", r"CHRISTMAS|XMAS|ADVENT|SANTA|REINDEER|SNOWMAN|NOEL"),
    ("Bags", r"\bBAGS?\b|HANDBAG|RUCKSAK|SHOPPER|SATCHEL"),
    ("Candles & lights", r"T-?LIGHT|CANDLE|LANTERN|\bLIGHT|LAMP"),
    (
        "Kitchen & tableware",
        r"CAKE|BAKING|COOK|KITCHEN|APRON|RECIPE|JAM |CUTLERY|BOWL|PLATE|TRAY|EGG"
        r"|OVEN|PANTRY|MOULD|SPICE|POPCORN|PEG|\bMUGS?\b|TEA ?(?:SET|CUP|POT)|SAUCER"
        r"|GLASS|BOTTLE|JUG|CUPS?\b|FLASK|DOILY|DOILIES|NAPKIN",
    ),
    (
        "Stationery & crafts",
        r"CARD|NOTEBOOK|PENCIL|\bPENS?\b|PAPER|WRAP|ENVELOPE|STICKER|CHALK|NOTE"
        r"|CRAYON|TISSUE|MEMO|BLACK ?BOARD|RIBBON|FELTCRAFT|SEWING|KNIT|CRAFT"
        r"|BEAD|WOOL|FABRIC|EMBROID|CROCHET",
    ),
    ("Storage", r"\bBOX(?:ES)?\b|\bTINS?\b|STORAGE|\bJARS?\b|BASKET|CRATE|DRAWER|CABINET|RACK|HOLDER"),
    (
        "Toys & jewellery",
        r"PLAYHOUSE|\bTOYS?\b|GAME|PUZZLE|DOLL|TEDDY|SPACEBOY|BUNTING|SKITTLE"
        r"|SOLDIER|BLOCK WORD|GLIDER|SPINNING TOP|SKIPPING|BINGO|LADDERS"
        r"|COLOURING|MICE|NECKLACE|BRACELET|EARRING|\bRINGS?\b|BROOCH|PENDANT|JEWEL",
    ),
    ("Garden & outdoor", r"GARDEN|PLANT|FLOWER ?POT|WATERING|BIRD|PARASOL|DOORMAT"),
    (
        "Home decoration",
        r"HEART|HANGING|DECORATION|\bSIGNS?\b|FRAME|MIRROR|CUSHION|CLOCK|VASE"
        r"|ORNAMENT|WALL|HOOK|STAR|FAN|WARMER|KEY FOB",
    ),
]

MONTH_LABELS = {
    1: "Jan", 2: "Fév", 3: "Mar", 4: "Avr", 5: "Mai", 6: "Juin",
    7: "Juil", 8: "Août", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Déc",
}


def load_sales() -> pd.DataFrame:
    """Load the running dataset written by prepare_dataset.py."""
    if not SALES_CSV.exists():
        raise FileNotFoundError(f"{SALES_CSV} is missing. Run scripts/prepare_dataset.py first.")
    return pd.read_csv(
        SALES_CSV,
        parse_dates=["InvoiceDate"],
        dtype={c: "string" for c in ["Invoice", "StockCode", "Description", "Country"]},
    )


def categorize(descriptions: pd.Series) -> pd.Series:
    """Assign a product category from the description, first rule wins."""
    upper = descriptions.str.upper()
    category = pd.Series("Other", index=descriptions.index, dtype="object")
    unassigned = pd.Series(True, index=descriptions.index)

    for label, pattern in CATEGORY_RULES:
        match = unassigned & upper.str.contains(pattern, regex=True, na=False)
        category[match] = label
        unassigned &= ~match

    return category


def build_product_catalog(df: pd.DataFrame) -> pd.DataFrame:
    """Build a purchasing referential: cost and supplier per product.

    The purchase cost is derived from the median selling price of each
    product, with a gross margin drawn between 25% and 55%. A share of the
    products is left out entirely, the way a real referential lags behind
    the catalogue actually sold.
    """
    rng = np.random.default_rng(SEED)

    valid = df[(df["Price"] > 0) & df["Description"].notna()]
    catalog = (
        valid.groupby("StockCode")
        .agg(median_price=("Price", "median"))
        .reset_index()
        .rename(columns={"StockCode": "product_id"})
    )

    margin = rng.uniform(0.25, 0.55, size=len(catalog))
    catalog["purchase_cost"] = (catalog["median_price"] * (1 - margin)).round(2)
    catalog["supplier"] = rng.choice(SUPPLIERS, size=len(catalog))

    keep = rng.random(len(catalog)) > MISSING_PRODUCT_SHARE
    catalog = catalog.loc[keep, ["product_id", "purchase_cost", "supplier"]]
    return catalog.sort_values("product_id").reset_index(drop=True)


def build_budget(df: pd.DataFrame) -> pd.DataFrame:
    """Build the 2025 revenue target per category and month, in wide format.

    The target is the actual 2025 revenue moved by a random amount between
    -12% and +12%, so that the achievement rate lands above target on some
    months and below on others. December is deliberately built on a full
    month, although the dataset stops on 5 December: a budget is set before
    the year starts, it does not know the data will be truncated.
    """
    rng = np.random.default_rng(SEED)

    year = df[(df["InvoiceDate"].dt.year == 2025) & (df["Quantity"] > 0) & (df["Price"] > 0)].copy()
    year["category"] = categorize(year["Description"].fillna(""))
    year["revenue"] = year["Quantity"] * year["Price"]
    year["month"] = year["InvoiceDate"].dt.month

    actual = year.pivot_table(
        index="category", columns="month", values="revenue", aggfunc="sum", fill_value=0
    )

    # December stops on the 5th: extrapolate it to a full month before
    # turning it into a target, otherwise the budget would be absurdly low.
    december_days = year.loc[year["month"] == 12, "InvoiceDate"].dt.day.max()
    if december_days and december_days < 28:
        actual[12] = actual[12] * 31 / december_days

    noise = rng.uniform(0.88, 1.12, size=actual.shape)
    budget = (actual.to_numpy() * noise / 1000).round(0) * 1000

    out = pd.DataFrame(budget, index=actual.index, columns=actual.columns)
    out = out.rename(columns=MONTH_LABELS).reset_index()
    out = out.rename(columns={"category": "product_category"})
    return out[out["product_category"] != "Shipping & fees"]


def main() -> None:
    df = load_sales()
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    catalog = build_product_catalog(df)
    catalog_path = RAW_DIR / "product_catalog.csv"
    catalog.to_csv(catalog_path, index=False)
    sold = df["StockCode"].nunique()
    print(f"{catalog_path}: {len(catalog):,} products out of {sold:,} sold")

    budget = build_budget(df)
    budget_path = RAW_DIR / "budget_2025.xlsx"
    budget.to_excel(budget_path, index=False)
    print(f"{budget_path}: {budget.shape[0]} categories x {budget.shape[1] - 1} months")


if __name__ == "__main__":
    main()
