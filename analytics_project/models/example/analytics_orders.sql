{{ config(
    materialized='view',
    schema='analytics_schema'
) }}

WITH ecommerce_orders AS (
    -- Use source() to reference ecommerce models
    SELECT * FROM {{ source('ecommerce_models', 'stg_orders') }}
),
test_project_data AS (
    -- Use source() to reference test project models
    SELECT * FROM {{ source('test_project_models', 'my_first_dbt_model') }}
)

SELECT
    eo.order_id,
    eo.customer_id,
    td.id as test_project_id,
    td.amount as some_metric
FROM ecommerce_orders eo
LEFT JOIN test_project_data td
ON eo.customer_id = td.order_id
