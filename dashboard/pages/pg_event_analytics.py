"""
Page 12 – Event Impact & External Factor Analytics
Source: "Retail Analytics: The Secret Weapon" Ch. 9
Also covers the book's famous case studies as worked examples.
"""
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.data_loader import (ext_event_summary, ext_event_region, ext_event_dept)
from dashboard.utils import (fmt_currency, fmt_pct, fmt_num, apply_dark_theme,
                               PALETTE, PRIMARY, SECONDARY, SUCCESS, DANGER, ACCENT, REGION_COLORS)


# ── Book case studies (hardcoded from Emmett Cox's documented outcomes) ───────
CASE_STUDIES = [
    {
        "name":        "White Lake Store Redesign",
        "chapter":     "Ch. 7 – Space Management",
        "technique":   "Planogram Optimisation + Affinity-Based Layout",
        "finding":     "Repositioned key categories based on purchase affinities. "
                       "Reduced total SKUs by 20% while redesigning end-caps around proven cross-sell pairs.",
        "outcome":     "20–30% sales increase",
        "outcome_val": 25.0,
        "metric":      "Sales Uplift %",
        "color":       "#27AE60",
    },
    {
        "name":        "Paper Towel Promotion Analysis",
        "chapter":     "Ch. 5 – Promotional Analytics",
        "technique":   "True Incremental Sales (cannibalisation deduction)",
        "finding":     "Consumers bought the same affinities regardless of the paper towel discount. "
                       "No true incremental sales were generated; the promotion only shifted spending "
                       "forward (pantry loading) without growing the basket.",
        "outcome":     "$0 true incremental (avoided unnecessary markdown)",
        "outcome_val": 0.0,
        "metric":      "True Lift ($M)",
        "color":       "#E74C3C",
    },
    {
        "name":        "Lifesavers Cross-Merchandising",
        "chapter":     "Ch. 6 – Market Basket Analytics",
        "technique":   "Affinity / Lift Analysis",
        "finding":     "High lift score identified Lifesavers candy placed near checkout "
                       "generated measurable incremental sales when positioned adjacent to "
                       "beverages — a non-obvious affinity pair.",
        "outcome":     "15% lift in confectionery sales",
        "outcome_val": 15.0,
        "metric":      "Category Sales Lift %",
        "color":       "#F39C12",
    },
    {
        "name":        "FlyBuys Loyalty Programme (Australia)",
        "chapter":     "Ch. 10 – Loyalty Analytics",
        "technique":   "RFM Segmentation + Tier Design",
        "finding":     "Segmented members into Loyalists, Cherry Pickers, and Soccer Moms. "
                       "Personalised offers per segment doubled redemption rates vs. blanket offers.",
        "outcome":     "2× redemption rate improvement",
        "outcome_val": 100.0,
        "metric":      "Redemption Rate Lift %",
        "color":       "#2E86C1",
    },
    {
        "name":        "Kmart School Spirit Programme (US)",
        "chapter":     "Ch. 10 – Loyalty Analytics",
        "technique":   "Community Loyalty + Emotional Engagement",
        "finding":     "School-linked loyalty programme drove repeat visits beyond "
                       "transactional motivation. Families shopped more frequently with "
                       "higher basket sizes when community impact was visible.",
        "outcome":     "22% increase in trip frequency among enrolled families",
        "outcome_val": 22.0,
        "metric":      "ATF Increase %",
        "color":       "#8E44AD",
    },
    {
        "name":        "New Store Breakeven Reduction",
        "chapter":     "Ch. 8 – Real Estate Analytics",
        "technique":   "Gravity Model + Transfer Sales Analysis",
        "finding":     "Applied Huff gravity model and transfer sales model to identify "
                       "optimal trade areas. Sister-store benchmarking set realistic revenue "
                       "forecasts, enabling more accurate site scoring.",
        "outcome":     "Breakeven reduced from 6 years → 2 years",
        "outcome_val": 67.0,
        "metric":      "Breakeven Time Reduction %",
        "color":       "#16A085",
    },
    {
        "name":        "POS Data Monetisation",
        "chapter":     "Ch. 2 – Data as an Asset",
        "technique":   "SKU-Level POS Data Sales to Third-Party Aggregators",
        "finding":     "Non-identifiable, store-level POS data sold to ACNielsen, NPD, and IRI. "
                       "Analytics department became self-funding within 18 months.",
        "outcome":     "$20M–$30M annual revenue",
        "outcome_val": 25.0,
        "metric":      "Annual Revenue ($M)",
        "color":       "#F39C12",
    },
]


