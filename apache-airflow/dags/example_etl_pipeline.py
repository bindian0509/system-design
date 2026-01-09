"""
Example 1: ETL Pipeline
========================
A classic Extract-Transform-Load pipeline that:
1. Extracts data from a source database
2. Validates the extracted data
3. Transforms data (cleaning, aggregations)
4. Loads to a data warehouse
5. Sends success notification

Use Case: Daily sales data sync from operational DB to analytics warehouse
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.operators.email import EmailOperator
from airflow.utils.trigger_rule import TriggerRule
import pandas as pd
import logging

# Default arguments applied to all tasks
default_args = {
    'owner': 'data-engineering',
    'depends_on_past': False,
    'email': ['data-team@company.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=1),
}

# DAG Definition
with DAG(
    dag_id='daily_sales_etl_pipeline',
    default_args=default_args,
    description='Daily ETL pipeline for sales data',
    schedule_interval='0 6 * * *',  # Run at 6 AM daily
    start_date=datetime(2024, 1, 1),
    catchup=False,  # Don't backfill for past dates
    tags=['etl', 'sales', 'daily'],
    max_active_runs=1,  # Prevent parallel DAG runs
) as dag:

    # Task 1: Extract data from source database
    def extract_sales_data(**context):
        """
        Extract yesterday's sales from operational database.
        Uses execution_date for idempotency.
        """
        execution_date = context['ds']  # YYYY-MM-DD format

        # Use hook to connect to source database
        source_hook = PostgresHook(postgres_conn_id='source_postgres')

        query = f"""
            SELECT
                order_id,
                customer_id,
                product_id,
                quantity,
                unit_price,
                discount,
                order_date,
                created_at
            FROM orders
            WHERE DATE(order_date) = '{execution_date}'
        """

        df = source_hook.get_pandas_df(query)

        # Log extraction metrics
        logging.info(f"Extracted {len(df)} records for {execution_date}")

        # Save to intermediate storage (could be S3, GCS, etc.)
        output_path = f"/tmp/sales_extract_{execution_date}.parquet"
        df.to_parquet(output_path, index=False)

        # Pass file path to next task via XCom
        return output_path

    extract_task = PythonOperator(
        task_id='extract_sales_data',
        python_callable=extract_sales_data,
        provide_context=True,
    )

    # Task 2: Validate extracted data
    def validate_data(**context):
        """
        Perform data quality checks on extracted data.
        Returns branch task to execute based on validation result.
        """
        # Get file path from previous task
        ti = context['ti']
        file_path = ti.xcom_pull(task_ids='extract_sales_data')

        df = pd.read_parquet(file_path)

        validation_errors = []

        # Check 1: No null order_ids
        null_orders = df['order_id'].isnull().sum()
        if null_orders > 0:
            validation_errors.append(f"Found {null_orders} null order_ids")

        # Check 2: Positive quantities
        negative_qty = (df['quantity'] < 0).sum()
        if negative_qty > 0:
            validation_errors.append(f"Found {negative_qty} negative quantities")

        # Check 3: Valid price range
        invalid_prices = ((df['unit_price'] <= 0) | (df['unit_price'] > 100000)).sum()
        if invalid_prices > 0:
            validation_errors.append(f"Found {invalid_prices} invalid prices")

        # Check 4: Record count threshold
        if len(df) == 0:
            validation_errors.append("No records extracted - possible data issue")

        if validation_errors:
            # Store errors in XCom for alerting
            context['ti'].xcom_push(key='validation_errors', value=validation_errors)
            return 'handle_validation_failure'

        return 'transform_data'

    validate_task = BranchPythonOperator(
        task_id='validate_data',
        python_callable=validate_data,
        provide_context=True,
    )

    # Task 3a: Handle validation failures
    def send_validation_alert(**context):
        """Send alert when validation fails."""
        errors = context['ti'].xcom_pull(key='validation_errors', task_ids='validate_data')
        logging.error(f"Validation failed with errors: {errors}")
        # In production, send to Slack, PagerDuty, etc.
        raise ValueError(f"Data validation failed: {errors}")

    handle_failure_task = PythonOperator(
        task_id='handle_validation_failure',
        python_callable=send_validation_alert,
        provide_context=True,
    )

    # Task 3b: Transform data
    def transform_data(**context):
        """
        Apply business transformations:
        - Calculate total amounts
        - Add derived columns
        - Aggregate metrics
        """
        ti = context['ti']
        file_path = ti.xcom_pull(task_ids='extract_sales_data')

        df = pd.read_parquet(file_path)

        # Calculate total amount after discount
        df['total_amount'] = df['quantity'] * df['unit_price'] * (1 - df['discount'])

        # Add time-based dimensions
        df['order_date'] = pd.to_datetime(df['order_date'])
        df['order_year'] = df['order_date'].dt.year
        df['order_month'] = df['order_date'].dt.month
        df['order_day_of_week'] = df['order_date'].dt.dayofweek
        df['is_weekend'] = df['order_day_of_week'].isin([5, 6])

        # Add processing metadata
        df['etl_timestamp'] = datetime.now()
        df['etl_batch_id'] = context['run_id']

        # Save transformed data
        output_path = f"/tmp/sales_transformed_{context['ds']}.parquet"
        df.to_parquet(output_path, index=False)

        # Calculate summary stats for logging
        summary = {
            'total_records': len(df),
            'total_revenue': df['total_amount'].sum(),
            'avg_order_value': df['total_amount'].mean(),
        }
        logging.info(f"Transformation complete. Summary: {summary}")

        return output_path

    transform_task = PythonOperator(
        task_id='transform_data',
        python_callable=transform_data,
        provide_context=True,
    )

    # Task 4: Load to data warehouse
    def load_to_warehouse(**context):
        """
        Load transformed data to warehouse.
        Uses UPSERT for idempotency.
        """
        ti = context['ti']
        file_path = ti.xcom_pull(task_ids='transform_data')
        execution_date = context['ds']

        df = pd.read_parquet(file_path)

        warehouse_hook = PostgresHook(postgres_conn_id='warehouse_postgres')

        # Delete existing data for this date (idempotency)
        delete_query = f"""
            DELETE FROM analytics.fact_sales
            WHERE DATE(order_date) = '{execution_date}'
        """
        warehouse_hook.run(delete_query)

        # Insert new data
        warehouse_hook.insert_rows(
            table='analytics.fact_sales',
            rows=df.values.tolist(),
            target_fields=df.columns.tolist(),
        )

        logging.info(f"Loaded {len(df)} records to warehouse")

        return len(df)

    load_task = PythonOperator(
        task_id='load_to_warehouse',
        python_callable=load_to_warehouse,
        provide_context=True,
    )

    # Task 5: Update aggregation tables
    update_aggregations = PostgresOperator(
        task_id='update_aggregations',
        postgres_conn_id='warehouse_postgres',
        sql="""
            -- Refresh daily sales summary
            INSERT INTO analytics.daily_sales_summary (
                sale_date, total_orders, total_revenue, avg_order_value
            )
            SELECT
                DATE(order_date) as sale_date,
                COUNT(DISTINCT order_id) as total_orders,
                SUM(total_amount) as total_revenue,
                AVG(total_amount) as avg_order_value
            FROM analytics.fact_sales
            WHERE DATE(order_date) = '{{ ds }}'
            GROUP BY DATE(order_date)
            ON CONFLICT (sale_date)
            DO UPDATE SET
                total_orders = EXCLUDED.total_orders,
                total_revenue = EXCLUDED.total_revenue,
                avg_order_value = EXCLUDED.avg_order_value,
                updated_at = NOW();
        """,
    )

    # Task 6: Send success notification
    success_notification = EmailOperator(
        task_id='send_success_notification',
        to=['data-team@company.com'],
        subject='Daily Sales ETL Complete - {{ ds }}',
        html_content="""
            <h2>Daily Sales ETL Pipeline Completed Successfully</h2>
            <p><strong>Date:</strong> {{ ds }}</p>
            <p><strong>Run ID:</strong> {{ run_id }}</p>
            <p>Check the dashboard for updated metrics.</p>
        """,
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )

    # Task 7: Cleanup temporary files
    def cleanup_temp_files(**context):
        """Remove temporary files after successful load."""
        import os
        execution_date = context['ds']
        temp_files = [
            f"/tmp/sales_extract_{execution_date}.parquet",
            f"/tmp/sales_transformed_{execution_date}.parquet",
        ]
        for f in temp_files:
            if os.path.exists(f):
                os.remove(f)
                logging.info(f"Cleaned up {f}")

    cleanup_task = PythonOperator(
        task_id='cleanup_temp_files',
        python_callable=cleanup_temp_files,
        provide_context=True,
        trigger_rule=TriggerRule.ALL_DONE,  # Run regardless of success/failure
    )

    # Define task dependencies
    # Main flow
    extract_task >> validate_task

    # Branch paths
    validate_task >> [handle_failure_task, transform_task]

    # Success path continues
    transform_task >> load_task >> update_aggregations >> success_notification >> cleanup_task


"""
Key Concepts Demonstrated:
=========================
1. BranchPythonOperator: Conditional workflow based on data validation
2. XCom: Passing data between tasks (file paths, not large data)
3. PostgresHook: Database connectivity
4. Templating: {{ ds }}, {{ run_id }} - Jinja templating for dynamic values
5. Idempotency: Delete-before-insert pattern for safe re-runs
6. Trigger Rules: Different execution conditions
7. Task Groups: Logical organization of related tasks
8. Error Handling: Validation failures routed to alert task
"""

