-- Reference queries for checking the agent's answers.
-- Replace the project and dataset names, or run them after loading .env.

-- 1. Net revenue and gross profit by product category.
WITH item_financials AS (
  SELECT
    p.category,
    oi.quantity,
    oi.quantity * p.unit_price * (1 - o.discount_pct) AS revenue,
    oi.quantity * p.cost AS cost
  FROM `PROJECT_ID.DATASET.orders` o
  JOIN `PROJECT_ID.DATASET.order_items` oi USING (order_id)
  JOIN `PROJECT_ID.DATASET.products` p USING (product_id)
  WHERE o.status = 'completed'
), returned AS (
  SELECT
    oi.product_id,
    SUM(r.quantity) AS returned_quantity
  FROM `PROJECT_ID.DATASET.returns` r
  JOIN `PROJECT_ID.DATASET.order_items` oi
    ON r.order_id = oi.order_id AND r.product_id = oi.product_id
  GROUP BY oi.product_id
)
SELECT category, SUM(revenue) AS gross_revenue, SUM(revenue - cost) AS gross_profit
FROM item_financials
GROUP BY category
ORDER BY gross_profit DESC;

-- 2. Repeat-purchase rate by acquisition channel.
WITH customer_orders AS (
  SELECT customer_id, channel, COUNT(DISTINCT order_id) AS orders
  FROM `PROJECT_ID.DATASET.orders`
  WHERE status = 'completed'
  GROUP BY customer_id, channel
)
SELECT
  channel,
  COUNT(*) AS customers,
  COUNTIF(orders >= 2) AS repeat_customers,
  SAFE_DIVIDE(COUNTIF(orders >= 2), COUNT(*)) AS repeat_purchase_rate
FROM customer_orders
GROUP BY channel
ORDER BY repeat_purchase_rate DESC;

-- 3. Return rate and refund exposure by category.
SELECT
  p.category,
  SUM(r.quantity) AS units_returned,
  SUM(oi.quantity) AS units_sold,
  SAFE_DIVIDE(SUM(r.quantity), SUM(oi.quantity)) AS unit_return_rate
FROM `PROJECT_ID.DATASET.returns` r
JOIN `PROJECT_ID.DATASET.order_items` oi
  ON r.order_id = oi.order_id AND r.product_id = oi.product_id
JOIN `PROJECT_ID.DATASET.products` p USING (product_id)
GROUP BY p.category
ORDER BY unit_return_rate DESC;
