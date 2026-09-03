"""
Page 1 – Executive Command Center
"""
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.data_loader import (exec_monthly_sales, exec_store_kpi,
                                    exec_daily_trend, exec_inv_turnover,
                                    cust_rfm_segs, cust_loyalty_funnel,
                                    ops_store_health)
from dashboard.utils import (fmt_currency, fmt_pct, fmt_num, apply_dark_theme,
                               gauge, waterfall, sparkline, PALETTE,
                               PRIMARY, SECONDARY, SUCCESS, DANGER, ACCENT,
                               REGION_COLORS)


def render():
    st.title("🏢 Executive Command Center")
    st.caption("30,000-ft view of enterprise health with drill-down capability")

    monthly    = exec_monthly_sales()
    store_kpi  = exec_store_kpi()
    daily      = exec_daily_trend()
    inv_turn   = exec_inv_turnover()
    rfm        = cust_rfm_segs()
    loyalty    = cust_loyalty_funnel()
    ops        = ops_store_health()

    # ── Filters ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.subheader("Executive Filters")
        regions = ["All"] + sorted(monthly["region"].unique().tolist())
        sel_region = st.selectbox("Region", regions)
        years = sorted(monthly["month"].str[:4].unique().tolist(), reverse=True)
        sel_year = st.selectbox("Year", ["All"] + years)

    if sel_region != "All":
        monthly   = monthly[monthly["region"] == sel_region]
        store_kpi = store_kpi[store_kpi["region"] == sel_region]
        ops       = ops[ops["region"] == sel_region]

    if sel_year != "All":
        monthly = monthly[monthly["month"].str.startswith(sel_year)]

    # ── KPI Strip ─────────────────────────────────────────────────────────────
    total_sales      = monthly["total_sales"].sum()
    total_txns       = monthly["txn_count"].sum()
    avg_basket       = monthly["avg_basket"].mean()
    avg_sales_sqft   = store_kpi["sales_per_sqft_actual"].mean()
    active_customers = rfm["n_customers"].sum()
    avg_churn        = rfm["avg_churn_prob"].mean() * 100
    avg_inv_turn     = inv_turn["inv_turnover"].mean()
    loyalty_members  = int(loyalty.loc[loyalty["stage"]=="Loyalty Members","count"].values[0])
    total_customers  = int(loyalty.loc[loyalty["stage"]=="Total Customers","count"].values[0])
    loyalty_pct      = loyalty_members / max(total_customers, 1) * 100

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Total Revenue",   fmt_currency(total_sales),  help="Sum of basket totals")
    k2.metric("Transactions",    fmt_num(total_txns),        help="Total transactions")
    k3.metric("Avg Basket",      fmt_currency(avg_basket),   help="Average transaction value")
    k4.metric("Sales / Sq Ft",   fmt_currency(avg_sales_sqft), help="Revenue per sq ft")
    k5.metric("Loyalty Penetr.", fmt_pct(loyalty_pct),       help="% customers enrolled in loyalty")
    k6.metric("Inv. Turnover",   fmt_num(avg_inv_turn, 1),   help="COGS / Avg Inventory (annualised)")

    st.divider()

    # ── Row 1: Gauges + Sales Trend ────────────────────────────────────────────
    col_g1, col_g2, col_g3, col_trend = st.columns([1, 1, 1, 3])

    # Enterprise health score (composite)
    health_score = min(100, (
        min(avg_basket / 75, 1) * 25 +
        min(loyalty_pct / 60, 1) * 25 +
        (1 - avg_churn / 100) * 25 +
        min(avg_sales_sqft / 500, 1) * 25
    ))
    col_g1.plotly_chart(gauge(health_score, "Enterprise Health"), use_container_width=True)
    col_g2.plotly_chart(gauge(loyalty_pct,  "Loyalty Penetr.", threshold_good=60, threshold_warn=40),
                        use_container_width=True)
    col_g3.plotly_chart(gauge(max(0, 100 - avg_churn * 5), "Customer Retention",
                              threshold_good=80, threshold_warn=60),
                        use_container_width=True)

    with col_trend:
        st.subheader("Daily Revenue Trend")
        daily_plot = daily.copy()
        daily_plot["transaction_date"] = pd.to_datetime(daily_plot["transaction_date"])
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=daily_plot["transaction_date"], y=daily_plot["total_sales"],
                                  name="Daily Sales", line=dict(color=SECONDARY, width=1),
                                  opacity=0.5))
        fig.add_trace(go.Scatter(x=daily_plot["transaction_date"], y=daily_plot["rolling_7d"],
                                  name="7-Day Avg", line=dict(color=ACCENT, width=2.5)))
        apply_dark_theme(fig, 240)
        fig.update_layout(margin=dict(t=10, b=20), legend=dict(orientation="h"))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 2: Monthly Sales by Region + Category Waterfall ───────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Monthly Revenue by Region")
        fig = px.area(monthly.sort_values("month"),
                      x="month", y="total_sales", color="region",
                      color_discrete_map=REGION_COLORS,
                      labels={"total_sales":"Revenue (USD)", "month":"Month"})
        apply_dark_theme(fig, 360)
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Revenue Contribution by Region")
        region_sum = monthly.groupby("region")["total_sales"].sum().reset_index()
        fig = px.treemap(region_sum, path=["region"], values="total_sales",
                         color="total_sales",
                         color_continuous_scale="Blues",
                         labels={"total_sales":"Revenue (USD)"})
        apply_dark_theme(fig, 360)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 3: Store Performance Table + Customer Health ──────────────────────
    col_left2, col_right2 = st.columns([3, 2])

    with col_left2:
        st.subheader("Top 20 Store Performance")
        top_stores = store_kpi.nlargest(20, "total_sales")[
            ["store_id","region","format","total_sales","sales_per_sqft_actual","atv","txn_count"]
        ].copy()
        top_stores["total_sales"] = top_stores["total_sales"].map(lambda x: fmt_currency(x))
        top_stores["sales_per_sqft_actual"] = top_stores["sales_per_sqft_actual"].map(lambda x: f"${x:.0f}")
        top_stores["atv"] = top_stores["atv"].map(lambda x: f"${x:.2f}")
        top_stores.columns = ["Store","Region","Format","Total Sales","$/SqFt","ATV","Transactions"]
        st.dataframe(top_stores, use_container_width=True, height=380)

    with col_right2:
        st.subheader("Customer Segments")
        rfm_plot = rfm.copy()
        fig = px.bar(rfm_plot, x="loyalty_segment", y="n_customers",
                     color="avg_clv", color_continuous_scale="Blues",
                     labels={"n_customers":"Customers","loyalty_segment":"Segment",
                             "avg_clv":"Avg CLV (USD)"})
        apply_dark_theme(fig, 380)
        fig.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 4: Loyalty Funnel + ATV trend ─────────────────────────────────────
    col_l3, col_r3 = st.columns(2)

    with col_l3:
        st.subheader("Loyalty Program Funnel")
        funnel_df = loyalty.copy()
        fig = go.Figure(go.Funnel(
            y=funnel_df["stage"], x=funnel_df["count"],
            textinfo="value+percent initial",
            marker={"color": [PRIMARY, SECONDARY, SUCCESS, ACCENT, DANGER]},
        ))
        apply_dark_theme(fig, 320)
        st.plotly_chart(fig, use_container_width=True)

    with col_r3:
        st.subheader("Monthly Avg Basket Value")
        atv = monthly.groupby("month")["atv"].mean().reset_index()
        fig = px.line(atv, x="month", y="atv",
                      labels={"atv":"Avg Basket (USD)", "month":"Month"})
        fig.update_traces(line_color=ACCENT, line_width=2.5)
        apply_dark_theme(fig, 320)
        fig.add_hline(y=75, line_dash="dash", line_color="white",
                      annotation_text="Target $75", annotation_position="bottom right")
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)




