"""
generate_data.py
-----------------
Generates a synthetic supply chain dataset (100K+ order records) plus
supporting dimension tables (products, suppliers, warehouses) and daily
inventory snapshots. Designed to reproducibly recreate the dataset used
throughout this project (SQL analysis, Python KPI pipeline, dashboard).

Usage:
    python generate_data.py [--orders 120000] [--seed 42] [--out ./raw]
"""

import argparse
import os
import random
import sqlite3
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

CATEGORIES = [
    "Electronics", "Apparel", "Home & Kitchen", "Industrial Parts",
    "Pharmaceuticals", "Automotive", "Food & Beverage", "Office Supplies",
]

REGIONS = ["North America", "Europe", "Asia Pacific", "Latin America", "Middle East & Africa"]

STATUSES = ["Delivered", "Delivered", "Delivered", "Delivered", "Delayed", "Cancelled", "Backordered"]
STATUS_WEIGHTS = [0.62, 0.10, 0.08, 0.05, 0.10, 0.03, 0.02]  # placeholder, normalized below


def build_dimensions(rng, n_suppliers=60, n_products=250, n_warehouses=12):
    suppliers = pd.DataFrame({
        "supplier_id": range(1, n_suppliers + 1),
        "supplier_name": [f"Supplier {i:03d}" for i in range(1, n_suppliers + 1)],
        "region": rng.choice(REGIONS, n_suppliers),
        # baseline reliability driving delay probability per supplier
        "reliability_score": np.round(rng.beta(6, 2, n_suppliers), 3),
        "avg_lead_time_days": rng.integers(3, 45, n_suppliers),
    })

    products = pd.DataFrame({
        "product_id": range(1, n_products + 1),
        "product_name": [f"Product {i:04d}" for i in range(1, n_products + 1)],
        "category": rng.choice(CATEGORIES, n_products),
        "unit_cost": np.round(rng.gamma(3, 18, n_products), 2),
        "unit_price": None,
        # base demand rate used to skew order volume -> creates "high-demand" products
        "demand_index": np.round(rng.pareto(2.2, n_products) + 0.1, 3),
    })
    products["unit_price"] = np.round(products["unit_cost"] * rng.uniform(1.25, 2.1, n_products), 2)

    warehouses = pd.DataFrame({
        "warehouse_id": range(1, n_warehouses + 1),
        "warehouse_name": [f"Warehouse {chr(65 + i)}" for i in range(n_warehouses)],
        "region": rng.choice(REGIONS, n_warehouses),
        "capacity_units": rng.integers(20000, 150000, n_warehouses),
    })

    return suppliers, products, warehouses


def build_orders(rng, n_orders, suppliers, products, warehouses,
                  start_date="2024-01-01", end_date="2026-01-31"):
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)
    span_days = (end - start).days

    # weight product selection by demand_index so some products are "high-demand"
    product_weights = products["demand_index"].to_numpy()
    product_weights = product_weights / product_weights.sum()
    product_ids = rng.choice(products["product_id"].to_numpy(), size=n_orders, p=product_weights)

    supplier_ids = rng.choice(suppliers["supplier_id"].to_numpy(), size=n_orders)
    warehouse_ids = rng.choice(warehouses["warehouse_id"].to_numpy(), size=n_orders)

    order_offsets = rng.integers(0, span_days, n_orders)
    order_dates = [start + timedelta(days=int(d)) for d in order_offsets]

    supplier_lookup = suppliers.set_index("supplier_id")
    reliability = supplier_lookup.loc[supplier_ids, "reliability_score"].to_numpy()
    base_lead = supplier_lookup.loc[supplier_ids, "avg_lead_time_days"].to_numpy()

    quantity_ordered = rng.integers(5, 500, n_orders)

    # promised delivery: base lead time +/- noise
    promised_lead = np.clip(base_lead + rng.normal(0, 2, n_orders), 1, None).round().astype(int)
    promised_dates = [od + timedelta(days=int(pl)) for od, pl in zip(order_dates, promised_lead)]

    # actual delivery delay grows as reliability drops; low-reliability suppliers = longer/late
    delay_noise = rng.normal(0, 1, n_orders)
    delay_days = ((1 - reliability) * rng.uniform(2, 18, n_orders) + np.clip(delay_noise, 0, None)).round().astype(int)

    statuses = []
    actual_dates = []
    quantity_delivered = []
    for i in range(n_orders):
        roll = rng.random()
        if roll < 0.03:
            status = "Cancelled"
            actual = None
            delivered_qty = 0
        elif roll < 0.05:
            status = "Backordered"
            actual = None
            delivered_qty = 0
        elif delay_days[i] > 3 or roll < 0.15 * (1 - reliability[i]) + 0.05:
            status = "Delayed"
            actual = promised_dates[i] + timedelta(days=int(max(delay_days[i], 1)))
            shortfall_rate = rng.uniform(0.7, 1.0)
            delivered_qty = int(quantity_ordered[i] * shortfall_rate)
        else:
            status = "Delivered"
            jitter = int(rng.integers(-1, 2))
            actual = promised_dates[i] + timedelta(days=jitter)
            if actual < order_dates[i]:
                actual = order_dates[i] + timedelta(days=1)
            delivered_qty = quantity_ordered[i]

        statuses.append(status)
        actual_dates.append(actual)
        quantity_delivered.append(delivered_qty)

    orders = pd.DataFrame({
        "order_id": range(1, n_orders + 1),
        "product_id": product_ids,
        "supplier_id": supplier_ids,
        "warehouse_id": warehouse_ids,
        "order_date": [d.date().isoformat() for d in order_dates],
        "promised_delivery_date": [d.date().isoformat() for d in promised_dates],
        "actual_delivery_date": [d.date().isoformat() if d is not None else None for d in actual_dates],
        "quantity_ordered": quantity_ordered,
        "quantity_delivered": quantity_delivered,
        "status": statuses,
    })

    return orders


