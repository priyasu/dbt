{{ config(
    materialized='table',
    schema='my_test',
    alias='my_first_dbt_model'
) }}

SELECT
    transaction_id as id,
    order_id,
    amount,
    transaction_date
FROM {{ source('my_test_project', 'raw_transactions') }}
WHERE transaction_id IS NOT NULL


