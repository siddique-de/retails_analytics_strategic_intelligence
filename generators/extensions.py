"""
Extended data generators — derived from "Retail Analytics: The Secret Weapon"
(Emmett Cox, Wiley/SAS, 2012).

New tables produced
───────────────────
fact_price_elasticity      – price × volume demand curve per SKU/dept
fact_purchase_cycles       – inter-purchase interval & cycle by customer × dept
fact_competitor_intel      – weekly competitor price & promo intelligence
fact_space_planogram       – store × dept space allocation & performance
fact_customer_acquisition  – acquisition channel, cost, first-purchase metrics
fact_event_analysis        – special-event impact (holiday, weather, competitor open)
fact_atf_atv               – Average Transaction Frequency & Value deep-dive
"""

import numpy as np
import pandas as pd
from tqdm import tqdm
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import (OUTPUT_DIR, DEPARTMENTS, RANDOM_SEED, START_DATE, END_DATE)
from generators.base import rng, weighted_choice, date_range_array, save_csv, save_parquet


# ── 1. Price Elasticity & Demand Curves ──────────────────────────────────────

def generate_price_elasticity(products_df: pd.DataFrame, n_obs: int = 120_000) -> pd.DataFrame:
    """
    Simulates price-point × units-sold observations per SKU.
    Elasticity = % change in quantity / % change in price.
    Book reference: Ch. 5 – Pricing Analytics, demand curve construction.
    """
    print("Generating fact_price_elasticity …")

    # Sample SKUs weighted toward velocity A/B (more data points available)
    vel  = products_df["velocity_tier"].values
    p    = np.where(vel=="A",40,np.where(vel=="B",15,np.where(vel=="C",4,1))).astype(float)
    p   /= p.sum()
    idx  = rng.choice(len(products_df), size=n_obs, p=p)

    base_prices  = products_df["sell_price_usd"].values[idx]
    departments  = products_df["department"].values[idx]
    sku_ids      = products_df["sku_id"].values[idx]

    # Price varies ±30 % around base
    price_mult   = rng.uniform(0.70, 1.30, n_obs)
    test_price   = np.round(base_prices * price_mult, 2)

    # True elasticity drawn per department (perishables more elastic)
    dept_elast = {
        "Fresh Produce": -1.9, "Bakery": -1.5, "Dairy & Eggs": -1.3,
        "Meat & Seafood": -2.1, "Frozen Foods": -1.2, "Beverages": -0.9,
        "Snacks & Confectionery": -1.6, "Health & Beauty": -0.7,
        "Household": -0.8, "Baby & Toddler": -0.5, "Pet Supplies": -0.6,
        "Clothing & Apparel": -1.8, "Electronics": -2.2,
        "Stationery": -0.6, "Seasonal & Gardening": -1.4,
    }
    elast_arr   = np.array([dept_elast.get(d, -1.2) for d in departments])
    elast_noise = rng.normal(0, 0.2, n_obs)
    obs_elast   = elast_arr + elast_noise

    # Base demand driven by velocity tier
    vel_arr     = products_df["velocity_tier"].values[idx]
    base_demand = np.where(vel_arr=="A", 500, np.where(vel_arr=="B", 150,
                  np.where(vel_arr=="C", 40, 12))).astype(float)
    base_demand *= rng.uniform(0.5, 2.0, n_obs)

    pct_price_chg   = (test_price - base_prices) / base_prices.clip(min=0.01)
    units_sold      = np.maximum(1, np.round(base_demand * (1 + obs_elast * pct_price_chg), 0))
    revenue         = np.round(test_price * units_sold, 2)
    margin_usd      = np.round((test_price - products_df["cost_price_usd"].values[idx]) * units_sold, 2)

    # Price zones
    pct_vs_base = pct_price_chg * 100
    price_zone  = np.select(
        [pct_vs_base < -15, pct_vs_base < -5, pct_vs_base < 5, pct_vs_base < 15],
        ["Deep Discount", "Moderate Discount", "Regular", "Slight Premium"],
        default="Premium",
    )

    weeks = pd.date_range(START_DATE, END_DATE, freq="W-MON")
    week_dates = weeks[rng.integers(0, len(weeks), n_obs)]

    df = pd.DataFrame({
        "obs_id":           [f"ELAST{i+1:08d}" for i in range(n_obs)],
        "sku_id":           sku_ids,
        "department":       departments,
        "week_start":       week_dates,
        "base_price_usd":   np.round(base_prices, 2),
        "test_price_usd":   test_price,
        "price_change_pct": np.round(pct_price_chg * 100, 2),
        "price_zone":       price_zone,
        "units_sold":       units_sold.astype(int),
        "revenue_usd":      revenue,
        "margin_usd":       margin_usd,
        "elasticity":       np.round(obs_elast, 3),
        "is_promo_price":   pct_vs_base < -5,
    })

    save_parquet(df, f"{OUTPUT_DIR}/extensions/fact_price_elasticity.parquet")
    save_csv(df.sample(min(50_000, len(df)), random_state=42),
             f"{OUTPUT_DIR}/extensions/fact_price_elasticity_sample.csv")
    return df


