"""
Market Basket / POS transaction generator.

Tables produced
───────────────
fact_transactions       – header-level transaction summary
fact_basket_detail      – line-item detail (the 10-billion-row MPP table, scaled)
fact_basket_affinities  – pre-aggregated item-pair affinity scores
"""

import numpy as np
import pandas as pd
from tqdm import tqdm

from config import (REGIONS, TARGET_BASKET_ROWS, OUTPUT_DIR,
                    START_DATE, END_DATE, STORE_OPEN_HOUR, STORE_CLOSE_HOUR)
from generators.base import rng, weighted_choice, date_range_array, save_csv, save_parquet

# Average items per basket by store format
FORMAT_AVG_BASKET = {
    "Hypermarket": 22, "Supermarket": 14, "Express": 6,
    "Online Hub": 18,  "Flagship": 16,
}

# Hour-of-day weight (captures morning rush, lunch, after-work peak)
_hours = list(range(STORE_OPEN_HOUR, STORE_CLOSE_HOUR + 1))
_raw_w = [1,2,4,5,4,3,5,8,9,7,6,6,7,8,10,9,6,4,3,2,2,1,1,1]
_raw_w = _raw_w[:len(_hours)]
HOUR_WEIGHTS = np.array(_raw_w, dtype=float) / sum(_raw_w)

# Day-of-week multiplier (0=Mon … 6=Sun)
DOW_MULT = np.array([0.80, 0.82, 0.85, 0.90, 1.10, 1.30, 1.20])

PAYMENT_METHODS = ["Cash", "Credit Card", "Debit Card", "Mobile Pay",
                   "Loyalty Points", "Gift Card", "BNPL"]
PAYMENT_WEIGHTS  = [0.10, 0.35, 0.28, 0.15, 0.05, 0.04, 0.03]


def _chunk_size(target_rows: int, chunk: int = 500_000) -> list:
    """Split target row count into processing chunks."""
    full, remainder = divmod(target_rows, chunk)
    sizes = [chunk] * full
    if remainder:
        sizes.append(remainder)
    return sizes


