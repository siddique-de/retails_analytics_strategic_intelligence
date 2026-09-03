"""
Page 5 – Marketing, Promotions & Data Monetisation
"""
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.data_loader import (mkt_channel_roi, mkt_monthly_media,
                                    mkt_data_monetise, mkt_ab_summary,
                                    mkt_promo_roi)
from dashboard.utils import (fmt_currency, fmt_pct, fmt_num, apply_dark_theme,
                               waterfall, PALETTE, PRIMARY, SECONDARY,
                               SUCCESS, DANGER, ACCENT, REGION_COLORS)


def render():
    st.title("📣 Marketing, Promotions & Data Monetisation")
    st.caption("Measure and optimise marketing ROI across all channels")

    ch_roi   = mkt_channel_roi()
    monthly  = mkt_monthly_media()
    monetise = mkt_data_monetise()
    ab_sum   = mkt_ab_summary()
    promo_roi= mkt_promo_roi()

    monthly["month"] = monthly["month"].astype(str)

    # ── Sidebar ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.subheader("Marketing Filters")
        regions  = ["All"] + sorted(ch_roi["region"].dropna().unique().tolist())
        sel_reg  = st.selectbox("Region", regions)
        channels = ["All"] + sorted(ch_roi["channel"].dropna().unique().tolist())
        sel_chan = st.selectbox("Channel", channels)

    cr = ch_roi.copy()
    if sel_reg  != "All": cr = cr[cr["region"]  == sel_reg]
    if sel_chan  != "All": cr = cr[cr["channel"] == sel_chan]

    mm = monthly.copy()
    if sel_chan != "All": mm = mm[mm["channel"] == sel_chan]

    # ── KPIs ──────────────────────────────────────────────────────────────────
    total_spend  = cr["total_spend"].sum()
    total_attr   = cr["total_attributed_sales"].sum()
    avg_roas     = cr["roas"].mean()
    total_mono   = monetise["revenue_usd"].sum()
    sig_pct      = ab_sum["sig_pct"].mean() * 100
    best_roi_ch  = ch_roi.groupby("channel")["avg_roi"].mean().idxmax()

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Media Spend",  fmt_currency(total_spend))
    k2.metric("Attributed Sales",   fmt_currency(total_attr))
    k3.metric("Avg ROAS",           fmt_num(avg_roas, 2),     help="Attributed Sales / Spend")
    k4.metric("Data Revenue (POS)", fmt_currency(total_mono), help="ACNielsen, NPD, IRI")
    k5.metric("A/B Sig. Rate",      fmt_pct(sig_pct),         help="% tests with p<0.05")

    st.divider()

    # ── Row 1: Channel ROI Bar + ROAS Scatter ─────────────────────────────────
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Channel ROI – All Regions")
        ch_agg = ch_roi.groupby("channel").agg(
            avg_roi=("avg_roi","mean"), total_spend=("total_spend","sum"),
            roas=("roas","mean")).reset_index().sort_values("avg_roi", ascending=False)
        fig = px.bar(ch_agg, x="channel", y="avg_roi",
                     color="roas", color_continuous_scale="YlGn",
                     labels={"avg_roi":"Avg ROI","channel":"Channel","roas":"ROAS"})
        apply_dark_theme(fig, 380)
        fig.add_hline(y=1, line_dash="dash", line_color="white",
                      annotation_text="Break-even ROI=1")
        fig.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("Spend vs. Attributed Sales (Bubble)")
        ch_agg2 = ch_roi.groupby("channel").agg(
            total_spend=("total_spend","sum"),
            total_attr=("total_attributed_sales","sum"),
            saturation=("saturation_count","sum")).reset_index()
        fig = px.scatter(ch_agg2, x="total_spend", y="total_attr",
                         size="saturation", color="channel",
                         text="channel",
                         color_discrete_sequence=PALETTE,
                         labels={"total_spend":"Total Spend ($)",
                                 "total_attr":"Attributed Sales ($)",
                                 "saturation":"Saturation Signals"})
        fig.update_traces(textposition="top center")
        apply_dark_theme(fig, 380)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 2: Monthly Media Mix + Data Monetisation ──────────────────────────
    col_l2, col_r2 = st.columns(2)

    with col_l2:
        st.subheader("Monthly Media Spend by Channel")
        fig = px.area(mm.sort_values("month"),
                      x="month", y="spend", color="channel",
                      color_discrete_sequence=PALETTE,
                      labels={"spend":"Spend ($)","month":"Month"})
        apply_dark_theme(fig, 360)
        fig.update_layout(xaxis_tickangle=-45, legend=dict(orientation="h", y=-0.35))
        st.plotly_chart(fig, use_container_width=True)

    with col_r2:
        st.subheader("POS Data Monetisation Revenue")
        mono_m = monetise.copy()
        mono_m["month"] = pd.to_datetime(mono_m["month"].str[:7])
        mono_monthly = mono_m.groupby(["month","data_buyer"])["revenue_usd"].sum().reset_index()
        fig = px.bar(mono_monthly, x="month", y="revenue_usd", color="data_buyer",
                     color_discrete_sequence=PALETTE,
                     barmode="stack",
                     labels={"revenue_usd":"Revenue ($)","data_buyer":"Buyer"})
        apply_dark_theme(fig, 360)
        annual = mono_m.groupby(mono_m["month"].dt.year)["revenue_usd"].sum()
        for yr, rev in annual.items():
            st.caption(f"**{yr}**: {fmt_currency(rev)} data revenue")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 3: A/B Tests + Promo Type ROI ─────────────────────────────────────
    col_l3, col_r3 = st.columns(2)

    with col_l3:
        st.subheader("A/B Test Results by Test Type")
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Significance Rate %",
                              x=ab_sum["test_type"], y=ab_sum["sig_pct"]*100,
                              marker_color=SECONDARY))
        fig.add_trace(go.Scatter(name="Avg Uplift %",
                                  x=ab_sum["test_type"], y=ab_sum["avg_uplift"],
                                  mode="lines+markers", line=dict(color=ACCENT, width=2.5),
                                  yaxis="y2"))
        fig.update_layout(
            yaxis=dict(title="Significance Rate %"),
            yaxis2=dict(title="Avg Uplift %", overlaying="y", side="right"),
        )
        apply_dark_theme(fig, 360)
        fig.update_layout(xaxis_tickangle=-20)
        st.plotly_chart(fig, use_container_width=True)

    with col_r3:
        st.subheader("Promotion Type – ROI & Avoidable Markdowns")
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Avg ROI",
                              x=promo_roi["promo_type"], y=promo_roi["avg_roi"],
                              marker_color=SECONDARY))
        fig.add_trace(go.Scatter(name="% Avoidable Markdowns",
                                  x=promo_roi["promo_type"],
                                  y=promo_roi["pct_avoidable"]*100,
                                  mode="lines+markers",
                                  line=dict(color=DANGER, width=2.5),
                                  yaxis="y2"))
        fig.update_layout(
            yaxis=dict(title="Avg ROI"),
            yaxis2=dict(title="Avoidable Markdown %", overlaying="y", side="right"),
        )
        apply_dark_theme(fig, 360)
        fig.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 4: Regional Spend Distribution ────────────────────────────────────
    st.subheader("Regional Media Spend Allocation")
    reg_spend = ch_roi.groupby("region")["total_spend"].sum().reset_index()
    fig = px.pie(reg_spend, names="region", values="total_spend",
                 color="region", color_discrete_map=REGION_COLORS, hole=0.35)
    apply_dark_theme(fig, 300)
    st.plotly_chart(fig, use_container_width=True)




