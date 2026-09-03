"""
Store master & GIS/site-selection data generator.

Tables produced
───────────────
dim_stores          – store master with lat/lon, format, region, open date
dim_trade_areas     – one row per store with GIS-derived trade-area metrics
fact_site_selection – candidate site evaluation dataset (gravity model inputs)
"""

import numpy as np
import pandas as pd
from faker import Faker
from tqdm import tqdm

from config import REGIONS, SITE_SELECTION_FEATURES, STORE_FORMATS, OUTPUT_DIR, RANDOM_SEED
from generators.base import rng, weighted_choice, save_csv, save_parquet

# Regional bounding boxes  [lat_min, lat_max, lon_min, lon_max]
REGION_BBOX = {
    "US":  [25.0,  49.0, -124.0,  -67.0],
    "AU":  [-38.0, -15.0,  115.0,  153.0],
    "UK":  [50.0,  58.5,   -5.5,    1.8],
    "EE":  [46.0,  55.0,   14.0,   32.0],
    "RU":  [50.0,  60.0,   30.0,   60.0],
    "UAE": [22.6,  26.1,   51.5,   56.4],
}

# Realistic population-density weights by format
FORMAT_WEIGHTS = [0.20, 0.40, 0.25, 0.10, 0.05]   # matches STORE_FORMATS order


def _fake_for_region(region_code: str) -> Faker:
    locale = REGIONS[region_code]["locale"]
    return Faker(locale)


def generate_stores() -> pd.DataFrame:
    print("Generating dim_stores …")
    rows = []
    store_id = 1
    for region_code, meta in REGIONS.items():
        fake = _fake_for_region(region_code)
        Faker.seed(RANDOM_SEED + store_id)
        bbox = REGION_BBOX[region_code]
        n = meta["store_count"]

        lats = rng.uniform(bbox[0], bbox[1], n)
        lons = rng.uniform(bbox[2], bbox[3], n)
        formats = weighted_choice(STORE_FORMATS, FORMAT_WEIGHTS, n)
        open_years = rng.integers(1985, 2023, n)
        open_months = rng.integers(1, 13, n)
        sizes_sqft = rng.integers(3_000, 120_000, n)

        for i in range(n):
            rows.append({
                "store_id":        f"STR{store_id:05d}",
                "store_name":      f"{meta['country']} Store {store_id:05d}",
                "region":          region_code,
                "country":         meta["country"],
                "currency":        meta["currency"],
                "format":          formats[i],
                "latitude":        round(float(lats[i]), 6),
                "longitude":       round(float(lons[i]), 6),
                "city":            fake.city(),
                "state_province":  fake.state() if hasattr(fake, "state") else fake.city(),
                "postal_code":     fake.postcode(),
                "size_sqft":       int(sizes_sqft[i]),
                "open_date":       pd.Timestamp(year=int(open_years[i]),
                                               month=int(open_months[i]), day=1),
                "is_active":       True,
            })
            store_id += 1

    df = pd.DataFrame(rows)
    save_parquet(df, f"{OUTPUT_DIR}/stores/dim_stores.parquet")
    save_csv(df, f"{OUTPUT_DIR}/stores/dim_stores.csv")
    return df


def generate_trade_areas(stores_df: pd.DataFrame) -> pd.DataFrame:
    print("Generating dim_trade_areas …")
    n = len(stores_df)
    pop_base = rng.integers(10_000, 500_000, n)

    df = stores_df[["store_id", "region", "format", "latitude", "longitude"]].copy()
    df["pop_1mi"]                = (pop_base * rng.uniform(0.05, 0.12, n)).astype(int)
    df["pop_3mi"]                = (pop_base * rng.uniform(0.25, 0.45, n)).astype(int)
    df["pop_5mi"]                = (pop_base * rng.uniform(0.55, 0.90, n)).astype(int)
    df["median_hh_income_usd"]   = rng.integers(28_000, 140_000, n)
    df["competitor_count_3mi"]   = rng.integers(0, 12, n)
    df["traffic_count_daily"]    = rng.integers(2_000, 85_000, n)
    df["parking_spaces"]         = rng.integers(50, 1_200, n)
    df["proximity_transit_mi"]   = np.round(rng.uniform(0.1, 5.0, n), 2)
    df["daytime_pop_density"]    = rng.integers(500, 25_000, n)
    df["residential_density"]    = rng.integers(200, 15_000, n)
    df["drive_time_nearest_store_min"] = np.round(rng.uniform(1.0, 45.0, n), 1)
    # Gravity model score  (simple Huff-style: pop / distance^2 relative to competitors)
    df["gravity_score"]          = np.round(
        df["pop_3mi"] / (df["drive_time_nearest_store_min"] ** 2 + 1), 2
    )
    # Predicted annual sales derived from gravity + income
    df["predicted_annual_sales_usd"] = (
        df["gravity_score"] * df["median_hh_income_usd"] * rng.uniform(0.004, 0.012, n)
    ).astype(int)
    df["breakeven_years_before"] = np.round(rng.uniform(4, 8, n), 1)
    df["breakeven_years_after"]  = np.round(rng.uniform(1.5, 3.0, n), 1)

    save_parquet(df, f"{OUTPUT_DIR}/stores/dim_trade_areas.parquet")
    save_csv(df, f"{OUTPUT_DIR}/stores/dim_trade_areas.csv")
    return df


