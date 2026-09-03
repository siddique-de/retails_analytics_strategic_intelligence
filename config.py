"""
Central configuration for the Enterprise Retail Analytics Data Generator.
All scale knobs, seeds, and domain constants live here.
"""

import os

# ── Reproducibility ──────────────────────────────────────────────────────────
RANDOM_SEED = 42

# ── Output ────────────────────────────────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

# ── Scale multipliers (set to 1.0 for full scale, lower for quick testing) ───
# At 1.0 the generator targets the project's documented data volumes.
# Reduce to 0.01 for a fast smoke-test run.
SCALE = 0.001          # default: 0.1 % of full scale → fast, still meaningful

# ── Geography ─────────────────────────────────────────────────────────────────
REGIONS = {
    "US":  {"country": "United States",   "currency": "USD", "locale": "en_US", "store_count": 320},
    "AU":  {"country": "Australia",        "currency": "AUD", "locale": "en_AU", "store_count":  85},
    "UK":  {"country": "United Kingdom",   "currency": "GBP", "locale": "en_GB", "store_count": 120},
    "EE":  {"country": "Eastern Europe",   "currency": "EUR", "locale": "pl_PL", "store_count":  60},
    "RU":  {"country": "Russia",           "currency": "RUB", "locale": "ru_RU", "store_count":  45},
    "UAE": {"country": "United Arab Emirates","currency":"AED","locale": "en_US", "store_count":  30},
}

# ── Date range ────────────────────────────────────────────────────────────────
START_DATE = "2018-01-01"
END_DATE   = "2023-12-31"

# ── Customers ─────────────────────────────────────────────────────────────────
NUM_CUSTOMERS = int(2_000_000 * SCALE)   # global customer base

# ── Products / SKUs ───────────────────────────────────────────────────────────
NUM_SKUS = 80_000          # full assortment (not scaled – needed for realistic MBT)

DEPARTMENTS = [
    "Fresh Produce", "Bakery", "Dairy & Eggs", "Meat & Seafood",
    "Frozen Foods", "Beverages", "Snacks & Confectionery",
    "Health & Beauty", "Household", "Baby & Toddler",
    "Pet Supplies", "Clothing & Apparel", "Electronics",
    "Stationery", "Seasonal & Gardening",
]

# ── Transactions (Market Basket) ──────────────────────────────────────────────
# Full project: 10 billion rows in the MPP basket detail table
# We target SCALE * 10B rows across the date range
TARGET_BASKET_ROWS = int(10_000_000_000 * SCALE)

# ── Promotions ────────────────────────────────────────────────────────────────
# Full project: 16 billion rows in the promotional calendar DB
TARGET_PROMO_ROWS  = int(16_000_000_000 * SCALE)

PROMO_TYPES = [
    "BOGO", "Percentage Off", "Fixed Price", "Multi-Buy",
    "Loyalty Points Multiplier", "Clearance", "New Product Launch",
    "Seasonal Event", "Basket Discount", "Digital Coupon",
]

# ── Loyalty programs by region ────────────────────────────────────────────────
LOYALTY_PROGRAMS = {
    "US":  "RetailRewards",
    "AU":  "FlyBuys",
    "UK":  "Nectar",
    "EE":  "RetailRewards",
    "RU":  "RetailRewards",
    "UAE": "RetailRewards",
}

LOYALTY_SEGMENTS = ["Loyalist", "Cherry Picker", "Soccer Mom",
                    "Occasional Shopper", "Lapsed", "New Customer"]

# ── GIS / Real-estate ─────────────────────────────────────────────────────────
STORE_FORMATS = ["Hypermarket", "Supermarket", "Express", "Online Hub", "Flagship"]

SITE_SELECTION_FEATURES = [
    "population_1mi", "population_3mi", "population_5mi",
    "median_hh_income", "competitor_count_3mi", "traffic_count_daily",
    "proximity_to_transit_mi", "parking_spaces",
    "daytime_pop_density", "residential_density",
    "drive_time_nearest_store_min",
]

# ── Labour forecasting ────────────────────────────────────────────────────────
STORE_OPEN_HOUR  = 6    # 06:00
STORE_CLOSE_HOUR = 23   # 23:00
TARGET_QUEUE_MAX = 3    # SLA: no more than 3 customers per queue

# ── Media Mix ────────────────────────────────────────────────────────────────
MEDIA_CHANNELS = [
    "TV", "Radio", "Print", "Outdoor", "Digital Display",
    "Paid Search", "Social Media", "Email", "Catalogue", "In-Store",
]

# ── Third-party data buyers (data monetisation) ───────────────────────────────
DATA_BUYERS = ["ACNielsen", "NPD", "IRI"]
ANNUAL_DATA_REVENUE_USD = 25_000_000   # mid-point of $20M-$30M range
