-- schema.sql
-- Supply Chain & Inventory Analytics — table definitions.
-- Compatible with SQLite (used by this repo) and easily portable to
-- PostgreSQL / SQL Server with minor type adjustments (INTEGER -> BIGINT, etc).

DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS inventory_snapshots;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS suppliers;
DROP TABLE IF EXISTS warehouses;

CREATE TABLE suppliers (
    supplier_id         INTEGER PRIMARY KEY,
    supplier_name        TEXT NOT NULL,
    region               TEXT NOT NULL,
    reliability_score    REAL NOT NULL,      -- 0-1, higher = more reliable
    avg_lead_time_days   INTEGER NOT NULL
);

CREATE TABLE products (
    product_id      INTEGER PRIMARY KEY,
    product_name    TEXT NOT NULL,
    category        TEXT NOT NULL,
    unit_cost       REAL NOT NULL,
    unit_price      REAL NOT NULL,
    demand_index    REAL NOT NULL           -- relative demand weight, higher = higher-demand product
);

CREATE TABLE warehouses (
    warehouse_id     INTEGER PRIMARY KEY,
    warehouse_name   TEXT NOT NULL,
    region           TEXT NOT NULL,
    capacity_units   INTEGER NOT NULL
);

CREATE TABLE orders (
    order_id                 INTEGER PRIMARY KEY,
    product_id               INTEGER NOT NULL REFERENCES products(product_id),
    supplier_id               INTEGER NOT NULL REFERENCES suppliers(supplier_id),
    warehouse_id              INTEGER NOT NULL REFERENCES warehouses(warehouse_id),
    order_date                TEXT NOT NULL,   -- ISO date
    promised_delivery_date    TEXT NOT NULL,
    actual_delivery_date      TEXT,            -- NULL for cancelled / backordered
    quantity_ordered          INTEGER NOT NULL,
    quantity_delivered         INTEGER NOT NULL,
    status                     TEXT NOT NULL     -- Delivered | Delayed | Cancelled | Backordered
);

CREATE TABLE inventory_snapshots (
    snapshot_id     INTEGER PRIMARY KEY,
    product_id      INTEGER NOT NULL REFERENCES products(product_id),
    warehouse_id    INTEGER NOT NULL REFERENCES warehouses(warehouse_id),
    snapshot_date   TEXT NOT NULL,             -- weekly, ISO date
    stock_level     INTEGER NOT NULL,
    reorder_point   INTEGER NOT NULL,
    safety_stock    INTEGER NOT NULL
);

CREATE INDEX idx_orders_product   ON orders(product_id);
CREATE INDEX idx_orders_supplier  ON orders(supplier_id);
CREATE INDEX idx_orders_warehouse ON orders(warehouse_id);
CREATE INDEX idx_orders_date      ON orders(order_date);
CREATE INDEX idx_inv_product_wh   ON inventory_snapshots(product_id, warehouse_id);
CREATE INDEX idx_inv_date         ON inventory_snapshots(snapshot_date);