# ── 2. Purchase Cycle Analytics ──────────────────────────────────────────────

def generate_purchase_cycles(customers_df: pd.DataFrame,
                              n_records: int = 80_000) -> pd.DataFrame:
    """
    Inter-purchase interval per customer × department.
    Book reference: Ch. 6 – Purchase Cycle Analysis.
    Enables: when to send re-engagement offers, predict next purchase date.
    """
    print("Generating fact_purchase_cycles …")

    cust_ids = customers_df["customer_id"].values

    # Realistic cycle medians (days) by department
    dept_cycle_med = {
        "Fresh Produce": 4,  "Bakery": 5, "Dairy & Eggs": 6,
        "Meat & Seafood": 8, "Frozen Foods": 14, "Beverages": 10,
        "Snacks & Confectionery": 12, "Health & Beauty": 30,
        "Household": 21, "Baby & Toddler": 14, "Pet Supplies": 30,
        "Clothing & Apparel": 60, "Electronics": 120,
        "Stationery": 45, "Seasonal & Gardening": 90,
    }

    rows = []
    cust_idx = rng.integers(0, len(cust_ids), n_records)
    dept_choices = rng.choice(DEPARTMENTS, n_records)

    for i in range(n_records):
        dept = dept_choices[i]
        med  = dept_cycle_med.get(dept, 30)
        avg_cycle = max(1, rng.normal(med, med * 0.35))
        n_purchases = max(1, int(rng.normal(365 / avg_cycle, 2)))
        days_since_last = max(0, int(rng.exponential(avg_cycle)))
        next_predicted  = int(avg_cycle * rng.uniform(0.8, 1.2))
        # Overdue flag: last purchase > 1.5× expected cycle
        is_overdue = days_since_last > (avg_cycle * 1.5)
        rows.append({
            "customer_id":         cust_ids[cust_idx[i]],
            "department":          dept,
            "avg_cycle_days":      round(avg_cycle, 1),
            "n_purchases_12m":     n_purchases,
            "days_since_last_purchase": days_since_last,
            "predicted_next_days": next_predicted,
            "is_overdue":          bool(is_overdue),
            "cycle_stability":     round(max(0, 1 - rng.uniform(0, 0.5)), 3),
        })

    df = pd.DataFrame(rows)
    save_parquet(df, f"{OUTPUT_DIR}/extensions/fact_purchase_cycles.parquet")
    save_csv(df,     f"{OUTPUT_DIR}/extensions/fact_purchase_cycles.csv")
    return df


# ── 3. Competitor Intelligence ───────────────────────────────────────────────

