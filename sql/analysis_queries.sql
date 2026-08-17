-- analysis_queries.sql
-- Core analytical queries over 100K+ supply chain records.
-- Each query is self-contained and annotated with what it answers.
-- Run with: sqlite3 supply_chain.db < analysis_queries.sql
--       or  the Python runner in analysis/run_sql_report.py

-- =========================================================
-- 1. INVENTORY SHORTAGES
-- Product/warehouse combinations currently below reorder point,
-- ranked by how far below safety stock they've fallen.
-- =========================================================
WITH latest_snapshot AS (
    SELECT product_id, warehouse_id, MAX(snapshot_date) AS latest_date
    FROM inventory_snapshots
    GROUP BY product_id, warehouse_id
)
SELECT
    p.product_name,
    w.warehouse_name,
    inv.stock_level,
    inv.reorder_point,
    inv.safety_stock,
    inv.stock_level - inv.safety_stock AS units_below_safety_stock,
    CASE WHEN inv.stock_level = 0 THEN 'STOCK-OUT'
         WHEN inv.stock_level < inv.safety_stock THEN 'CRITICAL'
         WHEN inv.stock_level < inv.reorder_point THEN 'REORDER'
         ELSE 'OK' END AS inventory_status
FROM inventory_snapshots inv
JOIN latest_snapshot ls
    ON inv.product_id = ls.product_id
   AND inv.warehouse_id = ls.warehouse_id
   AND inv.snapshot_date = ls.latest_date
JOIN products p ON p.product_id = inv.product_id
JOIN warehouses w ON w.warehouse_id = inv.warehouse_id
WHERE inv.stock_level < inv.reorder_point
ORDER BY units_below_safety_stock ASC
LIMIT 25;


-- =========================================================
-- 2. SUPPLIER DELAYS
-- Supplier-level on-time delivery rate and average delay,
-- for suppliers with at least 50 orders.
-- =========================================================
SELECT
    s.supplier_name,
    s.region,
    COUNT(*) AS total_orders,
    ROUND(100.0 * SUM(CASE WHEN o.status = 'Delayed' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_delayed,
    ROUND(AVG(
        CASE WHEN o.actual_delivery_date IS NOT NULL
             THEN julianday(o.actual_delivery_date) - julianday(o.promised_delivery_date)
        END
    ), 1) AS avg_delay_days,
    ROUND(100.0 * SUM(CASE WHEN o.status = 'Delivered' THEN 1 ELSE 0 END) / COUNT(*), 1) AS on_time_rate_pct
FROM orders o
JOIN suppliers s ON s.supplier_id = o.supplier_id
GROUP BY s.supplier_id
HAVING COUNT(*) >= 50
ORDER BY pct_delayed DESC
LIMIT 20;


-- =========================================================
-- 3. HIGH-DEMAND PRODUCTS
-- Top products by order volume and units ordered over the full period.
-- =========================================================
SELECT
    p.product_name,
    p.category,
    COUNT(*) AS order_count,
    SUM(o.quantity_ordered) AS total_units_ordered,
    ROUND(SUM(o.quantity_ordered * p.unit_price), 2) AS total_revenue,
    ROUND(100.0 * SUM(CASE WHEN o.status IN ('Delayed','Backordered') THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_fulfillment_issues
FROM orders o
JOIN products p ON p.product_id = o.product_id
GROUP BY p.product_id
ORDER BY total_units_ordered DESC
LIMIT 20;


-- =========================================================
-- 4. LEAD TIME ANALYSIS
-- Average and P90 lead time (order -> actual delivery) by supplier region.
-- =========================================================
SELECT
    s.region,
    COUNT(*) AS delivered_orders,
    ROUND(AVG(julianday(o.actual_delivery_date) - julianday(o.order_date)), 1) AS avg_lead_time_days,
    ROUND(AVG(julianday(o.promised_delivery_date) - julianday(o.order_date)), 1) AS avg_promised_lead_time_days
FROM orders o
JOIN suppliers s ON s.supplier_id = o.supplier_id
WHERE o.actual_delivery_date IS NOT NULL
GROUP BY s.region
ORDER BY avg_lead_time_days DESC;


-- =========================================================
-- 5. ORDER FULFILLMENT RATE
-- Share of ordered units actually delivered, overall and by warehouse.
-- =========================================================
SELECT
    w.warehouse_name,
    w.region,
    COUNT(*) AS total_orders,
    SUM(o.quantity_ordered) AS units_ordered,
    SUM(o.quantity_delivered) AS units_delivered,
    ROUND(100.0 * SUM(o.quantity_delivered) / NULLIF(SUM(o.quantity_ordered), 0), 1) AS fulfillment_rate_pct
FROM orders o
JOIN warehouses w ON w.warehouse_id = o.warehouse_id
GROUP BY w.warehouse_id
ORDER BY fulfillment_rate_pct ASC;


-- =========================================================
-- 6. STOCK-LEVEL TRENDS
-- Average stock level vs reorder point over time (monthly), across all products.
-- Useful for spotting systemic under-stocking trends.
-- =========================================================
SELECT
    strftime('%Y-%m', snapshot_date) AS month,
    ROUND(AVG(stock_level), 0) AS avg_stock_level,
    ROUND(AVG(reorder_point), 0) AS avg_reorder_point,
    ROUND(100.0 * SUM(CASE WHEN stock_level = 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS stockout_rate_pct
FROM inventory_snapshots
GROUP BY month
ORDER BY month;


-- =========================================================
-- 7. DELIVERY KPI SCORECARD
-- Overall network KPIs: on-time %, avg delay, cancellation %, fulfillment %.
-- =========================================================
SELECT
    COUNT(*) AS total_orders,
    ROUND(100.0 * SUM(CASE WHEN status = 'Delivered' THEN 1 ELSE 0 END) / COUNT(*), 1) AS on_time_rate_pct,
    ROUND(100.0 * SUM(CASE WHEN status = 'Delayed' THEN 1 ELSE 0 END) / COUNT(*), 1) AS delayed_rate_pct,
    ROUND(100.0 * SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END) / COUNT(*), 1) AS cancelled_rate_pct,
    ROUND(100.0 * SUM(CASE WHEN status = 'Backordered' THEN 1 ELSE 0 END) / COUNT(*), 1) AS backordered_rate_pct,
    ROUND(AVG(CASE WHEN actual_delivery_date IS NOT NULL
                   THEN julianday(actual_delivery_date) - julianday(promised_delivery_date) END), 2) AS avg_delay_vs_promised_days
FROM orders;


-- =========================================================
-- 8. OPERATIONAL BOTTLENECKS
-- Supplier x Warehouse lanes with the worst combination of delay rate
-- and fulfillment shortfall — the biggest bottlenecks in the network.
-- =========================================================
SELECT
    s.supplier_name,
    w.warehouse_name,
    COUNT(*) AS total_orders,
    ROUND(100.0 * SUM(CASE WHEN o.status IN ('Delayed','Backordered','Cancelled') THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_problem_orders,
    ROUND(100.0 * SUM(o.quantity_delivered) / NULLIF(SUM(o.quantity_ordered), 0), 1) AS fulfillment_rate_pct
FROM orders o
JOIN suppliers s ON s.supplier_id = o.supplier_id
JOIN warehouses w ON w.warehouse_id = o.warehouse_id
GROUP BY s.supplier_id, w.warehouse_id
HAVING COUNT(*) >= 30
ORDER BY pct_problem_orders DESC
LIMIT 20;
