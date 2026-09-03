"""
Product / SKU master data generator.

Tables produced
───────────────
dim_products   – full SKU catalogue with department, price, margin, brand
dim_store_sku  – store × SKU assortment (which SKUs are stocked at each store)
"""

import numpy as np
import pandas as pd
from faker import Faker

from config import DEPARTMENTS, NUM_SKUS, OUTPUT_DIR, RANDOM_SEED
from generators.base import rng, weighted_choice, save_csv, save_parquet

fake = Faker("en_US")
Faker.seed(RANDOM_SEED)

# Proportion of SKUs per department (sums to 1)
DEPT_WEIGHTS = [
    0.08, 0.05, 0.07, 0.08,  # Fresh, Bakery, Dairy, Meat
    0.06, 0.07, 0.09,        # Frozen, Beverages, Snacks
    0.10, 0.08, 0.04,        # H&B, Household, Baby
    0.04, 0.09, 0.05,        # Pet, Clothing, Electronics
    0.05, 0.05,              # Stationery, Seasonal
]
assert len(DEPT_WEIGHTS) == len(DEPARTMENTS)

BRANDS = [fake.company() for _ in range(400)]
BRAND_WEIGHTS = np.ones(400)
BRAND_WEIGHTS[:20] *= 15   # top-20 power brands get higher representation


def generate_products() -> pd.DataFrame:
    print(f"Generating dim_products ({NUM_SKUS:,} SKUs) …")
    n = NUM_SKUS
    departments = weighted_choice(DEPARTMENTS, DEPT_WEIGHTS, n)
    brands      = weighted_choice(BRANDS, BRAND_WEIGHTS.tolist(), n)

    base_prices = np.where(
        np.isin(departments, ["Electronics"]),
        rng.uniform(19.99, 899.99, n),
        np.where(
            np.isin(departments, ["Clothing & Apparel"]),
            rng.uniform(4.99, 149.99, n),
            rng.uniform(0.49, 29.99, n),
        ),
    )
    margin_pct = np.where(
        np.isin(departments, ["Fresh Produce", "Bakery", "Dairy & Eggs", "Meat & Seafood"]),
        rng.uniform(0.08, 0.22, n),
        rng.uniform(0.15, 0.55, n),
    )
    cost_price = np.round(base_prices * (1 - margin_pct), 2)

    # Velocity tier drives how often an SKU appears in baskets
    velocity_tiers = weighted_choice(["A", "B", "C", "D"],
                                     [0.10, 0.25, 0.40, 0.25], n)

    df = pd.DataFrame({
        "sku_id":           [f"SKU{i+1:07d}" for i in range(n)],
        "description":      [f"{brands[i]} {departments[i]} Item {i+1}" for i in range(n)],
        "department":       departments,
        "brand":            brands,
        "sell_price_usd":   np.round(base_prices, 2),
        "cost_price_usd":   cost_price,
        "margin_pct":       np.round(margin_pct * 100, 2),
        "unit_of_measure":  weighted_choice(["EA", "KG", "LB", "PKT", "L"], [0.5, 0.1, 0.1, 0.2, 0.1], n),
        "velocity_tier":    velocity_tiers,
        "is_private_label": rng.random(n) < 0.22,
        "is_perishable":    np.isin(departments, ["Fresh Produce","Bakery","Dairy & Eggs","Meat & Seafood"]),
        "sku_active":       rng.random(n) < 0.92,
    })

    save_parquet(df, f"{OUTPUT_DIR}/products/dim_products.parquet")
    save_csv(df,     f"{OUTPUT_DIR}/products/dim_products.csv")
    return df


def generate_store_sku(stores_df: pd.DataFrame, products_df: pd.DataFrame) -> pd.DataFrame:
    """
    Sparse assortment matrix – not every store carries every SKU.
    Built vectorially to avoid Python-level loops over millions of pairs.
    """
    print("Generating dim_store_sku assortment matrix …")
    store_ids = stores_df["store_id"].values
    sku_ids   = products_df["sku_id"].values
    vel_tier  = products_df["velocity_tier"].values

    # Inclusion probability by velocity tier
    prob_map = {"A": 1.00, "B": 0.90, "C": 0.70, "D": 0.50}
    incl_prob = np.array([prob_map[v] for v in vel_tier], dtype=float)

    parts = []
    for sid in store_ids:
        mask = rng.random(len(sku_ids)) < incl_prob
        parts.append(pd.DataFrame({
            "store_id": sid,
            "sku_id":   sku_ids[mask],
            "is_stocked": True,
        }))

    df = pd.concat(parts, ignore_index=True)
    save_parquet(df, f"{OUTPUT_DIR}/products/dim_store_sku.parquet")
    print(f"  (CSV skipped for store_sku – {len(df):,} rows)")
    return df
