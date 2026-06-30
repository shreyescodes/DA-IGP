-- =====================================================================
-- RetailIQ — MySQL Schema, Data Loading & Analytical Views
-- Class 2 | MySQL Data Warehouse
--
-- HOW TO RUN:
-- Open MySQL Workbench → connect to localhost → open this file
-- Run section by section (highlight + Ctrl+Shift+Enter)
-- Do NOT run the whole file at once — loading data is in between.
--
-- ORDER OF EXECUTION:
-- [1] Part 1 — CREATE DATABASE
-- [2] Part 2 — CREATE TABLES
-- [3] Load data (run load.py in Python terminal)
-- [4] Part 3 — VERIFY DATA
-- [5] Part 4 — CREATE INDEXES
-- [6] Part 5 — CREATE VIEWS (all 6 of them)
-- [7] Part 6 — VERIFY VIEWS
-- =====================================================================


-- =====================================================================
-- PART 1: DATABASE SETUP
-- =====================================================================

DROP DATABASE IF EXISTS retailiq;
CREATE DATABASE retailiq
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE retailiq;

SELECT 'Database created successfully' AS status;


-- =====================================================================
-- PART 2: CREATE TABLES
-- Run this BEFORE loading data via Python.
-- =====================================================================

-- Fact Table: one row per order
-- This is the center of our star schema.
CREATE TABLE fact_orders (
    order_id                    VARCHAR(50)     PRIMARY KEY,
    customer_id                 VARCHAR(50)     NOT NULL,      -- customer_unique_id from customers
    seller_id                   VARCHAR(50),
    product_id                  VARCHAR(50),
    order_status                VARCHAR(20),
    order_purchase_date         DATE,
    order_year                  SMALLINT,
    order_month                 TINYINT,
    order_quarter               TINYINT,
    order_day_of_week           VARCHAR(15),
    order_delivered_customer_date DATE,
    delivery_days               SMALLINT,
    estimated_days              SMALLINT,
    was_late                    TINYINT(1)      DEFAULT 0,
    is_delivered                TINYINT(1)      DEFAULT 0,
    item_count                  TINYINT         DEFAULT 1,
    revenue                     DECIMAL(12,2)   DEFAULT 0.00,
    freight_value               DECIMAL(10,2)   DEFAULT 0.00,
    order_value                 DECIMAL(12,2)   DEFAULT 0.00,
    total_payment               DECIMAL(12,2),
    payment_methods             VARCHAR(100),
    installments                TINYINT,
    review_score                DECIMAL(3,1),
    has_comment                 TINYINT(1)      DEFAULT 0
);

-- Dimension: Customers (one row per real person + their RFM scores)
CREATE TABLE dim_customers (
    customer_id                 VARCHAR(50)     PRIMARY KEY,
    customer_city               VARCHAR(100),
    customer_state              CHAR(2),
    recency_days                SMALLINT,
    frequency                   SMALLINT,
    monetary                    DECIMAL(12,2),
    r_score                     TINYINT,
    f_score                     TINYINT,
    m_score                     TINYINT,
    rfm_score                   TINYINT,
    rfm_segment                 VARCHAR(30)
);

-- Dimension: Products
CREATE TABLE dim_products (
    product_id                          VARCHAR(50)     PRIMARY KEY,
    product_category_name_english       VARCHAR(100),
    product_category_broad              VARCHAR(50),
    product_weight_g                    DECIMAL(10,2),
    product_length_cm                   DECIMAL(8,2),
    product_height_cm                   DECIMAL(8,2),
    product_width_cm                    DECIMAL(8,2)
);

-- Dimension: Sellers
CREATE TABLE dim_sellers (
    seller_id                   VARCHAR(50)     PRIMARY KEY,
    seller_city                 VARCHAR(100),
    seller_state                CHAR(2)
);

SELECT 'Tables created. Now load data using load.py' AS next_step;


-- =====================================================================
-- PART 3: VERIFY DATA LOADED
-- Run AFTER loading data via Python.
-- =====================================================================

SELECT
    'fact_orders'   AS table_name, COUNT(*) AS row_count FROM fact_orders
