"""
Promotional calendar & incremental-sales analytics generator.

Tables produced
───────────────
dim_promotions          – promotion master (type, discount, dates)
fact_promo_calendar     – the 16-billion-row promotional calendar (scaled)
fact_promo_uplift       – true incremental sales analysis per promotion event
fact_ab_tests           – champion/challenger A/B test results
"""

import numpy as np
import pandas as pd
from tqdm import tqdm

from config import (PROMO_TYPES, TARGET_PROMO_ROWS, OUTPUT_DIR,
                    START_DATE, END_DATE, DEPARTMENTS, RANDOM_SEED)
from generators.base import rng, weighted_choice, date_range_array, save_csv, save_parquet


PROMO_TYPE_DISCOUNT_RANGE = {
    "BOGO":                      (0.50, 0.50),
    "Percentage Off":            (0.05, 0.40),
    "Fixed Price":               (0.10, 0.35),
    "Multi-Buy":                 (0.15, 0.30),
    "Loyalty Points Multiplier": (0.00, 0.00),
    "Clearance":                 (0.30, 0.70),
    "New Product Launch":        (0.00, 0.15),
    "Seasonal Event":            (0.10, 0.50),
    "Basket Discount":           (0.05, 0.20),
    "Digital Coupon":            (0.10, 0.30),
}


def generate_promotions(n_promos: int = 25_000) -> pd.DataFrame:
    print(f"Generating dim_promotions ({n_promos:,} promos) …")
    promo_types = weighted_choice(
        PROMO_TYPES,
        [0.10, 0.22, 0.12, 0.10, 0.08, 0.06, 0.08, 0.10, 0.07, 0.07],
        n_promos,
    )
    start_dates = date_range_array(START_DATE, END_DATE, n_promos)
    durations   = rng.integers(1, 28, n_promos).astype("timedelta64[D]")
    end_dates   = start_dates + durations

    discounts = np.array([
        rng.uniform(*PROMO_TYPE_DISCOUNT_RANGE[pt])
        for pt in promo_types
    ])

    df = pd.DataFrame({
        "promo_id":          [f"PROMO{i+1:07d}" for i in range(n_promos)],
        "promo_type":        promo_types,
        "department":        weighted_choice(DEPARTMENTS,
                                             [1/len(DEPARTMENTS)] * len(DEPARTMENTS),
                                             n_promos),
        "promo_start_date":  start_dates,
        "promo_end_date":    end_dates,
        "discount_rate":     np.round(discounts, 3),
        "media_support":     weighted_choice(["TV", "Digital", "Catalogue",
                                              "In-Store Only", "Email", "Multi-Channel"],
                                             [0.10,0.25,0.20,0.20,0.15,0.10], n_promos),
        "is_national":       rng.random(n_promos) < 0.55,
        "budget_usd":        rng.integers(5_000, 2_000_000, n_promos),
    })

    save_parquet(df, f"{OUTPUT_DIR}/promotions/dim_promotions.parquet")
    save_csv(df,     f"{OUTPUT_DIR}/promotions/dim_promotions.csv")
    return df


def generate_promo_calendar(stores_df: pd.DataFrame,
                             products_df: pd.DataFrame,
                             promos_df: pd.DataFrame) -> pd.DataFrame:
    """
    Promotional calendar: one row per store × SKU × promo × day.
    Scaled version of the 16-billion-row MPP table.
    """
    print(f"Generating fact_promo_calendar (~{TARGET_PROMO_ROWS:,} rows target) …")

    store_ids = stores_df["store_id"].values
    sku_ids   = products_df["sku_id"].values
    promo_ids = promos_df["promo_id"].values
    promo_types= promos_df["promo_type"].values
    discounts = promos_df["discount_rate"].values

    n_target  = TARGET_PROMO_ROWS
    chunk_sz  = 500_000

    rows_written = 0
    parts = []

    with tqdm(total=n_target, desc="  promo calendar rows") as pbar:
        while rows_written < n_target:
            n = min(chunk_sz, n_target - rows_written)
            promo_idx = rng.integers(0, len(promo_ids), n)
            df_chunk = pd.DataFrame({
                "promo_calendar_id": np.arange(rows_written + 1, rows_written + n + 1),
                "promo_id":          promo_ids[promo_idx],
                "store_id":          rng.choice(store_ids, n),
                "sku_id":            rng.choice(sku_ids, n),
                "promo_type":        promo_types[promo_idx],
                "calendar_date":     date_range_array(START_DATE, END_DATE, n),
                "discount_rate":     discounts[promo_idx],
                "is_featured":       rng.random(n) < 0.30,
                "is_end_cap":        rng.random(n) < 0.20,
            })
            parts.append(df_chunk)
            rows_written += n
            pbar.update(n)

    df = pd.concat(parts, ignore_index=True)
    save_parquet(df, f"{OUTPUT_DIR}/promotions/fact_promo_calendar.parquet")
    # Sample CSV
    save_csv(df.sample(min(200_000, len(df)), random_state=42),
             f"{OUTPUT_DIR}/promotions/fact_promo_calendar_sample.csv")
    return df


