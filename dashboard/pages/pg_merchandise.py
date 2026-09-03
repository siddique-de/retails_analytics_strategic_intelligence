"""
Page 2 – Merchandise & Category Management
"""
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.data_loader import (merch_category, merch_sku, merch_promo_eff,
                                    merch_markdowns, merch_fcst_acc,
                                    inv_so_dept, inv_fcst_acc, inv_sku_health)
from dashboard.utils import (fmt_currency, fmt_pct, fmt_num, apply_dark_theme,
                               waterfall, PALETTE, PRIMARY, SECONDARY,
                               SUCCESS, DANGER, ACCENT, SEQ_BLUE)


def render():
    st.title("🛒 Merchandise & Category Management")
    st.caption("Deep dive into product performance, assortment optimisation, and pricing strategy")

    cat      = merch_category()
    sku_prod = merch_sku()
    promo    = merch_promo_eff()
    markdn   = merch_markdowns()
    fcst     = merch_fcst_acc()
    so_dept  = inv_so_dept()
    sku_hlth = inv_sku_health()

    cat["month"] = cat["month"].astype(str)

    # ── Sidebar Filters ────────────────────────────────────────────────────────
    with st.sidebar:
        st.subheader("Merchandise Filters")
        depts = ["All"] + sorted(cat["department"].unique().tolist())
        sel_dept = st.selectbox("Department", depts)
        months   = sorted(cat["month"].unique().tolist())
        sel_month_range = st.select_slider(
            "Month Range", options=months,
            value=(months[0], months[-1]) if len(months) >= 2 else (months[0], months[0])
        )

    cat_f = cat[(cat["month"] >= sel_month_range[0]) & (cat["month"] <= sel_month_range[1])]
    if sel_dept != "All":
        cat_f = cat_f[cat_f["department"] == sel_dept]

    # ── KPIs ──────────────────────────────────────────────────────────────────
    total_rev    = cat_f["revenue"].sum()
    avg_margin   = cat_f["avg_margin"].mean()
    n_slow       = sku_hlth["is_slow_mover"].sum()
    pct_slow     = n_slow / max(len(sku_hlth), 1) * 100
    avg_mape     = fcst["avg_mape"].mean()
    total_lost   = so_dept["total_lost"].sum()

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Category Revenue",    fmt_currency(total_rev))
    k2.metric("Avg Gross Margin",    fmt_pct(avg_margin))
    k3.metric("Slow Movers",         f"{n_slow:,}  ({fmt_pct(pct_slow)})", help="SKUs with DoS > 60 days")
    k4.metric("Forecast MAPE",       fmt_pct(avg_mape),   help="Mean Absolute Percentage Error")
    k5.metric("Lost Sales (OOS)",    fmt_currency(total_lost))

    st.divider()

    # ── Row 1: Category Treemap + Monthly trend ───────────────────────────────
    col_left, col_right = st.columns([2, 3])

    with col_left:
        st.subheader("Category Revenue Share (Treemap)")
        cat_agg = cat_f.groupby("department")["revenue"].sum().reset_index()
        fig = px.treemap(cat_agg, path=["department"], values="revenue",
                         color="revenue", color_continuous_scale="Blues")
        apply_dark_theme(fig, 380)
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Monthly Revenue by Department")
        top_depts = cat_f.groupby("department")["revenue"].sum().nlargest(8).index.tolist()
        cat_top   = cat_f[cat_f["department"].isin(top_depts)]
        fig = px.line(cat_top.sort_values("month"),
                      x="month", y="revenue", color="department",
                      color_discrete_sequence=PALETTE,
                      labels={"revenue":"Revenue (USD)", "month":"Month"})
        apply_dark_theme(fig, 380)
        fig.update_layout(xaxis_tickangle=-45, legend=dict(orientation="h", y=-0.3))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 2: Margin heatmap + Promotion Effectiveness ───────────────────────
    col_l2, col_r2 = st.columns(2)

    with col_l2:
        st.subheader("Gross Margin % by Department")
        margin_df = cat_f.groupby("department")["avg_margin"].mean().reset_index()
        margin_df = margin_df.sort_values("avg_margin", ascending=True)
        fig = px.bar(margin_df, x="avg_margin", y="department", orientation="h",
                     color="avg_margin", color_continuous_scale="RdYlGn",
                     labels={"avg_margin":"Margin %", "department":"Department"})
        apply_dark_theme(fig, 400)
        fig.add_vline(x=40, line_dash="dash", line_color="white",
                      annotation_text="Target 40%")
        st.plotly_chart(fig, use_container_width=True)

    with col_r2:
        st.subheader("Promotional Lift vs. ROI by Type")
        promo_f = promo.copy()
        if sel_dept != "All":
            promo_f = promo_f[promo_f["department"] == sel_dept]
        promo_agg = promo_f.groupby("promo_type").agg(
            avg_lift=("lift_pct","mean"), avg_roi=("avg_roi","mean"),
            pct_avoidable=("pct_markdown_avoidable","mean")).reset_index()
        fig = px.scatter(promo_agg, x="avg_lift", y="avg_roi",
                         size="pct_avoidable", color="promo_type",
                         text="promo_type",
                         color_discrete_sequence=PALETTE,
                         labels={"avg_lift":"Avg Lift %","avg_roi":"Avg ROI","promo_type":"Type"})
        fig.update_traces(textposition="top center")
        apply_dark_theme(fig, 400)
        fig.add_hline(y=1, line_dash="dash", line_color="white",
                      annotation_text="ROI = 1")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 3: SKU Rationalization + Forecast Accuracy ────────────────────────
    col_l3, col_r3 = st.columns(2)

    with col_l3:
        st.subheader("SKU Productivity (Scatter – Revenue vs Baskets)")
        sku_s = sku_prod.copy()
        if sel_dept != "All":
            sku_s = sku_s[sku_s["department"] == sel_dept]
        sku_s = sku_s.sample(min(2000, len(sku_s)), random_state=42)
        fig = px.scatter(sku_s, x="baskets", y="revenue",
                         color="velocity_tier",
                         color_discrete_map={"A":SUCCESS,"B":SECONDARY,"C":ACCENT,"D":DANGER},
                         opacity=0.6,
                         labels={"baskets":"Basket Appearances","revenue":"Revenue (USD)",
                                 "velocity_tier":"Velocity Tier"},
                         hover_data=["sku_id","department"])
        apply_dark_theme(fig, 400)
        st.plotly_chart(fig, use_container_width=True)

    with col_r3:
        st.subheader("Demand Forecast Accuracy (MAPE by Dept)")
        fig = px.bar(fcst.sort_values("avg_mape"),
                     x="department", y="avg_mape",
                     color="avg_mape", color_continuous_scale="RdYlGn_r",
                     labels={"avg_mape":"MAPE %","department":"Department"})
        apply_dark_theme(fig, 400)
        fig.add_hline(y=10, line_dash="dash", line_color="white",
                      annotation_text="Target MAPE 10%")
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 4: Lost Sales from Stockouts + Markdown Overview ──────────────────
    col_l4, col_r4 = st.columns(2)

    with col_l4:
        st.subheader("Lost Sales by Department (OOS Events)")
        fig = px.bar(so_dept.sort_values("total_lost", ascending=False),
                     x="department", y="total_lost",
                     color="n_events", color_continuous_scale="Reds",
                     labels={"total_lost":"Lost Sales ($)","n_events":"OOS Events"})
        apply_dark_theme(fig, 350)
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    with col_r4:
        st.subheader("Markdown Distribution")
        if len(markdn):
            fig = px.histogram(markdn, x="discount_pct", color="promo_type",
                               nbins=30, barmode="overlay",
                               color_discrete_sequence=PALETTE,
                               labels={"discount_pct":"Discount %","promo_type":"Type"})
            apply_dark_theme(fig, 350)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No markdown data for selected filters.")




