"""
Page 3 – Store Operations & Real Estate
"""
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.data_loader import (ops_store_health, ops_labour_heat,
                                    ops_layout, ops_site_sel, ops_traffic_trend,
                                    gis_stores, gis_regions, gis_candidates)
from dashboard.utils import (fmt_currency, fmt_pct, fmt_num, apply_dark_theme,
                               gauge, PALETTE, PRIMARY, SECONDARY,
                               SUCCESS, DANGER, ACCENT, REGION_COLORS)


def render():
    st.title("🏪 Store Operations & Real Estate")
    st.caption("Optimise store performance, labour costs, and real estate decisions")

    health   = ops_store_health()
    labour   = ops_labour_heat()
    layout   = ops_layout()
    site     = ops_site_sel()
    traffic  = ops_traffic_trend()
    gis      = gis_stores()
    regions  = gis_regions()

    # ── Sidebar ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.subheader("Store Operations Filters")
        all_regions = ["All"] + sorted(health["region"].dropna().unique().tolist())
        sel_region  = st.selectbox("Region", all_regions)
        all_formats = ["All"] + sorted(health["format"].dropna().unique().tolist())
        sel_format  = st.selectbox("Store Format", all_formats)

    h = health.copy()
    if sel_region != "All": h = h[h["region"] == sel_region]
    if sel_format != "All": h = h[h["format"] == sel_format]

    # ── KPIs ──────────────────────────────────────────────────────────────────
    avg_sps    = h["sales_per_sqft_actual"].mean()
    avg_conv   = h["avg_conversion"].mean() * 100
    avg_queue  = h["avg_queue"].mean()
    sla_pct    = h["sla_pct"].mean() * 100
    avg_traffic= h["avg_traffic"].mean()
    total_labour_pct = h["labour_pct_sales"].mean()

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Avg Sales/SqFt",   fmt_currency(avg_sps))
    k2.metric("Avg Conversion",   fmt_pct(avg_conv))
    k3.metric("Avg Queue Length", fmt_num(avg_queue, 1), delta=f"SLA {'✓' if avg_queue <= 3 else '✗'}",
              delta_color="normal" if avg_queue <= 3 else "inverse")
    k4.metric("Queue SLA Met",    fmt_pct(sla_pct))
    k5.metric("Avg Daily Traffic",fmt_num(avg_traffic))
    k6.metric("Labour % Sales",   fmt_pct(total_labour_pct))

    st.divider()

    # ── Row 1: Store Map + Region Summary ─────────────────────────────────────
    col_map, col_reg = st.columns([3, 2])

    with col_map:
        st.subheader("Store Network Map")
        map_df = gis.copy()
        if sel_region != "All":
            map_df = map_df[map_df["region"] == sel_region]
        fig = px.scatter_mapbox(
            map_df, lat="latitude", lon="longitude",
            color="region", size="size_sqft",
            color_discrete_map=REGION_COLORS,
            hover_data=["store_id","format","city","size_sqft"],
            zoom=1, height=400,
        )
        fig.update_layout(mapbox_style="carto-darkmatter",
                          paper_bgcolor="rgba(0,0,0,0)", font_color="white",
                          margin=dict(t=0,b=0,l=0,r=0), legend=dict(bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig, use_container_width=True)

    with col_reg:
        st.subheader("Region Summary")
        reg_df = regions.copy()
        st.dataframe(
            reg_df[["region","n_stores","avg_gravity","avg_breakeven_before",
                    "avg_breakeven_after","avg_predicted_sales"]]
            .rename(columns={"region":"Region","n_stores":"Stores",
                             "avg_gravity":"Gravity Score",
                             "avg_breakeven_before":"Breakeven (Before)",
                             "avg_breakeven_after":"Breakeven (After)",
                             "avg_predicted_sales":"Pred. Sales ($)"}),
            use_container_width=True, height=400
        )

    st.divider()

    # ── Row 2: Labour Heatmap + Traffic Trend ─────────────────────────────────
    col_l2, col_r2 = st.columns(2)

    with col_l2:
        st.subheader("Labour – Avg Queue by Hour of Day")
        lh = (labour.groupby("hour_of_day")
              .agg(avg_queue=("avg_queue","mean"), avg_staff=("avg_staff","mean"))
              .reset_index())
        fig = go.Figure()
        fig.add_trace(go.Bar(x=lh["hour_of_day"], y=lh["avg_queue"],
                              name="Avg Queue", marker_color=SECONDARY))
        fig.add_hline(y=3, line_dash="dash", line_color=DANGER,
                      annotation_text="SLA = 3")
        apply_dark_theme(fig, 340)
        fig.update_layout(xaxis_title="Hour", yaxis_title="Avg Queue Length")
        st.plotly_chart(fig, use_container_width=True)

    with col_r2:
        st.subheader("Daily Traffic Trend")
        tr = traffic.copy()
        tr["traffic_date"] = pd.to_datetime(tr["traffic_date"])
        tr["rolling_14d"] = tr["avg_traffic"].rolling(14, min_periods=1).mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=tr["traffic_date"], y=tr["avg_traffic"],
                                  name="Daily Traffic", line=dict(color=SECONDARY, width=1),
                                  opacity=0.4))
        fig.add_trace(go.Scatter(x=tr["traffic_date"], y=tr["rolling_14d"],
                                  name="14-Day Avg", line=dict(color=ACCENT, width=2.5)))
        apply_dark_theme(fig, 340)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 3: Store health scorecard + Layout test results ───────────────────
    col_l3, col_r3 = st.columns([3, 2])

    with col_l3:
        st.subheader("Store Health Scorecard (Top 25)")
        top25 = h.nlargest(25, "total_sales")[
            ["store_id","region","format","total_sales","sales_per_sqft_actual",
             "avg_conversion","avg_queue","sla_pct"]
        ].copy()
        top25["total_sales"] = top25["total_sales"].map(fmt_currency)
        top25["sales_per_sqft_actual"] = top25["sales_per_sqft_actual"].map(lambda x: f"${x:.0f}")
        top25["avg_conversion"] = top25["avg_conversion"].map(lambda x: fmt_pct(x*100))
        top25["avg_queue"]      = top25["avg_queue"].map(lambda x: f"{x:.2f}")
        top25["sla_pct"]        = top25["sla_pct"].map(lambda x: fmt_pct(x*100))
        top25.columns = ["Store","Region","Format","Revenue","$/SqFt","Conv.","Avg Queue","SLA%"]
        st.dataframe(top25, use_container_width=True, height=440)

    with col_r3:
        st.subheader("Store-in-a-Store Layout Uplift")
        fig = px.bar(layout.sort_values("avg_uplift", ascending=False),
                     x="avg_uplift", y="department", orientation="h",
                     color="avg_sku_reduction",
                     color_continuous_scale="Greens",
                     labels={"avg_uplift":"Sales Uplift %",
                             "avg_sku_reduction":"SKU Reduction %"})
        apply_dark_theme(fig, 440)
        fig.add_vline(x=20, line_dash="dash", line_color="white",
                      annotation_text="Target 20%")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 4: Site Selection ─────────────────────────────────────────────────
    st.subheader("🗺️ Candidate Site Selection Analysis")
    col_map2, col_box = st.columns([3, 2])

    with col_map2:
        site_map = site.copy()
        if sel_region != "All":
            site_map = site_map[site_map["region"] == sel_region]
        fig = px.scatter_mapbox(
            site_map, lat="latitude", lon="longitude",
            color="selected", size="gravity_score",
            color_discrete_map={0:"#E74C3C", 1:"#27AE60"},
            hover_data=["candidate_id","proposed_format",
                        "gravity_score","forecast_breakeven_yrs"],
            zoom=1, height=380,
        )
        fig.update_layout(mapbox_style="carto-darkmatter",
                          paper_bgcolor="rgba(0,0,0,0)", font_color="white",
                          margin=dict(t=0,b=0,l=0,r=0))
        st.plotly_chart(fig, use_container_width=True)

    with col_box:
        fig = px.box(site, x="proposed_format", y="forecast_breakeven_yrs",
                     color="proposed_format",
                     color_discrete_sequence=PALETTE,
                     labels={"forecast_breakeven_yrs":"Breakeven (Years)",
                             "proposed_format":"Format"})
        apply_dark_theme(fig, 380)
        fig.add_hline(y=2, line_dash="dash", line_color=SUCCESS,
                      annotation_text="Target 2yrs")
        fig.add_hline(y=6, line_dash="dash", line_color=DANGER,
                      annotation_text="Old target 6yrs")
        st.plotly_chart(fig, use_container_width=True)




