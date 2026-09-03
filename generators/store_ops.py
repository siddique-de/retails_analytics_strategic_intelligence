"""
Store operations generators:
  - Labour / staffing forecast
  - Store layout & traffic patterns
  - Store cluster / sister-store assignments
  - Store-in-a-store SKU performance (before / after layout change)

Tables produced
───────────────
fact_labour_schedule        – hourly staff counts vs. actual transaction volume
fact_store_traffic          – daily store traffic with entry/exit counts
dim_store_clusters          – sister-store cluster assignments
fact_layout_test_results    – before/after layout change KPIs
"""

import numpy as np
import pandas as pd
from tqdm import tqdm

from config import (OUTPUT_DIR, START_DATE, END_DATE,
                    STORE_OPEN_HOUR, STORE_CLOSE_HOUR,
                    TARGET_QUEUE_MAX, DEPARTMENTS, RANDOM_SEED)
from generators.base import rng, weighted_choice, date_range_array, save_csv, save_parquet

HOURS_OPEN = STORE_CLOSE_HOUR - STORE_OPEN_HOUR + 1

# Traffic pattern by hour (index 0 = STORE_OPEN_HOUR)
_TRAFFIC_SHAPE = np.array([
    1, 2, 4, 6, 5, 4, 6, 9, 10, 8, 7, 7, 8, 9, 11, 10, 7, 5, 4, 3, 2, 2, 1,
], dtype=float)
_TRAFFIC_SHAPE = _TRAFFIC_SHAPE[:HOURS_OPEN]
_TRAFFIC_SHAPE /= _TRAFFIC_SHAPE.sum()

# 11 clustering metrics used in the sister-store model
CLUSTER_METRICS = [
    "annual_sales_usd", "avg_basket_size_usd", "avg_weekly_transactions",
    "fresh_food_pct", "private_label_pct", "customer_loyalty_rate",
    "store_size_sqft", "median_hh_income_trade_area", "competitor_density",
    "daytime_pop_density", "sales_per_sqft",
]


# ── Labour forecasting ────────────────────────────────────────────────────────

def generate_labour_schedule(stores_df: pd.DataFrame,
                              transactions_df: pd.DataFrame) -> pd.DataFrame:
    """
    Hourly staff-count model based on transaction volume.
    Target: ≤ TARGET_QUEUE_MAX customers per queue.
    """
    print("Generating fact_labour_schedule …")

    # Aggregate transactions to store × date × hour
    txn = transactions_df[["store_id", "transaction_date", "hour_of_day"]].copy()
    txn["transaction_date"] = txn["transaction_date"].astype(str)
    hourly = (txn.groupby(["store_id", "transaction_date", "hour_of_day"])
                 .size().reset_index(name="txn_count"))

    # Staff required = ceil(txn_count / TARGET_QUEUE_MAX / avg_service_rate_per_staff)
    service_rate = 12   # transactions/hour per checkout staff member
    hourly["checkouts_required"] = np.ceil(
        hourly["txn_count"] / TARGET_QUEUE_MAX / service_rate
    ).astype(int)
    hourly["staff_rostered"]     = (hourly["checkouts_required"] * rng.uniform(1.0, 1.25,
                                                                                len(hourly))).astype(int)
    hourly["staff_actual"]       = (hourly["staff_rostered"] * rng.uniform(0.88, 1.05,
                                                                             len(hourly))).astype(int)
    hourly["avg_queue_length"]   = np.round(
        hourly["txn_count"] / np.maximum(hourly["staff_actual"] * service_rate, 1), 2
    )
    hourly["sla_met"]            = hourly["avg_queue_length"] <= TARGET_QUEUE_MAX
    hourly["labour_cost_usd"]    = hourly["staff_rostered"] * rng.uniform(12, 28, len(hourly))

    save_parquet(hourly, f"{OUTPUT_DIR}/store_ops/fact_labour_schedule.parquet")
    save_csv(hourly.sample(min(200_000, len(hourly)), random_state=42),
             f"{OUTPUT_DIR}/store_ops/fact_labour_schedule_sample.csv")
    return hourly


# ── Store traffic ─────────────────────────────────────────────────────────────