def generate_promo_uplift(promos_df: pd.DataFrame,
                           stores_df: pd.DataFrame) -> pd.DataFrame:
    """
    True incremental sales analysis.
    Captures the project insight: consumers often bought the same
    affinities regardless of discount → true uplift can be near zero.
    """
    print("Generating fact_promo_uplift …")

    n = len(promos_df) * 3   # 3 store samples per promo
    promo_idx = rng.integers(0, len(promos_df), n)
    store_idx = rng.integers(0, len(stores_df), n)

    base_sales      = rng.uniform(5_000, 250_000, n)
    promo_sales     = base_sales * rng.uniform(0.85, 2.20, n)
    # True incremental: subtract cannibalisation and pantry loading
    cannibalisation = base_sales * rng.uniform(0.00, 0.25, n)
    pantry_loading  = base_sales * rng.uniform(0.00, 0.15, n)
    true_incr_sales = np.maximum(0, promo_sales - base_sales - cannibalisation - pantry_loading)
    promo_cost      = base_sales * promos_df["discount_rate"].values[promo_idx] * rng.uniform(0.5, 1.0, n)
    roi             = np.where(promo_cost > 0, (true_incr_sales * 0.25) / promo_cost, 0)

    df = pd.DataFrame({
        "uplift_id":             [f"UPL{i+1:08d}" for i in range(n)],
        "promo_id":              promos_df["promo_id"].values[promo_idx],
        "promo_type":            promos_df["promo_type"].values[promo_idx],
        "store_id":              stores_df["store_id"].values[store_idx],
        "department":            promos_df["department"].values[promo_idx],
        "baseline_sales_usd":    np.round(base_sales, 2),
        "promo_period_sales_usd":np.round(promo_sales, 2),
        "cannibalisation_usd":   np.round(cannibalisation, 2),
        "pantry_loading_usd":    np.round(pantry_loading, 2),
        "true_incremental_usd":  np.round(true_incr_sales, 2),
        "promo_cost_usd":        np.round(promo_cost, 2),
        "roi":                   np.round(roi, 4),
        "markdown_avoidable":    true_incr_sales < (base_sales * 0.05),
    })

    save_parquet(df, f"{OUTPUT_DIR}/promotions/fact_promo_uplift.parquet")
    save_csv(df,     f"{OUTPUT_DIR}/promotions/fact_promo_uplift.csv")
    return df


def generate_ab_tests(stores_df: pd.DataFrame, n_tests: int = 500) -> pd.DataFrame:
    """
    Champion/Challenger A/B test results for promotions, layout changes, pricing.
    """
    print(f"Generating fact_ab_tests ({n_tests:,} tests) …")

    test_types = weighted_choice(
        ["Promotion Mechanic", "Store Layout", "Pricing Strategy",
         "Loyalty Offer", "Digital Coupon", "Endcap Placement"],
        [0.30, 0.20, 0.15, 0.15, 0.12, 0.08], n_tests,
    )
    start_dates = date_range_array(START_DATE, END_DATE, n_tests)
    durations   = rng.integers(7, 90, n_tests).astype("timedelta64[D]")

    control_sales   = rng.uniform(10_000, 500_000, n_tests)
    treatment_sales = control_sales * rng.uniform(0.85, 1.45, n_tests)
    uplift_pct      = (treatment_sales - control_sales) / control_sales * 100
    p_values        = rng.beta(1.5, 5, n_tests)          # realistic skew toward significance
    is_significant  = p_values < 0.05

    df = pd.DataFrame({
        "test_id":                 [f"AB{i+1:05d}" for i in range(n_tests)],
        "test_type":               test_types,
        "start_date":              start_dates,
        "end_date":                start_dates + durations,
        "duration_days":           durations.astype(int),
        "control_store_count":     rng.integers(5, 50, n_tests),
        "treatment_store_count":   rng.integers(5, 50, n_tests),
        "control_sales_usd":       np.round(control_sales, 2),
        "treatment_sales_usd":     np.round(treatment_sales, 2),
        "uplift_pct":              np.round(uplift_pct, 2),
        "p_value":                 np.round(p_values, 4),
        "is_statistically_significant": is_significant,
        "roll_out_decision":       np.where(is_significant & (uplift_pct > 5),
                                            "Roll Out", "No Action"),
        "estimated_annual_impact_usd": np.round(
            np.where(is_significant & (uplift_pct > 5),
                     treatment_sales * uplift_pct / 100 * 52, 0), 0),
    })

    save_parquet(df, f"{OUTPUT_DIR}/promotions/fact_ab_tests.parquet")
    save_csv(df,     f"{OUTPUT_DIR}/promotions/fact_ab_tests.csv")
    return df