UNION ALL SELECT 'dim_customers', COUNT(*) FROM dim_customers
UNION ALL SELECT 'dim_products',  COUNT(*) FROM dim_products
UNION ALL SELECT 'dim_sellers',   COUNT(*) FROM dim_sellers;

-- Quick sanity check on the fact table
SELECT
    MIN(order_purchase_date)         AS earliest_order,
    MAX(order_purchase_date)         AS latest_order,
    FORMAT(SUM(revenue), 2)          AS total_revenue_R$,
    FORMAT(AVG(order_value), 2)      AS avg_order_value_R$,
    COUNT(*)                          AS total_orders,
    ROUND(AVG(review_score), 2)      AS avg_review_score,
    ROUND(AVG(delivery_days), 1)     AS avg_delivery_days,
    ROUND(SUM(was_late)/COUNT(*)*100, 1) AS late_pct
FROM fact_orders;


-- =====================================================================
-- PART 4: INDEXES
-- Add after data is loaded — indexes slow down inserts but speed up reads.
-- =====================================================================

CREATE INDEX idx_orders_customer    ON fact_orders (customer_id);
CREATE INDEX idx_orders_seller      ON fact_orders (seller_id);
CREATE INDEX idx_orders_product     ON fact_orders (product_id);
CREATE INDEX idx_orders_date        ON fact_orders (order_purchase_date);
CREATE INDEX idx_orders_year_month  ON fact_orders (order_year, order_month);
CREATE INDEX idx_orders_delivered   ON fact_orders (is_delivered);
CREATE INDEX idx_customers_state    ON dim_customers (customer_state);
CREATE INDEX idx_customers_segment  ON dim_customers (rfm_segment);
CREATE INDEX idx_products_broad     ON dim_products (product_category_broad);

SELECT 'Indexes created' AS status;


-- =====================================================================
-- PART 5: ANALYTICAL VIEWS
-- Power BI will connect to these views, not the raw tables directly.
-- This is how it works in real analytics teams: the SQL layer owns the
-- business logic, Power BI owns the visualization.
-- =====================================================================


-- -------------------------------------------------------
-- VIEW 1: Monthly Revenue Trend
-- Used for: Revenue trend line, MoM analysis on exec page
-- -------------------------------------------------------
CREATE OR REPLACE VIEW vw_monthly_revenue AS
SELECT
    order_year,
    order_month,
    -- Build a proper date column so Power BI can use it in a time axis
    STR_TO_DATE(CONCAT(order_year, '-', LPAD(order_month, 2, '0'), '-01'), '%Y-%m-%d')
                                                AS month_start,
    COUNT(order_id)                             AS total_orders,
    ROUND(SUM(revenue), 2)                      AS total_revenue,
    ROUND(SUM(freight_value), 2)                AS total_freight,
    ROUND(SUM(order_value), 2)                  AS total_order_value,
    ROUND(AVG(order_value), 2)                  AS avg_order_value,
    ROUND(AVG(review_score), 2)                 AS avg_review_score,
    ROUND(AVG(delivery_days), 1)                AS avg_delivery_days,
    SUM(was_late)                               AS late_orders,
    ROUND(SUM(was_late) / COUNT(*) * 100, 2)    AS late_pct,
    SUM(item_count)                             AS total_items_sold
FROM fact_orders
WHERE is_delivered = 1
GROUP BY order_year, order_month
ORDER BY order_year, order_month;

-- Test it
SELECT * FROM vw_monthly_revenue LIMIT 6;


-- -------------------------------------------------------
-- VIEW 2: Category Performance
-- Used for: Category bar chart, category drill-down
-- -------------------------------------------------------
CREATE OR REPLACE VIEW vw_category_performance AS
SELECT
    p.product_category_broad                        AS category_broad,
    p.product_category_name_english                 AS category_detail,
    COUNT(DISTINCT o.order_id)                      AS total_orders,
    COUNT(DISTINCT o.customer_id)                   AS unique_customers,
    ROUND(SUM(o.revenue), 2)                        AS total_revenue,
    ROUND(AVG(o.revenue), 2)                        AS avg_order_revenue,
    ROUND(AVG(o.review_score), 2)                   AS avg_review_score,
    ROUND(AVG(o.delivery_days), 1)                  AS avg_delivery_days,
    SUM(o.was_late)                                 AS late_orders,
    ROUND(SUM(o.was_late) / COUNT(*) * 100, 2)      AS late_rate_pct,
    ROUND(
        SUM(o.revenue) / SUM(SUM(o.revenue)) OVER() * 100
    , 2)                                            AS revenue_share_pct
