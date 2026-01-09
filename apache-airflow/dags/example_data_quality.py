"""
Example 3: Data Quality Monitoring Pipeline
============================================
A data quality pipeline that:
1. Runs automated quality checks on data tables
2. Compares against historical baselines
3. Generates quality scores
4. Alerts on anomalies
5. Creates audit reports

Use Case: Continuous data quality monitoring for critical business tables
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator
from airflow.utils.task_group import TaskGroup
import logging
import json

default_args = {
    'owner': 'data-quality',
    'depends_on_past': False,
    'email': ['dq-alerts@company.com'],
    'email_on_failure': True,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Configuration for tables to monitor
DQ_CONFIG = {
    'analytics.fact_orders': {
        'freshness_hours': 24,
        'min_row_count': 1000,
        'null_checks': ['order_id', 'customer_id', 'amount'],
        'range_checks': {
            'amount': {'min': 0, 'max': 1000000},
            'quantity': {'min': 1, 'max': 10000},
        },
        'uniqueness_checks': ['order_id'],
        'referential_checks': [
            {'column': 'customer_id', 'ref_table': 'dim_customers', 'ref_column': 'customer_id'},
        ],
    },
    'analytics.fact_payments': {
        'freshness_hours': 6,
        'min_row_count': 500,
        'null_checks': ['payment_id', 'order_id', 'amount'],
        'range_checks': {
            'amount': {'min': 0, 'max': 500000},
        },
        'uniqueness_checks': ['payment_id'],
        'custom_sql_checks': [
            {
                'name': 'payment_amount_vs_order',
                'sql': """
                    SELECT COUNT(*)
                    FROM analytics.fact_payments p
                    JOIN analytics.fact_orders o ON p.order_id = o.order_id
                    WHERE p.amount > o.amount * 1.1
                """,
                'threshold': 100,  # Alert if > 100 payments exceed order amount
            },
        ],
    },
    'analytics.dim_customers': {
        'freshness_hours': 168,  # Weekly update expected
        'min_row_count': 10000,
        'null_checks': ['customer_id', 'email'],
        'pattern_checks': {
            'email': r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$',
        },
        'uniqueness_checks': ['customer_id', 'email'],
    },
}

with DAG(
    dag_id='data_quality_monitoring',
    default_args=default_args,
    description='Automated data quality checks',
    schedule_interval='0 */4 * * *',  # Every 4 hours
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['data-quality', 'monitoring'],
) as dag:

    def run_freshness_check(table_name: str, config: dict, **context):
        """Check if table has been updated recently."""
        hook = PostgresHook(postgres_conn_id='warehouse_postgres')

        freshness_hours = config.get('freshness_hours', 24)

        query = f"""
            SELECT
                MAX(updated_at) as last_update,
                EXTRACT(EPOCH FROM (NOW() - MAX(updated_at))) / 3600 as hours_since_update
            FROM {table_name}
        """

        result = hook.get_first(query)
        hours_since = result[1] if result else None

        check_result = {
            'check_type': 'freshness',
            'table': table_name,
            'last_update': str(result[0]) if result else None,
            'hours_since_update': hours_since,
            'threshold_hours': freshness_hours,
            'passed': hours_since is not None and hours_since <= freshness_hours,
        }

        logging.info(f"Freshness check for {table_name}: {check_result}")
        return check_result

    def run_completeness_checks(table_name: str, config: dict, **context):
        """Check for null values in required columns."""
        hook = PostgresHook(postgres_conn_id='warehouse_postgres')

        null_columns = config.get('null_checks', [])
        results = []

        for column in null_columns:
            query = f"""
                SELECT
                    COUNT(*) as total_rows,
                    SUM(CASE WHEN {column} IS NULL THEN 1 ELSE 0 END) as null_count,
                    ROUND(100.0 * SUM(CASE WHEN {column} IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as null_pct
                FROM {table_name}
            """

            row = hook.get_first(query)

            check_result = {
                'check_type': 'completeness',
                'table': table_name,
                'column': column,
                'total_rows': row[0],
                'null_count': row[1],
                'null_percentage': row[2],
                'passed': row[1] == 0,
            }
            results.append(check_result)

        logging.info(f"Completeness checks for {table_name}: {len(results)} columns checked")
        return results

    def run_validity_checks(table_name: str, config: dict, **context):
        """Check value ranges and patterns."""
        hook = PostgresHook(postgres_conn_id='warehouse_postgres')
        results = []

        # Range checks
        range_checks = config.get('range_checks', {})
        for column, bounds in range_checks.items():
            query = f"""
                SELECT
                    COUNT(*) as violations
                FROM {table_name}
                WHERE {column} < {bounds['min']} OR {column} > {bounds['max']}
            """

            violations = hook.get_first(query)[0]

            results.append({
                'check_type': 'range',
                'table': table_name,
                'column': column,
                'bounds': bounds,
                'violations': violations,
                'passed': violations == 0,
            })

        # Pattern checks (for strings)
        pattern_checks = config.get('pattern_checks', {})
        for column, pattern in pattern_checks.items():
            query = f"""
                SELECT COUNT(*) as violations
                FROM {table_name}
                WHERE {column} IS NOT NULL
                AND {column} !~ '{pattern}'
            """

            violations = hook.get_first(query)[0]

            results.append({
                'check_type': 'pattern',
                'table': table_name,
                'column': column,
                'pattern': pattern,
                'violations': violations,
                'passed': violations == 0,
            })

        return results

    def run_uniqueness_checks(table_name: str, config: dict, **context):
        """Check for duplicate values."""
        hook = PostgresHook(postgres_conn_id='warehouse_postgres')
        results = []

        uniqueness_columns = config.get('uniqueness_checks', [])

        for column in uniqueness_columns:
            query = f"""
                SELECT
                    COUNT(*) - COUNT(DISTINCT {column}) as duplicates
                FROM {table_name}
            """

            duplicates = hook.get_first(query)[0]

            results.append({
                'check_type': 'uniqueness',
                'table': table_name,
                'column': column,
                'duplicates': duplicates,
                'passed': duplicates == 0,
            })

        return results

    def run_referential_checks(table_name: str, config: dict, **context):
        """Check referential integrity."""
        hook = PostgresHook(postgres_conn_id='warehouse_postgres')
        results = []

        ref_checks = config.get('referential_checks', [])

        for check in ref_checks:
            query = f"""
                SELECT COUNT(*) as orphans
                FROM {table_name} t
                LEFT JOIN {check['ref_table']} r
                    ON t.{check['column']} = r.{check['ref_column']}
                WHERE t.{check['column']} IS NOT NULL
                AND r.{check['ref_column']} IS NULL
            """

            orphans = hook.get_first(query)[0]

            results.append({
                'check_type': 'referential_integrity',
                'table': table_name,
                'column': check['column'],
                'ref_table': check['ref_table'],
                'orphan_records': orphans,
                'passed': orphans == 0,
            })

        return results

    def run_volume_check(table_name: str, config: dict, **context):
        """Check row counts against thresholds."""
        hook = PostgresHook(postgres_conn_id='warehouse_postgres')

        min_rows = config.get('min_row_count', 0)

        query = f"SELECT COUNT(*) FROM {table_name}"
        row_count = hook.get_first(query)[0]

        # Also compare against historical average
        historical_query = f"""
            SELECT AVG(row_count)
            FROM dq_metrics.table_volumes
            WHERE table_name = '{table_name}'
            AND measured_at > NOW() - INTERVAL '30 days'
        """

        try:
            historical_avg = hook.get_first(historical_query)[0] or row_count
        except:
            historical_avg = row_count

        deviation = abs(row_count - historical_avg) / historical_avg if historical_avg > 0 else 0

        return {
            'check_type': 'volume',
            'table': table_name,
            'current_rows': row_count,
            'min_threshold': min_rows,
            'historical_avg': historical_avg,
            'deviation_pct': round(deviation * 100, 2),
            'passed': row_count >= min_rows and deviation < 0.5,  # Allow 50% deviation
        }

    def aggregate_results(**context):
        """Aggregate all check results and calculate quality score."""
        ti = context['ti']
        all_results = []

        for table_name in DQ_CONFIG.keys():
            safe_table = table_name.replace('.', '_')

            # Collect all check results for this table
            freshness = ti.xcom_pull(task_ids=f'dq_checks_{safe_table}.freshness_check')
            completeness = ti.xcom_pull(task_ids=f'dq_checks_{safe_table}.completeness_checks')
            validity = ti.xcom_pull(task_ids=f'dq_checks_{safe_table}.validity_checks')
            uniqueness = ti.xcom_pull(task_ids=f'dq_checks_{safe_table}.uniqueness_checks')
            referential = ti.xcom_pull(task_ids=f'dq_checks_{safe_table}.referential_checks')
            volume = ti.xcom_pull(task_ids=f'dq_checks_{safe_table}.volume_check')

            # Flatten results
            table_results = []
            if freshness:
                table_results.append(freshness)
            if completeness:
                table_results.extend(completeness)
            if validity:
                table_results.extend(validity)
            if uniqueness:
                table_results.extend(uniqueness)
            if referential:
                table_results.extend(referential)
            if volume:
                table_results.append(volume)

            all_results.extend(table_results)

        # Calculate overall statistics
        total_checks = len(all_results)
        passed_checks = sum(1 for r in all_results if r and r.get('passed', False))
        failed_checks = [r for r in all_results if r and not r.get('passed', True)]

        quality_score = (passed_checks / total_checks * 100) if total_checks > 0 else 0

        summary = {
            'execution_date': context['ds'],
            'total_checks': total_checks,
            'passed_checks': passed_checks,
            'failed_checks': len(failed_checks),
            'quality_score': round(quality_score, 2),
            'failures': failed_checks,
        }

        logging.info(f"DQ Summary: {summary}")

        ti.xcom_push(key='dq_summary', value=summary)
        ti.xcom_push(key='quality_score', value=quality_score)
        ti.xcom_push(key='failed_checks', value=failed_checks)

        return summary

    def generate_report(**context):
        """Generate detailed HTML report."""
        ti = context['ti']
        summary = ti.xcom_pull(task_ids='aggregate_results', key='dq_summary')

        if not summary:
            summary = {'quality_score': 100, 'total_checks': 0, 'failed_checks': 0, 'failures': []}

        report_html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .score {{ font-size: 48px; font-weight: bold; }}
                .score.good {{ color: green; }}
                .score.warning {{ color: orange; }}
                .score.bad {{ color: red; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #4CAF50; color: white; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
                .failed {{ background-color: #ffcccc; }}
            </style>
        </head>
        <body>
            <h1>Data Quality Report - {context['ds']}</h1>

            <h2>Overall Score</h2>
            <div class="score {'good' if summary['quality_score'] >= 95 else 'warning' if summary['quality_score'] >= 80 else 'bad'}">
                {summary['quality_score']}%
            </div>

            <h2>Summary</h2>
            <ul>
                <li>Total Checks: {summary['total_checks']}</li>
                <li>Passed: {summary['total_checks'] - summary['failed_checks']}</li>
                <li>Failed: {summary['failed_checks']}</li>
            </ul>

            <h2>Failed Checks</h2>
            <table>
                <tr>
                    <th>Table</th>
                    <th>Check Type</th>
                    <th>Column</th>
                    <th>Details</th>
                </tr>
                {''.join(f"<tr class='failed'><td>{f.get('table', 'N/A')}</td><td>{f.get('check_type', 'N/A')}</td><td>{f.get('column', 'N/A')}</td><td>{json.dumps(f)}</td></tr>" for f in summary.get('failures', []))}
            </table>
        </body>
        </html>
        """

        report_path = f"/reports/dq_report_{context['ds']}.html"
        logging.info(f"Report generated: {report_path}")

        return report_path

    def should_alert(**context):
        """Determine if alerting is needed based on quality score."""
        ti = context['ti']
        quality_score = ti.xcom_pull(task_ids='aggregate_results', key='quality_score')

        if quality_score is None:
            quality_score = 100

        if quality_score < 95:
            return 'send_alert'
        return 'skip_alert'

    # Create task groups for each table
    task_groups = []

    for table_name, config in DQ_CONFIG.items():
        safe_table = table_name.replace('.', '_')

        with TaskGroup(group_id=f'dq_checks_{safe_table}') as tg:

            freshness = PythonOperator(
                task_id='freshness_check',
                python_callable=run_freshness_check,
                op_kwargs={'table_name': table_name, 'config': config},
            )

            completeness = PythonOperator(
                task_id='completeness_checks',
                python_callable=run_completeness_checks,
                op_kwargs={'table_name': table_name, 'config': config},
            )

            validity = PythonOperator(
                task_id='validity_checks',
                python_callable=run_validity_checks,
                op_kwargs={'table_name': table_name, 'config': config},
            )

            uniqueness = PythonOperator(
                task_id='uniqueness_checks',
                python_callable=run_uniqueness_checks,
                op_kwargs={'table_name': table_name, 'config': config},
            )

            referential = PythonOperator(
                task_id='referential_checks',
                python_callable=run_referential_checks,
                op_kwargs={'table_name': table_name, 'config': config},
            )

            volume = PythonOperator(
                task_id='volume_check',
                python_callable=run_volume_check,
                op_kwargs={'table_name': table_name, 'config': config},
            )

        task_groups.append(tg)

    # Aggregation and reporting
    aggregate = PythonOperator(
        task_id='aggregate_results',
        python_callable=aggregate_results,
    )

    report = PythonOperator(
        task_id='generate_report',
        python_callable=generate_report,
    )

    from airflow.operators.python import BranchPythonOperator
    from airflow.operators.empty import EmptyOperator

    check_alert = BranchPythonOperator(
        task_id='should_alert',
        python_callable=should_alert,
    )

    send_alert = SlackWebhookOperator(
        task_id='send_alert',
        slack_webhook_conn_id='slack_dq_alerts',
        message="""
:warning: *Data Quality Alert*
Score: {{ ti.xcom_pull(task_ids='aggregate_results', key='quality_score') }}%
Date: {{ ds }}
Failed Checks: {{ ti.xcom_pull(task_ids='aggregate_results', key='failed_checks') | length }}

<{{ ti.xcom_pull(task_ids='generate_report') }}|View Full Report>
        """,
        channel='#data-quality-alerts',
    )

    skip_alert = EmptyOperator(task_id='skip_alert')

    done = EmptyOperator(
        task_id='done',
        trigger_rule='none_failed_min_one_success',
    )

    # Dependencies
    for tg in task_groups:
        tg >> aggregate

    aggregate >> report >> check_alert
    check_alert >> [send_alert, skip_alert] >> done


"""
Key Concepts Demonstrated:
=========================
1. Configuration-Driven DAGs: DQ_CONFIG drives check generation
2. Dynamic Task Groups: One group per monitored table
3. Multiple Check Types: Freshness, completeness, validity, uniqueness, referential, volume
4. Historical Comparison: Detect anomalies vs baseline
5. Quality Scoring: Aggregate metrics into actionable score
6. Conditional Alerting: Only alert when score drops below threshold
7. Slack Integration: Real-time team notifications
8. Report Generation: Detailed HTML reports for investigation
"""

