"""
Data Engineering – Extension Marts
Builds mart tables from the new extension raw tables.
Run after build_marts.py (or standalone).

Output: output/marts/ext_*.parquet
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
import pandas as pd

RAW   = os.path.join(os.path.dirname(__file__), "..", "output")
MARTS = os.path.join(RAW, "marts")
EXT   = os.path.join(RAW, "extensions")
os.makedirs(MARTS, exist_ok=True)


def _save(df, name):
    path = os.path.join(MARTS, f"{name}.parquet")
    df.to_parquet(path, index=False, engine="pyarrow", compression="snappy")
    print(f"  ✓ {name}.parquet  ({len(df):,} rows)")
    return df

def _read_ext(table):
    return pd.read_parquet(os.path.join(EXT, f"{table}.parquet"))

def _read_raw(domain, table):
    return pd.read_parquet(os.path.join(RAW, domain, f"{table}.parquet"))


# ── 1. Price Elasticity Mart ─────────────────────────────────────────────────
def build_elasticity_mart():
    print("\n[EXT-1] Price Elasticity Mart")
    elast = _read_ext("fact_price_elasticity")
    elast["week_start"] = pd.to_datetime(elast["week_start"])

    # Dept-level elasticity summary
    dept = (elast.groupby(["department","price_zone"])
            .agg(avg_elasticity=("elasticity","mean"),
                 avg_units=("units_sold","mean"),
                 avg_revenue=("revenue_usd","mean"),
                 avg_margin=("margin_usd","mean"),
                 n_obs=("obs_id","count"))
            .reset_index())
    _save(dept, "ext_elasticity_by_dept")

    # SKU-level top 200 most elastic
    sku = (elast.groupby("sku_id")
           .agg(avg_elasticity=("elasticity","mean"),
                avg_price=("test_price_usd","mean"),
                revenue_total=("revenue_usd","sum"),
                n_obs=("obs_id","count"),
                dept=("department","first"))
           .reset_index()
           .nlargest(500, "n_obs"))
    _save(sku, "ext_elasticity_by_sku")

    # Weekly demand curve (revenue vs price-zone)
    weekly = (elast.groupby(["week_start","price_zone"])
              .agg(avg_units=("units_sold","mean"),
                   avg_revenue=("revenue_usd","mean"))
              .reset_index())
    _save(weekly, "ext_elasticity_weekly")

    # Promo vs non-promo lift
    promo_comp = (elast.groupby(["department","is_promo_price"])
                  .agg(avg_units=("units_sold","mean"),
                       avg_revenue=("revenue_usd","mean"),
                       avg_margin=("margin_usd","mean"))
                  .reset_index())
    _save(promo_comp, "ext_elasticity_promo_comp")


# ── 2. Purchase Cycle Mart ───────────────────────────────────────────────────
def build_purchase_cycle_mart():
    print("\n[EXT-2] Purchase Cycle Mart")
    pc = _read_ext("fact_purchase_cycles")

    # Dept summary
    dept = (pc.groupby("department")
            .agg(avg_cycle_days=("avg_cycle_days","mean"),
                 avg_annual_freq=("n_purchases_12m","mean"),
                 pct_overdue=("is_overdue","mean"),
                 avg_days_since=("days_since_last_purchase","mean"),
                 avg_predicted_next=("predicted_next_days","mean"))
            .reset_index())
    dept["overdue_pct"] = dept["pct_overdue"] * 100
    _save(dept, "ext_purchase_cycles_dept")

    # At-risk customers (overdue in ≥2 departments)
    overdue = (pc[pc["is_overdue"]]
               .groupby("customer_id")["department"]
               .count().reset_index(name="overdue_depts"))
    at_risk = overdue[overdue["overdue_depts"] >= 2]
    _save(at_risk, "ext_at_risk_customers")

    # Cycle stability distribution
    _save(pc[["customer_id","department","avg_cycle_days","cycle_stability",
              "days_since_last_purchase","is_overdue"]], "ext_purchase_cycles_detail")


# ── 3. Competitor Intelligence Mart ─────────────────────────────────────────
def build_competitor_mart():
    print("\n[EXT-3] Competitor Intelligence Mart")
    comp = _read_ext("fact_competitor_intel")
    comp["week_start"] = pd.to_datetime(comp["week_start"])

    # Price gap summary by competitor × dept
    gap = (comp.groupby(["competitor","department"])
           .agg(avg_price_gap=("price_gap_pct","mean"),
                n_obs=("record_id","count"),
                comp_promo_rate=("comp_on_promo","mean"),
                own_promo_rate=("own_on_promo","mean"))
           .reset_index())
    # pct_premium: fraction of observations where own price > competitor
    prem = (comp.assign(is_prem=(comp["price_position"]=="Premium").astype(int))
            .groupby(["competitor","department"])["is_prem"].mean().reset_index(name="pct_premium"))
    gap = gap.merge(prem, on=["competitor","department"], how="left")
    _save(gap, "ext_competitor_price_gap")

    # Weekly price position trend
    weekly_pos = (comp.groupby(["week_start","price_position"])
                  .size().reset_index(name="count"))
    _save(weekly_pos, "ext_competitor_position_trend")

    # By region
    reg = (comp.groupby(["region","competitor"])
           .agg(avg_gap=("price_gap_pct","mean"),
                n_obs=("record_id","count"))
           .reset_index())
    _save(reg, "ext_competitor_by_region")


# ── 4. Space / Planogram Mart ────────────────────────────────────────────────
def build_space_mart():
    print("\n[EXT-4] Space / Planogram Mart")
    space = _read_ext("fact_space_planogram")

    # Department productivity ranking
    dept = (space.groupby("department")
            .agg(avg_sales_per_sqft=("sales_per_sqft","mean"),
                 avg_allocated_pct=("allocated_pct","mean"),
                 avg_optimal_pct=("optimal_pct","mean"),
                 avg_space_gap=("space_gap_pct","mean"),
                 avg_compliance=("planogram_compliance_pct","mean"),
                 total_revenue=("dept_revenue_annual","sum"))
            .reset_index())
    dept["opportunity_usd"] = np.round(
        dept["avg_sales_per_sqft"] * dept["avg_space_gap"].clip(lower=0) * 10, 0
    )
    dept = dept.sort_values("avg_sales_per_sqft", ascending=False)
    _save(dept, "ext_space_dept_ranking")

    # Store-level compliance
    store_comp = (space.groupby("store_id")
                  .agg(avg_compliance=("planogram_compliance_pct","mean"),
                       total_revenue=("dept_revenue_annual","sum"),
                       avg_sales_sqft=("sales_per_sqft","mean"))
                  .reset_index())
    _save(store_comp, "ext_space_store_compliance")

    # Region summary
    space_with_region = space.copy()
    if "region" not in space_with_region.columns:
        stores_df = _read_raw("stores", "dim_stores")[["store_id", "region"]]
        space_with_region = space_with_region.merge(stores_df, on="store_id", how="left")
    region = (space_with_region.groupby("region")
              .agg(avg_compliance=("planogram_compliance_pct","mean"),
                   avg_sales_sqft=("sales_per_sqft","mean"),
                   avg_space_gap=("space_gap_pct","mean"))
              .reset_index())
    _save(region, "ext_space_region_summary")


# ── 5. Customer Acquisition Mart ────────────────────────────────────────────
def build_acquisition_mart():
    print("\n[EXT-5] Customer Acquisition Mart")
    acq = _read_ext("fact_customer_acquisition")

    # Channel summary
    ch = (acq.groupby("acquisition_channel")
          .agg(n_customers=("customer_id","count"),
               avg_cac=("acquisition_cost_usd","mean"),
               avg_first30=("first_30d_spend_usd","mean"),
               avg_first90=("first_90d_spend_usd","mean"),
               activation_rate=("is_activated","mean"),
               repeat_rate=("repeat_purchase_30d","mean"),
               avg_roi=("channel_roi","mean"),
               avg_payback_days=("payback_period_days","mean"))
          .reset_index())
    ch["activation_pct"] = ch["activation_rate"] * 100
    ch["repeat_pct"]     = ch["repeat_rate"] * 100
    _save(ch, "ext_acquisition_by_channel")

    # Region × channel
    reg_ch = (acq.groupby(["region","acquisition_channel"])
              .agg(n=("customer_id","count"),
                   avg_cac=("acquisition_cost_usd","mean"),
                   avg_roi=("channel_roi","mean"))
              .reset_index())
    _save(reg_ch, "ext_acquisition_region_channel")

    # Payback period distribution
    _save(acq[["customer_id","acquisition_channel","acquisition_cost_usd",
               "first_90d_spend_usd","is_activated","channel_roi",
               "payback_period_days"]], "ext_acquisition_detail")


# ── 6. Event Impact Mart ────────────────────────────────────────────────────
def build_event_mart():
    print("\n[EXT-6] Event Impact Mart")
    ev = _read_ext("fact_event_analysis")
    ev["event_week"] = pd.to_datetime(ev["event_week"])

    # Summary by event type
    evt = (ev.groupby("event_type")
           .agg(n_occurrences=("store_id","count"),
                avg_uplift_pct=("uplift_pct","mean"),
                avg_incremental=("incremental_usd","mean"),
                total_incremental=("incremental_usd","sum"),
                prep_rate=("was_prepared","mean"))
           .reset_index()
           .sort_values("avg_uplift_pct", ascending=False))
    evt["prep_pct"] = evt["prep_rate"] * 100
    _save(evt, "ext_event_summary")

    # By region
    reg = (ev.groupby(["region","event_type"])
           .agg(avg_uplift=("uplift_pct","mean"),
                total_incremental=("incremental_usd","sum"))
           .reset_index())
    _save(reg, "ext_event_by_region")

    # By department
    dept = (ev.groupby(["primary_dept","event_type"])
            .agg(avg_uplift=("uplift_pct","mean"),
                 n=("store_id","count"))
            .reset_index())
    _save(dept, "ext_event_by_dept")


# ── 7. ATF / ATV Mart ───────────────────────────────────────────────────────
def build_atf_atv_mart():
    print("\n[EXT-7] ATF / ATV Mart")
    atf = _read_ext("fact_atf_atv")
    det = pd.read_parquet(os.path.join(EXT, "fact_atf_atv_detail.parquet"))

    # Already aggregated; just save as-is
    _save(atf, "ext_atf_atv_segments")

    # Age group breakdown
    age = (det.groupby(["age_group","loyalty_segment"])
           .agg(avg_atf=("atf","mean"),
                avg_atv=("atv","mean"),
                avg_spend=("atv_x_atf","mean"),
                n=("customer_id","count"))
           .reset_index())
    _save(age, "ext_atf_atv_by_age")

    # Format breakdown
    fmt = (det.groupby(["preferred_format","loyalty_segment"])
           .agg(avg_atf=("atf","mean"),
                avg_atv=("atv","mean"))
           .reset_index())
    _save(fmt, "ext_atf_atv_by_format")


# ── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import time
    t0 = time.time()
    print("=" * 55)
    print("  Building Extension Marts")
    print("=" * 55)

    build_elasticity_mart()
    build_purchase_cycle_mart()
    build_competitor_mart()
    build_space_mart()
    build_acquisition_mart()
    build_event_mart()
    build_atf_atv_mart()

    print(f"\n{'='*55}")
    print(f"  Done in {time.time()-t0:.1f}s")
    print("=" * 55)
