"""
Page 4 – Customer & Loyalty Dashboard
"""
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.data_loader import (cust_rfm_segs, cust_demo, cust_loyalty_funnel,
                                    cust_loyalty_tiers, cust_cohort, cust_churn)
from dashboard.utils import (fmt_currency, fmt_pct, fmt_num, apply_dark_theme,
                               gauge, PALETTE, PRIMARY, SECONDARY,
                               SUCCESS, DANGER, ACCENT)

SEGMENT_COLORS = {
    "Loyalist":          "#27AE60",
    "Soccer Mom":        "#2E86C1",
    "Cherry Picker":     "#F39C12",
    "Occasional Shopper":"#8E44AD",
    "Lapsed":            "#E74C3C",
    "New Customer":      "#16A085",
}


def render():
    st.title("👥 Customer & Loyalty Analytics")
    st.caption("360-degree customer view, RFM segmentation, and lifecycle management")

    rfm_seg = cust_rfm_segs()
    demo    = cust_demo()
    funnel  = cust_loyalty_funnel()
    tiers   = cust_loyalty_tiers()
    cohort  = cust_cohort()
    churn   = cust_churn()

    # ── Sidebar ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.subheader("Customer Filters")
        regions = ["All"] + sorted(demo["region"].dropna().unique().tolist())
        sel_region = st.selectbox("Region", regions)
        segments   = ["All"] + sorted(demo["loyalty_segment"].dropna().unique().tolist())
        sel_seg    = st.selectbox("Loyalty Segment", segments)

    demo_f = demo.copy()
    if sel_region != "All": demo_f = demo_f[demo_f["region"]   == sel_region]
    if sel_seg    != "All": demo_f = demo_f[demo_f["loyalty_segment"] == sel_seg]

    # ── KPIs ──────────────────────────────────────────────────────────────────
    total_cust   = len(demo_f)
    avg_clv      = demo_f["clv_12m_usd"].mean()
    avg_churn    = demo_f["churn_prob"].mean() * 100
    retention    = 100 - avg_churn
    active_count = int(funnel.loc[funnel["stage"]=="Active Members","count"].values[0])
    total_loy    = int(funnel.loc[funnel["stage"]=="Loyalty Members","count"].values[0])
    active_rate  = active_count / max(total_loy, 1) * 100

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Customers",  fmt_num(total_cust))
    k2.metric("Avg 12M CLV",      fmt_currency(avg_clv))
    k3.metric("Avg Churn Risk",   fmt_pct(avg_churn),   delta="↓ = better",  delta_color="inverse")
    k4.metric("Retention Rate",   fmt_pct(retention),   delta="Target >80%")
    k5.metric("Loyalty Active %", fmt_pct(active_rate), delta="Target >70%")

    st.divider()

    # ── Row 1: RFM Bubble + Segment Treemap ───────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("RFM Segment Overview")
        fig = px.scatter(rfm_seg,
                         x="avg_recency", y="avg_frequency",
                         size="n_customers", color="loyalty_segment",
                         color_discrete_map=SEGMENT_COLORS,
                         text="loyalty_segment",
                         size_max=60,
                         labels={"avg_recency":"Avg Recency (days)",
                                 "avg_frequency":"Avg Frequency (txns/yr)",
                                 "loyalty_segment":"Segment"})
        fig.update_traces(textposition="top center")
        apply_dark_theme(fig, 400)
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Revenue Contribution by Segment")
        fig = px.treemap(rfm_seg, path=["loyalty_segment"],
                         values="revenue_share",
                         color="avg_clv",
                         color_continuous_scale="Blues",
                         labels={"revenue_share":"Revenue Share %",
                                 "avg_clv":"Avg CLV ($)"})
        apply_dark_theme(fig, 400)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 2: Loyalty Funnel + Tier Breakdown ────────────────────────────────
    col_l2, col_r2 = st.columns(2)

    with col_l2:
        st.subheader("Loyalty Programme Funnel")
        fig = go.Figure(go.Funnel(
            y=funnel["stage"], x=funnel["count"],
            textinfo="value+percent initial",
            marker={"color": [PRIMARY, SECONDARY, SUCCESS, ACCENT, DANGER]},
        ))
        apply_dark_theme(fig, 360)
        st.plotly_chart(fig, use_container_width=True)

    with col_r2:
        st.subheader("Loyalty Tier – Avg CLV & Churn")
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Avg CLV ($)",
                              x=tiers["loyalty_tier"], y=tiers["avg_clv"],
                              marker_color=SECONDARY, yaxis="y"))
        fig.add_trace(go.Scatter(name="Avg Churn %",
                                  x=tiers["loyalty_tier"], y=tiers["avg_churn"] * 100,
                                  mode="lines+markers", line=dict(color=DANGER, width=2.5),
                                  yaxis="y2"))
        fig.update_layout(
            yaxis=dict(title="Avg CLV ($)"),
            yaxis2=dict(title="Churn %", overlaying="y", side="right"),
            barmode="group",
        )
        apply_dark_theme(fig, 360)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 3: Cohort Retention Heatmap + Churn Risk Distribution ─────────────
    col_l3, col_r3 = st.columns(2)

    with col_l3:
        st.subheader("Cohort Retention Heatmap")
        cohort_piv = cohort.pivot_table(
            index="cohort", columns="txn_period",
            values="retention_rate", aggfunc="mean"
        ).fillna(0)
        # Limit to last 24 cohorts for readability
        cohort_piv = cohort_piv.iloc[-24:, :24] if len(cohort_piv) >= 24 else cohort_piv
        fig = px.imshow(cohort_piv, color_continuous_scale="Blues",
                        labels=dict(x="Transaction Period", y="Enrolment Cohort",
                                    color="Retention %"),
                        aspect="auto")
        apply_dark_theme(fig, 440)
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    with col_r3:
        st.subheader("Churn Risk Distribution")
        churn_band = (churn.groupby(["risk_band","loyalty_segment"], observed=True)["customer_id"]
                      .count().reset_index(name="count"))
        fig = px.bar(churn_band, x="risk_band", y="count",
                     color="loyalty_segment",
                     color_discrete_map=SEGMENT_COLORS,
                     barmode="stack",
                     labels={"risk_band":"Risk Band","count":"Customers",
                             "loyalty_segment":"Segment"},
                     category_orders={"risk_band":["Very Low","Low","Medium","High","Critical"]})
        apply_dark_theme(fig, 440)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 4: Demographics ────────────────────────────────────────────────────
    col_l4, col_r4 = st.columns(2)

    with col_l4:
        st.subheader("Customer Age Group Distribution")
        age = demo_f.groupby("age_group")["customer_id"].count().reset_index(name="count")
        fig = px.pie(age, names="age_group", values="count",
                     color_discrete_sequence=PALETTE, hole=0.4)
        apply_dark_theme(fig, 320)
        st.plotly_chart(fig, use_container_width=True)

    with col_r4:
        st.subheader("Avg CLV by Age Group & Gender")
        clv_age = demo_f.groupby(["age_group","gender"])["clv_12m_usd"].mean().reset_index()
        fig = px.bar(clv_age, x="age_group", y="clv_12m_usd", color="gender",
                     barmode="group",
                     color_discrete_sequence=PALETTE,
                     labels={"clv_12m_usd":"Avg 12M CLV ($)","age_group":"Age Group"})
        apply_dark_theme(fig, 320)
        st.plotly_chart(fig, use_container_width=True)




