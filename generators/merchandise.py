"""
Merchandise planning & inventory generators.

Tables produced
───────────────
fact_inventory          – weekly on-hand vs. demand by store × SKU
fact_demand_forecast    – model output: baseline + uplift demand forecast
fact_stockouts          – stockout events with lost-sales estimate
"""

import numpy as np
import pandas as pd
from tqdm import tqdm

from config import OUTPUT_DIR, START_DATE, END_DATE, DEPARTMENTS
from generators.base import rng, weighted_choice, save_csv, save_parquet


def generate_inventory(stores_df: pd.DataFrame, products_df: pd.DataFrame,
                        sample_stores: int = 50) -> pd.DataFrame:
    """
    Weekly inventory snapshots for a sample of stores × SKUs (vectorised).
    """
    print(f"Generating fact_inventory (sample: {sample_stores} stores) …")

    stores_sample = stores_df.sample(n=min(sample_stores, len(stores_df)), random_state=42)
    weeks         = pd.date_range(START_DATE, END_DATE, freq="W-MON")
    n_weeks       = len(weeks)

    vel = products_df["velocity_tier"].values
    p   = np.where(vel == "A", 40, np.where(vel == "B", 20, np.where(vel == "C", 5, 1))).astype(float)
    p  /= p.sum()
    sku_sample = products_df.sample(n=min(500, len(products_df)), weights=p, random_state=42)

    parts = []
    for _, store in tqdm(stores_sample.iterrows(), total=len(stores_sample), desc="  inventory stores"):
        n_skus      = len(sku_sample)
        avg_demands = rng.uniform(5, 400, n_skus)          # one per SKU

        # Demand: (n_skus, n_weeks)
        demands   = np.maximum(0, rng.normal(
            avg_demands[:, None], avg_demands[:, None] * 0.25,
            size=(n_skus, n_weeks)
        ))
        received  = avg_demands[:, None] * rng.uniform(0.8, 1.2, size=(n_skus, n_weeks))

        # Simulate running on-hand via cumsum trick (approx, no negative stock)
        on_hand_init = avg_demands * rng.uniform(1.5, 4.0)
        net_flow     = received - demands
        on_hand_all  = np.maximum(0, on_hand_init[:, None] + net_flow.cumsum(axis=1))

        fill_rate = np.minimum(1.0, on_hand_all / np.maximum(demands, 0.01))
        dos        = on_hand_all / np.maximum(demands / 7, 0.01)

        # Flatten to rows
        store_ids_col = np.full(n_skus * n_weeks, store["store_id"])
        sku_ids_col   = np.tile(sku_sample["sku_id"].values, n_weeks)
        weeks_col     = np.repeat(weeks, n_skus)

        chunk = pd.DataFrame({
            "store_id":       store_ids_col,
            "sku_id":         sku_ids_col,
            "week_start":     weeks_col,
            "on_hand_units":  on_hand_all.T.ravel().round(0),
            "demand_units":   demands.T.ravel().round(0),
            "received_units": received.T.ravel().round(0),
            "fill_rate":      fill_rate.T.ravel().round(4),
            "days_of_supply": dos.T.ravel().round(1),
        })
        parts.append(chunk)

    df = pd.concat(parts, ignore_index=True)
    save_parquet(df, f"{OUTPUT_DIR}/merchandise/fact_inventory.parquet")
    save_csv(df.sample(min(300_000, len(df)), random_state=42),
             f"{OUTPUT_DIR}/merchandise/fact_inventory_sample.csv")
    return df


def generate_demand_forecast(stores_df: pd.DataFrame, products_df: pd.DataFrame,
                               n_rows: int = 500_000) -> pd.DataFrame:
    """
    Demand forecast table: baseline + promotional uplift + seasonality.
    Feeds the merchandise mix model.
    """
    print(f"Generating fact_demand_forecast ({n_rows:,} rows) …")

    store_ids = stores_df["store_id"].values
    sku_ids   = products_df["sku_id"].values
    depts     = products_df["department"].values

    idx       = rng.integers(0, len(sku_ids), n_rows)
    weeks     = pd.date_range(START_DATE, END_DATE, freq="W-MON")
    week_idx  = rng.integers(0, len(weeks), n_rows)

    baseline_demand = rng.uniform(10, 500, n_rows)
    seasonal_idx    = np.sin((weeks[week_idx].month.values - 1) * np.pi / 6) * 0.2 + 1.0
    promo_uplift    = np.where(rng.random(n_rows) < 0.18,
                               rng.uniform(1.1, 2.5, n_rows), 1.0)
    forecast        = np.round(baseline_demand * seasonal_idx * promo_uplift, 1)
    actual          = np.round(forecast * rng.uniform(0.85, 1.18, n_rows), 1)
    mape            = np.abs(forecast - actual) / np.maximum(actual, 0.01) * 100

    df = pd.DataFrame({
        "forecast_id":      [f"FCST{i+1:09d}" for i in range(n_rows)],
        "store_id":         rng.choice(store_ids, n_rows),
        "sku_id":           sku_ids[idx],
        "department":       depts[idx],
        "week_start":       weeks[week_idx],
        "baseline_demand":  baseline_demand.round(1),
        "seasonal_index":   seasonal_idx.round(4),
        "promo_uplift_factor": promo_uplift.round(3),
        "forecast_units":   forecast,
        "actual_units":     actual,
        "mape_pct":         mape.round(2),
        "model_version":    weighted_choice(["v1.0", "v1.5", "v2.0", "v2.1"],
                                            [0.10, 0.20, 0.40, 0.30], n_rows),
    })

    save_parquet(df, f"{OUTPUT_DIR}/merchandise/fact_demand_forecast.parquet")
    save_csv(df,     f"{OUTPUT_DIR}/merchandise/fact_demand_forecast.csv")
    return df


def generate_stockouts(inventory_df: pd.DataFrame) -> pd.DataFrame:
    """Extract stockout events from inventory fact and estimate lost sales."""
    print("Generating fact_stockouts …")
    stockouts = inventory_df[inventory_df["on_hand_units"] < inventory_df["demand_units"]].copy()
    stockouts["lost_units"]      = (stockouts["demand_units"] - stockouts["on_hand_units"]).clip(lower=0)
    # Assume avg unit price ~$4.50 for lost sales estimate
    stockouts["lost_sales_usd"]  = (stockouts["lost_units"] * rng.uniform(0.50, 25.0,
                                                                            len(stockouts))).round(2)
    stockouts["stockout_days"]   = rng.integers(1, 8, len(stockouts))
    stockouts["root_cause"]      = weighted_choice(
        ["Forecast Error", "Supply Disruption", "DC Delay",
         "Supplier OOS", "Excess Demand", "System Error"],
        [0.28, 0.20, 0.18, 0.16, 0.12, 0.06], len(stockouts),
    )

    save_parquet(stockouts, f"{OUTPUT_DIR}/merchandise/fact_stockouts.parquet")
    save_csv(stockouts,     f"{OUTPUT_DIR}/merchandise/fact_stockouts.csv")
    return stockouts