def generate_site_selection_candidates(stores_df: pd.DataFrame) -> pd.DataFrame:
    """
    Candidate sites for new stores – the evaluation dataset fed into
    the gravity / transfer-sales model.
    """
    print("Generating fact_site_selection …")
    n_candidates = len(stores_df) * 3    # 3 evaluated candidates per existing store on avg

    # Draw random region for each candidate proportional to region store counts
    regions = list(REGIONS.keys())
    region_weights = [REGIONS[r]["store_count"] for r in regions]

    candidate_regions = weighted_choice(regions, region_weights, n_candidates)
    bboxes = np.array([REGION_BBOX[r] for r in candidate_regions])

    lats = rng.uniform(bboxes[:, 0], bboxes[:, 1])
    lons = rng.uniform(bboxes[:, 2], bboxes[:, 3])
    pop_base = rng.integers(5_000, 600_000, n_candidates)

    df = pd.DataFrame({
        "candidate_id":         [f"CAND{i+1:06d}" for i in range(n_candidates)],
        "region":               candidate_regions,
        "latitude":             np.round(lats, 6),
        "longitude":            np.round(lons, 6),
        "proposed_format":      weighted_choice(STORE_FORMATS, FORMAT_WEIGHTS, n_candidates),
        "population_1mi":       (pop_base * rng.uniform(0.05, 0.12, n_candidates)).astype(int),
        "population_3mi":       (pop_base * rng.uniform(0.25, 0.45, n_candidates)).astype(int),
        "population_5mi":       (pop_base * rng.uniform(0.55, 0.90, n_candidates)).astype(int),
        "median_hh_income":     rng.integers(25_000, 150_000, n_candidates),
        "competitor_count_3mi": rng.integers(0, 15, n_candidates),
        "traffic_count_daily":  rng.integers(1_000, 100_000, n_candidates),
        "parking_spaces":       rng.integers(40, 1_500, n_candidates),
        "proximity_transit_mi": np.round(rng.uniform(0.1, 6.0, n_candidates), 2),
        "daytime_pop_density":  rng.integers(300, 30_000, n_candidates),
        "residential_density":  rng.integers(100, 20_000, n_candidates),
        "drive_time_nearest_store_min": np.round(rng.uniform(0.5, 60.0, n_candidates), 1),
        "site_lease_cost_annual_usd":   rng.integers(50_000, 2_000_000, n_candidates),
        "build_out_cost_usd":           rng.integers(500_000, 15_000_000, n_candidates),
        "gravity_score":                None,  # computed below
        "forecast_yr1_sales_usd":       None,
        "forecast_breakeven_yrs":       None,
        "selected":                     None,
    })

    df["gravity_score"] = np.round(
        df["population_3mi"] / (df["drive_time_nearest_store_min"] ** 2 + 1), 2
    )
    df["forecast_yr1_sales_usd"] = (
        df["gravity_score"] * df["median_hh_income"] * rng.uniform(0.003, 0.011, n_candidates)
    ).astype(int)
    total_cost = df["site_lease_cost_annual_usd"] + df["build_out_cost_usd"] / 10
    df["forecast_breakeven_yrs"] = np.round(
        total_cost / (df["forecast_yr1_sales_usd"].clip(lower=1) * 0.08), 1
    ).clip(upper=15)
    df["selected"] = (df["gravity_score"] > df["gravity_score"].quantile(0.60)).astype(int)

    save_parquet(df, f"{OUTPUT_DIR}/stores/fact_site_selection.parquet")
    save_csv(df, f"{OUTPUT_DIR}/stores/fact_site_selection.csv")
    return df