def render():
    st.title("📅 Event Impact Analytics & Book Case Studies")
    st.caption("Ch. 9: External factor analysis – plus worked examples from Emmett Cox's documented retail outcomes")

    ev_sum  = ext_event_summary()
    ev_reg  = ext_event_region()
    ev_dept = ext_event_dept()

    tabs = st.tabs(["📊 Event Impact Analysis",
                    "📖 Case Study Library"])

    # ────────────────────────────────────────────────────────────────────────
    # TAB 1: Event Impact
    # ────────────────────────────────────────────────────────────────────────
    with tabs[0]:
        st.subheader("Special Event & External Factor Impact")

        best_event  = ev_sum.loc[ev_sum["avg_uplift_pct"].idxmax(), "event_type"]
        worst_event = ev_sum.loc[ev_sum["avg_uplift_pct"].idxmin(), "event_type"]
        total_incr  = ev_sum["total_incremental"].sum()
        prep_gap    = (1 - ev_sum["prep_pct"].mean() / 100) * 100

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Best Uplift Event",      best_event)
        k2.metric("Most Disruptive Event",  worst_event,
                   help="Lowest uplift / potential downside")
        k3.metric("Total Incremental Rev.", fmt_currency(total_incr))
        k4.metric("Unprepared Rate",        fmt_pct(prep_gap),
                   help="% of events stores were not prepared for", delta_color="inverse")

        st.divider()

        col_l, col_r = st.columns(2)

        with col_l:
            st.subheader("Event Uplift % (Avg) – All Regions")
            ev_s = ev_sum.sort_values("avg_uplift_pct", ascending=True)
            colors = [SUCCESS if v > 0 else DANGER for v in ev_s["avg_uplift_pct"]]
            fig = px.bar(ev_s, x="avg_uplift_pct", y="event_type",
                         orientation="h",
                         color="avg_uplift_pct", color_continuous_scale="RdYlGn",
                         labels={"avg_uplift_pct":"Avg Uplift %","event_type":"Event"})
            apply_dark_theme(fig, 420)
            fig.add_vline(x=0, line_color="white", line_dash="solid")
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            st.subheader("Preparation Rate vs. Uplift")
            fig = px.scatter(ev_sum, x="prep_pct", y="avg_uplift_pct",
                              size="n_occurrences", color="event_type",
                              color_discrete_sequence=PALETTE,
                              text="event_type",
                              labels={"prep_pct":"Preparation Rate %",
                                      "avg_uplift_pct":"Avg Uplift %",
                                      "n_occurrences":"Occurrences"})
            fig.update_traces(textposition="top center")
            apply_dark_theme(fig, 420)
            fig.add_vline(x=70, line_dash="dash", line_color="white",
                          annotation_text="Target 70% prep")
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        col_l2, col_r2 = st.columns(2)

        with col_l2:
            st.subheader("Event Impact by Region")
            fig = px.bar(ev_reg, x="region", y="avg_uplift",
                         color="event_type",
                         barmode="group",
                         color_discrete_sequence=PALETTE,
                         labels={"avg_uplift":"Avg Uplift %","region":"Region"})
            apply_dark_theme(fig, 380)
            fig.update_layout(legend=dict(orientation="h", y=-0.3))
            st.plotly_chart(fig, use_container_width=True)

        with col_r2:
            st.subheader("Event Incremental Revenue by Event Type")
            fig = px.pie(ev_sum, names="event_type", values="total_incremental",
                         color_discrete_sequence=PALETTE, hole=0.4)
            apply_dark_theme(fig, 380)
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        st.subheader("Event Impact by Department & Event Type (Heatmap)")
        piv = ev_dept.pivot_table(index="primary_dept", columns="event_type",
                                   values="avg_uplift", aggfunc="mean").fillna(0)
        fig = px.imshow(piv, color_continuous_scale="RdYlGn",
                         labels=dict(x="Event Type", y="Department", color="Avg Uplift %"),
                         text_auto=".1f", aspect="auto")
        apply_dark_theme(fig, 500)
        fig.update_layout(xaxis_tickangle=-40)
        st.plotly_chart(fig, use_container_width=True)

    # ────────────────────────────────────────────────────────────────────────
    # TAB 2: Case Studies
    # ────────────────────────────────────────────────────────────────────────
    with tabs[1]:
        st.subheader("📖 Documented Case Studies from 'Retail Analytics: The Secret Weapon'")
        st.caption("Emmett Cox (Wiley/SAS, 2012) — real-world outcomes that shaped this platform's analytics")

        st.divider()

        # Summary chart
        cs_df = pd.DataFrame([{
            "Case Study":  c["name"],
            "Outcome Val": c["outcome_val"],
            "Metric":      c["metric"],
            "Chapter":     c["chapter"],
            "Color":       c["color"],
        } for c in CASE_STUDIES])

        fig = px.bar(cs_df, x="Case Study", y="Outcome Val",
                     color="Chapter",
                     color_discrete_sequence=PALETTE,
                     labels={"Outcome Val":"Measured Outcome (value)", "Case Study":"Case"},
                     text="Outcome Val")
        fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
        apply_dark_theme(fig, 380)
        fig.update_layout(xaxis_tickangle=-25)
        st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # Individual case study cards
        for i in range(0, len(CASE_STUDIES), 2):
            cols = st.columns(2)
            for j, col in enumerate(cols):
                if i + j < len(CASE_STUDIES):
                    cs = CASE_STUDIES[i + j]
                    with col:
                        st.markdown(f"""
<div style="background: linear-gradient(135deg,#0D1B2A,#1B2A3B);
            border-left: 4px solid {cs['color']};
            border-radius: 8px; padding: 16px; margin-bottom: 12px;">
  <h4 style="color:{cs['color']}; margin:0 0 4px 0;">{cs['name']}</h4>
  <p style="color:#AEB6BF; font-size:11px; margin:0 0 8px 0;">
    {cs['chapter']} | <b>{cs['technique']}</b>
  </p>
  <p style="color:#E0E0E0; font-size:13px; margin:0 0 10px 0;">{cs['finding']}</p>
  <div style="background:{cs['color']}22; border-radius:4px; padding:8px;">
    <b style="color:{cs['color']};">Outcome: {cs['outcome']}</b>
  </div>
</div>""", unsafe_allow_html=True)

        st.divider()

        st.subheader("Key Techniques Applied Across Case Studies")
        technique_counts = {}
        for cs in CASE_STUDIES:
            for t in cs["technique"].split("+"):
                t = t.strip()
                technique_counts[t] = technique_counts.get(t, 0) + 1
        tc_df = pd.DataFrame(list(technique_counts.items()), columns=["Technique","Count"])
        fig = px.bar(tc_df.sort_values("Count", ascending=True),
                     x="Count", y="Technique", orientation="h",
                     color="Count", color_continuous_scale="Blues",
                     labels={"Count":"Times Applied"})
        apply_dark_theme(fig, 360)
        st.plotly_chart(fig, use_container_width=True)