def build_inventory_snapshots(rng, products, warehouses, orders, start_date="2024-01-01", end_date="2026-01-31"):
    """Weekly stock-level snapshots per product/warehouse, derived loosely from order volume
    so that high-demand products realistically show more stock-outs."""
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)
    weeks = pd.date_range(start, end, freq="W-MON")

    demand_lookup = products.set_index("product_id")["demand_index"]

    rows = []
    snapshot_id = 1
    # sample a manageable subset of product/warehouse pairs to keep the table reasonably sized
    pw_pairs = [(p, w) for p in products["product_id"].sample(120, random_state=1) for w in warehouses["warehouse_id"]]
    rng2 = np.random.default_rng(7)
    for product_id, warehouse_id in pw_pairs:
        demand = demand_lookup.loc[product_id]
        reorder_point = int(30 + demand * 40)
        safety_stock = int(reorder_point * 0.4)
        stock = int(reorder_point * rng2.uniform(1.2, 3.0))
        for wk in weeks:
            consumption = int(max(0, rng2.normal(demand * 25, demand * 8)))
            replenishment = int(rng2.poisson(demand * 22)) if rng2.random() < 0.35 else 0
            stock = max(0, stock - consumption + replenishment)
            rows.append((snapshot_id, product_id, warehouse_id, wk.date().isoformat(),
                         stock, reorder_point, safety_stock))
            snapshot_id += 1

    inventory = pd.DataFrame(rows, columns=[
        "snapshot_id", "product_id", "warehouse_id", "snapshot_date",
        "stock_level", "reorder_point", "safety_stock",
    ])
    return inventory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--orders", type=int, default=120000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default=os.path.join(os.path.dirname(__file__), "raw"))
    parser.add_argument("--sqlite", type=str, default=os.path.join(os.path.dirname(__file__), "..", "sql", "supply_chain.db"))
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    random.seed(args.seed)

    print("Building dimension tables...")
    suppliers, products, warehouses = build_dimensions(rng)

    print(f"Building {args.orders:,} order records...")
    orders = build_orders(rng, args.orders, suppliers, products, warehouses)

    print("Building weekly inventory snapshots...")
    inventory = build_inventory_snapshots(rng, products, warehouses, orders)

    print("Writing CSVs...")
    suppliers.to_csv(os.path.join(args.out, "suppliers.csv"), index=False)
    products.to_csv(os.path.join(args.out, "products.csv"), index=False)
    warehouses.to_csv(os.path.join(args.out, "warehouses.csv"), index=False)
    orders.to_csv(os.path.join(args.out, "orders.csv"), index=False)
    inventory.to_csv(os.path.join(args.out, "inventory_snapshots.csv"), index=False)

    print(f"Loading into SQLite database at {args.sqlite} ...")
    os.makedirs(os.path.dirname(args.sqlite), exist_ok=True)
    conn = sqlite3.connect(args.sqlite)
    suppliers.to_sql("suppliers", conn, if_exists="replace", index=False)
    products.to_sql("products", conn, if_exists="replace", index=False)
    warehouses.to_sql("warehouses", conn, if_exists="replace", index=False)
    orders.to_sql("orders", conn, if_exists="replace", index=False)
    inventory.to_sql("inventory_snapshots", conn, if_exists="replace", index=False)
    conn.commit()
    conn.close()

    print("Done.")
    print(f"  suppliers:            {len(suppliers):,} rows")
    print(f"  products:             {len(products):,} rows")
    print(f"  warehouses:           {len(warehouses):,} rows")
    print(f"  orders:               {len(orders):,} rows")
    print(f"  inventory_snapshots:  {len(inventory):,} rows")


if __name__ == "__main__":
    main()
