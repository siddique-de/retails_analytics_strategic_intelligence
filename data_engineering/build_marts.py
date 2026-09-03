"""
Data Engineering: Build pre-aggregated mart tables from raw Parquet files.
Run once (or on refresh) to produce fast-loading datasets for the dashboard.

Output: output/marts/*.parquet
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd

RAW   = os.path.join(os.path.dirname(__file__), "..", "output")
MARTS = os.path.join(RAW, "marts")
os.makedirs(MARTS, exist_ok=True)


def _save(df: pd.DataFrame, name: str):
    path = os.path.join(MARTS, f"{name}.parquet")
    df.to_parquet(path, index=False, engine="pyarrow", compression="snappy")
    print(f"  ✓ {name}.parquet  ({len(df):,} rows)")
    return df


def _read(domain: str, table: str) -> pd.DataFrame:
    path = os.path.join(RAW, domain, f"{table}.parquet")
    return pd.read_parquet(path)


# ─────────────────────────────────────────────────────────────────────────────
# 1. EXECUTIVE SUMMARY MART
# ─────────────────────────────────────────────────────────────────────────────
def build_exec_summary():
    print("\n[1] Executive Summary Mart")

    txn = _read("transactions", "fact_transactions")
    txn["transaction_date"] = pd.to_datetime(txn["transaction_date"])
    txn["year"]  = txn["transaction_date"].dt.year
    txn["month"] = txn["transaction_date"].dt.to_period("M").astype(str)
    txn["week"]  = txn["transaction_date"].dt.to_period("W").astype(str)

    stores = _read("stores", "dim_stores")[["store_id", "region", "size_sqft", "format"]]
    txn    = txn.merge(stores, on="store_id", how="left")

    products = _read("products", "dim_products")[["sku_id", "cost_price_usd", "sell_price_usd",
                                                   "department", "margin_pct"]]

    # Monthly sales summary
    monthly = (txn.groupby(["month", "region"])
               .agg(
                   total_sales=("basket_total_usd", "sum"),
                   txn_count=("transaction_id", "count"),
                   unique_customers=("customer_id", "nunique"),
                   avg_basket=("basket_total_usd", "mean"),
                   avg_items=("item_count", "mean"),
               ).reset_index())
    monthly["atv"] = monthly["total_sales"] / monthly["txn_count"].clip(lower=1)
    _save(monthly, "exec_monthly_sales")

    # Store-level KPIs
    store_kpi = (txn.groupby("store_id")
                 .agg(
                     total_sales=("basket_total_usd", "sum"),
                     txn_count=("transaction_id", "count"),
                     unique_customers=("customer_id", "nunique"),
                 ).reset_index()
                 .merge(stores, on="store_id"))
    store_kpi["sales_per_sqft_actual"] = store_kpi["total_sales"] / store_kpi["size_sqft"].clip(lower=1)
    store_kpi["atv"]                   = store_kpi["total_sales"] / store_kpi["txn_count"].clip(lower=1)
    _save(store_kpi, "exec_store_kpi")

    # Daily sales trend (all regions)
    daily = (txn.groupby("transaction_date")
             .agg(total_sales=("basket_total_usd","sum"),
                  txn_count=("transaction_id","count"))
             .reset_index())
    daily["rolling_7d"] = daily["total_sales"].rolling(7, min_periods=1).mean()
    _save(daily, "exec_daily_trend")

    # Simple inventory turnover proxy
    inv = _read("merchandise", "fact_inventory")
    inv_turn = (inv.groupby("store_id")
                .agg(avg_on_hand=("on_hand_units","mean"),
                     total_demand=("demand_units","sum"))
                .reset_index())
    inv_turn["inv_turnover"] = inv_turn["total_demand"] / inv_turn["avg_on_hand"].clip(lower=1)
    _save(inv_turn, "exec_inv_turnover")

    return monthly


# ─────────────────────────────────────────────────────────────────────────────
# 2. MERCHANDISE / CATEGORY MART
# ─────────────────────────────────────────────────────────────────────────────
def build_merchandise_mart():
    print("\n[2] Merchandise Mart")

    bd  = _read("transactions", "fact_basket_detail")
    bd["transaction_date"] = pd.to_datetime(bd["transaction_date"])
    bd["month"] = bd["transaction_date"].dt.to_period("M").astype(str)
    bd["year"]  = bd["transaction_date"].dt.year

    prod = _read("products", "dim_products")

    # Ensure product columns are present (basket_detail already has dept from generator)
    bd = bd.merge(prod[["sku_id","margin_pct","velocity_tier","cost_price_usd"]],
                  on="sku_id", how="left")

    # Category scorecard
    cat = (bd.groupby(["department","month"])
             .agg(
                 revenue=("extended_price_usd","sum"),
                 units_sold=("quantity","sum"),
                 txn_count=("transaction_id","nunique"),
                 avg_margin=("margin_pct","mean"),
             ).reset_index())
    cat["revenue_share"] = cat.groupby("month")["revenue"].transform(lambda x: x/x.sum()*100)
    _save(cat, "merch_category_scorecard")

    # SKU productivity
    sku_perf = (bd.groupby(["sku_id","department","velocity_tier"])
                  .agg(
                      revenue=("extended_price_usd","sum"),
                      units=("quantity","sum"),
                      baskets=("transaction_id","nunique"),
                  ).reset_index())
    sku_perf["revenue_per_basket"] = sku_perf["revenue"] / sku_perf["baskets"].clip(lower=1)
    _save(sku_perf, "merch_sku_productivity")

    # Promotion effectiveness
    uplift = _read("promotions", "fact_promo_uplift")
    promo_eff = (uplift.groupby(["promo_type","department"])
                 .agg(
                     avg_baseline=("baseline_sales_usd","mean"),
                     avg_promo_sales=("promo_period_sales_usd","mean"),
                     avg_incremental=("true_incremental_usd","mean"),
                     avg_roi=("roi","mean"),
                     pct_markdown_avoidable=("markdown_avoidable","mean"),
                 ).reset_index())
    promo_eff["lift_pct"] = ((promo_eff["avg_promo_sales"] - promo_eff["avg_baseline"])
                              / promo_eff["avg_baseline"].clip(lower=1) * 100)
    _save(promo_eff, "merch_promo_effectiveness")

    # Markdown / clearance indicator from promo types
    promos = _read("promotions", "dim_promotions")
    markdown = promos[promos["promo_type"].isin(["Clearance","Percentage Off"])].copy()
    markdown["discount_pct"] = markdown["discount_rate"] * 100
    _save(markdown[["promo_id","promo_type","department","discount_pct","budget_usd",
                     "promo_start_date","promo_end_date"]], "merch_markdowns")

    # Demand forecast accuracy — department already in fact_demand_forecast
    fcst = _read("merchandise", "fact_demand_forecast")
    fcst_dept = (fcst.groupby(["department","model_version"])
                     .agg(avg_mape=("mape_pct","mean"), n=("forecast_id","count"))
                     .reset_index())
    _save(fcst_dept, "merch_forecast_accuracy")

    return cat


# ─────────────────────────────────────────────────────────────────────────────
# 3. STORE OPERATIONS MART
# ─────────────────────────────────────────────────────────────────────────────
def build_store_ops_mart():
    print("\n[3] Store Operations Mart")

    txn      = _read("transactions", "fact_transactions")
    txn["transaction_date"] = pd.to_datetime(txn["transaction_date"])
    stores   = _read("stores",       "dim_stores")
    traffic  = _read("store_ops",    "fact_store_traffic")
    traffic["traffic_date"] = pd.to_datetime(traffic["traffic_date"])
    labour   = _read("store_ops",    "fact_labour_schedule")
    labour["transaction_date"] = pd.to_datetime(labour["transaction_date"])
    clusters = _read("store_ops",    "dim_store_clusters")
    layout   = _read("store_ops",    "fact_layout_test_results")
    trade    = _read("stores",       "dim_trade_areas")

    # Store health scorecard
    store_sales = (txn.groupby("store_id")
                   .agg(total_sales=("basket_total_usd","sum"),
                        txn_count=("transaction_id","count"),
                        avg_basket=("basket_total_usd","mean"))
                   .reset_index())

    traffic_agg = (traffic.groupby("store_id")
                   .agg(avg_traffic=("foot_traffic","mean"),
                        avg_conversion=("conversion_rate","mean"),
                        avg_dwell=("dwell_time_min","mean"),
                        avg_impulse=("impulse_purchase_rate","mean"))
                   .reset_index())

    labour_agg = (labour.groupby("store_id")
                  .agg(avg_queue=("avg_queue_length","mean"),
                       sla_pct=("sla_met","mean"),
                       total_labour_cost=("labour_cost_usd","sum"))
                  .reset_index())

    store_health = (stores[["store_id","region","format","size_sqft","country"]]
                    .merge(store_sales,  on="store_id", how="left")
                    .merge(traffic_agg,  on="store_id", how="left")
                    .merge(labour_agg,   on="store_id", how="left")
                    .merge(clusters[["store_id","cluster_label"]], on="store_id", how="left")
                    .merge(trade[["store_id","gravity_score","competitor_count_3mi"]], on="store_id", how="left"))

    store_health["sales_per_sqft_actual"] = (store_health["total_sales"]
                                              / store_health["size_sqft"].clip(lower=1))
    store_health["labour_pct_sales"] = (store_health["total_labour_cost"]
                                         / store_health["total_sales"].clip(lower=1) * 100)
    _save(store_health, "ops_store_health")

    # Hourly labour heatmap
    labour_heat = (labour.groupby(["store_id","hour_of_day"])
                   .agg(avg_queue=("avg_queue_length","mean"),
                        sla_pct=("sla_met","mean"),
                        avg_staff=("staff_rostered","mean"),
                        avg_txns=("txn_count","mean"))
                   .reset_index())
    _save(labour_heat, "ops_labour_heatmap")

    # Layout test summary
    layout_sum = (layout.groupby("department")
                  .agg(avg_uplift=("sales_uplift_pct","mean"),
                       avg_sku_reduction=("sku_reduction_pct","mean"),
                       avg_dwell_gain=("avg_dwell_after_min","mean"),
                       avg_impulse_gain=("impulse_rate_after","mean"),
                       n_stores=("store_id","nunique"))
                  .reset_index())
    _save(layout_sum, "ops_layout_summary")

    # Trade area / GIS data
    site = _read("stores", "fact_site_selection")
    _save(site, "ops_site_selection")

    # Daily traffic trend
    traffic_daily = (traffic.groupby("traffic_date")
                     .agg(avg_traffic=("foot_traffic","mean"),
                          avg_conversion=("conversion_rate","mean"))
                     .reset_index())
    _save(traffic_daily, "ops_traffic_trend")

    return store_health


# ─────────────────────────────────────────────────────────────────────────────
# 4. CUSTOMER & LOYALTY MART
# ─────────────────────────────────────────────────────────────────────────────
def build_customer_mart():
    print("\n[4] Customer & Loyalty Mart")

    cust    = _read("customers", "dim_customers")
    rfm     = _read("customers", "fact_rfm")
    loyalty = _read("customers", "dim_loyalty_members")
    txn     = _read("transactions", "fact_transactions")
    txn["transaction_date"] = pd.to_datetime(txn["transaction_date"])

    # RFM segment summary
    seg = (rfm.groupby("loyalty_segment")
           .agg(n_customers=("customer_id","count"),
                avg_recency=("recency_days","mean"),
                avg_frequency=("frequency","mean"),
                avg_monetary=("monetary_usd","mean"),
                avg_churn_prob=("churn_prob","mean"),
                avg_clv=("clv_12m_usd","mean"))
           .reset_index())
    seg["revenue_contribution"] = seg["n_customers"] * seg["avg_monetary"]
    seg["revenue_share"] = seg["revenue_contribution"] / seg["revenue_contribution"].sum() * 100
    _save(seg, "cust_rfm_segments")

    # Customer demographics
    demo = (cust.merge(rfm[["customer_id","loyalty_segment","churn_prob","clv_12m_usd"]], on="customer_id"))
    _save(demo, "cust_demographics")

    # Loyalty funnel
    loy_agg = pd.DataFrame({
        "stage": ["Total Customers","Loyalty Members","Active Members",
                  "Gold/Platinum","Redeemers"],
        "count": [
            len(cust),
            len(loyalty),
            loyalty["is_active_member"].sum(),
            loyalty[loyalty["loyalty_tier"].isin(["Gold","Platinum"])].shape[0],
            loyalty[loyalty["redemption_count"] > 0].shape[0],
        ]
    })
    _save(loy_agg, "cust_loyalty_funnel")

    # Loyalty tier breakdown
    tier = (loyalty.merge(rfm[["customer_id","loyalty_segment","clv_12m_usd","churn_prob"]],
                           on="customer_id", how="left")
            .groupby("loyalty_tier")
            .agg(n=("customer_id","count"),
                 avg_points=("points_balance","mean"),
                 avg_lifetime_pts=("lifetime_points","mean"),
                 avg_redemptions=("redemption_count","mean"),
                 avg_clv=("clv_12m_usd","mean"),
                 avg_churn=("churn_prob","mean"))
            .reset_index())
    _save(tier, "cust_loyalty_tiers")

    # Cohort retention (monthly cohorts)
    txn_cust = txn[txn["customer_id"].notna()].copy()
    txn_cust["customer_id"] = txn_cust["customer_id"].astype(str)
    cust_enroll = cust[["customer_id","enroll_date"]].copy()
    cust_enroll["enroll_date"] = pd.to_datetime(cust_enroll["enroll_date"])
    cust_enroll["cohort"] = cust_enroll["enroll_date"].dt.to_period("M").astype(str)

    txn_cust = txn_cust.merge(cust_enroll, on="customer_id", how="left")
    txn_cust["txn_period"] = txn_cust["transaction_date"].dt.to_period("M").astype(str)

    cohort = (txn_cust.groupby(["cohort","txn_period"])["customer_id"]
              .nunique().reset_index(name="active_customers"))
    cohort_size = (txn_cust.groupby("cohort")["customer_id"]
                   .nunique().reset_index(name="cohort_size"))
    cohort = cohort.merge(cohort_size, on="cohort")
    cohort["retention_rate"] = cohort["active_customers"] / cohort["cohort_size"] * 100
    _save(cohort, "cust_cohort_retention")

    # Churn risk distribution — include RFM columns needed by predictive page
    churn_dist = rfm[["customer_id","recency_days","frequency","monetary_usd",
                       "churn_prob","loyalty_segment","clv_12m_usd"]].copy()
    churn_dist["risk_band"] = pd.cut(churn_dist["churn_prob"],
                                      bins=[0,.2,.4,.6,.8,1.0],
                                      labels=["Very Low","Low","Medium","High","Critical"])
    _save(churn_dist, "cust_churn_risk")

    return seg


# ─────────────────────────────────────────────────────────────────────────────
# 5. MARKETING & PROMOTIONS MART
# ─────────────────────────────────────────────────────────────────────────────
def build_marketing_mart():
    print("\n[5] Marketing & Promotions Mart")

    media   = _read("media", "fact_media_response")
    media["week_start_date"] = pd.to_datetime(media["week_start_date"])
    media["month"] = media["week_start_date"].dt.to_period("M").astype(str)

    monetise = _read("media", "fact_data_monetisation")
    monetise["month"] = pd.to_datetime(monetise["month"]).dt.to_period("M").astype(str)

    ab    = _read("promotions", "fact_ab_tests")
    promos = _read("promotions", "dim_promotions")
    uplift = _read("promotions", "fact_promo_uplift")

    # Channel ROI summary
    ch_roi = (media.groupby(["channel","region"])
              .agg(total_spend=("spend_usd","sum"),
                   total_attributed_sales=("attributed_sales_usd","sum"),
                   avg_roi=("roi","mean"),
                   avg_marginal_roi=("marginal_roi","mean"),
                   saturation_count=("saturation_flag","sum"))
              .reset_index())
    ch_roi["roas"] = ch_roi["total_attributed_sales"] / ch_roi["total_spend"].clip(lower=1)
    _save(ch_roi, "mkt_channel_roi")

    # Monthly media spend by channel
    monthly_media = (media.groupby(["month","channel"])
                     .agg(spend=("spend_usd","sum"),
                          attributed_sales=("attributed_sales_usd","sum"))
                     .reset_index())
    _save(monthly_media, "mkt_monthly_media")

    # Data monetisation revenue
    monetise["year"] = pd.to_datetime(monetise["month"].str[:7]).dt.year
    _save(monetise, "mkt_data_monetisation")

    # A/B test summary
    ab_sig = ab.copy()
    ab_sig["is_statistically_significant"] = ab_sig["is_statistically_significant"].astype(bool)
    ab_summary = (ab_sig.groupby("test_type")
                  .agg(n_tests=("test_id","count"),
                       sig_pct=("is_statistically_significant","mean"),
                       avg_uplift=("uplift_pct","mean"),
                       avg_impact=("estimated_annual_impact_usd","mean"))
                  .reset_index())
    _save(ab_summary, "mkt_ab_summary")

    # Promo type ROI
    promo_roi = (uplift.groupby("promo_type")
                 .agg(total_incremental=("true_incremental_usd","sum"),
                      total_cost=("promo_cost_usd","sum"),
                      avg_roi=("roi","mean"),
                      pct_avoidable=("markdown_avoidable","mean"))
                 .reset_index())
    _save(promo_roi, "mkt_promo_type_roi")

    return ch_roi


# ─────────────────────────────────────────────────────────────────────────────
# 6. INVENTORY & SUPPLY CHAIN MART
# ─────────────────────────────────────────────────────────────────────────────
def build_inventory_mart():
    print("\n[6] Inventory Mart")

    inv      = _read("merchandise", "fact_inventory")
    inv["week_start"] = pd.to_datetime(inv["week_start"])
    stockout = _read("merchandise", "fact_stockouts")
    stockout["week_start"] = pd.to_datetime(stockout["week_start"])
    prod     = _read("products",    "dim_products")
    stores   = _read("stores",      "dim_stores")[["store_id","region"]]
    fcst     = _read("merchandise", "fact_demand_forecast")

    # Weekly inventory health
    inv_weekly = (inv.groupby("week_start")
                  .agg(avg_fill_rate=("fill_rate","mean"),
                       avg_dos=("days_of_supply","mean"),
                       total_on_hand=("on_hand_units","sum"),
                       total_demand=("demand_units","sum"))
                  .reset_index())
    inv_weekly["oos_proxy"] = 1 - inv_weekly["avg_fill_rate"]
    _save(inv_weekly, "inv_weekly_health")

    # Stockout by root cause
    so_cause = (stockout.groupby("root_cause")
                .agg(n_events=("store_id","count"),
                     total_lost_sales=("lost_sales_usd","sum"),
                     avg_stockout_days=("stockout_days","mean"))
                .reset_index())
    _save(so_cause, "inv_stockout_causes")

    # Stockout by dept (join prod)
    so_dept = (stockout.merge(prod[["sku_id","department"]], on="sku_id", how="left")
               .groupby("department")
               .agg(n_events=("store_id","count"),
                    total_lost=("lost_sales_usd","sum"))
               .reset_index())
    _save(so_dept, "inv_stockout_dept")

    # Forecast accuracy by department
    fcst_acc = (fcst.groupby("department")
                .agg(avg_mape=("mape_pct","mean"),
                     n=("forecast_id","count"),
                     avg_baseline=("baseline_demand","mean"))
                .reset_index())
    _save(fcst_acc, "inv_forecast_accuracy")

    # SKU-level slow movers (low sell-through proxy)
    sku_slow = (inv.groupby("sku_id")
                .agg(avg_fill=("fill_rate","mean"),
                     avg_dos=("days_of_supply","mean"),
                     total_demand=("demand_units","sum"))
                .reset_index()
                .merge(prod[["sku_id","department","velocity_tier"]], on="sku_id"))
    sku_slow["is_slow_mover"] = sku_slow["avg_dos"] > 60
    _save(sku_slow, "inv_sku_health")

    return inv_weekly


# ─────────────────────────────────────────────────────────────────────────────
# 7. MARKET BASKET & AFFINITY MART
# ─────────────────────────────────────────────────────────────────────────────
def build_affinity_mart():
    print("\n[7] Affinity Mart")

    aff  = _read("transactions", "fact_basket_affinities")
    prod = _read("products", "dim_products")[["sku_id","department","brand","description"]]

    # Dept-to-dept affinity (aggregated)
    dept_aff = (aff.groupby(["antecedent_dept","consequent_dept"])
                .agg(avg_lift=("lift","mean"),
                     avg_confidence=("confidence","mean"),
                     total_co_occ=("co_occurrence_count","sum"))
                .reset_index())
    dept_aff = dept_aff[dept_aff["antecedent_dept"] != dept_aff["consequent_dept"]]
    _save(dept_aff, "aff_dept_pairs")

    # Top SKU pairs by lift
    top_pairs = (aff.nlargest(5000, "lift")
                 .merge(prod.rename(columns={"sku_id":"antecedent_sku","description":"ant_desc",
                                             "department":"ant_dept"})[["antecedent_sku","ant_desc","ant_dept"]],
                        on="antecedent_sku", how="left")
                 .merge(prod.rename(columns={"sku_id":"consequent_sku","description":"con_desc",
                                             "department":"con_dept"})[["consequent_sku","con_desc","con_dept"]],
                        on="consequent_sku", how="left"))
    _save(top_pairs, "aff_top_sku_pairs")

    # Affinity by dept heatmap pivot
    pivot = dept_aff.pivot_table(index="antecedent_dept", columns="consequent_dept",
                                  values="avg_lift", aggfunc="mean").fillna(0)
    pivot_df = pivot.reset_index()
    _save(pivot_df, "aff_dept_heatmap")

    return dept_aff


# ─────────────────────────────────────────────────────────────────────────────
# 8. REAL ESTATE / GIS MART
# ─────────────────────────────────────────────────────────────────────────────
def build_gis_mart():
    print("\n[8] GIS / Real Estate Mart")

    trade  = _read("stores", "dim_trade_areas")
    stores = _read("stores", "dim_stores")
    site   = _read("stores", "fact_site_selection")

    gis = stores.merge(trade, on="store_id", suffixes=("","_ta"))
    # Drop duplicate cols
    dup = [c for c in gis.columns if c.endswith("_ta")]
    gis = gis.drop(columns=dup)
    _save(gis, "gis_store_trade_areas")

    # Region summary
    region_sum = (gis.groupby("region")
                  .agg(n_stores=("store_id","count"),
                       avg_pop_3mi=("pop_3mi","mean"),
                       avg_income=("median_hh_income_usd","mean"),
                       avg_gravity=("gravity_score","mean"),
                       avg_breakeven_before=("breakeven_years_before","mean"),
                       avg_breakeven_after=("breakeven_years_after","mean"),
                       avg_predicted_sales=("predicted_annual_sales_usd","mean"))
                  .reset_index())
    _save(region_sum, "gis_region_summary")

    # Candidate sites
    _save(site, "gis_candidate_sites")

    return gis


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import time
    t0 = time.time()
    print("=" * 55)
    print("  Building Analytics Marts")
    print("=" * 55)

    build_exec_summary()
    build_merchandise_mart()
    build_store_ops_mart()
    build_customer_mart()
    build_marketing_mart()
    build_inventory_mart()
    build_affinity_mart()
    build_gis_mart()

    print(f"\n{'='*55}")
    print(f"  Done in {time.time()-t0:.1f}s  →  output/marts/")
    print("=" * 55)