def generate_competitor_intel(stores_df: pd.DataFrame,
                               products_df: pd.DataFrame,
                               n_records: int = 50_000) -> pd.DataFrame:
    """
    Weekly competitor price + promo observations.
    Book reference: Ch. 8 – Competitive Intelligence.
    """
    print("Generating fact_competitor_intel …")

    COMPETITORS = ["CompetitorA", "CompetitorB", "CompetitorC",
                   "PrivateLabelRival", "DiscountChain"]
    weeks       = pd.date_range(START_DATE, END_DATE, freq="W-MON")

    vel  = products_df["velocity_tier"].values
    p    = np.where(vel=="A",40,np.where(vel=="B",15,np.where(vel=="C",4,1))).astype(float)
    p   /= p.sum()
    idx  = rng.choice(len(products_df), size=n_records, p=p)

    own_price   = products_df["sell_price_usd"].values[idx]
    comp_mult   = rng.uniform(0.80, 1.25, n_records)
    comp_price  = np.round(own_price * comp_mult, 2)
    price_gap   = np.round((own_price - comp_price) / comp_price.clip(min=0.01) * 100, 2)

    df = pd.DataFrame({
        "record_id":           [f"COMP{i+1:08d}" for i in range(n_records)],
        "week_start":          weeks[rng.integers(0, len(weeks), n_records)],
        "region":              weighted_choice(list(stores_df["region"].unique()),
                                               [1]*len(stores_df["region"].unique()), n_records),
        "competitor":          rng.choice(COMPETITORS, n_records),
        "sku_id":              products_df["sku_id"].values[idx],
        "department":          products_df["department"].values[idx],
        "own_price_usd":       np.round(own_price, 2),
        "competitor_price_usd":comp_price,
        "price_gap_pct":       price_gap,
        "own_on_promo":        rng.random(n_records) < 0.18,
        "comp_on_promo":       rng.random(n_records) < 0.20,
        "comp_has_feature":    rng.random(n_records) < 0.15,
        "price_position":      np.where(price_gap > 5, "Premium",
                               np.where(price_gap < -5, "Value", "Parity")),
    })

    save_parquet(df, f"{OUTPUT_DIR}/extensions/fact_competitor_intel.parquet")
    save_csv(df.sample(min(30_000, len(df)), random_state=42),
             f"{OUTPUT_DIR}/extensions/fact_competitor_intel_sample.csv")
    return df


# ── 4. Space / Planogram Performance ─────────────────────────────────────────

def generate_space_planogram(stores_df: pd.DataFrame) -> pd.DataFrame:
    """
    Store × department space allocation vs. sales performance.
    Book reference: Ch. 7 – Space Management & Planogram Analytics.
    """
    print("Generating fact_space_planogram …")

    rows = []
    for _, store in stores_df.iterrows():
        total_sqft = store["size_sqft"]
        for dept in DEPARTMENTS:
            alloc_pct = rng.uniform(0.03, 0.18)
            dept_sqft = int(total_sqft * alloc_pct)
            sales_per_sqft = rng.uniform(80, 900)
            dept_sales = dept_sqft * sales_per_sqft

            # Optimal allocation based on sales productivity
            optimal_pct  = alloc_pct * rng.uniform(0.75, 1.35)
            space_gap    = round((optimal_pct - alloc_pct) * 100, 2)
            adjacencies  = rng.choice(DEPARTMENTS, size=rng.integers(1, 4), replace=False).tolist()
            adjacencies  = [a for a in adjacencies if a != dept][:3]

            rows.append({
                "store_id":            store["store_id"],
                "region":              store["region"],
                "department":          dept,
                "allocated_sqft":      dept_sqft,
                "allocated_pct":       round(alloc_pct * 100, 2),
                "optimal_pct":         round(optimal_pct * 100, 2),
                "space_gap_pct":       space_gap,
                "sales_per_sqft":      round(sales_per_sqft, 2),
                "dept_revenue_annual": round(dept_sales, 2),
                "planogram_compliance_pct": round(rng.uniform(55, 99), 1),
                "n_fixtures":          rng.integers(4, 40),
                "avg_shelf_height_cm": rng.integers(150, 220),
                "adjacency_depts":     "|".join(adjacencies),
                "is_endcap_dept":      rng.random() < 0.25,
                "impulse_zone":        rng.random() < 0.15,
            })

    df = pd.DataFrame(rows)
    save_parquet(df, f"{OUTPUT_DIR}/extensions/fact_space_planogram.parquet")
    save_csv(df,     f"{OUTPUT_DIR}/extensions/fact_space_planogram.csv")
    return df


