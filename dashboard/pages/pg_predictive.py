"""
Page 8 – Predictive Models & What-If Simulator
"""
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

from dashboard.data_loader import (cust_rfm_segs, cust_churn, cust_demo,
                                    gis_candidates, ops_store_health,
                                    inv_fcst_acc, merch_promo_eff)
from dashboard.utils import (fmt_currency, fmt_pct, fmt_num, apply_dark_theme,
                               PALETTE, PRIMARY, SECONDARY, SUCCESS, DANGER, ACCENT)


def render():
    st.title("🤖 Predictive Models & What-If Simulator")
    st.caption("Integrated ML models: churn, demand, site scoring, and scenario analysis")

    rfm     = cust_rfm_segs()
    churn   = cust_churn()
    demo    = cust_demo()
    sites   = gis_candidates()
    health  = ops_store_health()
    fcst    = inv_fcst_acc()
    promo   = merch_promo_eff()

    tabs = st.tabs([
        "🔮 Churn Prediction",
        "🏗️ Site Selection Scorer",
        "💰 What-If Simulator",
        "📈 Sales Regression",
        "🎯 Next-Best-Offer",
    ])

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 1: Churn Prediction
    # ─────────────────────────────────────────────────────────────────────────
    with tabs[0]:
        st.subheader("Churn Risk Prediction Model")
        st.write("Logistic regression model on RFM features – identifies at-risk customers.")

        col_in, col_out = st.columns([1, 2])
        with col_in:
            st.write("**Predict for a customer:**")
            recency   = st.slider("Recency (days since last purchase)", 1, 365, 45)
            frequency = st.slider("Purchase Frequency (annual)", 1, 60, 8)
            monetary  = st.number_input("Annual Spend ($)", 50, 20000, 800)
            loyalty_tier = st.selectbox("Loyalty Tier", ["Bronze","Silver","Gold","Platinum"])
            tier_map  = {"Bronze": 1, "Silver": 2, "Gold": 3, "Platinum": 4}

        # Fit a lightweight logistic regression on the churn data
        churn_model_data = demo[["customer_id","churn_prob"]].merge(
            churn[["customer_id","recency_days","frequency","monetary_usd","risk_band"]],
            on="customer_id", how="inner"
        ).dropna()

        if len(churn_model_data) >= 20:
            X = churn_model_data[["recency_days","frequency","monetary_usd"]].values
            y = (churn_model_data["churn_prob"] > 0.5).astype(int).values
            scaler = StandardScaler()
            Xs     = scaler.fit_transform(X)
            model  = LogisticRegression(max_iter=500)
            model.fit(Xs, y)

            x_new  = scaler.transform([[recency, frequency, monetary]])
            prob   = model.predict_proba(x_new)[0][1]
            pred   = model.predict(x_new)[0]

            with col_out:
                col_g1, col_g2 = st.columns(2)
                color = DANGER if prob > 0.6 else (ACCENT if prob > 0.3 else SUCCESS)
                col_g1.metric("Churn Probability", fmt_pct(prob*100),
                               delta="⚠️ HIGH RISK" if prob > 0.6 else ("⚡ MEDIUM" if prob > 0.3 else "✅ LOW RISK"),
                               delta_color="inverse" if prob > 0.6 else "normal")
                action = ("Send retention offer immediately" if prob > 0.6 else
                          ("Monitor & send targeted offer" if prob > 0.3 else
                           "Maintain engagement programme"))
                col_g2.info(f"**Recommended Action:** {action}")

                # Churn risk band distribution
                fig = px.histogram(churn, x="churn_prob", nbins=30,
                                    color_discrete_sequence=[SECONDARY],
                                    labels={"churn_prob":"Churn Probability"})
                fig.add_vline(x=prob, line_color=ACCENT, line_dash="dash",
                               annotation_text=f"Customer: {prob:.2f}")
                apply_dark_theme(fig, 280)
                st.plotly_chart(fig, use_container_width=True)
        else:
            with col_out:
                st.info("Insufficient data for model fitting.")

        # Segment churn distribution
        st.subheader("Churn Probability by Segment")
        seg_churn = rfm[["loyalty_segment","avg_churn_prob"]].copy()
        seg_churn["avg_churn_prob"] *= 100
        fig = px.bar(seg_churn.sort_values("avg_churn_prob", ascending=False),
                     x="loyalty_segment", y="avg_churn_prob",
                     color="avg_churn_prob", color_continuous_scale="RdYlGn_r",
                     labels={"avg_churn_prob":"Avg Churn %","loyalty_segment":"Segment"})
        apply_dark_theme(fig, 320)
        fig.add_hline(y=20, line_dash="dash", line_color="white",
                      annotation_text="Alert Threshold 20%")
        st.plotly_chart(fig, use_container_width=True)

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 2: Site Selection Scorer
    # ─────────────────────────────────────────────────────────────────────────
    with tabs[1]:
        st.subheader("🏗️ New Store Site Scoring (Gravity Model)")
        st.write("Adjust inputs to score a hypothetical new store site.")

        col_i, col_o = st.columns([1, 2])
        with col_i:
            pop3mi   = st.number_input("Population within 3 miles", 1000, 500000, 50000, step=1000)
            income   = st.number_input("Median HH Income ($)", 20000, 200000, 65000, step=1000)
            comp3mi  = st.slider("Competitors within 3 miles", 0, 20, 3)
            traffic  = st.number_input("Daily traffic count", 1000, 200000, 25000, step=1000)
            drive_time = st.slider("Drive time to nearest store (min)", 1, 90, 15)

        gravity = pop3mi / max(drive_time ** 2, 1)
        forecast_sales = gravity * income * 0.007
        breakeven_simple = (500000 + 200000) / max(forecast_sales * 0.08, 1)

        with col_o:
            m1, m2, m3 = st.columns(3)
            m1.metric("Gravity Score",  f"{gravity:,.0f}")
            m2.metric("Forecast Yr1 Sales", fmt_currency(forecast_sales))
            m3.metric("Est. Breakeven", f"{breakeven_simple:.1f} yrs",
                       delta="✅ < 2yr target" if breakeven_simple < 2 else
                             ("⚠️ 2-4yr" if breakeven_simple < 4 else "❌ > 4yr"),
                       delta_color="normal" if breakeven_simple < 2 else "inverse")

            # Compare against candidate sites
            sites_c = sites.copy()
            fig = px.scatter(sites_c, x="gravity_score", y="forecast_yr1_sales_usd",
                              color="selected", size="population_3mi",
                              color_discrete_map={0:DANGER, 1:SUCCESS},
                              opacity=0.5, size_max=20,
                              labels={"gravity_score":"Gravity Score",
                                      "forecast_yr1_sales_usd":"Forecast Sales ($)",
                                      "selected":"Site Selected?"})
            fig.add_scatter(x=[gravity], y=[forecast_sales],
                             mode="markers+text",
                             text=["Your Site"], textposition="top right",
                             marker=dict(size=18, color=ACCENT, symbol="star"),
                             name="Your Site")
            apply_dark_theme(fig, 380)
            st.plotly_chart(fig, use_container_width=True)

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 3: What-If Simulator
    # ─────────────────────────────────────────────────────────────────────────
    with tabs[2]:
        st.subheader("💰 What-If Sales Impact Simulator")
        st.write("Test scenarios: price change, promo lift, traffic change.")

        col_a, col_b = st.columns(2)
        with col_a:
            base_sales     = st.number_input("Baseline Weekly Sales ($)", 10000, 5000000, 100000, step=10000)
            price_change   = st.slider("Price Change (%)", -30, 30, 0)
            traffic_change = st.slider("Traffic Change (%)", -40, 40, 0)
            promo_on       = st.checkbox("Run Promotion?", value=False)
            promo_lift_pct = st.slider("Promo Lift (%)", 5, 100, 20, disabled=not promo_on)
            margin_pct     = st.slider("Gross Margin (%)", 10, 60, 35)

        # Simple elasticity model: price elasticity = -1.5
        elasticity = -1.5
        price_impact    = base_sales * (price_change / 100 * elasticity)
        traffic_impact  = base_sales * (traffic_change / 100)
        promo_impact    = base_sales * (promo_lift_pct / 100) if promo_on else 0
        new_sales       = base_sales + price_impact + traffic_impact + promo_impact
        margin_before   = base_sales * margin_pct / 100
        margin_after    = new_sales * margin_pct / 100
        margin_change   = margin_after - margin_before

        with col_b:
            m1, m2, m3 = st.columns(3)
            m1.metric("New Weekly Sales",    fmt_currency(new_sales),
                       delta=fmt_currency(new_sales - base_sales),
                       delta_color="normal" if new_sales >= base_sales else "inverse")
            m2.metric("Gross Margin After",  fmt_currency(margin_after))
            m3.metric("Margin Impact",       fmt_currency(margin_change),
                       delta_color="normal" if margin_change >= 0 else "inverse")

        # Waterfall
        labels = ["Baseline","Price Effect","Traffic Effect","Promo Effect","Result"]
        values_wf = [base_sales, price_impact, traffic_impact, promo_impact, 0]
        fig = go.Figure(go.Waterfall(
            orientation="v", measure=["absolute","relative","relative","relative","total"],
            x=labels, y=values_wf,
            increasing={"marker":{"color":SUCCESS}},
            decreasing={"marker":{"color":DANGER}},
            totals={"marker":{"color":ACCENT}},
            connector={"line":{"color":"grey"}},
        ))
        apply_dark_theme(fig, 360)
        fig.update_layout(title="Sales Impact Waterfall")
        st.plotly_chart(fig, use_container_width=True)

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 4: Sales Regression
    # ─────────────────────────────────────────────────────────────────────────
    with tabs[3]:
        st.subheader("📈 Store Sales Regression Model")
        st.write("Multiple linear regression: sales ~ store size + gravity score + income + competitors")

        health_clean = health[["total_sales","size_sqft","gravity_score",
                                "competitor_count_3mi"]].dropna()
        if len(health_clean) >= 20:
            X = health_clean[["size_sqft","gravity_score","competitor_count_3mi"]].values
            y = health_clean["total_sales"].values
            scaler = StandardScaler()
            Xs = scaler.fit_transform(X)
            reg = LinearRegression()
            reg.fit(Xs, y)
            y_pred = reg.predict(Xs)
            residuals = y - y_pred
            r2 = reg.score(Xs, y)

            c1, c2 = st.columns(2)
            c1.metric("R² Score", f"{r2:.3f}")
            c2.metric("Intercept", fmt_currency(reg.intercept_))

            coef_df = pd.DataFrame({
                "Feature":    ["Store Size (SqFt)","Gravity Score","Competitor Count"],
                "Coefficient": reg.coef_,
            }).sort_values("Coefficient", ascending=False)
            fig_coef = px.bar(coef_df, x="Coefficient", y="Feature", orientation="h",
                               color="Coefficient", color_continuous_scale="RdBu",
                               labels={"Coefficient":"Normalised Coefficient"})
            apply_dark_theme(fig_coef, 280)
            c1.plotly_chart(fig_coef, use_container_width=True)

            fig_res = px.scatter(x=y_pred, y=residuals,
                                  labels={"x":"Predicted Sales","y":"Residuals"},
                                  opacity=0.5, color_discrete_sequence=[SECONDARY])
            apply_dark_theme(fig_res, 280)
            fig_res.add_hline(y=0, line_dash="dash", line_color="white")
            c2.plotly_chart(fig_res, use_container_width=True)
        else:
            st.info("Not enough store data to fit regression.")

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 5: Next-Best-Offer
    # ─────────────────────────────────────────────────────────────────────────
    with tabs[4]:
        st.subheader("🎯 Next-Best-Offer Engine")
        st.write("Select a customer segment to see recommended offers based on propensity scores.")

        seg_sel  = st.selectbox("Customer Segment", rfm["loyalty_segment"].tolist())
        seg_data = rfm[rfm["loyalty_segment"] == seg_sel].iloc[0]

        col_p, col_o2 = st.columns([1, 2])
        with col_p:
            st.write(f"**Segment Profile: {seg_sel}**")
            st.metric("Avg Recency",  f"{seg_data['avg_recency']:.0f} days")
            st.metric("Avg Frequency",f"{seg_data['avg_frequency']:.0f} txns/yr")
            st.metric("Avg Monetary", fmt_currency(seg_data["avg_monetary"]))
            st.metric("Avg CLV",      fmt_currency(seg_data["avg_clv"]))
            st.metric("Churn Risk",   fmt_pct(seg_data["avg_churn_prob"]*100))

        with col_o2:
            # Rule-based NBO using promo data
            promo_sorted = promo.sort_values("avg_roi", ascending=False)
            offers = []
            for _, row in promo_sorted.head(5).iterrows():
                dept        = row["department"]
                lift        = row["lift_pct"]
                roi         = row["avg_roi"]
                avoidable   = row["pct_markdown_avoidable"]
                offer_type  = ("Loyalty Points Multiplier" if seg_sel == "Loyalist" else
                               "Percentage Off"            if seg_sel == "Cherry Picker" else
                               "Multi-Buy"                 if seg_sel == "Soccer Mom" else
                               "Digital Coupon")
                offers.append({
                    "Offer":        f"{offer_type} – {dept}",
                    "Dept":         dept,
                    "Est. Lift %":  f"{lift:.1f}%",
                    "Offer ROI":    f"{roi:.2f}x",
                    "Avoid Markdown": "✅" if avoidable > 0.5 else "❌",
                })
            st.dataframe(pd.DataFrame(offers), use_container_width=True)

            # Propensity radar
            categories = ["Loyalty",   "Frequency", "Monetary",   "Recency\n(inv)", "CLV"]
            max_vals   = [1.0,          60,          10000,         365,              5000]
            vals       = [
                1 - seg_data["avg_churn_prob"],
                min(seg_data["avg_frequency"] / 60, 1),
                min(seg_data["avg_monetary"]  / 10000, 1),
                max(0, 1 - seg_data["avg_recency"] / 365),
                min(seg_data["avg_clv"] / 5000, 1),
            ]
            fig_radar = go.Figure(go.Scatterpolar(
                r=vals + [vals[0]], theta=categories + [categories[0]],
                fill="toself", fillcolor="rgba(46,134,193,0.3)",
                line=dict(color=SECONDARY, width=2),
            ))
            fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0,1])),
                                     height=320, paper_bgcolor="rgba(0,0,0,0)",
                                     font_color="white")
            st.plotly_chart(fig_radar, use_container_width=True)