def generate_store_traffic(stores_df: pd.DataFrame, n_days=None) -> pd.DataFrame:
    """
    Daily traffic counts per store, written in store-batches to stay within memory.
    n_days caps the date range (default: full 6-year range).
    """
    import os, pathlib
    all_dates = pd.date_range(START_DATE, END_DATE, freq="D")
    if n_days:
        all_dates = all_dates[:n_days]

    print(f"Generating fact_store_traffic ({len(stores_df)} stores × {len(all_dates)} days) …")

    out_path = f"{OUTPUT_DIR}/store_ops/fact_store_traffic.parquet"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    import pyarrow as pa, pyarrow.parquet as pq
    writer = None
    total_rows = 0
    dow_mult = np.array([1.0, 1.0, 1.0, 1.0, 1.2, 1.5, 1.3])
    day_mult_arr = dow_mult[all_dates.dayofweek]
    n = len(all_dates)

    for _, store in tqdm(stores_df.iterrows(), total=len(stores_df), desc="  stores"):
        base_traffic = int(rng.integers(200, 8_000))
        noise        = rng.uniform(0.85, 1.15, n)
        traffic      = (base_traffic * day_mult_arr * noise).astype(int)

        chunk = pd.DataFrame({
            "store_id":              store["store_id"],
            "traffic_date":          all_dates,
            "foot_traffic":          traffic,
            "conversion_rate":       np.round(rng.uniform(0.28, 0.72, n), 3),
            "dwell_time_min":        np.round(rng.uniform(8, 65, n), 1),
            "impulse_purchase_rate": np.round(rng.uniform(0.10, 0.45, n), 3),
        })
        table = pa.Table.from_pandas(chunk, preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(out_path, table.schema, compression="snappy")
        writer.write_table(table)
        total_rows += len(chunk)

    if writer:
        writer.close()

    mb = os.path.getsize(out_path) / 1_048_576
    print(f"  → {out_path}  ({total_rows:,} rows, {mb:.1f} MB)")

    # Small CSV sample
    sample = pd.read_parquet(out_path).sample(min(100_000, total_rows), random_state=42)
    save_csv(sample, f"{OUTPUT_DIR}/store_ops/fact_store_traffic_sample.csv")
    return sample  # return sample to avoid holding full df in memory


# ── Sister-store clustering ───────────────────────────────────────────────────

def generate_store_clusters(stores_df: pd.DataFrame,
                             n_clusters: int = 12) -> pd.DataFrame:
    """
    Assign stores to clusters using simulated cluster metrics.
    Mirrors the demand-model approach: 11+ metrics → K-means → sister stores.
    """
    print(f"Generating dim_store_clusters ({n_clusters} clusters) …")
    n = len(stores_df)

    metric_data = {m: rng.uniform(0, 1, n) for m in CLUSTER_METRICS}
    metric_df   = pd.DataFrame(metric_data)

    # Normalise
    from sklearn.preprocessing import StandardScaler
    scaler      = StandardScaler()
    scaled      = scaler.fit_transform(metric_df)

    from sklearn.cluster import KMeans
    km = KMeans(n_clusters=n_clusters, random_state=RANDOM_SEED, n_init=10)
    labels = km.fit_predict(scaled)

    df = stores_df[["store_id", "region", "format", "size_sqft"]].copy()
    df["cluster_id"]    = labels
    df["cluster_label"] = [f"Cluster_{c:02d}" for c in labels]

    # Attach raw metrics for interpretability
    for m in CLUSTER_METRICS:
        df[m] = np.round(metric_df[m].values, 4)

    # Sister-store: nearest store in same cluster (by Euclidean on scaled metrics)
    from sklearn.neighbors import NearestNeighbors
    sister_ids = []
    for c in range(n_clusters):
        mask = labels == c
        if mask.sum() < 2:
            sister_ids.extend(stores_df["store_id"].values[mask])
            continue
        nn = NearestNeighbors(n_neighbors=2)
        nn.fit(scaled[mask])
        _, idx = nn.kneighbors(scaled[mask])
        cluster_stores = stores_df["store_id"].values[mask]
        for i, row_idx in enumerate(idx):
            # row_idx[1] is the nearest neighbour (not self)
            sister_ids.append(cluster_stores[row_idx[1]])

    df["sister_store_id"] = sister_ids

    save_parquet(df, f"{OUTPUT_DIR}/store_ops/dim_store_clusters.parquet")
    save_csv(df,     f"{OUTPUT_DIR}/store_ops/dim_store_clusters.csv")
    return df


# ── Store-in-a-store layout test ──────────────────────────────────────────────

def generate_layout_test_results(stores_df: pd.DataFrame, n_test_stores=None) -> pd.DataFrame:
    """
    Before/after KPIs for store-in-a-store layout redesign.
    Target: 20-30% sales lift with 20% SKU reduction.
    """
    if n_test_stores is None:
        n_test_stores = max(20, len(stores_df) // 10)
    print(f"Generating fact_layout_test_results ({n_test_stores} test stores) …")

    test_stores = stores_df.sample(n=n_test_stores, random_state=RANDOM_SEED)

    dept_results = []
    for _, store in test_stores.iterrows():
        for dept in DEPARTMENTS:
            sku_count_before = rng.integers(200, 2_000)
            sku_count_after  = int(sku_count_before * rng.uniform(0.75, 0.85))  # ~20% reduction
            sales_before     = rng.uniform(50_000, 800_000)
            # Aligned with documented 20-30% uplift
            uplift_factor    = rng.uniform(1.18, 1.33)
            sales_after      = sales_before * uplift_factor
            dept_results.append({
                "store_id":            store["store_id"],
                "department":          dept,
                "sku_count_before":    int(sku_count_before),
                "sku_count_after":     int(sku_count_after),
                "sku_reduction_pct":   round((1 - sku_count_after / sku_count_before) * 100, 2),
                "sales_before_usd":    round(sales_before, 2),
                "sales_after_usd":     round(sales_after, 2),
                "sales_uplift_pct":    round((uplift_factor - 1) * 100, 2),
                "avg_dwell_before_min":round(rng.uniform(4, 18), 1),
                "avg_dwell_after_min": round(rng.uniform(8, 28), 1),
                "impulse_rate_before": round(rng.uniform(0.10, 0.25), 3),
                "impulse_rate_after":  round(rng.uniform(0.22, 0.42), 3),
                "test_wave":           weighted_choice(["Wave 1","Wave 2","Wave 3"],
                                                       [0.4, 0.35, 0.25], 1)[0],
            })

    df = pd.DataFrame(dept_results)
    save_parquet(df, f"{OUTPUT_DIR}/store_ops/fact_layout_test_results.parquet")
    save_csv(df,     f"{OUTPUT_DIR}/store_ops/fact_layout_test_results.csv")
    return df
