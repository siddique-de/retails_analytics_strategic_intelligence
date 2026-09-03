"""
Media Mix Modelling & Data Monetisation generators.

Tables produced
───────────────
fact_media_spend        – weekly media spend by channel and region
fact_media_response     – modelled sales response curves per channel
fact_data_monetisation  – monthly revenue from selling POS data to third parties
"""

import numpy as np
import pandas as pd

from config import MEDIA_CHANNELS, REGIONS, DATA_BUYERS, ANNUAL_DATA_REVENUE_USD, OUTPUT_DIR
from generators.base import rng, weighted_choice, save_csv, save_parquet

# Relative channel effectiveness (ROI multiplier)
CHANNEL_ROI_MED = {
    "TV":               2.1,
    "Radio":            1.6,
    "Print":            1.3,
    "Outdoor":          1.4,
    "Digital Display":  1.8,
    "Paid Search":      3.2,
    "Social Media":     2.4,
    "Email":            4.1,
    "Catalogue":        1.7,
    "In-Store":         2.8,
}

CHANNEL_SPEND_SHARE = {      # % of total media budget
    "TV":               0.28,
    "Radio":            0.05,
    "Print":            0.06,
    "Outdoor":          0.04,
    "Digital Display":  0.12,
    "Paid Search":      0.10,
    "Social Media":     0.11,
    "Email":            0.03,
    "Catalogue":        0.09,
    "In-Store":         0.12,
}


def generate_media_spend(start: str = "2018-01-01", end: str = "2023-12-31") -> pd.DataFrame:
    print("Generating fact_media_spend …")
    weeks = pd.date_range(start, end, freq="W-MON")
    rows  = []
    for region_code, meta in REGIONS.items():
        annual_budget = rng.integers(5_000_000, 80_000_000)
        weekly_budget = annual_budget / 52

        for wk in weeks:
            # Seasonal multiplier (Q4 higher, summer moderate)
            month     = wk.month
            seas_mult = 1.0 + 0.4 * np.sin((month - 3) * np.pi / 6)
            wk_total  = weekly_budget * seas_mult * rng.uniform(0.85, 1.15)

            for channel in MEDIA_CHANNELS:
                spend = wk_total * CHANNEL_SPEND_SHARE[channel] * rng.uniform(0.80, 1.20)
                rows.append({
                    "week_start_date": wk,
                    "region":          region_code,
                    "channel":         channel,
                    "spend_usd":       round(spend, 2),
                })

    df = pd.DataFrame(rows)
    save_parquet(df, f"{OUTPUT_DIR}/media/fact_media_spend.parquet")
    save_csv(df,     f"{OUTPUT_DIR}/media/fact_media_spend.csv")
    return df


def generate_media_response(media_spend_df: pd.DataFrame) -> pd.DataFrame:
    """
    Adstock / diminishing-returns response model output.
    Each row: channel × week × region → attributed sales incremental.
    """
    print("Generating fact_media_response …")
    df = media_spend_df.copy()
    channel_roi = np.array([CHANNEL_ROI_MED[c] for c in df["channel"]])
    noise       = rng.normal(1.0, 0.15, len(df))
    # Adstock: carryover effect (simplified lambda = 0.5)
    df["adstock_spend_usd"]        = df["spend_usd"] * rng.uniform(0.6, 1.0, len(df))
    df["attributed_sales_usd"]     = np.round(df["adstock_spend_usd"] * channel_roi * noise, 2)
    df["roi"]                      = np.round(df["attributed_sales_usd"] / df["spend_usd"].clip(lower=1), 4)
    df["marginal_roi"]             = np.round(df["roi"] * rng.uniform(0.55, 0.95, len(df)), 4)
    df["saturation_flag"]          = df["spend_usd"] > df["spend_usd"].quantile(0.85)

    save_parquet(df, f"{OUTPUT_DIR}/media/fact_media_response.parquet")
    save_csv(df,     f"{OUTPUT_DIR}/media/fact_media_response.csv")
    return df


def generate_data_monetisation(start: str = "2018-01-01", end: str = "2023-12-31") -> pd.DataFrame:
    """
    Monthly revenue from selling non-identifiable SKU-level POS data
    to ACNielsen, NPD, and IRI.  Target: $20M–$30M annually.
    """
    print("Generating fact_data_monetisation …")
    months = pd.date_range(start, end, freq="MS")
    monthly_target = ANNUAL_DATA_REVENUE_USD / 12

    rows = []
    for m in months:
        for buyer in DATA_BUYERS:
            rev = monthly_target / len(DATA_BUYERS) * rng.uniform(0.85, 1.20)
            rows.append({
                "month":              m,
                "data_buyer":         buyer,
                "data_type":          weighted_choice(
                    ["SKU-Level POS", "Category Aggregate", "Store-Level Volume",
                     "Basket Composition", "Shopper Panel"],
                    [0.35, 0.25, 0.18, 0.14, 0.08], 1)[0],
                "revenue_usd":        round(rev, 2),
                "records_delivered":  rng.integers(50_000_000, 500_000_000),
                "is_non_identifiable": True,
                "contract_type":      weighted_choice(["Annual", "Monthly", "Per-Use"],
                                                      [0.60, 0.25, 0.15], 1)[0],
            })

    df = pd.DataFrame(rows)
    annual = df.groupby(df["month"].dt.year)["revenue_usd"].sum()
    print(f"  Annual data revenue (first year): ${annual.iloc[0]:,.0f}")
    save_parquet(df, f"{OUTPUT_DIR}/media/fact_data_monetisation.parquet")
    save_csv(df,     f"{OUTPUT_DIR}/media/fact_data_monetisation.csv")
    return df
