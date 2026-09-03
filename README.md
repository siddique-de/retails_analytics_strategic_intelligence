# Enterprise Retail Analytics Platform

> A complete, production-grade analytics platform built on synthetic retail data derived from a
> real-world multi-year programme at a major global retailer. Extended with the analytical
> frameworks documented in **"Retail Analytics: The Secret Weapon"** (Emmett Cox, Wiley/SAS, 2012).

---

## Table of Contents

1. [Overview](#1-overview)
2. [Quick Start](#2-quick-start)
3. [Architecture](#3-architecture)
4. [Data Generation Pipeline](#4-data-generation-pipeline)
5. [Data Engineering & Mart Layer](#5-data-engineering--mart-layer)
6. [Dashboard Pages](#6-dashboard-pages)
7. [Raw Data Catalogue](#7-raw-data-catalogue)
8. [Mart Table Catalogue](#8-mart-table-catalogue)
9. [Key KPIs & Metrics](#9-key-kpis--metrics)
10. [Analytical Techniques](#10-analytical-techniques)
11. [Extension: Secret Weapon Book](#11-extension-secret-weapon-book)
12. [Configuration & Scaling](#12-configuration--scaling)
13. [Project Structure](#13-project-structure)
14. [Technology Stack](#14-technology-stack)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Overview

### Business Context

This platform replicates the analytics infrastructure described in a documented enterprise retail
transformation:

- **6 global regions**: United States, Australia, United Kingdom, Eastern Europe, Russia, UAE
- **660 stores** across all regions and formats
- **80,000 SKUs** with velocity tiering, margin data, and assortment matrices
- **10 billion basket rows** at full scale (0.1% scale default = 10M rows)
- **16 billion promotional calendar rows** at full scale (0.1% scale default = 16M rows)
- **$25M/year** POS data monetisation revenue stream (ACNielsen, NPD, IRI)

### What It Demonstrates

| Domain | Capability |
|---|---|
| Data Monetisation | Selling non-identifiable SKU-level POS data to third-party aggregators |
| Real Estate | GIS gravity model, trade area analysis, breakeven reduction from 6 yrs → 2 yrs |
| Merchandise | Store demand models, sister-store clustering, assortment optimisation |
| Loyalty | RFM segmentation (Loyalists, Cherry Pickers, Soccer Moms), FlyBuys/Nectar/School Spirit |
| Store Operations | Layout redesign (20–30% uplift, 20% SKU reduction), labour forecasting |
| Promotions | True incremental analysis with cannibalisation & pantry-loading deduction |
| Labour | POS-driven staffing model, queue SLA ≤ 3 customers |
| Media Mix | Adstock modelling, ROI by channel, saturation detection |
| Price Elasticity | Demand curves by department, price zone analysis |
| Purchase Cycles | Inter-purchase intervals, overdue detection, next-purchase prediction |

---

## 2. Quick Start

### Prerequisites

- Python 3.10+
- ~2 GB disk space (at default 0.1% scale)

### Install

```bash
pip install -r requirements.txt
pip install streamlit plotly
```

### Generate Data

```bash
# Default scale (0.1% of full volume – fast, ~23 minutes)
python generate_all.py --scale 0.001

# Quick smoke-test (very small)
python generate_all.py --scale 0.0001

# Larger dataset (1% – ~4 hours, ~10 GB)
python generate_all.py --scale 0.01
```

### Build Mart Tables

```bash
# Core marts (~45 seconds)
python data_engineering/build_marts.py

# Extension marts from the Secret Weapon book (~5 seconds)
python data_engineering/build_extension_marts.py
```

### Launch Dashboard

```bash
# Option 1 — Windows batch file (double-click or run from terminal)
run_dashboard.bat

# Option 2 — direct Python (always works regardless of PATH)
C:\Python\python.exe -m streamlit run app.py

# Option 3 — if streamlit is on PATH
streamlit run app.py
```

Open **http://localhost:8501** in your browser.

> **Note:** Always run from the project root (`retails_analytics_strategic_intelligence/`),
> not from inside a subdirectory. The `dashboard` package uses relative imports.

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     DATA GENERATION LAYER                           │
│  generators/                                                        │
│  ├── stores.py          GIS, trade areas, site selection            │
│  ├── products.py        80,000 SKUs, assortment matrix              │
│  ├── customers.py       2M customers, loyalty, RFM                 │
│  ├── transactions.py    10B basket rows (scaled), affinities        │
│  ├── promotions.py      16B promo calendar rows (scaled)           │
│  ├── store_ops.py       Labour, traffic, clusters, layout tests     │
│  ├── merchandise.py     Inventory, demand forecast, stockouts       │
│  ├── media_labour.py    Media mix, data monetisation                │
│  └── extensions.py      Price elasticity, purchase cycles,         │
│                         competitor intel, space, events, ATF/ATV    │
└──────────────────────┬──────────────────────────────────────────────┘
                       │  Parquet + CSV  (output/)
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   DATA ENGINEERING LAYER                            │
│  data_engineering/                                                  │
│  ├── build_marts.py           30 core pre-aggregated mart tables    │
│  └── build_extension_marts.py 21 extension mart tables              │
└──────────────────────┬──────────────────────────────────────────────┘
                       │  output/marts/*.parquet
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     DASHBOARD LAYER                                 │
│  app.py  →  dashboard/                                              │
│  ├── data_loader.py   @st.cache_data wrappers (one per mart)        │
│  ├── utils.py         Plotly helpers, dark theme, formatters        │
│  └── pages/           12 Streamlit page modules                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Generation Pipeline

### Scale Factor

All volume targets are multiplied by `config.SCALE`. Set it via `--scale` on the CLI or
edit `config.py` directly.

| Scale | Basket Rows | Promo Rows | Customers | Approx. Time | Disk |
|-------|------------|-----------|-----------|-------------|------|
| 0.0001 | 1M | 1.6M | 200 | ~3 min | ~200 MB |
| 0.001 | 10M | 16M | 2,000 | ~23 min | ~1.2 GB |
| 0.01 | 100M | 160M | 20,000 | ~4 hrs | ~12 GB |
| 0.1 | 1B | 1.6B | 200,000 | ~40 hrs | ~120 GB |
| 1.0 | 10B | 16B | 2,000,000 | full scale | ~1.2 TB |

### Generator Modules

| Module | Tables | Key Design Decisions |
|---|---|---|
| `generators/stores.py` | `dim_stores`, `dim_trade_areas`, `fact_site_selection` | Huff gravity model; regional bounding boxes; breakeven before/after comparison |
| `generators/products.py` | `dim_products`, `dim_store_sku` | 80K SKUs; A/B/C/D velocity tiers; probabilistic assortment per store |
| `generators/customers.py` | `dim_customers`, `dim_loyalty_members`, `fact_rfm` | 6 loyalty segments; RFM quintile scoring; region-proportional distribution |
| `generators/transactions.py` | `fact_transactions`, `fact_basket_detail`, `fact_basket_affinities` | Chunked generation for memory safety; velocity-weighted SKU selection; sparse co-occurrence matrix for lift/confidence/support |
| `generators/promotions.py` | `dim_promotions`, `fact_promo_calendar`, `fact_promo_uplift`, `fact_ab_tests` | 10 promo types; true incremental = promo sales − baseline − cannibalisation − pantry loading |
| `generators/store_ops.py` | `fact_labour_schedule`, `fact_store_traffic`, `dim_store_clusters`, `fact_layout_test_results` | K-means (11 metrics) for sister-store clusters; Parquet streaming writer for traffic; 20–30% layout uplift |
| `generators/merchandise.py` | `fact_inventory`, `fact_demand_forecast`, `fact_stockouts` | Vectorised weekly simulation; 6 stockout root causes |
| `generators/media_labour.py` | `fact_media_spend`, `fact_media_response`, `fact_data_monetisation` | Adstock λ=0.5; seasonal spend curve; $25M/yr POS data revenue |
| `generators/extensions.py` | 7 extension tables | Price elasticity, purchase cycles, competitor intel, planogram, acquisition, events, ATF/ATV |

---

## 5. Data Engineering & Mart Layer

The mart layer pre-aggregates raw Parquet files into analysis-ready tables that load in
milliseconds. All marts are cached per Streamlit session via `@st.cache_data`.

### Running the Mart Build

```bash
# Step 1 – core marts (must run first)
python data_engineering/build_marts.py

# Step 2 – extension marts (requires extensions raw data)
python data_engineering/build_extension_marts.py
```

### ETL Pipeline per Mart Group

```
Raw transactions  ──┐
Raw stores        ──┤──► build_marts.py ──► exec_*   (Executive KPIs)
Raw products      ──┤                  ──► merch_*  (Merchandise)
Raw customers     ──┤                  ──► ops_*    (Store Ops)
Raw promotions    ──┤                  ──► cust_*   (Customer/Loyalty)
Raw media         ──┤                  ──► mkt_*    (Marketing)
Raw inventory     ──┤                  ──► inv_*    (Inventory)
Raw affinities    ──┘                  ──► aff_*    (Affinity)
                                       ──► gis_*    (GIS/Real Estate)

Raw extensions    ──► build_extension_marts.py ──► ext_*  (Secret Weapon)
```

---

## 6. Dashboard Pages

The app is a 12-page Streamlit application with a persistent dark-themed sidebar navigation.
Every page supports sidebar filters (region, department, segment, etc.) and renders fully
interactive Plotly charts.

### Page 1 — 🏢 Executive Command Center

**Purpose:** C-suite 30,000-ft view with drill-down capability.

| Component | Visualisation | KPIs |
|---|---|---|
| Enterprise Health Score | Gauge chart (composite index) | Sales, loyalty, churn, $/sqft |
| Daily Revenue Trend | Line + 7-day rolling average | Total sales, transaction count |
| Monthly Revenue by Region | Stacked area chart | 6 regions × 72 months |
| Revenue by Region | Treemap | Revenue share % |
| Top 20 Store Performance | Sortable data table | Total sales, $/sqft, ATV |
| Customer Segments | Bar chart coloured by CLV | Customers per segment |
| Loyalty Funnel | Funnel chart | Total → Members → Active → Gold/Platinum |
| Monthly ATV Trend | Line with $75 target | Avg basket vs benchmark |

**Sidebar filters:** Region, Year

---

### Page 2 — 🛒 Merchandise & Category Management

**Purpose:** Deep-dive into product performance, assortment, and pricing strategy.

| Component | Visualisation | KPIs |
|---|---|---|
| Category Revenue Share | Treemap | Revenue by department |
| Monthly Revenue by Dept | Multi-line chart | Top-8 departments |
| Gross Margin % by Dept | Horizontal bar (RdYlGn) | 40% target line |
| Promotional Lift vs ROI | Bubble scatter | Lift %, ROI, markdown avoidable % |
| SKU Productivity | Scatter (Revenue vs Baskets) | Coloured by velocity tier |
| Forecast MAPE by Dept | Bar chart | 10% MAPE target |
| Lost Sales by Dept | Bar chart | OOS events, lost revenue $ |
| Markdown Distribution | Histogram by promo type | Discount % distribution |

**Sidebar filters:** Department, Month Range slider

---

### Page 3 — 🏪 Store Operations & Real Estate

**Purpose:** Store performance optimisation, labour forecasting, and real estate decisions.

| Component | Visualisation | KPIs |
|---|---|---|
| Store Network Map | Mapbox scatter (lat/lon) | 660 stores coloured by region |
| Region Summary | Data table | Gravity score, breakeven before/after |
| Labour Queue Heatmap | Bar chart by hour | Avg queue vs SLA=3 |
| Daily Traffic Trend | Line + 14-day rolling avg | Foot traffic, conversion rate |
| Store Health Scorecard | Sortable table (top 25) | Revenue, $/sqft, conversion, queue |
| Store-in-a-Store Layout | Horizontal bar | Sales uplift % by dept (20–30% target) |
| Candidate Site Map | Mapbox scatter | Green=selected, red=rejected |
| Breakeven by Format | Box plot | Target 2yr vs old 6yr benchmark |

**Sidebar filters:** Region, Store Format

---

### Page 4 — 👥 Customer & Loyalty Analytics

**Purpose:** 360-degree customer view, segmentation, lifecycle management.

| Component | Visualisation | KPIs |
|---|---|---|
| RFM Segment Overview | Bubble scatter (recency vs frequency) | 6 segments sized by customer count |
| Revenue by Segment | Treemap (CLV coloured) | Revenue share % |
| Loyalty Funnel | Funnel chart | Enrolment → Active → Gold/Platinum |
| CLV vs Churn by Tier | Dual-axis bar + line | Bronze through Platinum |
| Cohort Retention Heatmap | Imshow (month × month) | 3/6/12-month retention |
| Churn Risk Distribution | Stacked bar | 5 risk bands × segment |
| Age Group Distribution | Donut pie | 6 age groups |
| CLV by Age × Gender | Grouped bar | Demographic CLV comparison |

**Sidebar filters:** Region, Loyalty Segment

---

### Page 5 — 📣 Marketing, Promotions & Data Monetisation

**Purpose:** Marketing ROI, media mix modelling, A/B test analysis, POS data revenue.

| Component | Visualisation | KPIs |
|---|---|---|
| Channel ROI | Bar chart (ROAS coloured) | ROI by channel, break-even line |
| Spend vs Attributed Sales | Bubble scatter | Saturation signal sized |
| Monthly Media Mix | Stacked area chart | 10 channels × 72 months |
| Data Monetisation Revenue | Stacked bar (by buyer) | ACNielsen, NPD, IRI revenue |
| A/B Test Results | Dual-axis (sig rate + uplift) | By test type |
| Promo ROI vs Avoidable Markdowns | Dual-axis | 10 promo types |
| Regional Spend Allocation | Donut pie | % by region |

**Sidebar filters:** Region, Channel

---

### Page 6 — 📦 Inventory & Supply Chain

**Purpose:** Stock health monitoring, OOS root cause analysis, demand forecast accuracy.

| Component | Visualisation | KPIs |
|---|---|---|
| Fill Rate & OOS Trend | Dual-axis line (fill rate + OOS %) | 70% fill rate target |
| Supply vs Demand | Bar + line overlay | Weekly on-hand vs demand |
| Stockout Root Cause | Donut pie | 6 root causes by lost sales $ |
| Lost Sales by Dept | Bar chart | OOS events, total lost $ |
| Forecast MAPE by Dept | Bar chart | 10% MAPE target |
| SKU DoS Distribution | Histogram by velocity tier | 60-day slow-mover threshold |
| SKU Health Detail Table | Filterable data table | Top-50 slow movers |

**Sidebar filters:** Department, Velocity Tier

---

### Page 7 — 🛍️ Market Basket & Affinity Analysis

**Purpose:** Item-pair co-occurrence, cross-sell opportunities, department adjacency.

| Component | Visualisation | KPIs |
|---|---|---|
| Dept × Dept Affinity Heatmap | Imshow (avg lift) | 15×15 department matrix |
| Top SKU Pairs by Lift | Horizontal bar (confidence coloured) | Top-20 pairs |
| Support vs Confidence | Scatter (lift coloured) | Apriori metrics |
| Department Pair Affinity | Horizontal bar (co-occurrence coloured) | Top-30 pairs |
| Affinity Detail Table | Filterable data table | Lift, confidence, support, co-occ |

**Sidebar filters:** Antecedent Department, Minimum Lift, Top-N pairs

---

### Page 8 — 🤖 Predictive Models & What-If Simulator

**Purpose:** Live ML models, scenario testing, and next-best-offer engine.

| Tab | Model | Output |
|---|---|---|
| Churn Prediction | Logistic regression (RFM features) | Churn probability, risk band, recommended action |
| Site Selection Scorer | Huff gravity model | Forecast sales, breakeven, vs candidate sites |
| What-If Simulator | Price elasticity × traffic × promo | Waterfall chart of sales/margin impact |
| Sales Regression | Multiple linear regression (size, gravity, competition) | R², coefficients, residuals |
| Next-Best-Offer | Rule-based propensity + radar chart | Top-5 offers per segment |

---

### Page 9 — 💲 Price Elasticity & Demand Curves *(Extension)*

**Source:** Chapter 5 — Pricing Analytics (*Retail Analytics: The Secret Weapon*)

| Component | Visualisation | KPIs |
|---|---|---|
| Elasticity by Department | Horizontal bar (RdYlGn) | Unit elastic = −1 reference line |
| Demand Curve Simulator | Interactive dual-axis (units + revenue) | Adjustable base price slider |
| Revenue by Price Zone | Bar + line overlay | Deep Discount → Premium |
| Promo vs Non-Promo | Grouped bar | Units, revenue, margin comparison |
| Weekly Demand by Price Zone | Stacked area | 72-month trend |
| Top-20 SKUs by Revenue | Horizontal bar (elasticity coloured) | Most productive SKUs |

**Sidebar filters:** Department

---

### Page 10 — 🧠 Customer Science: ATF/ATV & Acquisition *(Extension)*

**Source:** Chapters 3, 4, 6 — ATF/ATV KPIs, Customer Acquisition, Purchase Cycle Analysis

| Tab | Component | KPIs |
|---|---|---|
| ATF & ATV | Bubble scatter (ATF vs ATV) | Sized by annual spend, coloured by segment |
| ATF & ATV | Annual spend by segment × region | ATF × ATV = annual value identity |
| ATF & ATV | ATF by age group & segment | Demographic frequency comparison |
| ATF & ATV | ATV by store format & segment | Format preference analysis |
| Purchase Cycle | Cycle days by department | Overdue flag, next-purchase prediction |
| Purchase Cycle | Days since last vs predicted next | Overdue scatter |
| Purchase Cycle | Cycle distribution box plot | By department |
| Acquisition | CAC vs 90-day revenue scatter | Break-even line |
| Acquisition | Activation & repeat rate by channel | 8 acquisition channels |
| Acquisition | Channel volume by region | Regional acquisition mix |

---

### Page 11 — 🗂️ Space Management & Competitor Intelligence *(Extension)*

**Source:** Chapters 7, 8 — Space Management, Competitive Intelligence

| Tab | Component | KPIs |
|---|---|---|
| Space | Sales/SqFt by department (ranked) | Compliance % coloured |
| Space | Allocated vs optimal space % | Gap analysis per department |
| Space | Revenue opportunity by department | Space reallocation upside $ |
| Space | Compliance by region | 90% target reference |
| Space | Store compliance distribution | Histogram, 90% threshold |
| Competitor | Price gap by competitor | Heatmap: competitor × department |
| Competitor | Price position trend over time | Premium / Parity / Value |
| Competitor | Competitor × dept gap heatmap | Imshow (RdYlGn) |
| Competitor | Avg price gap by region | Regional exposure |

---

### Page 12 — 📅 Event Impact & Case Studies *(Extension)*

**Source:** Chapter 9 — External Factor Analytics; documented programme outcomes

| Tab | Component | KPIs |
|---|---|---|
| Event Impact | Event uplift % (all types) | Preparation rate, incremental revenue |
| Event Impact | Preparation rate vs uplift scatter | Sized by occurrence count |
| Event Impact | Event impact by region | 10 event types × 6 regions |
| Event Impact | Incremental revenue pie | Share by event type |
| Event Impact | Dept × event heatmap | Avg uplift per cell |
| Case Studies | Summary bar chart | Documented outcomes |
| Case Studies | Interactive case study cards | 7 documented outcomes |
| Case Studies | Techniques applied frequency | Methodology summary |

---

## 7. Raw Data Catalogue

### Core Domains

#### Stores & GIS (`output/stores/`)

| Table | Rows | Key Columns |
|---|---|---|
| `dim_stores` | 660 | store_id, region, country, currency, format, lat/lon, size_sqft, open_date |
| `dim_trade_areas` | 660 | store_id, pop_1/3/5mi, median_hh_income_usd, competitor_count_3mi, gravity_score, breakeven_years_before/after |
| `fact_site_selection` | 1,980 | candidate_id, gravity_score, forecast_yr1_sales_usd, forecast_breakeven_yrs, selected |

#### Products (`output/products/`)

| Table | Rows | Key Columns |
|---|---|---|
| `dim_products` | 80,000 | sku_id, description, department, brand, sell_price_usd, cost_price_usd, margin_pct, velocity_tier, is_private_label |
| `dim_store_sku` | 38.5M | store_id, sku_id, is_stocked |

#### Customers (`output/customers/`)

| Table | Rows | Key Columns |
|---|---|---|
| `dim_customers` | 2,000 | customer_id, region, gender, age_group, household_size, annual_income_usd, has_children, has_pet |
| `dim_loyalty_members` | 2,000 | customer_id, loyalty_program, loyalty_tier, points_balance, lifetime_points, redemption_count |
| `fact_rfm` | 2,000 | customer_id, recency_days, frequency, monetary_usd, r/f/m_score, rfm_combined, loyalty_segment, churn_prob, clv_12m_usd |

#### Transactions (`output/transactions/`)

| Table | Rows | Key Columns |
|---|---|---|
| `fact_transactions` | 572K | transaction_id, store_id, customer_id, transaction_date, hour_of_day, payment_method, item_count, basket_total_usd |
| `fact_basket_detail` | 10M | transaction_id, line_id, store_id, sku_id, department, quantity, unit_price_usd, discount_pct, extended_price_usd |
| `fact_basket_affinities` | 100K | antecedent_sku, consequent_sku, support, confidence, lift, co_occurrence_count, ant/con_dept |

#### Promotions (`output/promotions/`)

| Table | Rows | Key Columns |
|---|---|---|
| `dim_promotions` | 25,000 | promo_id, promo_type, department, discount_rate, media_support, is_national, budget_usd |
| `fact_promo_calendar` | 16M | promo_id, store_id, sku_id, calendar_date, discount_rate, is_featured, is_end_cap |
| `fact_promo_uplift` | 75K | uplift_id, baseline_sales_usd, promo_period_sales_usd, cannibalisation_usd, pantry_loading_usd, true_incremental_usd, roi, markdown_avoidable |
| `fact_ab_tests` | 500 | test_id, test_type, uplift_pct, p_value, is_statistically_significant, roll_out_decision, estimated_annual_impact_usd |

#### Store Operations (`output/store_ops/`)

| Table | Rows | Key Columns |
|---|---|---|
| `fact_labour_schedule` | 565K | store_id, transaction_date, hour_of_day, txn_count, staff_rostered, avg_queue_length, sla_met, labour_cost_usd |
| `fact_store_traffic` | 1.45M | store_id, traffic_date, foot_traffic, conversion_rate, dwell_time_min, impulse_purchase_rate |
| `dim_store_clusters` | 660 | store_id, cluster_id, cluster_label, sister_store_id, 11 clustering metrics |
| `fact_layout_test_results` | 990 | store_id, department, sku_count_before/after, sales_before/after_usd, sales_uplift_pct, dwell change, impulse change |

#### Merchandise (`output/merchandise/`)

| Table | Rows | Key Columns |
|---|---|---|
| `fact_inventory` | 7.8M | store_id, sku_id, week_start, on_hand_units, demand_units, fill_rate, days_of_supply |
| `fact_demand_forecast` | 500K | forecast_id, store_id, sku_id, department, baseline_demand, seasonal_index, promo_uplift_factor, forecast_units, actual_units, mape_pct |
| `fact_stockouts` | 2.19M | store_id, sku_id, lost_units, lost_sales_usd, stockout_days, root_cause |

#### Media & Monetisation (`output/media/`)

| Table | Rows | Key Columns |
|---|---|---|
| `fact_media_spend` | 18,780 | week_start_date, region, channel, spend_usd |
| `fact_media_response` | 18,780 | channel, adstock_spend_usd, attributed_sales_usd, roi, marginal_roi, saturation_flag |
| `fact_data_monetisation` | 216 | month, data_buyer, data_type, revenue_usd, records_delivered, contract_type |

### Extension Domains (`output/extensions/`)

| Table | Rows | Description |
|---|---|---|
| `fact_price_elasticity` | 120K | Price × demand observations; elasticity, price zone, promo flag |
| `fact_purchase_cycles` | 80K | Customer × dept inter-purchase intervals; overdue flags |
| `fact_competitor_intel` | 50K | Weekly own vs competitor prices; price gap %, position |
| `fact_space_planogram` | 9,900 | Store × dept space allocation, sales/sqft, compliance %, adjacencies |
| `fact_customer_acquisition` | 2,000 | Acquisition channel, CAC, 30/90-day spend, activation, payback |
| `fact_event_analysis` | 9,900 | 10 event types × stores; uplift factor, preparation flag |
| `fact_atf_atv` | 36 | ATF/ATV summary by segment × region |
| `fact_atf_atv_detail` | 2,000 | Customer-level ATF, ATV, annual spend, preferred format |

---

## 8. Mart Table Catalogue

All 58 mart tables live in `output/marts/` as Snappy-compressed Parquet files.

### Executive Marts (`exec_*`)

| Mart | Rows | Description |
|---|---|---|
| `exec_monthly_sales` | 432 | Revenue, transactions, customers, ATV by month × region |
| `exec_store_kpi` | 660 | Total sales, sales/sqft, ATV per store |
| `exec_daily_trend` | 2,190 | Daily revenue with 7-day rolling average |
| `exec_inv_turnover` | 50 | Inventory turnover ratio per store sample |

### Merchandise Marts (`merch_*`)

| Mart | Rows | Description |
|---|---|---|
| `merch_category_scorecard` | 1,080 | Revenue, margin, units by department × month |
| `merch_sku_productivity` | 80,000 | Revenue, units, baskets, revenue/basket per SKU |
| `merch_promo_effectiveness` | 150 | Avg baseline, promo sales, incremental, ROI, lift % by type × dept |
| `merch_markdowns` | 6,965 | Clearance and Percentage Off promos with discount % |
| `merch_forecast_accuracy` | 60 | Avg MAPE by department × model version |

### Store Operations Marts (`ops_*`)

| Mart | Rows | Description |
|---|---|---|
| `ops_store_health` | 660 | Combined store KPIs: sales, traffic, queue, labour, gravity |
| `ops_labour_heatmap` | 11,879 | Avg queue, SLA %, staff by store × hour |
| `ops_layout_summary` | 15 | Sales uplift, SKU reduction, dwell/impulse gain by department |
| `ops_site_selection` | 1,980 | Candidate sites with gravity score and breakeven forecast |
| `ops_traffic_trend` | 2,191 | Daily avg traffic and conversion rate trend |

### Customer & Loyalty Marts (`cust_*`)

| Mart | Rows | Description |
|---|---|---|
| `cust_rfm_segments` | 6 | Segment KPIs: recency, frequency, monetary, churn, CLV, revenue share |
| `cust_demographics` | 2,000 | Customer demographics merged with RFM segment and CLV |
| `cust_loyalty_funnel` | 5 | Stage counts: Total → Members → Active → Gold/Platinum → Redeemers |
| `cust_loyalty_tiers` | 4 | Points, redemptions, CLV, churn by Bronze/Silver/Gold/Platinum |
| `cust_cohort_retention` | 5,184 | Monthly cohort × transaction period retention rate |
| `cust_churn_risk` | 2,000 | Customer-level churn probability, RFM, risk band |

### Marketing Marts (`mkt_*`)

| Mart | Rows | Description |
|---|---|---|
| `mkt_channel_roi` | 60 | Total spend, attributed sales, ROI, ROAS by channel × region |
| `mkt_monthly_media` | 720 | Spend and attributed sales by month × channel |
| `mkt_data_monetisation` | 216 | Monthly POS data revenue by buyer and data type |
| `mkt_ab_summary` | 6 | Significance rate, avg uplift, avg impact by test type |
| `mkt_promo_type_roi` | 10 | Total incremental, avg ROI, avoidable markdown % by promo type |

### Inventory Marts (`inv_*`)

| Mart | Rows | Description |
|---|---|---|
| `inv_weekly_health` | 313 | Avg fill rate, DoS, on-hand, demand, OOS proxy by week |
| `inv_stockout_causes` | 6 | Events, lost sales, avg stockout days by root cause |
| `inv_stockout_dept` | 15 | Events and lost sales by department |
| `inv_forecast_accuracy` | 15 | Avg MAPE and baseline demand by department |
| `inv_sku_health` | 500 | Fill rate, DoS, slow-mover flag per sampled SKU |

### Affinity Marts (`aff_*`)

| Mart | Rows | Description |
|---|---|---|
| `aff_dept_pairs` | 210 | Avg lift, confidence, co-occurrence for department pairs |
| `aff_top_sku_pairs` | 5,000 | Top SKU pairs by lift with descriptions and departments |
| `aff_dept_heatmap` | 15 | Pivoted dept × dept lift matrix (15×15) |

### GIS / Real Estate Marts (`gis_*`)

| Mart | Rows | Description |
|---|---|---|
| `gis_store_trade_areas` | 660 | Stores joined with full trade area metrics |
| `gis_region_summary` | 6 | Per-region: store count, avg gravity, income, breakeven, predicted sales |
| `gis_candidate_sites` | 1,980 | Candidate sites with full gravity model inputs and outputs |

### Extension Marts (`ext_*`)

| Mart | Rows | Description |
|---|---|---|
| `ext_elasticity_by_dept` | 75 | Avg elasticity, units, revenue, margin by dept × price zone |
| `ext_elasticity_by_sku` | 500 | Revenue total, avg elasticity per top-500 SKU |
| `ext_elasticity_weekly` | 1,565 | Weekly avg units and revenue by price zone |
| `ext_elasticity_promo_comp` | 30 | Promo vs non-promo units/revenue/margin by department |
| `ext_purchase_cycles_dept` | 15 | Avg cycle, annual frequency, overdue %, days since last by dept |
| `ext_at_risk_customers` | 1,998 | Customers overdue in ≥2 departments |
| `ext_purchase_cycles_detail` | 80,000 | Customer × dept cycle detail with stability score |
| `ext_competitor_price_gap` | 75 | Avg price gap, promo rates, premium % by competitor × dept |
| `ext_competitor_position_trend` | 939 | Weekly count of Premium/Parity/Value positions |
| `ext_competitor_by_region` | 30 | Avg price gap by region × competitor |
| `ext_space_dept_ranking` | 15 | Sales/sqft, allocated/optimal %, compliance, revenue opportunity |
| `ext_space_store_compliance` | 660 | Avg compliance and revenue per store |
| `ext_space_region_summary` | 6 | Compliance, sales/sqft, space gap by region |
| `ext_acquisition_by_channel` | 8 | CAC, 30/90-day spend, activation %, repeat %, ROI, payback per channel |
| `ext_acquisition_region_channel` | 48 | Volume, CAC, ROI by region × channel |
| `ext_acquisition_detail` | 2,000 | Customer-level acquisition metrics |
| `ext_event_summary` | 10 | Avg uplift %, total incremental, preparation rate per event type |
| `ext_event_by_region` | 60 | Avg uplift and incremental by region × event type |
| `ext_event_by_dept` | 150 | Avg uplift per dept × event type |
| `ext_atf_atv_segments` | 36 | ATF, ATV, annual spend, CLV by segment × region |
| `ext_atf_atv_by_age` | 36 | ATF, ATV, spend by age group × segment |
| `ext_atf_atv_by_format` | 30 | ATF, ATV by preferred store format × segment |

---

## 9. Key KPIs & Metrics

### Financial

| KPI | Definition | Target | Source Table |
|---|---|---|---|
| Total Revenue | Sum of basket totals | — | `exec_monthly_sales` |
| Average Transaction Value (ATV) | Revenue / transactions | > $75 | `exec_store_kpi` |
| Sales per Sq Ft | Revenue / store size | > $500 | `ops_store_health` |
| Gross Margin % | (Revenue − COGS) / Revenue | > 40% | `merch_category_scorecard` |
| Inventory Turnover | Total demand / avg on-hand | > 12× | `exec_inv_turnover` |
| Media ROI | Attributed sales / spend | > 1.0 | `mkt_channel_roi` |
| Promo True Lift | True incremental / baseline | > 20% | `merch_promo_effectiveness` |

### Customer

| KPI | Definition | Target | Source Table |
|---|---|---|---|
| Loyalty Penetration | Loyalty members / total customers | > 60% | `cust_loyalty_funnel` |
| Active Member Rate | Active members / enrolled | > 70% | `cust_loyalty_funnel` |
| Churn Probability | Logistic regression on RFM | < 20% | `cust_churn_risk` |
| 12-Month CLV | ATF × ATV × retention factor | > $2,500 | `cust_rfm_segments` |
| Average Transaction Frequency (ATF) | Trips per year per customer | > 12 | `ext_atf_atv_segments` |
| Cohort Retention (12M) | Active customers / cohort size | > 80% | `cust_cohort_retention` |

### Operational

| KPI | Definition | Target | Source Table |
|---|---|---|---|
| Avg Queue Length | Customers in checkout queue | ≤ 3 | `ops_labour_heatmap` |
| Queue SLA Met | % hours queue ≤ 3 | > 95% | `ops_store_health` |
| Fill Rate | On-hand / demand | > 70% | `inv_weekly_health` |
| Days of Supply | On-hand / daily demand | 14–30 days | `inv_sku_health` |
| Planogram Compliance | Correctly executed / total | > 90% | `ext_space_store_compliance` |
| Forecast MAPE | |forecast − actual| / actual | < 10% | `inv_forecast_accuracy` |

### Real Estate

| KPI | Definition | Target | Source Table |
|---|---|---|---|
| Gravity Score | Population / drive-time² | Higher is better | `gis_store_trade_areas` |
| Breakeven (After) | Years to recover investment | < 2 years | `gis_region_summary` |
| Trade Area Penetration | Transactions / trade area pop | > 15% | `gis_store_trade_areas` |

---

## 10. Analytical Techniques

| Technique | Implementation | Location |
|---|---|---|
| Market Basket Analysis | Sparse co-occurrence matrix → support / confidence / lift | `generators/transactions.py` |
| RFM Segmentation | Quintile scoring → 6 named segments | `generators/customers.py` |
| K-Means Clustering | 11-metric sister-store model (n=12) | `generators/store_ops.py` |
| Huff Gravity Model | Population / distance² for trade area scoring | `generators/stores.py` |
| Transfer Sales Analysis | Breakeven forecast from gravity × income | `generators/stores.py` |
| True Incremental Analysis | Promo sales − baseline − cannibalisation − pantry loading | `generators/promotions.py` |
| Adstock Modelling | Media response with λ=0.5 carryover, saturation flag | `generators/media_labour.py` |
| Price Elasticity | % Δ quantity / % Δ price by department | `generators/extensions.py` |
| Logistic Regression | Live churn prediction on RFM features | `dashboard/pages/pg_predictive.py` |
| Linear Regression | Store sales ~ size + gravity + competition | `dashboard/pages/pg_predictive.py` |
| Purchase Cycle Analysis | Inter-purchase intervals + overdue detection | `generators/extensions.py` |
| Champion/Challenger A/B | p-value significance + roll-out decision | `generators/promotions.py` |
| Cohort Retention | Monthly enrolment cohort × transaction period | `data_engineering/build_marts.py` |
| Time Series | 7/14-day rolling averages, seasonal index | `generators/merchandise.py` |
| Demand Forecasting | Baseline × seasonal index × promo uplift factor | `generators/merchandise.py` |

---

## 11. Extension: Secret Weapon Book

The platform is extended with analytical frameworks from:

> **"Retail Analytics: The Secret Weapon"**  
> Emmett Cox · Wiley/SAS Institute · 2012  
> ISBN: 978-1-118-09760-0

### Chapter-by-Chapter Coverage

| Chapter | Topic | Dashboard Page | Generator |
|---|---|---|---|
| Ch. 2 | Data as a Strategic Asset / POS Monetisation | 📣 Marketing | `media_labour.py` |
| Ch. 3 | ATF & ATV KPIs | 🧠 Customer Science | `extensions.py` |
| Ch. 4 | Customer Acquisition Analytics | 🧠 Customer Science | `extensions.py` |
| Ch. 5 | Price Elasticity & Demand Curves | 💲 Price Elasticity | `extensions.py` |
| Ch. 6 | Market Basket & Purchase Cycles | 🛍️ Basket + 🧠 Customer Science | `transactions.py` + `extensions.py` |
| Ch. 7 | Space Management & Planogram | 🗂️ Space & Competitor | `extensions.py` |
| Ch. 8 | Competitive Intelligence & Real Estate | 🗂️ Space & Competitor + 🏪 Store Ops | `extensions.py` + `stores.py` |
| Ch. 9 | Event & External Factor Analytics | 📅 Event Impact | `extensions.py` |
| Ch. 10 | Loyalty Programme Design | 👥 Customer & Loyalty | `customers.py` |

### Documented Case Study Outcomes

| Case Study | Technique | Outcome |
|---|---|---|
| White Lake Store Redesign | Planogram optimisation + affinity layout | 20–30% sales increase |
| Paper Towel Promotion | True incremental analysis | $0 true lift — markdown avoided |
| Lifesavers Cross-Merchandising | Affinity / lift analysis | 15% confectionery uplift |
| FlyBuys Loyalty (Australia) | RFM segmentation + tier design | 2× redemption rate |
| Kmart School Spirit (US) | Community loyalty + ATF tracking | 22% trip frequency increase |
| New Store Breakeven | Gravity model + transfer sales | 6 years → 2 years breakeven |
| POS Data Monetisation | SKU-level data sales | $20M–$30M annual revenue |

---

## 12. Configuration & Scaling

### `config.py` Settings

```python
SCALE = 0.001          # Master scale multiplier — change this to scale up
RANDOM_SEED = 42       # Reproducibility seed
START_DATE = "2018-01-01"
END_DATE   = "2023-12-31"

# Derived volumes (auto-scaled)
NUM_CUSTOMERS        = int(2_000_000   * SCALE)
TARGET_BASKET_ROWS   = int(10_000_000_000 * SCALE)
TARGET_PROMO_ROWS    = int(16_000_000_000 * SCALE)

# Geography
REGIONS = {
    "US": {..., "store_count": 320},
    "AU": {..., "store_count":  85},
    "UK": {..., "store_count": 120},
    "EE": {..., "store_count":  60},
    "RU": {..., "store_count":  45},
    "UAE":{..., "store_count":  30},
}
```

### CLI Override

```bash
# Override scale without editing config.py
python generate_all.py --scale 0.01

# Skip expensive steps
python generate_all.py --scale 0.001 --skip-basket-affinities
python generate_all.py --scale 0.001 --skip-traffic
```

### Memory Management

Large tables use chunked writes via PyArrow's `ParquetWriter` to avoid OOM errors:

- `fact_basket_detail` — processed in 500K-row chunks
- `fact_promo_calendar` — processed in 500K-row chunks
- `fact_store_traffic` — written one store at a time

---

## 13. Project Structure

```
retails_analytics_strategic_intelligence/
│
├── app.py                              # Streamlit entry point (12-page app)
├── config.py                           # Scale knobs, constants, geography
├── generate_all.py                     # Master orchestrator — runs all generators
├── run_dashboard.bat                   # Windows one-click launcher
├── requirements.txt                    # Python dependencies
├── README.md                           # This file
├── dashboard.txt                       # Dashboard specification document
├── Retail Analytics The Secret Weapon.pdf  # Reference book
│
├── .streamlit/
│   └── config.toml                     # Dark theme, port 8501
│
├── generators/                         # Data generation layer
│   ├── __init__.py
│   ├── base.py                         # Shared RNG, helpers (save_csv, save_parquet)
│   ├── stores.py                       # GIS, trade areas, site selection
│   ├── products.py                     # SKU master, store assortment
│   ├── customers.py                    # Customer master, loyalty, RFM
│   ├── transactions.py                 # Market basket, affinities
│   ├── promotions.py                   # Promo calendar, uplift, A/B tests
│   ├── store_ops.py                    # Labour, traffic, clusters, layout
│   ├── merchandise.py                  # Inventory, forecast, stockouts
│   ├── media_labour.py                 # Media spend, response, data monetisation
│   └── extensions.py                   # Price elasticity, purchase cycles,
│                                       # competitor intel, space, events, ATF/ATV
│
├── data_engineering/                   # ETL / mart layer
│   ├── __init__.py
│   ├── build_marts.py                  # 30 core mart tables
│   └── build_extension_marts.py        # 21 extension mart tables (Secret Weapon)
│
├── dashboard/                          # Streamlit application layer
│   ├── __init__.py
│   ├── data_loader.py                  # @st.cache_data wrappers for all 58 marts
│   ├── utils.py                        # Plotly helpers, dark theme, formatters
│   └── pages/
│       ├── __init__.py
│       ├── pg_executive.py             # Page 1  — Executive Command Center
│       ├── pg_merchandise.py           # Page 2  — Merchandise & Category Mgmt
│       ├── pg_store_ops.py             # Page 3  — Store Operations & Real Estate
│       ├── pg_customer.py              # Page 4  — Customer & Loyalty
│       ├── pg_marketing.py             # Page 5  — Marketing & Promotions
│       ├── pg_inventory.py             # Page 6  — Inventory & Supply Chain
│       ├── pg_basket.py                # Page 7  — Market Basket & Affinity
│       ├── pg_predictive.py            # Page 8  — Predictive Models & What-If
│       ├── pg_price_elasticity.py      # Page 9  — Price Elasticity (Ch. 5)
│       ├── pg_customer_science.py      # Page 10 — Customer Science (Ch. 3,4,6)
│       ├── pg_space_competitor.py      # Page 11 — Space & Competitor (Ch. 7,8)
│       └── pg_event_analytics.py       # Page 12 — Events & Case Studies (Ch. 9)
│
└── output/                             # Generated data (git-ignored)
    ├── MANIFEST.csv                    # Auto-generated file inventory
    ├── stores/                         # dim_stores, dim_trade_areas, fact_site_selection
    ├── products/                       # dim_products, dim_store_sku
    ├── customers/                      # dim_customers, dim_loyalty_members, fact_rfm
    ├── transactions/                   # fact_transactions, fact_basket_detail, affinities
    ├── promotions/                     # dim_promotions, promo_calendar, uplift, ab_tests
    ├── store_ops/                      # labour, traffic, clusters, layout_tests
    ├── merchandise/                    # inventory, demand_forecast, stockouts
    ├── media/                          # media_spend, media_response, data_monetisation
    ├── extensions/                     # price_elasticity, purchase_cycles, competitor,
    │                                   # space_planogram, customer_acquisition, events, atf_atv
    └── marts/                          # 58 pre-aggregated Parquet mart tables
```

---

## 14. Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Language | Python 3.13 | All data generation, engineering, and dashboard |
| Dashboard | Streamlit 1.50 | Multi-page web application |
| Visualisation | Plotly 6.x | All interactive charts (dark theme) |
| Data Processing | Pandas 3.x, NumPy 2.x | Dataframe operations, vectorised generation |
| ML | scikit-learn 1.7 | K-means clustering, logistic/linear regression |
| Storage | Apache Parquet (PyArrow 21) | Columnar storage with Snappy compression |
| Fake Data | Faker 37 | Realistic names, cities, postcodes |
| Statistics | SciPy 1.16 | Sparse matrix operations for affinity computation |
| Serialisation | tqdm 4.67 | Progress bars for long-running generators |
| Maps | Plotly Mapbox (carto-darkmatter) | GIS store and site selection maps |

### Python Dependencies

```
faker>=26.0
numpy>=1.26
pandas>=2.2
scipy>=1.13
scikit-learn>=1.5
tqdm>=4.66
pyarrow>=16.0
openpyxl>=3.1
streamlit>=1.50
plotly>=5.20
```

---

## 15. Troubleshooting

### `streamlit` not found / not on PATH

```bash
# Always use python -m streamlit (guaranteed to use the right interpreter)
C:\Python\python.exe -m streamlit run app.py
```

### `KeyError: 'column_name'` in dashboard

The mart tables are stale. Rebuild them:

```bash
python data_engineering/build_marts.py
python data_engineering/build_extension_marts.py
```

### `MemoryError` during data generation

Reduce the scale factor:

```bash
python generate_all.py --scale 0.0005
```

Or skip the large traffic table:

```bash
python generate_all.py --scale 0.001 --skip-traffic
```

### Dashboard shows old data after regenerating

Streamlit caches mart files per session. Press **F5** or click **Rerun** in the browser, or
restart the Streamlit process to force a cache reload.

### Extension pages fail to load

The extension raw data and mart tables must be generated separately:

```bash
# 1. Generate extension raw data
python -c "
import sys, os, pandas as pd
sys.path.insert(0,'.')
from generators.extensions import *
prod  = pd.read_parquet('output/products/dim_products.parquet')
cust  = pd.read_parquet('output/customers/dim_customers.parquet')
rfm   = pd.read_parquet('output/customers/fact_rfm.parquet')
stores= pd.read_parquet('output/stores/dim_stores.parquet')
os.makedirs('output/extensions', exist_ok=True)
generate_price_elasticity(prod)
generate_purchase_cycles(cust)
generate_competitor_intel(stores, prod)
generate_space_planogram(stores)
generate_customer_acquisition(cust)
generate_event_analysis(stores)
generate_atf_atv(cust, rfm)
"

# 2. Build extension marts
python data_engineering/build_extension_marts.py
```

### Plotly deprecation warnings

If you see `"keyword arguments have been deprecated"` — all `st.plotly_chart` calls should use
`use_container_width=True`, not `width='stretch'`. Run the following to fix:

```powershell
Get-ChildItem dashboard\pages\*.py | ForEach-Object {
    (Get-Content $_.FullName -Raw) -replace "width='stretch'", 'use_container_width=True' |
    Set-Content $_.FullName
}
```

---

*Platform version: 2.0 · Data scale: 0.1% (10M basket rows) · Regions: US · AU · UK · EE · RU · UAE*