# ── 5. Customer Acquisition Analytics ────────────────────────────────────────

def generate_customer_acquisition(customers_df: pd.DataFrame) -> pd.DataFrame:
    """
    Customer acquisition channel, cost, and first-30/90-day behaviour.
    Book reference: Ch. 4 – Customer Acquisition & Onboarding.
    """
    print("Generating fact_customer_acquisition …")
    n = len(customers_df)

    CHANNELS = ["In-Store Sign-Up", "Digital Ad", "Referral", "Direct Mail",
                "Social Media", "Email Campaign", "Event/Sampling", "App Download"]
    CHAN_W   = [0.30, 0.18, 0.15, 0.10, 0.12, 0.07, 0.05, 0.03]
    acq_channels = weighted_choice(CHANNELS, CHAN_W, n)

    # CAC by channel
    cac_map = {"In-Store Sign-Up":8, "Digital Ad":35, "Referral":12, "Direct Mail":22,
               "Social Media":28, "Email Campaign":15, "Event/Sampling":45, "App Download":18}
    cac = np.array([cac_map[c] * rng.uniform(0.7, 1.4) for c in acq_channels])

    # First 30/90 day spend
    first_30d  = rng.uniform(0, 200, n)
    first_90d  = first_30d + rng.uniform(0, 350, n)
    activated  = first_30d > 20          # made at least one meaningful purchase
    repeat_30d = rng.random(n) < np.where(activated, 0.60, 0.20)

    df = customers_df[["customer_id","region","enroll_date"]].copy()
    df["acquisition_channel"]   = acq_channels
    df["acquisition_cost_usd"]  = np.round(cac, 2)
    df["first_30d_spend_usd"]   = np.round(first_30d, 2)
    df["first_90d_spend_usd"]   = np.round(first_90d, 2)
    df["is_activated"]          = activated
    df["repeat_purchase_30d"]   = repeat_30d
    df["channel_roi"]           = np.round(first_90d / cac.clip(min=0.01), 3)
    df["payback_period_days"]   = np.round(cac / (first_90d / 90).clip(min=0.01), 0).astype(int)

    save_parquet(df, f"{OUTPUT_DIR}/extensions/fact_customer_acquisition.parquet")
    save_csv(df,     f"{OUTPUT_DIR}/extensions/fact_customer_acquisition.csv")
    return df


# ── 6. Event Impact Analysis ─────────────────────────────────────────────────