def generate_transactions(stores_df: pd.DataFrame,
                          customers_df: pd.DataFrame,
                          products_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (transactions_header_df, basket_detail_df).
    Writes Parquet files in chunks for memory efficiency.
    """
    print(f"Generating market basket detail (~{TARGET_BASKET_ROWS:,} rows target) …")

    store_ids  = stores_df["store_id"].values
    store_fmt  = dict(zip(stores_df["store_id"], stores_df["format"]))
    cust_ids   = customers_df["customer_id"].values
    sku_ids    = products_df["sku_id"].values
    sku_prices = products_df["sell_price_usd"].values
    sku_depts  = products_df["department"].values
    vel_tier   = products_df["velocity_tier"].values

    # Velocity-based SKU selection weights
    vel_weight_map = {"A": 40.0, "B": 15.0, "C": 4.0, "D": 1.0}
    sku_weights = np.array([vel_weight_map[v] for v in vel_tier], dtype=float)
    sku_weights /= sku_weights.sum()

    chunk_sizes = _chunk_size(TARGET_BASKET_ROWS)
    total_chunks = len(chunk_sizes)

    txn_header_parts  = []
    basket_detail_parts = []

    txn_id_start  = 1
    line_id_start = 1

    for chunk_idx, n_lines in enumerate(tqdm(chunk_sizes, desc="  basket chunks")):
        # Determine basket sizes for this chunk
        avg_items    = 14
        est_baskets  = n_lines // avg_items + 200
        basket_sizes = rng.integers(1, 35, size=est_baskets)
        cum          = basket_sizes.cumsum()
        cut          = np.searchsorted(cum, n_lines, side="right")
        basket_sizes = basket_sizes[:max(cut, 1)]
        actual_lines = int(basket_sizes.sum())
        n_baskets    = len(basket_sizes)

        # ── Transaction header fields ─────────────────────────────────────────
        txn_dates = date_range_array(START_DATE, END_DATE, n_baskets)
        txn_dow   = (txn_dates.astype("datetime64[D]").view("int64") % 7)
        txn_hours = rng.choice(_hours, size=n_baskets, p=HOUR_WEIGHTS)

        txn_store_ids   = rng.choice(store_ids, size=n_baskets)
        txn_cust_ids    = np.where(
            rng.random(n_baskets) < 0.72,   # 72 % loyalty card scan rate
            rng.choice(cust_ids, size=n_baskets),
            None,
        )
        payment_methods = weighted_choice(PAYMENT_METHODS, PAYMENT_WEIGHTS, n_baskets)

        # ── Expand basket sizes into line index arrays ─────────────────────────
        line_basket_idx  = np.repeat(np.arange(n_baskets), basket_sizes)
        n_actual         = len(line_basket_idx)

        # SKU selection
        line_sku_idx   = rng.choice(len(sku_ids), size=n_actual, p=sku_weights)
        line_sku_ids   = sku_ids[line_sku_idx]
        line_prices    = sku_prices[line_sku_idx]
        line_depts     = sku_depts[line_sku_idx]
        line_qty       = rng.integers(1, 5, size=n_actual)
        line_discount  = np.where(rng.random(n_actual) < 0.18,
                                  np.round(rng.uniform(0.05, 0.40, n_actual), 2), 0.0)
        line_ext_price = np.round(line_prices * line_qty * (1 - line_discount), 2)

        # ── Basket detail dataframe ────────────────────────────────────────────
        basket_txn_ids = np.arange(txn_id_start, txn_id_start + n_baskets)
        line_txn_ids   = basket_txn_ids[line_basket_idx]

        bd = pd.DataFrame({
            "transaction_id":   line_txn_ids,
            "line_id":          np.arange(line_id_start, line_id_start + n_actual),
            "store_id":         txn_store_ids[line_basket_idx],
            "transaction_date": txn_dates[line_basket_idx],
            "sku_id":           line_sku_ids,
            "department":       line_depts,
            "quantity":         line_qty,
            "unit_price_usd":   line_prices,
            "discount_pct":     line_discount,
            "extended_price_usd": line_ext_price,
        })

        # ── Header ────────────────────────────────────────────────────────────
        basket_totals = bd.groupby("transaction_id")["extended_price_usd"].sum().reset_index()
        basket_totals.columns = ["transaction_id", "basket_total_usd"]

        hdr = pd.DataFrame({
            "transaction_id":   basket_txn_ids,
            "store_id":         txn_store_ids,
            "customer_id":      txn_cust_ids,
            "transaction_date": txn_dates,
            "hour_of_day":      txn_hours,
            "day_of_week":      txn_dow,
            "payment_method":   payment_methods,
            "item_count":       basket_sizes,
        }).merge(basket_totals, on="transaction_id", how="left")

        txn_header_parts.append(hdr)
        basket_detail_parts.append(bd)

        txn_id_start  += n_baskets
        line_id_start += n_actual

    print("  Concatenating and saving …")
    txn_df  = pd.concat(txn_header_parts,  ignore_index=True)
    bd_df   = pd.concat(basket_detail_parts, ignore_index=True)

    save_parquet(txn_df, f"{OUTPUT_DIR}/transactions/fact_transactions.parquet")
    save_parquet(bd_df,  f"{OUTPUT_DIR}/transactions/fact_basket_detail.parquet")
    save_csv(txn_df,     f"{OUTPUT_DIR}/transactions/fact_transactions.csv")
    # basket_detail is too large for a single CSV; write a sample
    bd_sample = bd_df.sample(n=min(500_000, len(bd_df)), random_state=42)
    save_csv(bd_sample,  f"{OUTPUT_DIR}/transactions/fact_basket_detail_sample.csv")

    return txn_df, bd_df


def generate_basket_affinities(basket_detail_df: pd.DataFrame,
                                products_df: pd.DataFrame,
                                top_n: int = 5_000) -> pd.DataFrame:
    """
    Compute item-pair co-occurrence (support, confidence, lift) for
    the top_n most frequent SKUs.  Uses a vectorised approach suitable
    for the scaled dataset.
    """
    print("Generating fact_basket_affinities …")

    sku_freq = basket_detail_df["sku_id"].value_counts().head(top_n)
    top_skus = sku_freq.index.tolist()

    # Filter to top SKUs only
    bd_top = basket_detail_df[basket_detail_df["sku_id"].isin(top_skus)][
        ["transaction_id", "sku_id"]].drop_duplicates()

    # Pivot to basket × sku binary matrix (sparse-ish)
    from scipy.sparse import csr_matrix

    sku_cat  = pd.Categorical(bd_top["sku_id"], categories=top_skus)
    txn_cat  = pd.Categorical(bd_top["transaction_id"])
    mat = csr_matrix(
        (np.ones(len(bd_top)), (txn_cat.codes, sku_cat.codes)),
        shape=(txn_cat.categories.size, len(top_skus)),
    )

    n_txns = mat.shape[0]
    support_vec = np.asarray(mat.sum(axis=0)).flatten() / n_txns

    # Co-occurrence: M^T × M  gives pair counts
    co_mat = (mat.T @ mat).toarray()
    np.fill_diagonal(co_mat, 0)

    # Build long-form affinity table
    rows = []
    for i in range(len(top_skus)):
        top_j = np.argsort(co_mat[i])[-20:][::-1]  # top-20 pairs per SKU
        for j in top_j:
            if co_mat[i, j] == 0:
                continue
            pair_support    = co_mat[i, j] / n_txns
            confidence_ij   = co_mat[i, j] / max((support_vec[i] * n_txns), 1)
            lift_ij         = pair_support / max(support_vec[i] * support_vec[j], 1e-10)
            rows.append({
                "antecedent_sku":   top_skus[i],
                "consequent_sku":   top_skus[j],
                "support":          round(pair_support, 6),
                "confidence":       round(float(confidence_ij), 4),
                "lift":             round(float(lift_ij), 4),
                "co_occurrence_count": int(co_mat[i, j]),
            })

    df = pd.DataFrame(rows)
    df = df[df["lift"] > 1.0].sort_values("lift", ascending=False).reset_index(drop=True)

    # Merge in department names
    dept_map = dict(zip(products_df["sku_id"], products_df["department"]))
    df["antecedent_dept"] = df["antecedent_sku"].map(dept_map)
    df["consequent_dept"] = df["consequent_sku"].map(dept_map)

    save_parquet(df, f"{OUTPUT_DIR}/transactions/fact_basket_affinities.parquet")
    save_csv(df,     f"{OUTPUT_DIR}/transactions/fact_basket_affinities.csv")
    return df
