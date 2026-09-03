"""
Page 7 – Market Basket Analytics & Affinity Analysis
"""
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.data_loader import aff_dept_pairs, aff_top_pairs, aff_dept_heatmap
from dashboard.utils import (fmt_num, fmt_pct, apply_dark_theme,
                               PALETTE, PRIMARY, SECONDARY, SUCCESS, DANGER, ACCENT)


def render():
    st.title("🛍️ Market Basket Analytics & Affinity Analysis")
    st.caption("Item-pair co-occurrence, lift scores, and cross-sell opportunities")

    dept_pairs = aff_dept_pairs()
    top_pairs  = aff_top_pairs()
    heatmap_df = aff_dept_heatmap()

    # ── Sidebar ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.subheader("Affinity Filters")
        depts = ["All"] + sorted(dept_pairs["antecedent_dept"].dropna().unique().tolist())
        sel_dept = st.selectbox("Antecedent Department", depts)
        min_lift = st.slider("Minimum Lift", 1.0, 10.0, 1.5, 0.1)
        top_n    = st.slider("Top N Pairs", 10, 200, 50)

    tp = top_pairs.copy()
    if sel_dept != "All":
        tp = tp[tp["antecedent_dept"] == sel_dept]
    tp = tp[tp["lift"] >= min_lift].head(top_n)

    dp = dept_pairs.copy()
    if sel_dept != "All":
        dp = dp[dp["antecedent_dept"] == sel_dept]
    dp = dp[dp["avg_lift"] >= min_lift]

    # ── KPIs ──────────────────────────────────────────────────────────────────
    max_lift   = top_pairs["lift"].max()
    avg_lift   = top_pairs["lift"].mean()
    n_strong   = len(top_pairs[top_pairs["lift"] >= 3])
    top_dept_pair = dept_pairs.nlargest(1,"avg_lift")
    best_pair  = f"{top_dept_pair['antecedent_dept'].values[0]} → {top_dept_pair['consequent_dept'].values[0]}" if len(top_dept_pair) else "—"

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Max Lift Score",   f"{max_lift:.2f}")
    k2.metric("Avg Lift",         f"{avg_lift:.2f}")
    k3.metric("Strong Pairs (≥3x lift)", fmt_num(n_strong))
    k4.metric("Strongest Dept Pair", best_pair)

    st.divider()

    # ── Row 1: Dept Affinity Heatmap ──────────────────────────────────────────
    st.subheader("Department × Department Affinity Heatmap (Avg Lift)")
    hm = heatmap_df.set_index("antecedent_dept")
    hm = hm.drop(columns=[c for c in hm.columns if c == "antecedent_dept"], errors="ignore")
    fig = px.imshow(hm, color_continuous_scale="Blues",
                    labels=dict(x="Consequent Dept", y="Antecedent Dept", color="Avg Lift"),
                    aspect="auto", text_auto=".2f")
    apply_dark_theme(fig, 500)
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 2: Top Pairs Bar + Scatter ────────────────────────────────────────
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader(f"Top {min(20, len(tp))} SKU Pairs by Lift")
        tp_top20 = tp.head(20).copy()
        if "ant_desc" in tp_top20.columns and "con_desc" in tp_top20.columns:
            tp_top20["pair"] = (tp_top20["ant_desc"].str[:20] + " → " +
                                tp_top20["con_desc"].str[:20])
        else:
            tp_top20["pair"] = tp_top20["antecedent_sku"] + " → " + tp_top20["consequent_sku"]
        fig = px.bar(tp_top20.sort_values("lift"), x="lift", y="pair", orientation="h",
                     color="confidence", color_continuous_scale="Blues",
                     labels={"lift":"Lift Score","pair":"SKU Pair","confidence":"Confidence"})
        apply_dark_theme(fig, 500)
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("Support vs. Confidence (coloured by Lift)")
        fig = px.scatter(tp, x="support", y="confidence",
                         color="lift", color_continuous_scale="Viridis",
                         opacity=0.6, size_max=12,
                         labels={"support":"Support","confidence":"Confidence","lift":"Lift"},
                         hover_data=["antecedent_sku","consequent_sku"])
        apply_dark_theme(fig, 500)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 3: Dept Pair Bar ───────────────────────────────────────────────────
    st.subheader("Department Pair Affinity (Avg Lift – sorted)")
    top_dp = dp.nlargest(30, "avg_lift").copy()
    top_dp["pair"] = top_dp["antecedent_dept"] + " → " + top_dp["consequent_dept"]
    fig = px.bar(top_dp.sort_values("avg_lift"), x="avg_lift", y="pair", orientation="h",
                 color="total_co_occ", color_continuous_scale="Greens",
                 labels={"avg_lift":"Avg Lift","pair":"Department Pair",
                         "total_co_occ":"Co-occurrence Count"})
    apply_dark_theme(fig, 600)
    fig.add_vline(x=1, line_dash="dash", line_color="white", annotation_text="Lift = 1")
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 4: Raw affinity table ──────────────────────────────────────────────
    st.subheader("Affinity Detail Table")
    show_df = tp[["antecedent_sku","consequent_sku","antecedent_dept","consequent_dept",
                  "lift","confidence","support","co_occurrence_count"]].copy()
    show_df["lift"]       = show_df["lift"].map(lambda x: f"{x:.3f}")
    show_df["confidence"] = show_df["confidence"].map(lambda x: f"{x:.3f}")
    show_df["support"]    = show_df["support"].map(lambda x: f"{x:.6f}")
    show_df.columns       = ["Antecedent SKU","Consequent SKU","Ant. Dept","Con. Dept",
                              "Lift","Confidence","Support","Co-Occ."]
    st.dataframe(show_df, use_container_width=True, height=350)




