"""
Example 5: Automated Report Generation & Distribution
======================================================
A pipeline that:
1. Queries data warehouse for metrics
2. Generates visualizations
3. Creates formatted reports (PDF, Excel)
4. Distributes via email and Slack
5. Archives reports to cloud storage

Use Case: Weekly executive business report distributed to stakeholders
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.email import EmailOperator
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.utils.task_group import TaskGroup
from airflow.models import Variable
import logging
import json

default_args = {
    'owner': 'business-intelligence',
    'depends_on_past': False,
    'email': ['bi-team@company.com'],
    'email_on_failure': True,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# Report configuration
REPORT_CONFIG = {
    'name': 'Weekly Executive Summary',
    'sections': [
        {
            'id': 'revenue',
            'title': 'Revenue Metrics',
            'metrics': ['total_revenue', 'revenue_growth', 'avg_order_value'],
        },
        {
            'id': 'customers',
            'title': 'Customer Metrics',
            'metrics': ['new_customers', 'churn_rate', 'customer_lifetime_value'],
        },
        {
            'id': 'operations',
            'title': 'Operational Metrics',
            'metrics': ['order_fulfillment_time', 'customer_satisfaction', 'support_tickets'],
        },
    ],
    'recipients': {
        'executive': ['ceo@company.com', 'cfo@company.com'],
        'management': ['vp-sales@company.com', 'vp-ops@company.com'],
        'analysts': ['bi-team@company.com'],
    },
    'slack_channels': ['#executive-metrics', '#bi-reports'],
}

with DAG(
    dag_id='weekly_executive_report',
    default_args=default_args,
    description='Generate and distribute weekly executive report',
    schedule_interval='0 8 * * 1',  # Every Monday at 8 AM
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['reporting', 'executive', 'weekly'],
    max_active_runs=1,
) as dag:

    def calculate_metrics(**context):
        """
        Query data warehouse and calculate all report metrics.
        """
        # In production, use PostgresHook or similar
        # Simulated metrics for demonstration

        execution_date = context['ds']
        week_start = context['data_interval_start'].strftime('%Y-%m-%d')
        week_end = context['data_interval_end'].strftime('%Y-%m-%d')

        metrics = {
            'period': {
                'start': week_start,
                'end': week_end,
                'report_date': execution_date,
            },
            'revenue': {
                'total_revenue': 1_250_000,
                'previous_period': 1_180_000,
                'revenue_growth': 5.9,
                'avg_order_value': 85.50,
                'aov_change': 2.3,
                'top_products': [
                    {'name': 'Product A', 'revenue': 320000},
                    {'name': 'Product B', 'revenue': 280000},
                    {'name': 'Product C', 'revenue': 195000},
                ],
            },
            'customers': {
                'total_customers': 45_000,
                'new_customers': 1_250,
                'new_customer_change': 8.5,
                'churn_rate': 2.1,
                'churn_change': -0.3,
                'customer_lifetime_value': 450,
                'clv_change': 12.0,
                'segments': {
                    'enterprise': {'count': 150, 'revenue_pct': 45},
                    'mid_market': {'count': 2500, 'revenue_pct': 35},
                    'smb': {'count': 42350, 'revenue_pct': 20},
                },
            },
            'operations': {
                'order_count': 14_600,
                'order_fulfillment_time_hours': 18.5,
                'fulfillment_change': -2.5,
                'customer_satisfaction': 4.6,
                'csat_change': 0.1,
                'support_tickets': 850,
                'ticket_change': -5.2,
                'resolution_time_hours': 4.2,
            },
        }

        logging.info(f"Calculated metrics for period {week_start} to {week_end}")

        # Push metrics to XCom
        context['ti'].xcom_push(key='metrics', value=metrics)

        return metrics

    def generate_visualizations(**context):
        """
        Create charts and visualizations for the report.
        Uses matplotlib/plotly for chart generation.
        """
        ti = context['ti']
        metrics = ti.xcom_pull(task_ids='calculate_metrics', key='metrics')

        charts = []
        chart_dir = f"/tmp/charts_{context['ds']}"

        # In production, generate actual charts with matplotlib/plotly
        # Simulating chart generation

        # Revenue trend chart
        charts.append({
            'id': 'revenue_trend',
            'title': 'Weekly Revenue Trend',
            'type': 'line',
            'path': f"{chart_dir}/revenue_trend.png",
        })

        # Customer segment pie chart
        charts.append({
            'id': 'customer_segments',
            'title': 'Revenue by Customer Segment',
            'type': 'pie',
            'path': f"{chart_dir}/customer_segments.png",
        })

        # Top products bar chart
        charts.append({
            'id': 'top_products',
            'title': 'Top Products by Revenue',
            'type': 'bar',
            'path': f"{chart_dir}/top_products.png",
        })

        # Operations dashboard
        charts.append({
            'id': 'ops_metrics',
            'title': 'Operational Metrics',
            'type': 'gauge',
            'path': f"{chart_dir}/ops_metrics.png",
        })

        logging.info(f"Generated {len(charts)} visualizations")

        ti.xcom_push(key='charts', value=charts)
        return charts

    def generate_pdf_report(**context):
        """
        Generate formatted PDF report combining metrics and visualizations.
        Uses reportlab or weasyprint in production.
        """
        ti = context['ti']
        metrics = ti.xcom_pull(task_ids='calculate_metrics', key='metrics')
        charts = ti.xcom_pull(task_ids='generate_visualizations', key='charts')

        report_path = f"/tmp/executive_report_{context['ds']}.pdf"

        # In production, use reportlab/weasyprint to generate PDF
        # Simulating PDF content structure

        report_structure = {
            'title': REPORT_CONFIG['name'],
            'period': metrics['period'],
            'sections': [],
        }

        for section_config in REPORT_CONFIG['sections']:
            section_data = metrics.get(section_config['id'], {})
            section = {
                'title': section_config['title'],
                'metrics': {},
            }

            for metric_name in section_config['metrics']:
                if metric_name in section_data:
                    section['metrics'][metric_name] = section_data[metric_name]

            report_structure['sections'].append(section)

        logging.info(f"Generated PDF report: {report_path}")

        ti.xcom_push(key='pdf_path', value=report_path)
        return report_path

    def generate_excel_report(**context):
        """
        Generate Excel report with detailed data for analysts.
        Uses pandas + openpyxl in production.
        """
        ti = context['ti']
        metrics = ti.xcom_pull(task_ids='calculate_metrics', key='metrics')

        excel_path = f"/tmp/executive_report_{context['ds']}.xlsx"

        # In production, use pandas to create Excel with multiple sheets
        # Simulating Excel structure

        sheets = {
            'Summary': 'High-level KPIs',
            'Revenue_Detail': 'Daily revenue breakdown',
            'Customer_Analysis': 'Customer segment deep dive',
            'Operations': 'Operational metrics detail',
            'Raw_Data': 'Underlying data for analysis',
        }

        logging.info(f"Generated Excel report with {len(sheets)} sheets: {excel_path}")

        ti.xcom_push(key='excel_path', value=excel_path)
        return excel_path

    def upload_to_s3(**context):
        """
        Archive reports to S3 for historical access.
        """
        ti = context['ti']
        pdf_path = ti.xcom_pull(task_ids='generate_pdf_report', key='pdf_path')
        excel_path = ti.xcom_pull(task_ids='generate_excel_report', key='excel_path')

        execution_date = context['ds']
        year = execution_date[:4]
        month = execution_date[5:7]

        s3_bucket = Variable.get('reports_s3_bucket', default_var='company-reports')

        s3_paths = []

        # In production, actually upload to S3
        # s3_hook = S3Hook(aws_conn_id='aws_default')

        for local_path, report_type in [(pdf_path, 'pdf'), (excel_path, 'xlsx')]:
            s3_key = f"executive-reports/{year}/{month}/weekly_report_{execution_date}.{report_type}"
            s3_paths.append(f"s3://{s3_bucket}/{s3_key}")

            # s3_hook.load_file(
            #     filename=local_path,
            #     key=s3_key,
            #     bucket_name=s3_bucket,
            #     replace=True,
            # )

            logging.info(f"Uploaded {report_type} to s3://{s3_bucket}/{s3_key}")

        ti.xcom_push(key='s3_paths', value=s3_paths)
        return s3_paths

    def build_email_content(**context):
        """
        Build HTML email content with embedded metrics summary.
        """
        ti = context['ti']
        metrics = ti.xcom_pull(task_ids='calculate_metrics', key='metrics')
        s3_paths = ti.xcom_pull(task_ids='upload_to_s3', key='s3_paths')

        period = metrics['period']
        revenue = metrics['revenue']
        customers = metrics['customers']
        ops = metrics['operations']

        # Color coding for metrics
        def get_color(value, threshold=0):
            return '#28a745' if value > threshold else '#dc3545' if value < threshold else '#6c757d'

        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #333; max-width: 800px; margin: 0 auto; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; }}
                .content {{ padding: 20px; background: #f8f9fa; }}
                .metric-card {{ background: white; border-radius: 8px; padding: 20px; margin: 10px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .metric-value {{ font-size: 32px; font-weight: bold; }}
                .metric-change {{ font-size: 14px; padding: 4px 8px; border-radius: 4px; }}
                .positive {{ color: #28a745; background: #d4edda; }}
                .negative {{ color: #dc3545; background: #f8d7da; }}
                .metric-label {{ color: #6c757d; font-size: 14px; margin-top: 5px; }}
                .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }}
                .section-title {{ font-size: 18px; font-weight: bold; margin: 20px 0 10px 0; color: #495057; }}
                .footer {{ background: #343a40; color: white; padding: 20px; border-radius: 0 0 10px 10px; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{REPORT_CONFIG['name']}</h1>
                <p>Week of {period['start']} to {period['end']}</p>
            </div>

            <div class="content">
                <div class="section-title">💰 Revenue Highlights</div>
                <div class="grid">
                    <div class="metric-card">
                        <div class="metric-value">${revenue['total_revenue']:,.0f}</div>
                        <div class="metric-label">Total Revenue</div>
                        <span class="metric-change {'positive' if revenue['revenue_growth'] > 0 else 'negative'}">
                            {'+' if revenue['revenue_growth'] > 0 else ''}{revenue['revenue_growth']}% vs last week
                        </span>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">${revenue['avg_order_value']:.2f}</div>
                        <div class="metric-label">Avg Order Value</div>
                        <span class="metric-change {'positive' if revenue['aov_change'] > 0 else 'negative'}">
                            {'+' if revenue['aov_change'] > 0 else ''}{revenue['aov_change']}%
                        </span>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{ops['order_count']:,}</div>
                        <div class="metric-label">Orders</div>
                    </div>
                </div>

                <div class="section-title">👥 Customer Metrics</div>
                <div class="grid">
                    <div class="metric-card">
                        <div class="metric-value">{customers['new_customers']:,}</div>
                        <div class="metric-label">New Customers</div>
                        <span class="metric-change {'positive' if customers['new_customer_change'] > 0 else 'negative'}">
                            {'+' if customers['new_customer_change'] > 0 else ''}{customers['new_customer_change']}%
                        </span>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{customers['churn_rate']}%</div>
                        <div class="metric-label">Churn Rate</div>
                        <span class="metric-change {'positive' if customers['churn_change'] < 0 else 'negative'}">
                            {'+' if customers['churn_change'] > 0 else ''}{customers['churn_change']}%
                        </span>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">${customers['customer_lifetime_value']:,}</div>
                        <div class="metric-label">Customer LTV</div>
                        <span class="metric-change {'positive' if customers['clv_change'] > 0 else 'negative'}">
                            {'+' if customers['clv_change'] > 0 else ''}{customers['clv_change']}%
                        </span>
                    </div>
                </div>

                <div class="section-title">⚙️ Operations</div>
                <div class="grid">
                    <div class="metric-card">
                        <div class="metric-value">{ops['order_fulfillment_time_hours']}h</div>
                        <div class="metric-label">Fulfillment Time</div>
                        <span class="metric-change {'positive' if ops['fulfillment_change'] < 0 else 'negative'}">
                            {'+' if ops['fulfillment_change'] > 0 else ''}{ops['fulfillment_change']}%
                        </span>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{ops['customer_satisfaction']}/5</div>
                        <div class="metric-label">Customer Satisfaction</div>
                        <span class="metric-change {'positive' if ops['csat_change'] > 0 else 'negative'}">
                            {'+' if ops['csat_change'] > 0 else ''}{ops['csat_change']}
                        </span>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{ops['support_tickets']}</div>
                        <div class="metric-label">Support Tickets</div>
                        <span class="metric-change {'positive' if ops['ticket_change'] < 0 else 'negative'}">
                            {'+' if ops['ticket_change'] > 0 else ''}{ops['ticket_change']}%
                        </span>
                    </div>
                </div>

                <p style="margin-top: 30px;">
                    📎 <strong>Attachments:</strong> Full PDF and Excel reports are attached for detailed analysis.
                </p>
            </div>

            <div class="footer">
                <p>Generated by the Business Intelligence Team</p>
                <p>Reports archived at: {', '.join(s3_paths or ['S3 path'])}</p>
                <p>Questions? Contact bi-team@company.com</p>
            </div>
        </body>
        </html>
        """

        ti.xcom_push(key='email_html', value=html_content)
        return html_content

    def build_slack_message(**context):
        """
        Build Slack message with key metrics summary.
        """
        ti = context['ti']
        metrics = ti.xcom_pull(task_ids='calculate_metrics', key='metrics')

        period = metrics['period']
        revenue = metrics['revenue']
        customers = metrics['customers']

        def emoji(value, threshold=0):
            return '📈' if value > threshold else '📉' if value < threshold else '➡️'

        slack_message = f"""
:chart_with_upwards_trend: *{REPORT_CONFIG['name']}*
_Week of {period['start']} to {period['end']}_

*💰 Revenue*
• Total: *${revenue['total_revenue']:,}* {emoji(revenue['revenue_growth'])} ({'+' if revenue['revenue_growth'] > 0 else ''}{revenue['revenue_growth']}%)
• AOV: *${revenue['avg_order_value']:.2f}*

*👥 Customers*
• New: *{customers['new_customers']:,}* {emoji(customers['new_customer_change'])} ({'+' if customers['new_customer_change'] > 0 else ''}{customers['new_customer_change']}%)
• Churn: *{customers['churn_rate']}%* {emoji(-customers['churn_change'])}

:page_facing_up: Full report sent to stakeholder mailing lists.
"""

        ti.xcom_push(key='slack_message', value=slack_message)
        return slack_message

    # Define tasks
    calc_metrics = PythonOperator(
        task_id='calculate_metrics',
        python_callable=calculate_metrics,
    )

    with TaskGroup(group_id='generate_reports') as report_gen:
        visualizations = PythonOperator(
            task_id='generate_visualizations',
            python_callable=generate_visualizations,
        )

        pdf_report = PythonOperator(
            task_id='generate_pdf_report',
            python_callable=generate_pdf_report,
        )

        excel_report = PythonOperator(
            task_id='generate_excel_report',
            python_callable=generate_excel_report,
        )

        visualizations >> pdf_report

    upload = PythonOperator(
        task_id='upload_to_s3',
        python_callable=upload_to_s3,
    )

    with TaskGroup(group_id='distribute') as distribution:

        email_content = PythonOperator(
            task_id='build_email_content',
            python_callable=build_email_content,
        )

        # Email to executives
        email_executives = EmailOperator(
            task_id='email_executives',
            to=REPORT_CONFIG['recipients']['executive'],
            subject='Weekly Executive Report - {{ ds }}',
            html_content="{{ ti.xcom_pull(task_ids='distribute.build_email_content', key='email_html') }}",
            # In production, attach files:
            # files=[
            #     "{{ ti.xcom_pull(task_ids='generate_reports.generate_pdf_report', key='pdf_path') }}",
            # ],
        )

        # Email to management with Excel
        email_management = EmailOperator(
            task_id='email_management',
            to=REPORT_CONFIG['recipients']['management'],
            subject='Weekly Report - {{ ds }}',
            html_content="{{ ti.xcom_pull(task_ids='distribute.build_email_content', key='email_html') }}",
        )

        # Slack notifications
        slack_content = PythonOperator(
            task_id='build_slack_message',
            python_callable=build_slack_message,
        )

        slack_notification = SlackWebhookOperator(
            task_id='send_slack',
            slack_webhook_conn_id='slack_reports',
            message="{{ ti.xcom_pull(task_ids='distribute.build_slack_message', key='slack_message') }}",
        )

        email_content >> [email_executives, email_management]
        slack_content >> slack_notification

    def cleanup(**context):
        """Clean up temporary files."""
        import os
        import glob

        temp_files = glob.glob(f"/tmp/*_{context['ds']}*")
        for f in temp_files:
            try:
                os.remove(f)
                logging.info(f"Cleaned up: {f}")
            except Exception as e:
                logging.warning(f"Failed to clean up {f}: {e}")

    cleanup_task = PythonOperator(
        task_id='cleanup',
        python_callable=cleanup,
        trigger_rule='all_done',
    )

    # Task dependencies
    calc_metrics >> report_gen >> upload >> distribution >> cleanup_task


"""
Key Concepts Demonstrated:
=========================
1. Report Generation: PDF and Excel report creation
2. Data Visualization: Chart generation for reports
3. Cloud Storage: S3 archival for historical access
4. Multi-Channel Distribution: Email and Slack notifications
5. Rich HTML Templates: Professional email formatting
6. Stakeholder Groups: Different content for different audiences
7. Jinja Templating: Dynamic content in email subjects/bodies
8. Task Groups: Organized report generation and distribution stages
9. File Attachments: Sending reports as email attachments
10. Cleanup Tasks: Temporary file management
"""

