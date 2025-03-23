-- models/stg_orders.sql
SELECT
    order_id,
    customer_id,
    order_date,
    status
FROM public.raw_orders