"""
Cached data loader – reads mart Parquet files once per session.
"""
import os
import pandas as pd
import streamlit as st

MARTS = os.path.join(os.path.dirname(__file__), "..", "output", "marts")


@st.cache_data(show_spinner=False)
def load(name: str) -> pd.DataFrame:
    path = os.path.join(MARTS, f"{name}.parquet")
    return pd.read_parquet(path)


# ── convenience wrappers ──────────────────────────────────────────────────────

def exec_monthly_sales():   return load("exec_monthly_sales")
def exec_store_kpi():       return load("exec_store_kpi")
def exec_daily_trend():     return load("exec_daily_trend")
def exec_inv_turnover():    return load("exec_inv_turnover")

def merch_category():       return load("merch_category_scorecard")
def merch_sku():            return load("merch_sku_productivity")
def merch_promo_eff():      return load("merch_promo_effectiveness")
def merch_markdowns():      return load("merch_markdowns")
def merch_fcst_acc():       return load("merch_forecast_accuracy")

def ops_store_health():     return load("ops_store_health")
def ops_labour_heat():      return load("ops_labour_heatmap")
def ops_layout():           return load("ops_layout_summary")
def ops_site_sel():         return load("ops_site_selection")
def ops_traffic_trend():    return load("ops_traffic_trend")

def cust_rfm_segs():        return load("cust_rfm_segments")
def cust_demo():            return load("cust_demographics")
def cust_loyalty_funnel():  return load("cust_loyalty_funnel")
def cust_loyalty_tiers():   return load("cust_loyalty_tiers")
def cust_cohort():          return load("cust_cohort_retention")
def cust_churn():           return load("cust_churn_risk")

def mkt_channel_roi():      return load("mkt_channel_roi")
def mkt_monthly_media():    return load("mkt_monthly_media")
def mkt_data_monetise():    return load("mkt_data_monetisation")
def mkt_ab_summary():       return load("mkt_ab_summary")
def mkt_promo_roi():        return load("mkt_promo_type_roi")

def inv_weekly():           return load("inv_weekly_health")
def inv_so_causes():        return load("inv_stockout_causes")
def inv_so_dept():          return load("inv_stockout_dept")
def inv_fcst_acc():         return load("inv_forecast_accuracy")
def inv_sku_health():       return load("inv_sku_health")

def aff_dept_pairs():       return load("aff_dept_pairs")
def aff_top_pairs():        return load("aff_top_sku_pairs")
def aff_dept_heatmap():     return load("aff_dept_heatmap")

def gis_stores():           return load("gis_store_trade_areas")
def gis_regions():          return load("gis_region_summary")
def gis_candidates():       return load("gis_candidate_sites")

# ── Extension loaders (Retail Analytics: The Secret Weapon extensions) ────────

def ext_elast_dept():        return load("ext_elasticity_by_dept")
def ext_elast_sku():         return load("ext_elasticity_by_sku")
def ext_elast_weekly():      return load("ext_elasticity_weekly")
def ext_elast_promo():       return load("ext_elasticity_promo_comp")

def ext_pc_dept():           return load("ext_purchase_cycles_dept")
def ext_at_risk():           return load("ext_at_risk_customers")
def ext_pc_detail():         return load("ext_purchase_cycles_detail")

def ext_comp_gap():          return load("ext_competitor_price_gap")
def ext_comp_trend():        return load("ext_competitor_position_trend")
def ext_comp_region():       return load("ext_competitor_by_region")

def ext_space_dept():        return load("ext_space_dept_ranking")
def ext_space_store():       return load("ext_space_store_compliance")
def ext_space_region():      return load("ext_space_region_summary")

def ext_acq_channel():       return load("ext_acquisition_by_channel")
def ext_acq_region():        return load("ext_acquisition_region_channel")
def ext_acq_detail():        return load("ext_acquisition_detail")

def ext_event_summary():     return load("ext_event_summary")
def ext_event_region():      return load("ext_event_by_region")
def ext_event_dept():        return load("ext_event_by_dept")

def ext_atf_atv_seg():       return load("ext_atf_atv_segments")
def ext_atf_atv_age():       return load("ext_atf_atv_by_age")
def ext_atf_atv_fmt():       return load("ext_atf_atv_by_format")
