"""
Page 9 – Price Elasticity & Demand Curves
Source: "Retail Analytics: The Secret Weapon" Ch. 5
"""
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.data_loader import (ext_elast_dept, ext_elast_sku,
                                    ext_elast_weekly, ext_elast_promo)
from dashboard.utils import (fmt_currency, fmt_pct, fmt_num, apply_dark_theme,
                               PALETTE, PRIMARY, SECONDARY, SUCCESS, DANGER, ACCENT)

ZONE_COLORS = {
    "Deep Discount": "#E74C3C", "Moderate Discount": "#F39C12",
    "Regular": "#2E86C1", "Slight Premium": "#8E44AD", "Premium": "#27AE60",
}


def render():
    st.title("💲 Price Elasticity & Demand Curves")
    st.caption("Chapter 5: Pricing Analytics – demand curves, price elasticity, and promo cannibalisation")

    dept_df  = ext_elast_dept()
    sku_df   = ext_elast_sku()
    weekly   = ext_elast_weekly()
    promo_df = ext_elast_promo()

    weekly["week_start"] = pd.to_datetime(weekly["week_start"])

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.subheader("Price Elasticity Filters")
        depts = ["All"] + sorted(dept_df["department"].unique().tolist())
        sel_dept = st.selectbox("Department", depts)

    dept_f = dept_df.copy()
    if sel_dept != "All":
        dept_f = dept_f[dept_f["department"] == sel_dept]

    # ── KPIs ──────────────────────────────────────────────────────────────────
    avg_elast  = dept_f["avg_elasticity"].mean()
    most_elast = dept_df.loc[dept_df["avg_elasticity"].abs().idxmax(), "department"]
    least_elast= dept_df.loc[dept_df["avg_elasticity"].abs().idxmin(), "department"]
    promo_rev  = promo_df[promo_df["is_promo_price"]==True]["avg_revenue"].mean()
    base_rev   = promo_df[promo_df["is_promo_price"]==False]["avg_revenue"].mean()
    promo_lift  = (promo_rev / max(base_rev, 1) - 1) * 100

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Avg Price Elasticity",  f"{avg_elast:.2f}",        help="Negative = demand falls when price rises")
    k2.metric("Most Elastic Dept",     most_elast,                help="Highest |elasticity|")
    k3.metric("Least Elastic Dept",    least_elast,               help="Lowest |elasticity|")
    k4.metric("Promo Revenue Lift",    fmt_pct(promo_lift),       help="Promo vs regular price avg revenue")

    st.divider()

    # ── Row 1: Elasticity by dept + Demand Curve simulator ───────────────────
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Price Elasticity by Department")
        d = dept_df.groupby("department")["avg_elasticity"].mean().reset_index()
        d = d.sort_values("avg_elasticity")
        d["color"] = d["avg_elasticity"].apply(
            lambda x: DANGER if x < -1.5 else (ACCENT if x < -0.8 else SUCCESS))
        fig = px.bar(d, x="avg_elasticity", y="department", orientation="h",
                     color="avg_elasticity", color_continuous_scale="RdYlGn",
                     labels={"avg_elasticity":"Elasticity","department":"Department"})
        apply_dark_theme(fig, 420)
        fig.add_vline(x=-1, line_dash="dash", line_color="white",
                      annotation_text="Unit elastic (-1)")
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("Demand Curve Simulator")
        sim_dept   = st.selectbox("Simulate Department", dept_df["department"].unique().tolist(),
                                   key="sim_dept")
        base_price = st.slider("Base Price ($)", 0.5, 50.0, 5.0, 0.5)
        elast_val  = float(dept_df[dept_df["department"]==sim_dept]["avg_elasticity"].mean())

        prices     = np.linspace(base_price * 0.5, base_price * 1.5, 30)
        base_units = 100
        units      = base_units * (prices / base_price) ** elast_val
        revenues   = prices * units

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=prices, y=units, name="Units Sold",
                                  line=dict(color=SECONDARY, width=2.5)))
        fig.add_trace(go.Scatter(x=prices, y=revenues, name="Revenue ($)",
                                  line=dict(color=ACCENT, width=2.5), yaxis="y2"))
        fig.add_vline(x=base_price, line_dash="dash", line_color="white",
                      annotation_text="Current Price")
        fig.update_layout(
            yaxis=dict(title="Units Sold"),
            yaxis2=dict(title="Revenue ($)", overlaying="y", side="right"),
            xaxis_title="Price ($)",
        )
        apply_dark_theme(fig, 420)
        st.caption(f"Elasticity for {sim_dept}: **{elast_val:.2f}**")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 2: Revenue by price zone + Promo vs non-promo ────────────────────
    col_l2, col_r2 = st.columns(2)

    with col_l2:
        st.subheader("Revenue by Price Zone")
        zone_agg = dept_f.groupby("price_zone").agg(
            avg_units=("avg_units","mean"),
            avg_revenue=("avg_revenue","mean")).reset_index()
        zone_order = ["Deep Discount","Moderate Discount","Regular","Slight Premium","Premium"]
        zone_agg["price_zone"] = pd.Categorical(zone_agg["price_zone"],
                                                  categories=zone_order, ordered=True)
        zone_agg = zone_agg.sort_values("price_zone")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=zone_agg["price_zone"], y=zone_agg["avg_revenue"],
                              name="Avg Revenue", marker_color=[ZONE_COLORS.get(z, SECONDARY)
                                                                 for z in zone_agg["price_zone"]]))
        fig.add_trace(go.Scatter(x=zone_agg["price_zone"], y=zone_agg["avg_units"],
                                  name="Avg Units", mode="lines+markers",
                                  line=dict(color=ACCENT, width=2.5), yaxis="y2"))
        fig.update_layout(yaxis=dict(title="Avg Revenue ($)"),
                          yaxis2=dict(title="Avg Units", overlaying="y", side="right"))
        apply_dark_theme(fig, 380)
        st.plotly_chart(fig, use_container_width=True)

    with col_r2:
        st.subheader("Promo vs. Non-Promo Performance")
        pc = promo_df.copy()
        pc["promo_label"] = pc["is_promo_price"].map({True: "On Promotion", False: "Regular Price"})
        fig = go.Figure()
        fig.add_trace(go.Bar(x=pc["department"] if "department" in pc.columns else pc["promo_label"],
                              y=pc["avg_units"],
                              color=pc["promo_label"] if "promo_label" in pc.columns else None,
                              marker_color=[SUCCESS if v else SECONDARY
                                            for v in pc["is_promo_price"]],
                              name="Avg Units",
                              text=pc["avg_margin"].map(lambda x: f"${x:.0f}"),
                              textposition="outside"))
        apply_dark_theme(fig, 380)
        fig.update_layout(xaxis_tickangle=-30, barmode="group")
        fig.add_annotation(text="Green = Promo price", xref="paper", yref="paper",
                           x=0.01, y=1.05, showarrow=False, font=dict(color="white", size=11))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Row 3: Weekly demand trend by price zone + top elastic SKUs ───────────
    col_l3, col_r3 = st.columns(2)

    with col_l3:
        st.subheader("Weekly Revenue by Price Zone (Trend)")
        fig = px.area(weekly.sort_values("week_start"),
                      x="week_start", y="avg_revenue", color="price_zone",
                      color_discrete_map=ZONE_COLORS,
                      labels={"avg_revenue":"Avg Revenue","week_start":"Week"})
        apply_dark_theme(fig, 360)
        fig.update_layout(xaxis_tickangle=-30, legend=dict(orientation="h", y=-0.3))
        st.plotly_chart(fig, use_container_width=True)

    with col_r3:
        st.subheader("Top 20 SKUs by Revenue (Elasticity coloured)")
        top20 = sku_df.nlargest(20, "revenue_total").copy()
        fig = px.bar(top20.sort_values("revenue_total"),
                     x="revenue_total", y="sku_id", orientation="h",
                     color="avg_elasticity", color_continuous_scale="RdYlGn",
                     labels={"revenue_total":"Total Revenue","sku_id":"SKU",
                             "avg_elasticity":"Elasticity"})
        apply_dark_theme(fig, 360)
        st.plotly_chart(fig, use_container_width=True)
