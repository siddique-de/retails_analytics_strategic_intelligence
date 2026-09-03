"""
Page 11 – Space Management & Competitor Intelligence
Source: "Retail Analytics: The Secret Weapon" Ch. 7, 8
"""
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.data_loader import (ext_space_dept, ext_space_store, ext_space_region,
                                    ext_comp_gap, ext_comp_trend, ext_comp_region)
from dashboard.utils import (fmt_currency, fmt_pct, fmt_num, apply_dark_theme,
                               PALETTE, PRIMARY, SECONDARY, SUCCESS, DANGER, ACCENT, REGION_COLORS)


def render():
    st.title("🗂️ Space Management & Competitor Intelligence")
    st.caption("Ch. 7–8: Planogram compliance, space productivity, and competitor price positioning")

    space_dept  = ext_space_dept()
    space_store = ext_space_store()
    space_reg   = ext_space_region()
    comp_gap    = ext_comp_gap()
    comp_trend  = ext_comp_trend()
    comp_reg    = ext_comp_region()

    tabs = st.tabs(["🗺️ Space & Planogram Analytics",
                    "🏪 Competitor Intelligence"])

    # ────────────────────────────────────────────────────────────────────────
    # TAB 1: Space Management
    # ────────────────────────────────────────────────────────────────────────
    with tabs[0]:
        st.subheader("Space & Planogram Optimisation")

        avg_comp  = space_store["avg_compliance"].mean()
        best_dept = space_dept.iloc[0]["department"]
        worst_comp= space_store.loc[space_store["avg_compliance"].idxmin(), "store_id"]
        total_opp = space_dept["opportunity_usd"].sum()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Avg Planogram Compliance", fmt_pct(avg_comp))
        k2.metric("Top Sales/SqFt Dept",      best_dept)
        k3.metric("Revenue Opportunity",      fmt_currency(total_opp),
                   help="Estimated revenue from space reallocation")
        k4.metric("Worst Compliance Store",   worst_comp)

        st.divider()

        col_l, col_r = st.columns(2)

        with col_l:
            st.subheader("Sales/SqFt by Department (ranked)")
            fig = px.bar(space_dept, x="avg_sales_per_sqft", y="department",
                         orientation="h",
                         color="avg_compliance", color_continuous_scale="RdYlGn",
                         labels={"avg_sales_per_sqft":"Sales / SqFt ($)",
                                 "avg_compliance":"Compliance %"})
            apply_dark_theme(fig, 450)
            fig.add_vline(x=500, line_dash="dash", line_color="white",
                          annotation_text="Target $500/SqFt")
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            st.subheader("Allocated vs. Optimal Space % by Department")
            fig = go.Figure()
            fig.add_trace(go.Bar(name="Allocated %",
                                  x=space_dept["department"],
                                  y=space_dept["avg_allocated_pct"],
                                  marker_color=SECONDARY))
            fig.add_trace(go.Bar(name="Optimal %",
                                  x=space_dept["department"],
                                  y=space_dept["avg_optimal_pct"],
                                  marker_color=ACCENT, opacity=0.7))
            apply_dark_theme(fig, 450)
            fig.update_layout(barmode="group", xaxis_tickangle=-40)
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        col_l2, col_r2 = st.columns(2)

        with col_l2:
            st.subheader("Space Opportunity by Department ($)")
            fig = px.bar(space_dept.sort_values("opportunity_usd", ascending=False),
                         x="department", y="opportunity_usd",
                         color="avg_space_gap",
                         color_continuous_scale="YlOrRd",
                         labels={"opportunity_usd":"Revenue Opportunity ($)",
                                 "avg_space_gap":"Space Gap %"})
            apply_dark_theme(fig, 360)
            fig.update_layout(xaxis_tickangle=-40)
            st.plotly_chart(fig, use_container_width=True)

        with col_r2:
            st.subheader("Planogram Compliance by Region")
            fig = px.bar(space_reg, x="region", y="avg_compliance",
                         color="avg_sales_sqft", color_continuous_scale="Blues",
                         labels={"avg_compliance":"Avg Compliance %",
                                 "avg_sales_sqft":"Sales/SqFt ($)"})
            apply_dark_theme(fig, 360)
            fig.add_hline(y=90, line_dash="dash", line_color="white",
                          annotation_text="Target 90%")
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        st.subheader("Store-Level Compliance Distribution")
        fig = px.histogram(space_store, x="avg_compliance", nbins=30,
                            color_discrete_sequence=[SECONDARY],
                            labels={"avg_compliance":"Planogram Compliance %"})
        apply_dark_theme(fig, 300)
        fig.add_vline(x=90, line_dash="dash", line_color=ACCENT,
                      annotation_text="Target 90%")
        st.plotly_chart(fig, use_container_width=True)

    # ────────────────────────────────────────────────────────────────────────
    # TAB 2: Competitor Intelligence
    # ────────────────────────────────────────────────────────────────────────
    with tabs[1]:
        st.subheader("Competitor Price Intelligence")
        st.caption("Weekly price gap monitoring vs. key competitors")

        # Sidebar filters within tab
        competitors = ["All"] + sorted(comp_gap["competitor"].unique().tolist())
        sel_comp = st.selectbox("Filter Competitor", competitors)

        cg = comp_gap.copy()
        if sel_comp != "All": cg = cg[cg["competitor"] == sel_comp]

        avg_gap    = cg["avg_price_gap"].mean()
        pct_prem   = cg["pct_premium"].mean() * 100
        best_pos_dept = comp_gap.groupby("department")["avg_price_gap"].mean().idxmax()
        worst_pos_dept= comp_gap.groupby("department")["avg_price_gap"].mean().idxmin()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Avg Price Gap vs Comp",  fmt_pct(avg_gap),
                   help="Positive = our price higher", delta_color="inverse")
        k2.metric("% SKUs at Premium",      fmt_pct(pct_prem))
        k3.metric("Best Positioned Dept",   best_pos_dept, help="Largest positive gap")
        k4.metric("Most Exposed Dept",      worst_pos_dept, help="Most negative gap")

        st.divider()

        col_l, col_r = st.columns(2)

        with col_l:
            st.subheader("Price Gap by Competitor (Dept avg)")
            fig = px.bar(cg.groupby("competitor")["avg_price_gap"].mean().reset_index(),
                         x="competitor", y="avg_price_gap",
                         color="avg_price_gap", color_continuous_scale="RdYlGn",
                         labels={"avg_price_gap":"Avg Price Gap %","competitor":"Competitor"})
            apply_dark_theme(fig, 380)
            fig.add_hline(y=0, line_dash="solid", line_color="white")
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            st.subheader("Price Position Distribution Over Time")
            comp_trend["week_start"] = pd.to_datetime(comp_trend["week_start"])
            fig = px.bar(comp_trend.sort_values("week_start"),
                         x="week_start", y="count", color="price_position",
                         color_discrete_map={"Premium":SUCCESS,
                                             "Parity":SECONDARY,
                                             "Value":DANGER},
                         barmode="stack",
                         labels={"count":"SKU Observations","week_start":"Week"})
            apply_dark_theme(fig, 380)
            fig.update_layout(xaxis_tickangle=-30)
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        col_l2, col_r2 = st.columns(2)

        with col_l2:
            st.subheader("Price Gap Heatmap: Competitor × Department")
            piv = cg.pivot_table(index="competitor", columns="department",
                                   values="avg_price_gap", aggfunc="mean").fillna(0)
            fig = px.imshow(piv, color_continuous_scale="RdYlGn",
                             labels=dict(x="Department", y="Competitor",
                                         color="Price Gap %"),
                             text_auto=".1f", aspect="auto")
            apply_dark_theme(fig, 420)
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)

        with col_r2:
            st.subheader("Competitor Promo Activity by Region")
            fig = px.bar(comp_reg, x="region", y="avg_gap",
                         color="competitor",
                         barmode="group",
                         color_discrete_sequence=PALETTE,
                         labels={"avg_gap":"Avg Price Gap %","region":"Region"})
            apply_dark_theme(fig, 420)
            fig.add_hline(y=0, line_color="white", line_dash="solid")
            st.plotly_chart(fig, use_container_width=True)
