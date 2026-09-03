"""
Customer master & loyalty data generator.

Tables produced
───────────────
dim_customers       – customer master with demographics & loyalty membership
dim_loyalty_members – loyalty programme details, tier, programme name
fact_rfm            – RFM scores and derived loyalty segment per customer
"""

import numpy as np
import pandas as pd
from faker import Faker

from config import (REGIONS, NUM_CUSTOMERS, LOYALTY_PROGRAMS,
                    LOYALTY_SEGMENTS, OUTPUT_DIR, RANDOM_SEED, START_DATE, END_DATE)
from generators.base import rng, weighted_choice, date_range_array, save_csv, save_parquet

fake = Faker("en_US")
Faker.seed(RANDOM_SEED)

# Segment distribution (mirrors RFM reality: most are mid-tier)
SEGMENT_WEIGHTS = [0.15, 0.20, 0.18, 0.22, 0.12, 0.13]


def generate_customers(stores_df: pd.DataFrame) -> pd.DataFrame:
    print(f"Generating dim_customers ({NUM_CUSTOMERS:,} customers) …")
    n = NUM_CUSTOMERS

    # Distribute customers across regions proportional to store count
    regions = list(REGIONS.keys())
    region_weights = [REGIONS[r]["store_count"] for r in regions]
    cust_regions = weighted_choice(regions, region_weights, n)

    # Demographics
    genders     = weighted_choice(["F", "M", "Non-binary", "Prefer not to say"],
                                  [0.52, 0.44, 0.02, 0.02], n)
    age_groups  = weighted_choice(["18-24","25-34","35-44","45-54","55-64","65+"],
                                  [0.10, 0.22, 0.24, 0.20, 0.14, 0.10], n)
    hh_sizes    = rng.choice([1,2,3,4,5,6], p=[0.28,0.34,0.16,0.13,0.06,0.03], size=n)

    income_map = {"18-24":35_000,"25-34":52_000,"35-44":68_000,
                  "45-54":75_000,"55-64":70_000,"65+":48_000}
    incomes = np.array([income_map[a] for a in age_groups])
    incomes = (incomes * rng.uniform(0.6, 1.6, n)).astype(int)

    enroll_dates = date_range_array(START_DATE, END_DATE, n)

    df = pd.DataFrame({
        "customer_id":      [f"CUST{i+1:08d}" for i in range(n)],
        "region":           cust_regions,
        "country":          [REGIONS[r]["country"] for r in cust_regions],
        "loyalty_program":  [LOYALTY_PROGRAMS[r] for r in cust_regions],
        "gender":           genders,
        "age_group":        age_groups,
        "household_size":   hh_sizes,
        "annual_income_usd":incomes,
        "enroll_date":      enroll_dates,
        "has_children":     (hh_sizes >= 3) & (np.isin(age_groups, ["25-34","35-44","45-54"])),
        "has_pet":          rng.random(n) < 0.30,
        "email_opt_in":     rng.random(n) < 0.68,
        "mobile_opt_in":    rng.random(n) < 0.54,
    })

    save_parquet(df, f"{OUTPUT_DIR}/customers/dim_customers.parquet")
    save_csv(df,     f"{OUTPUT_DIR}/customers/dim_customers.csv")
    return df


def generate_loyalty_members(customers_df: pd.DataFrame) -> pd.DataFrame:
    """~78 % of customers are enrolled in loyalty."""
    print("Generating dim_loyalty_members …")
    df = customers_df[customers_df["loyalty_program"].notna()].copy()
    n  = len(df)

    df = df[["customer_id", "region", "loyalty_program", "enroll_date"]].copy()
    df["loyalty_tier"] = weighted_choice(
        ["Bronze", "Silver", "Gold", "Platinum"],
        [0.45, 0.30, 0.17, 0.08], n
    )
    df["points_balance"]    = rng.integers(0, 50_000, n)
    df["lifetime_points"]   = df["points_balance"] + rng.integers(0, 200_000, n)
    df["redemption_count"]  = rng.integers(0, 40, n)
    df["is_active_member"]  = rng.random(n) < 0.82

    save_parquet(df, f"{OUTPUT_DIR}/customers/dim_loyalty_members.parquet")
    save_csv(df,     f"{OUTPUT_DIR}/customers/dim_loyalty_members.csv")
    return df


def generate_rfm(customers_df: pd.DataFrame,
                 transactions_summary=None) -> pd.DataFrame:
    """
    RFM scoring table.  If a transactions_summary is passed it is used;
    otherwise synthetic RFM values are generated directly.
    """
    print("Generating fact_rfm …")
    n = len(customers_df)

    segments = weighted_choice(LOYALTY_SEGMENTS, SEGMENT_WEIGHTS, n)

    # RFM raw values driven by segment
    seg_recency_med = {
        "Loyalist": 7,  "Cherry Picker": 45, "Soccer Mom": 14,
        "Occasional Shopper": 90, "Lapsed": 270, "New Customer": 5,
    }
    seg_freq_med = {
        "Loyalist": 52, "Cherry Picker": 8, "Soccer Mom": 28,
        "Occasional Shopper": 4, "Lapsed": 2, "New Customer": 2,
    }
    seg_monetary_med = {
        "Loyalist": 6_500, "Cherry Picker": 800, "Soccer Mom": 3_200,
        "Occasional Shopper": 400, "Lapsed": 200, "New Customer": 150,
    }

    recency_days = np.array([
        max(1, int(rng.normal(seg_recency_med[s], seg_recency_med[s] * 0.4)))
        for s in segments
    ])
    frequency = np.array([
        max(1, int(rng.normal(seg_freq_med[s], seg_freq_med[s] * 0.3)))
        for s in segments
    ])
    monetary = np.array([
        max(1, int(rng.normal(seg_monetary_med[s], seg_monetary_med[s] * 0.35)))
        for s in segments
    ])

    # Score 1-5
    def quintile_score(arr):
        scores = np.zeros(len(arr), dtype=int)
        qs = np.percentile(arr, [20, 40, 60, 80])
        scores[arr <= qs[0]] = 5
        scores[(arr > qs[0]) & (arr <= qs[1])] = 4
        scores[(arr > qs[1]) & (arr <= qs[2])] = 3
        scores[(arr > qs[2]) & (arr <= qs[3])] = 2
        scores[arr > qs[3]] = 1
        return scores

    r_score = quintile_score(recency_days)  # lower recency → better score
    f_score = quintile_score(-frequency)    # higher freq → better score (negate)
    m_score = quintile_score(-monetary)

    df = pd.DataFrame({
        "customer_id":     customers_df["customer_id"].values,
        "region":          customers_df["region"].values,
        "recency_days":    recency_days,
        "frequency":       frequency,
        "monetary_usd":    monetary,
        "r_score":         r_score,
        "f_score":         f_score,
        "m_score":         m_score,
        "rfm_combined":    r_score * 100 + f_score * 10 + m_score,
        "loyalty_segment": segments,
        "churn_prob":      np.round(
            np.where(segments == "Lapsed", rng.uniform(0.65, 0.95, n),
            np.where(segments == "Occasional Shopper", rng.uniform(0.30, 0.60, n),
            rng.uniform(0.02, 0.25, n))), 4),
        "clv_12m_usd":     (monetary * frequency * rng.uniform(0.08, 0.15, n)).astype(int),
    })

    save_parquet(df, f"{OUTPUT_DIR}/customers/fact_rfm.parquet")
    save_csv(df,     f"{OUTPUT_DIR}/customers/fact_rfm.csv")
    return df
