"""
Enterprise Retail Analytics Platform
Streamlit multi-page application
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Enterprise Retail Analytics",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Dark sidebar */
[data-testid="stSidebar"] {background-color: #0D1B2A;}

/* Metric cards */
[data-testid="metric-container"] {
    background: linear-gradient(135deg,#0D1B2A 0%,#1B2A3B 100%);
    border: 1px solid #2E86C1;
    border-radius: 8px;
    padding: 12px;
}
[data-testid="metric-container"] label {color: #AEB6BF !important; font-size:12px;}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #FFFFFF !important; font-size:22px; font-weight:700;
}

/* Dividers */
hr {border-color: #2E3B4E !important;}

/* Tab styling */
[data-testid="stTabs"] [data-baseweb="tab"] {
    background: #0D1B2A; color:#AEB6BF;
}
[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
    background: #1B4F72; color:#FFFFFF;
}

/* Scrollbar */
::-webkit-scrollbar {width:6px;}
::-webkit-scrollbar-track {background:#0D1B2A;}
::-webkit-scrollbar-thumb {background:#2E86C1; border-radius:3px;}
</style>
""", unsafe_allow_html=True)

# ── Navigation ────────────────────────────────────────────────────────────────
PAGES = {
    "🏢 Executive Command Center":          "executive",
    "🛒 Merchandise & Category Mgmt":       "merchandise",
    "🏪 Store Operations & Real Estate":    "store_ops",
    "👥 Customer & Loyalty":                "customer",
    "📣 Marketing & Promotions":            "marketing",
    "📦 Inventory & Supply Chain":          "inventory",
    "🛍️ Market Basket & Affinity":         "basket",
    "🤖 Predictive Models & What-If":       "predictive",
    "─── Extensions (Secret Weapon) ───":  "divider",
    "💲 Price Elasticity & Demand Curves":  "price_elasticity",
    "🧠 Customer Science & Acquisition":    "customer_science",
    "🗂️ Space Mgmt & Competitor Intel":    "space_competitor",
    "📅 Event Impact & Case Studies":       "event_analytics",
}

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/bar-chart.png", width=64)
    st.title("Retail Analytics")
    st.caption("Enterprise Strategic Intelligence")
    st.divider()

    # Filter out the divider pseudo-entry for radio
    nav_options = [k for k in PAGES if PAGES[k] != "divider"]
    page_name = st.radio("Navigate to", nav_options, label_visibility="collapsed")

    st.divider()
    st.caption("Data refreshed daily  |  Scale: 0.1%")
    st.caption("Regions: US · AU · UK · EE · RU · UAE")
    st.caption("📖 Extended: Retail Analytics: The Secret Weapon")

# ── Route to page ─────────────────────────────────────────────────────────────
page_key = PAGES[page_name]

if page_key == "executive":
    from dashboard.pages.pg_executive        import render
elif page_key == "merchandise":
    from dashboard.pages.pg_merchandise      import render
elif page_key == "store_ops":
    from dashboard.pages.pg_store_ops        import render
elif page_key == "customer":
    from dashboard.pages.pg_customer         import render
elif page_key == "marketing":
    from dashboard.pages.pg_marketing        import render
elif page_key == "inventory":
    from dashboard.pages.pg_inventory        import render
elif page_key == "basket":
    from dashboard.pages.pg_basket           import render
elif page_key == "predictive":
    from dashboard.pages.pg_predictive       import render
elif page_key == "price_elasticity":
    from dashboard.pages.pg_price_elasticity import render
elif page_key == "customer_science":
    from dashboard.pages.pg_customer_science import render
elif page_key == "space_competitor":
    from dashboard.pages.pg_space_competitor import render
elif page_key == "event_analytics":
    from dashboard.pages.pg_event_analytics  import render

render()

