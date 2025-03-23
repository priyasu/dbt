
  create view "dbt_sample"."analytics_schema_analytics_schema"."analytics_orders__dbt_tmp"
    
    
  as (
    

WITH ecommerce_orders AS (
    -- Use source() to reference ecommerce models
    SELECT * FROM "dbt_sample"."ecommerce_ecommerce_schema"."stg_orders"
),
test_project_data AS (
    -- Use source() to reference test project models
    SELECT * FROM "dbt_sample"."my_test_my_test"."my_first_dbt_model"
)

SELECT
    eo.order_id,
    eo.customer_id,
    td.id as test_project_id,
    td.amount as some_metric
FROM ecommerce_orders eo
LEFT JOIN test_project_data td
ON eo.customer_id = td.order_id
  );