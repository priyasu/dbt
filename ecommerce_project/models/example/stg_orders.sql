{{ config(
    materialized='view',
    schema='ecommerce_schema',
    alias='stg_orders'
) }}

SELECT
    order_id,
    customer_id,
    order_date,
    status
FROM {{ source('ecommerce_source', 'raw_orders') }}