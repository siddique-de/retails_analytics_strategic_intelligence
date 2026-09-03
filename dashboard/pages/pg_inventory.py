"""
Page 6 – Inventory, Supply Chain & Demand Forecasting
"""
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.data_loader import (inv_weekly, inv_so_causes, inv_so_dept,
                                    inv_fcst_acc, inv_sku_health, merch_fcst_acc)
from dashboard.utils import (fmt_currency, fmt_pct, fmt_num, apply_dark_theme,
                               PALETTE, PRIMARY, SECONDARY, SUCCESS, DANGER, ACCENT)


def render():
    st.title("📦 Inventory, Supply Chain & Demand Forecasting")
    st.caption("Monitor stock health, stockout root causes, and forecast accuracy")

    weekly   = inv_weekly()
    so_cause = inv_so_causes()
    so_dept  = inv_so_dept()
    fcst     = inv_fcst_acc()
    sku_hlth = inv_sku_health()

    weekly["week_start"] = pd.to_datetime(weekly["week_start"])

    # ── Sidebar ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.subheader("Inventory Filters")
        all_depts = ["All"] + sorted(sku_hlth["department"].dropna().unique().tolist())
        sel_dept  = st.selectbox("Department", all_depts)
        vel_tiers = ["All", "A", "B", "C", "D"]
        sel_vel   = st.selectbox("Velocity Tier", vel_tiers)

    sku_f = sku_hlth.copy()
    if sel_dept != "All": sku_f = sku_f[sku_f["department"] == sel_dept]
    if sel_vel  != "All": sku_f = sku_f[sku_f["velocity_tier"] == sel_vel]

    # ── KPIs ──────────────────────────────────────────────────────────────────
    avg_fill  = weekly["avg_fill_rate"].mean() * 100
    avg_dos   = weekly["avg_dos"].mean()
    oos_rate  = weekly["oos_proxy"].mean() * 100
    total_lost= so_dept["total_lost"].sum()
    n_slow    = sku_hlth["is_slow_mover"].sum()
    avg_mape  = fcst["avg_mape"].mean()

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Avg Fill Rate",    fmt_pct(avg_fill),     delta="Target >70%")
    k2.metric("Avg Days Supply",  fmt_num(avg_dos, 1),   help="Days of inventory on hand")
    k3.metric("Est. OOS Rate",    fmt_pct(oos_rate),     delta="Target <2%", delta_color="inverse")
    k4.metric("Total Lost Sales", fmt_currency(total_lost))
    k5.metric("Slow Movers",      fmt_num(n_slow),       help="SKUs with DoS > 60 days")
    k6.metric("Avg Fcst MAPE",    fmt_pct(avg_mape),     help="Lower is better")

    st.divider()

    # ── Row 1: Weekly Fill Rate Trend + Inventory Turnover ────────────────────
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Weekly Fill Rate & OOS Trend")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=weekly["week_start"], y=weekly["avg_fill_rate"]*100,
                                  name="Fill Rate %", line=dict(color=SUCCESS, width=2),
                                  fill="tozeroy", fillcolor="rgba(39,174,96,0.15)"))
        fig.add_trace(go.Scatter(x=weekly["week_start"], y=weekly["oos_proxy"]*100,
                                  name="Est. OOS %", line=dict(color=DANGER, width=2),
                                  yaxis="y2"))
        fig.update_layout(yaxis=dict(title="Fill Rate %", range=[0,105]),
                          yaxis2=dict(title="OOS %", overlaying="y", side="right",
                                      range=[0,30]))
        apply_dark_theme(fig, 360)
        fig.add_hline(y=70, line_dash="dash", line_color="white",
                      annotation_text="Fill Rate Target 70%")
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("Weekly Supply vs. Demand")
        weekly_sample = weekly.tail(52)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=weekly_sample["week_start"],
                              y=weekly_sample["total_on_hand"],
                              name="On Hand", marker_color=SECONDARY, opacity=0.7))
        fig.add_trace(go.Scatter(x=weekly_sample["week_start"],
                                  y=weekly_sample["total_demand"],
                                  name="Demand", line=dict(color=ACCENT, width=2.5)))
        apply_dark_theme(fig, 360)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 2: Stockout Root Cause + Lost Sales by Dept ───────────────────────
    col_l2, col_r2 = st.columns(2)

    with col_l2:
        st.subheader("Stockout Root Cause Analysis")
        fig = px.pie(so_cause, names="root_cause", values="total_lost_sales",
                     hole=0.4, color_discrete_sequence=PALETTE,
                     labels={"total_lost_sales":"Lost Sales ($)"})
        apply_dark_theme(fig, 360)
        st.plotly_chart(fig, use_container_width=True)

    with col_r2:
        st.subheader("Lost Sales by Department")
        so_dept_s = so_dept.sort_values("total_lost", ascending=False)
        fig = px.bar(so_dept_s, x="department", y="total_lost",
                     color="n_events", color_continuous_scale="Reds",
                     labels={"total_lost":"Lost Sales ($)","n_events":"OOS Events"})
        apply_dark_theme(fig, 360)
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 3: MAPE by Dept + Model Version ───────────────────────────────────
    col_l3, col_r3 = st.columns(2)

    with col_l3:
        st.subheader("Forecast MAPE by Department")
        fcst_s = fcst.sort_values("avg_mape")
        fig = px.bar(fcst_s, x="department", y="avg_mape",
                     color="avg_mape", color_continuous_scale="RdYlGn_r",
                     labels={"avg_mape":"MAPE %","department":"Department"})
        apply_dark_theme(fig, 360)
        fig.add_hline(y=10, line_dash="dash", line_color="white",
                      annotation_text="Target 10%")
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    with col_r3:
        st.subheader("SKU Health – Days of Supply Distribution")
        fig = px.histogram(sku_f, x="avg_dos", color="velocity_tier",
                           nbins=40, barmode="overlay",
                           color_discrete_map={"A":SUCCESS,"B":SECONDARY,"C":ACCENT,"D":DANGER},
                           labels={"avg_dos":"Avg Days of Supply","velocity_tier":"Velocity Tier"})
        apply_dark_theme(fig, 360)
        fig.add_vline(x=60, line_dash="dash", line_color=DANGER,
                      annotation_text="Slow Mover Threshold (60d)")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 4: SKU Health Table ────────────────────────────────────────────────
    st.subheader("SKU Health Details")
    top_slow = sku_f[sku_f["is_slow_mover"]].nlargest(50, "avg_dos")[
        ["sku_id","department","velocity_tier","avg_fill","avg_dos","total_demand","is_slow_mover"]
    ].copy()
    top_slow["avg_fill"] = top_slow["avg_fill"].map(lambda x: fmt_pct(x*100))
    top_slow["avg_dos"]  = top_slow["avg_dos"].map(lambda x: f"{x:.1f} days")
    top_slow["total_demand"] = top_slow["total_demand"].map(lambda x: fmt_num(x))
    top_slow.columns = ["SKU","Dept","Tier","Fill Rate","Avg DoS","Total Demand","Slow Mover"]
    st.dataframe(top_slow, use_container_width=True, height=320)