def generate_event_analysis(stores_df: pd.DataFrame) -> pd.DataFrame:
    """
    Special-event uplift: holiday, weather shock, competitor opening, local event.
    Book reference: Ch. 9 – Event & External Factor Analytics.
    """
    print("Generating fact_event_analysis …")

    EVENTS = {
        "Christmas Week":       {"prob": 0.08, "uplift_range": (1.40, 2.20)},
        "Easter":               {"prob": 0.04, "uplift_range": (1.15, 1.60)},
        "Back to School":       {"prob": 0.05, "uplift_range": (1.10, 1.50)},
        "Black Friday":         {"prob": 0.02, "uplift_range": (1.60, 2.80)},
        "Valentine Day":        {"prob": 0.02, "uplift_range": (1.08, 1.30)},
        "Heatwave/Snow Event":  {"prob": 0.06, "uplift_range": (0.70, 1.40)},
        "Competitor Opening":   {"prob": 0.03, "uplift_range": (0.60, 0.90)},
        "Local Sports Event":   {"prob": 0.05, "uplift_range": (1.05, 1.25)},
        "Public Holiday":       {"prob": 0.10, "uplift_range": (0.85, 1.30)},
        "Pay Day Week":         {"prob": 0.08, "uplift_range": (1.10, 1.35)},
    }

    all_weeks = pd.date_range(START_DATE, END_DATE, freq="W-MON")
    rows = []

    for _, store in stores_df.iterrows():
        for event_name, meta in EVENTS.items():
            # Each store × event has several occurrences per year
            n_occ = max(1, int(len(all_weeks) * meta["prob"] / 52 * 6))
            for _ in range(n_occ):
                wk         = all_weeks[rng.integers(0, len(all_weeks))]
                uplift_f   = rng.uniform(*meta["uplift_range"])
                base_sales = rng.uniform(50_000, 800_000)
                event_sales = base_sales * uplift_f
                dept_impact = weighted_choice(DEPARTMENTS, [1/len(DEPARTMENTS)]*len(DEPARTMENTS), 1)[0]
                rows.append({
                    "store_id":         store["store_id"],
                    "region":           store["region"],
                    "event_type":       event_name,
                    "event_week":       wk,
                    "primary_dept":     dept_impact,
                    "baseline_sales":   round(base_sales, 2),
                    "event_sales":      round(event_sales, 2),
                    "uplift_factor":    round(uplift_f, 3),
                    "uplift_pct":       round((uplift_f - 1) * 100, 2),
                    "incremental_usd":  round(event_sales - base_sales, 2),
                    "was_prepared":     rng.random() < 0.70,
                    "staff_added":      max(0, int(rng.normal(3, 2))) if uplift_f > 1.1 else 0,
                })

    df = pd.DataFrame(rows)
    save_parquet(df, f"{OUTPUT_DIR}/extensions/fact_event_analysis.parquet")
    save_csv(df.sample(min(100_000, len(df)), random_state=42),
             f"{OUTPUT_DIR}/extensions/fact_event_analysis_sample.csv")
    return df


# ── 7. ATF / ATV Deep Dive ───────────────────────────────────────────────────

def generate_atf_atv(customers_df: pd.DataFrame,
                     rfm_df: pd.DataFrame) -> pd.DataFrame:
    """
    Average Transaction Frequency (ATF) and Average Transaction Value (ATV)
    by customer segment, region, store format, and time period.
    Book reference: Ch. 3 – ATF & ATV KPIs (core retail health metrics).
    """
    print("Generating fact_atf_atv …")

    merged = customers_df[["customer_id","region","age_group","gender"]].merge(
        rfm_df[["customer_id","loyalty_segment","frequency","monetary_usd","clv_12m_usd"]], 
        on="customer_id"
    )

    # ATF = frequency per year; ATV = monetary / frequency
    merged["atf"]        = merged["frequency"]
    merged["atv"]        = np.round(merged["monetary_usd"] / merged["frequency"].clip(lower=1), 2)
    merged["atv_x_atf"]  = np.round(merged["atv"] * merged["atf"], 2)   # = annual spend

    # Add store format dimension (random assignment for demo)
    from config import STORE_FORMATS
    merged["preferred_format"] = rng.choice(STORE_FORMATS, len(merged))

    # Segment KPI table
    seg_kpi = (merged.groupby(["loyalty_segment","region"])
               .agg(n_customers=("customer_id","count"),
                    avg_atf=("atf","mean"),
                    avg_atv=("atv","mean"),
                    avg_annual_spend=("atv_x_atf","mean"),
                    avg_clv=("clv_12m_usd","mean"))
               .reset_index())
    seg_kpi["atf_x_atv"] = np.round(seg_kpi["avg_atf"] * seg_kpi["avg_atv"], 2)

    save_parquet(seg_kpi, f"{OUTPUT_DIR}/extensions/fact_atf_atv.parquet")
    save_csv(seg_kpi,     f"{OUTPUT_DIR}/extensions/fact_atf_atv.csv")

    # Full customer-level table too
    save_parquet(merged, f"{OUTPUT_DIR}/extensions/fact_atf_atv_detail.parquet")
    return seg_kpi
