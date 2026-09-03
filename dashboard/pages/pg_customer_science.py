"""
Page 10 – Customer Science: Purchase Cycles, ATF/ATV & Acquisition
Source: "Retail Analytics: The Secret Weapon" Ch. 3, 4, 6
"""
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.data_loader import (ext_pc_dept, ext_at_risk, ext_pc_detail,
                                    ext_acq_channel, ext_acq_region, ext_acq_detail,
                                    ext_atf_atv_seg, ext_atf_atv_age, ext_atf_atv_fmt)
from dashboard.utils import (fmt_currency, fmt_pct, fmt_num, apply_dark_theme,
                               PALETTE, PRIMARY, SECONDARY, SUCCESS, DANGER, ACCENT)

SEG_COLORS = {
    "Loyalist": "#27AE60", "Soccer Mom": "#2E86C1",
    "Cherry Picker": "#F39C12", "Occasional Shopper": "#8E44AD",
    "Lapsed": "#E74C3C", "New Customer": "#16A085",
}


def render():
    st.title("🧠 Customer Science: Cycles, ATF/ATV & Acquisition")
    st.caption("Ch. 3–4, 6: ATF/ATV KPIs, purchase cycle prediction, and acquisition channel ROI")

    pc_dept  = ext_pc_dept()
    at_risk  = ext_at_risk()
    pc_det   = ext_pc_detail()
    acq_ch   = ext_acq_channel()
    acq_reg  = ext_acq_region()
    atf_seg  = ext_atf_atv_seg()
    atf_age  = ext_atf_atv_age()
    atf_fmt  = ext_atf_atv_fmt()

    tabs = st.tabs(["📊 ATF & ATV Analysis",
                    "🔄 Purchase Cycle Analytics",
                    "📥 Customer Acquisition"])

    # ────────────────────────────────────────────────────────────────────────
    # TAB 1: ATF / ATV
    # ────────────────────────────────────────────────────────────────────────
    with tabs[0]:
        st.subheader("Average Transaction Frequency (ATF) & Value (ATV)")
        st.caption("Core retail health metrics – how often customers shop and how much they spend per visit")

        # KPIs
        overall_atf = atf_seg["avg_atf"].mean()
        overall_atv = atf_seg["avg_atv"].mean()
        overall_spend = atf_seg["avg_annual_spend"].mean()
        top_seg = atf_seg.loc[atf_seg["avg_annual_spend"].idxmax(), "loyalty_segment"]

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Overall Avg ATF",         f"{overall_atf:.1f} trips/yr")
        k2.metric("Overall Avg ATV",         fmt_currency(overall_atv))
        k3.metric("Avg Annual Spend",        fmt_currency(overall_spend))
        k4.metric("Highest Value Segment",   top_seg)

        st.divider()

        col_l, col_r = st.columns(2)
        with col_l:
            st.subheader("ATF vs ATV by Segment (Bubble = Annual Spend)")
            fig = px.scatter(atf_seg, x="avg_atf", y="avg_atv",
                              size="avg_annual_spend",
                              color="loyalty_segment",
                              color_discrete_map=SEG_COLORS,
                              text="loyalty_segment",
                              size_max=50,
                              labels={"avg_atf":"Avg ATF (trips/yr)",
                                      "avg_atv":"Avg ATV ($)",
                                      "loyalty_segment":"Segment"})
            fig.update_traces(textposition="top center")
            apply_dark_theme(fig, 420)
            fig.add_hline(y=75, line_dash="dash", line_color="white",
                          annotation_text="ATV Target $75")
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            st.subheader("ATF × ATV (Annual Spend) by Segment & Region")
            fig = px.bar(atf_seg.sort_values("avg_annual_spend", ascending=False),
                         x="loyalty_segment", y="avg_annual_spend",
                         color="region",
                         barmode="group",
                         color_discrete_sequence=PALETTE,
                         labels={"avg_annual_spend":"Avg Annual Spend ($)",
                                 "loyalty_segment":"Segment"})
            apply_dark_theme(fig, 420)
            fig.update_layout(xaxis_tickangle=-25)
            st.plotly_chart(fig, use_container_width=True)

        st.divider()
        col_l2, col_r2 = st.columns(2)

        with col_l2:
            st.subheader("ATF by Age Group & Loyalty Segment")
            fig = px.bar(atf_age, x="age_group", y="avg_atf",
                         color="loyalty_segment",
                         color_discrete_map=SEG_COLORS,
                         barmode="group",
                         labels={"avg_atf":"Avg ATF","age_group":"Age Group"})
            apply_dark_theme(fig, 360)
            st.plotly_chart(fig, use_container_width=True)

        with col_r2:
            st.subheader("ATV by Store Format & Segment")
            fig = px.bar(atf_fmt, x="preferred_format", y="avg_atv",
                         color="loyalty_segment",
                         color_discrete_map=SEG_COLORS,
                         barmode="group",
                         labels={"avg_atv":"Avg ATV ($)","preferred_format":"Format"})
            apply_dark_theme(fig, 360)
            fig.add_hline(y=75, line_dash="dash", line_color="white",
                          annotation_text="Target $75")
            st.plotly_chart(fig, use_container_width=True)

    # ────────────────────────────────────────────────────────────────────────
    # TAB 2: Purchase Cycle
    # ────────────────────────────────────────────────────────────────────────
    with tabs[1]:
        st.subheader("Purchase Cycle Analysis")
        st.caption("Inter-purchase intervals by department – when to trigger re-engagement messages")

        n_at_risk = len(at_risk)
        avg_cycle = pc_dept["avg_cycle_days"].mean()
        pct_overdue = pc_dept["overdue_pct"].mean()
        fastest_dept = pc_dept.loc[pc_dept["avg_cycle_days"].idxmin(), "department"]

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Avg Purchase Cycle",  f"{avg_cycle:.0f} days")
        k2.metric("% Customers Overdue", fmt_pct(pct_overdue))
        k3.metric("At-Risk Customers",   fmt_num(n_at_risk),
                   help="Overdue in 2+ departments")
        k4.metric("Fastest Cycle Dept",  fastest_dept)

        st.divider()

        col_l, col_r = st.columns(2)

        with col_l:
            st.subheader("Avg Purchase Cycle by Department")
            pc_s = pc_dept.sort_values("avg_cycle_days")
            fig = px.bar(pc_s, x="avg_cycle_days", y="department", orientation="h",
                         color="overdue_pct", color_continuous_scale="RdYlGn_r",
                         labels={"avg_cycle_days":"Avg Cycle (days)",
                                 "overdue_pct":"Overdue %"})
            apply_dark_theme(fig, 420)
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            st.subheader("Days Since Last Purchase vs. Predicted Next")
            fig = px.scatter(pc_dept, x="avg_days_since", y="avg_predicted_next",
                              size="avg_annual_freq", color="overdue_pct",
                              color_continuous_scale="RdYlGn_r",
                              text="department",
                              labels={"avg_days_since":"Avg Days Since Last Purchase",
                                      "avg_predicted_next":"Avg Days to Next Purchase",
                                      "avg_annual_freq":"Annual Frequency"})
            fig.update_traces(textposition="top center")
            apply_dark_theme(fig, 420)
            fig.add_line(x0=0, y0=0, x1=200, y1=200,  # diagonal = overdue line
                         line_dict=dict(color="white", dash="dash", width=1))
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        st.subheader("Purchase Cycle Stability by Department")
        fig = px.box(pc_det, x="department", y="avg_cycle_days",
                     color="is_overdue",
                     color_discrete_map={True: DANGER, False: SUCCESS},
                     labels={"avg_cycle_days":"Cycle Days","is_overdue":"Overdue?"})
        apply_dark_theme(fig, 380)
        fig.update_layout(xaxis_tickangle=-40)
        st.plotly_chart(fig, use_container_width=True)

    # ────────────────────────────────────────────────────────────────────────
    # TAB 3: Customer Acquisition
    # ────────────────────────────────────────────────────────────────────────
    with tabs[2]:
        st.subheader("Customer Acquisition Analytics")
        st.caption("CAC, activation rates, and channel ROI — who acquires the best customers?")

        best_roi_ch = acq_ch.loc[acq_ch["avg_roi"].idxmax(), "acquisition_channel"]
        lowest_cac  = acq_ch.loc[acq_ch["avg_cac"].idxmin(), "acquisition_channel"]
        avg_payback = acq_ch["avg_payback_days"].mean()
        overall_activ = acq_ch["activation_pct"].mean()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Best ROI Channel",   best_roi_ch)
        k2.metric("Lowest CAC Channel", lowest_cac)
        k3.metric("Avg Payback Period", f"{avg_payback:.0f} days")
        k4.metric("Overall Activation", fmt_pct(overall_activ))

        st.divider()

        col_l, col_r = st.columns(2)

        with col_l:
            st.subheader("CAC vs. 90-Day Revenue by Channel")
            fig = px.scatter(acq_ch, x="avg_cac", y="avg_first90",
                              size="n_customers", color="acquisition_channel",
                              text="acquisition_channel",
                              color_discrete_sequence=PALETTE,
                              labels={"avg_cac":"Avg CAC ($)",
                                      "avg_first90":"Avg 90-Day Revenue ($)"})
            fig.update_traces(textposition="top center")
            apply_dark_theme(fig, 420)
            # Diagonal = breakeven line
            max_v = max(acq_ch["avg_first90"].max(), acq_ch["avg_cac"].max())
            fig.add_scatter(x=[0, max_v], y=[0, max_v], mode="lines",
                             line=dict(color="white", dash="dash", width=1),
                             name="Break-even")
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            st.subheader("Activation & Repeat Rate by Channel")
            fig = go.Figure()
            fig.add_trace(go.Bar(x=acq_ch["acquisition_channel"],
                                  y=acq_ch["activation_pct"],
                                  name="Activation %", marker_color=SECONDARY))
            fig.add_trace(go.Scatter(x=acq_ch["acquisition_channel"],
                                      y=acq_ch["repeat_pct"],
                                      mode="lines+markers", name="Repeat 30d %",
                                      line=dict(color=ACCENT, width=2.5), yaxis="y2"))
            fig.update_layout(yaxis=dict(title="Activation %"),
                               yaxis2=dict(title="Repeat %", overlaying="y", side="right"),
                               xaxis_tickangle=-30)
            apply_dark_theme(fig, 420)
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        st.subheader("Channel Performance by Region")
        fig = px.bar(acq_reg, x="acquisition_channel", y="n",
                     color="region", barmode="group",
                     color_discrete_sequence=PALETTE,
                     labels={"n":"Customers Acquired","acquisition_channel":"Channel"})
        apply_dark_theme(fig, 360)
        fig.update_layout(xaxis_tickangle=-25)
        st.plotly_chart(fig, use_container_width=True)
