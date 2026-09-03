"""
Enterprise Retail Analytics – Master Data Generator
====================================================
Run this script to generate all synthetic datasets.

Usage
-----
    python generate_all.py                # default scale (config.SCALE)
    python generate_all.py --scale 0.01   # quick smoke-test
    python generate_all.py --scale 1.0    # full scale (very large files)

Output
------
All files land in ./output/<domain>/ as both Parquet (primary) and CSV.
"""

import argparse
import os
import sys
import time

# ── Allow imports from project root ──────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

import config  # noqa: E402  (must come after sys.path patch)


def parse_args():
    p = argparse.ArgumentParser(description="Retail Analytics Data Generator")
    p.add_argument("--scale", type=float, default=None,
                   help="Override config.SCALE (0.001 – 1.0)")
    p.add_argument("--skip-basket-affinities", action="store_true",
                   help="Skip the basket affinity computation (slow for large scale)")
    p.add_argument("--skip-traffic", action="store_true",
                   help="Skip daily store traffic table")
    return p.parse_args()


def main():
    args = parse_args()
    if args.scale is not None:
        config.SCALE = args.scale
        config.NUM_CUSTOMERS        = int(2_000_000   * config.SCALE)
        config.TARGET_BASKET_ROWS   = int(10_000_000_000 * config.SCALE)
        config.TARGET_PROMO_ROWS    = int(16_000_000_000 * config.SCALE)

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    print("=" * 65)
    print("  Enterprise Retail Analytics – Data Generator")
    print(f"  Scale factor : {config.SCALE}")
    print(f"  Customers    : {config.NUM_CUSTOMERS:,}")
    print(f"  Basket rows  : {config.TARGET_BASKET_ROWS:,}")
    print(f"  Promo rows   : {config.TARGET_PROMO_ROWS:,}")
    print(f"  Output dir   : {config.OUTPUT_DIR}")
    print("=" * 65)
    t0 = time.time()

    # ── 1. Stores & GIS ──────────────────────────────────────────────────────
    from generators.stores import (generate_stores, generate_trade_areas,
                                   generate_site_selection_candidates)
    print("\n[1/9] Stores & GIS")
    stores_df     = generate_stores()
    trade_areas   = generate_trade_areas(stores_df)
    site_sel      = generate_site_selection_candidates(stores_df)

    # ── 2. Products / SKUs ───────────────────────────────────────────────────
    from generators.products import generate_products, generate_store_sku
    print("\n[2/9] Products & assortment")
    products_df = generate_products()
    store_sku   = generate_store_sku(stores_df, products_df)

    # ── 3. Customers & Loyalty ───────────────────────────────────────────────
    from generators.customers import (generate_customers,
                                      generate_loyalty_members, generate_rfm)
    print("\n[3/9] Customers & Loyalty")
    customers_df  = generate_customers(stores_df)
    loyalty_df    = generate_loyalty_members(customers_df)
    rfm_df        = generate_rfm(customers_df)

    # ── 4. Transactions (Market Basket) ──────────────────────────────────────
    from generators.transactions import generate_transactions, generate_basket_affinities
    print("\n[4/9] Transactions & Market Basket")
    txn_df, bd_df = generate_transactions(stores_df, customers_df, products_df)

    if not args.skip_basket_affinities:
        print("\n[4b] Basket Affinities")
        affinities_df = generate_basket_affinities(bd_df, products_df)

    # ── 5. Promotions ────────────────────────────────────────────────────────
    from generators.promotions import (generate_promotions, generate_promo_calendar,
                                       generate_promo_uplift, generate_ab_tests)
    print("\n[5/9] Promotions & Incremental Sales")
    promos_df     = generate_promotions()
    promo_cal     = generate_promo_calendar(stores_df, products_df, promos_df)
    promo_uplift  = generate_promo_uplift(promos_df, stores_df)
    ab_tests      = generate_ab_tests(stores_df)

    # ── 6. Store Operations ──────────────────────────────────────────────────
    from generators.store_ops import (generate_labour_schedule, generate_store_traffic,
                                      generate_store_clusters, generate_layout_test_results)
    print("\n[6/9] Store Operations")
    labour_df   = generate_labour_schedule(stores_df, txn_df)
    clusters_df = generate_store_clusters(stores_df)
    layout_df   = generate_layout_test_results(stores_df)

    if not args.skip_traffic:
        traffic_df = generate_store_traffic(stores_df)

    # ── 7. Merchandise & Inventory ───────────────────────────────────────────
    from generators.merchandise import (generate_inventory, generate_demand_forecast,
                                        generate_stockouts)
    print("\n[7/9] Merchandise & Inventory")
    inventory_df  = generate_inventory(stores_df, products_df)
    forecast_df   = generate_demand_forecast(stores_df, products_df)
    stockouts_df  = generate_stockouts(inventory_df)

    # ── 8. Media Mix & Data Monetisation ────────────────────────────────────
    from generators.media_labour import (generate_media_spend, generate_media_response,
                                         generate_data_monetisation)
    print("\n[8/9] Media Mix & Data Monetisation")
    media_df      = generate_media_spend()
    response_df   = generate_media_response(media_df)
    monetise_df   = generate_data_monetisation()

    # ── 9. Summary manifest ──────────────────────────────────────────────────
    print("\n[9/9] Writing data manifest …")
    _write_manifest(config.OUTPUT_DIR)

    elapsed = time.time() - t0
    print(f"\n{'='*65}")
    print(f"  Done.  Total time: {elapsed:.1f}s")
    print(f"  Output: {os.path.abspath(config.OUTPUT_DIR)}")
    print("=" * 65)


def _write_manifest(output_dir: str):
    """Walk output dir and write a manifest CSV listing every generated file."""
    import pathlib
    rows = []
    for p in sorted(pathlib.Path(output_dir).rglob("*")):
        if p.is_file():
            rows.append({
                "file":        str(p.relative_to(output_dir)),
                "size_mb":     round(p.stat().st_size / 1_048_576, 2),
                "rows":        "—",   # filled in by Parquet metadata if needed
            })
    manifest = __import__("pandas").DataFrame(rows)
    manifest.to_csv(os.path.join(output_dir, "MANIFEST.csv"), index=False)
    print(f"  Manifest: {len(rows)} files, "
          f"{manifest['size_mb'].sum():.1f} MB total")


if __name__ == "__main__":
    main()