FROM fact_orders o
JOIN dim_products p ON o.product_id = p.product_id
WHERE o.is_delivered = 1
GROUP BY p.product_category_broad, p.product_category_name_english
ORDER BY total_revenue DESC;

-- Test it
SELECT category_broad, total_revenue, revenue_share_pct
FROM vw_category_performance
GROUP BY category_broad, total_revenue, revenue_share_pct
ORDER BY total_revenue DESC
LIMIT 10;


-- -------------------------------------------------------
-- VIEW 3: RFM Segment Summary
-- Used for: Customer segment donut, segment KPI cards
-- -------------------------------------------------------
CREATE OR REPLACE VIEW vw_rfm_segments AS
SELECT
    rfm_segment,
    COUNT(customer_id)                              AS customer_count,
    ROUND(AVG(recency_days), 1)                    AS avg_recency_days,
    ROUND(AVG(frequency), 2)                       AS avg_orders_per_customer,
    ROUND(AVG(monetary), 2)                        AS avg_spend,
    ROUND(SUM(monetary), 2)                        AS total_spend,
    ROUND(
        SUM(monetary) / SUM(SUM(monetary)) OVER() * 100
    , 1)                                           AS revenue_contribution_pct
FROM dim_customers
WHERE rfm_segment IS NOT NULL
GROUP BY rfm_segment
ORDER BY total_spend DESC;

-- Test it
SELECT * FROM vw_rfm_segments;


-- -------------------------------------------------------
-- VIEW 4: State-Level Performance (Geographic)
-- Used for: Brazil filled map, state bar chart
-- -------------------------------------------------------
CREATE OR REPLACE VIEW vw_state_performance AS
SELECT
    c.customer_state,
    COUNT(DISTINCT o.order_id)                      AS total_orders,
    COUNT(DISTINCT o.customer_id)                   AS unique_customers,
    ROUND(SUM(o.revenue), 2)                        AS total_revenue,
    ROUND(AVG(o.review_score), 2)                   AS avg_review_score,
    ROUND(AVG(o.delivery_days), 1)                  AS avg_delivery_days,
    ROUND(SUM(o.was_late) / COUNT(*) * 100, 2)      AS late_rate_pct,
    ROUND(SUM(o.revenue) / COUNT(DISTINCT o.customer_id), 2)
                                                    AS revenue_per_customer
FROM fact_orders o
JOIN dim_customers c ON o.customer_id = c.customer_id
WHERE o.is_delivered = 1
GROUP BY c.customer_state
ORDER BY total_revenue DESC;

-- Test it
SELECT customer_state, total_revenue, late_rate_pct, avg_review_score
FROM vw_state_performance
LIMIT 10;


-- -------------------------------------------------------
-- VIEW 5: Seller Performance
-- Used for: Seller scatter plot, seller drill-through page
-- Filter: sellers with at least 10 orders (removes noise)
-- -------------------------------------------------------
CREATE OR REPLACE VIEW vw_seller_performance AS
SELECT
    s.seller_id,
    s.seller_city,
    s.seller_state,
    COUNT(DISTINCT o.order_id)                          AS total_orders,
    COUNT(DISTINCT o.customer_id)                       AS unique_customers,
    ROUND(SUM(o.revenue), 2)                            AS total_revenue,
    ROUND(AVG(o.review_score), 2)                       AS avg_review_score,
    ROUND(AVG(o.delivery_days), 1)                      AS avg_delivery_days,
    -- On-time delivery % (only among delivered orders)
    ROUND(
        SUM(CASE WHEN o.was_late = 0 AND o.is_delivered = 1 THEN 1 ELSE 0 END)
        / NULLIF(SUM(o.is_delivered), 0) * 100
    , 1)                                                AS on_time_pct,
    -- Delivery completion % (how many orders actually arrived)
    ROUND(SUM(o.is_delivered) / COUNT(*) * 100, 1)     AS delivery_completion_pct,
    -- Review quality bucket
    CASE
        WHEN AVG(o.review_score) >= 4.5 THEN 'Excellent'
        WHEN AVG(o.review_score) >= 3.5 THEN 'Good'
        WHEN AVG(o.review_score) >= 2.5 THEN 'Average'
        ELSE 'Poor'
    END                                                 AS review_rating_bucket
FROM fact_orders o
JOIN dim_sellers s ON o.seller_id = s.seller_id
GROUP BY s.seller_id, s.seller_city, s.seller_state
HAVING total_orders >= 10
ORDER BY total_revenue DESC;

-- Test it — the scatter plot quadrant story
SELECT
    on_time_pct,
    avg_review_score,
    total_revenue,
    seller_state,
    CASE
        WHEN on_time_pct >= 90 AND avg_review_score >= 4.0 THEN 'Top Performers'
        WHEN on_time_pct < 90  AND avg_review_score < 4.0  THEN 'Problem Sellers'
        WHEN on_time_pct >= 90 AND avg_review_score < 4.0  THEN 'Fast but Rated Low'
        ELSE 'Slow but Well Reviewed'
    END AS quadrant
FROM vw_seller_performance
LIMIT 20;


-- -------------------------------------------------------
-- VIEW 6: Payment Method Analysis
-- Used for: Payment method bar chart on exec page
-- -------------------------------------------------------
CREATE OR REPLACE VIEW vw_payment_analysis AS
SELECT
    payment_methods,
    COUNT(order_id)                     AS order_count,
    ROUND(SUM(revenue), 2)              AS total_revenue,
    ROUND(AVG(installments), 1)         AS avg_installments,
    ROUND(AVG(order_value), 2)          AS avg_order_value,
    ROUND(COUNT(order_id) / SUM(COUNT(order_id)) OVER() * 100, 1)
                                        AS order_share_pct
FROM fact_orders
WHERE revenue IS NOT NULL
GROUP BY payment_methods
ORDER BY order_count DESC;

-- Test it
SELECT * FROM vw_payment_analysis;


-- =====================================================================
-- PART 6: VERIFY ALL VIEWS
-- =====================================================================

SELECT 'vw_monthly_revenue'    AS view_name, COUNT(*) AS `rows` FROM vw_monthly_revenue
UNION ALL SELECT 'vw_category_performance', COUNT(*) FROM vw_category_performance
UNION ALL SELECT 'vw_rfm_segments',         COUNT(*) FROM vw_rfm_segments
UNION ALL SELECT 'vw_state_performance',    COUNT(*) FROM vw_state_performance
UNION ALL SELECT 'vw_seller_performance',   COUNT(*) FROM vw_seller_performance
UNION ALL SELECT 'vw_payment_analysis',     COUNT(*) FROM vw_payment_analysis;

SELECT '✓ All views ready. Open Power BI Desktop and connect to MySQL.' AS final_status;


-- =====================================================================
-- BONUS QUERIES: Try These Before Power BI (They Tell the Story)
-- =====================================================================

-- Which customer segment is worth the most?
SELECT
    rfm_segment,
    customer_count,
    FORMAT(total_spend, 0) AS total_spend_R$,
    CONCAT(revenue_contribution_pct, '%') AS revenue_share
FROM vw_rfm_segments;

-- Which states have the worst delivery experience?
SELECT
    customer_state,
    avg_delivery_days,
    late_rate_pct,
    avg_review_score
FROM vw_state_performance
ORDER BY late_rate_pct DESC
LIMIT 10;

-- Revenue trend: is the business growing or shrinking?
SELECT
    month_start,
    total_revenue,
    total_orders,
    avg_order_value,
    late_pct
FROM vw_monthly_revenue
ORDER BY month_start;
