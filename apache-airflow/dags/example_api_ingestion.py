"""
Example 4: API Data Ingestion Pipeline
=======================================
A pipeline that:
1. Fetches data from multiple REST APIs
2. Handles pagination and rate limiting
3. Transforms and normalizes data
4. Incrementally loads to data warehouse
5. Handles failures gracefully with retries

Use Case: Daily ingestion of data from third-party APIs (payment providers,
          marketing platforms, analytics services)
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.http.operators.http import HttpOperator
from airflow.providers.http.sensors.http import HttpSensor
from airflow.utils.task_group import TaskGroup
from airflow.models import Variable
from airflow.exceptions import AirflowSkipException
import logging
import json
import time

default_args = {
    'owner': 'data-engineering',
    'depends_on_past': False,
    'email': ['data-team@company.com'],
    'email_on_failure': True,
    'retries': 5,
    'retry_delay': timedelta(minutes=2),
    'retry_exponential_backoff': True,
    'max_retry_delay': timedelta(minutes=30),
}

# API configurations
API_SOURCES = {
    'stripe': {
        'conn_id': 'stripe_api',
        'base_endpoint': '/v1',
        'endpoints': [
            {'name': 'charges', 'path': '/charges', 'date_field': 'created'},
            {'name': 'customers', 'path': '/customers', 'date_field': 'created'},
            {'name': 'refunds', 'path': '/refunds', 'date_field': 'created'},
        ],
        'rate_limit': {'requests_per_second': 25},
        'pagination': {'type': 'cursor', 'param': 'starting_after', 'response_key': 'data'},
    },
    'hubspot': {
        'conn_id': 'hubspot_api',
        'base_endpoint': '/crm/v3',
        'endpoints': [
            {'name': 'contacts', 'path': '/objects/contacts', 'date_field': 'updatedAt'},
            {'name': 'deals', 'path': '/objects/deals', 'date_field': 'updatedAt'},
            {'name': 'companies', 'path': '/objects/companies', 'date_field': 'updatedAt'},
        ],
        'rate_limit': {'requests_per_second': 10},
        'pagination': {'type': 'offset', 'param': 'after', 'response_key': 'results'},
    },
    'google_analytics': {
        'conn_id': 'ga4_api',
        'base_endpoint': '/v1beta',
        'endpoints': [
            {'name': 'page_views', 'path': '/reports:batchGet', 'method': 'POST'},
            {'name': 'user_activity', 'path': '/reports:batchGet', 'method': 'POST'},
        ],
        'rate_limit': {'requests_per_second': 5},
        'pagination': {'type': 'token', 'param': 'pageToken', 'response_key': 'rows'},
    },
}

with DAG(
    dag_id='api_data_ingestion',
    default_args=default_args,
    description='Ingest data from external APIs',
    schedule_interval='0 5 * * *',  # Daily at 5 AM
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['api', 'ingestion', 'daily'],
    max_active_runs=1,
) as dag:

    def check_api_health(source_name: str, **context):
        """
        Health check for API before ingestion.
        Raises exception if API is unavailable.
        """
        from airflow.providers.http.hooks.http import HttpHook

        config = API_SOURCES[source_name]
        hook = HttpHook(http_conn_id=config['conn_id'], method='GET')

        try:
            # Most APIs have a simple health/ping endpoint
            response = hook.run(f"{config['base_endpoint']}/health", extra_options={'timeout': 30})

            if response.status_code != 200:
                logging.warning(f"{source_name} health check returned {response.status_code}")

            return True
        except Exception as e:
            logging.error(f"{source_name} API health check failed: {e}")
            raise

    def fetch_api_data(source_name: str, endpoint_config: dict, **context):
        """
        Fetch data from API with pagination and rate limiting.
        Handles incremental extraction based on execution date.
        """
        from airflow.providers.http.hooks.http import HttpHook

        config = API_SOURCES[source_name]
        hook = HttpHook(http_conn_id=config['conn_id'], method='GET')

        execution_date = context['ds']
        next_date = context['next_ds']

        all_records = []
        pagination_cursor = None
        page_count = 0
        max_pages = 1000  # Safety limit

        # Rate limiting setup
        rate_limit = config['rate_limit']['requests_per_second']
        min_interval = 1.0 / rate_limit
        last_request_time = 0

        pagination_config = config['pagination']
        endpoint_path = endpoint_config['path']
        date_field = endpoint_config.get('date_field', 'created_at')

        logging.info(f"Fetching {source_name}/{endpoint_config['name']} for {execution_date}")

        while page_count < max_pages:
            # Rate limiting
            elapsed = time.time() - last_request_time
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)

            # Build request parameters
            params = {
                'limit': 100,
                f'{date_field}[gte]': execution_date,
                f'{date_field}[lt]': next_date,
            }

            if pagination_cursor:
                params[pagination_config['param']] = pagination_cursor

            # Make request
            last_request_time = time.time()

            try:
                response = hook.run(
                    f"{config['base_endpoint']}{endpoint_path}",
                    data=params,
                    extra_options={'timeout': 60}
                )

                response_data = response.json()

            except Exception as e:
                logging.error(f"API request failed: {e}")
                raise

            # Extract records
            response_key = pagination_config['response_key']
            records = response_data.get(response_key, [])
            all_records.extend(records)

            logging.info(f"Page {page_count + 1}: fetched {len(records)} records")

            # Check for more pages
            if pagination_config['type'] == 'cursor':
                if records:
                    pagination_cursor = records[-1].get('id')
                    has_more = response_data.get('has_more', False)
                else:
                    has_more = False

            elif pagination_config['type'] == 'offset':
                pagination_cursor = response_data.get('paging', {}).get('next', {}).get('after')
                has_more = pagination_cursor is not None

            elif pagination_config['type'] == 'token':
                pagination_cursor = response_data.get('nextPageToken')
                has_more = pagination_cursor is not None

            page_count += 1

            if not has_more or not records:
                break

        logging.info(f"Total records fetched: {len(all_records)}")

        # Save to staging location
        output_path = f"/tmp/{source_name}_{endpoint_config['name']}_{execution_date}.json"
        with open(output_path, 'w') as f:
            json.dump(all_records, f)

        context['ti'].xcom_push(key='record_count', value=len(all_records))
        context['ti'].xcom_push(key='output_path', value=output_path)

        return output_path

    def transform_api_data(source_name: str, endpoint_config: dict, **context):
        """
        Transform raw API data:
        - Flatten nested structures
        - Standardize field names
        - Apply business logic transformations
        - Add metadata
        """
        ti = context['ti']
        task_id = f"ingest_{source_name}.fetch_{endpoint_config['name']}"
        input_path = ti.xcom_pull(task_ids=task_id, key='output_path')

        if not input_path:
            raise AirflowSkipException("No data to transform")

        with open(input_path, 'r') as f:
            records = json.load(f)

        if not records:
            raise AirflowSkipException("Empty dataset, skipping transform")

        transformed = []

        for record in records:
            # Flatten nested objects
            flat_record = flatten_dict(record)

            # Standardize timestamps to ISO format
            for key, value in flat_record.items():
                if 'date' in key.lower() or 'time' in key.lower() or key in ['created', 'updated']:
                    if isinstance(value, (int, float)):
                        # Unix timestamp
                        flat_record[key] = datetime.fromtimestamp(value).isoformat()

            # Add ingestion metadata
            flat_record['_source'] = source_name
            flat_record['_endpoint'] = endpoint_config['name']
            flat_record['_ingested_at'] = datetime.now().isoformat()
            flat_record['_execution_date'] = context['ds']

            transformed.append(flat_record)

        output_path = f"/tmp/{source_name}_{endpoint_config['name']}_{context['ds']}_transformed.json"
        with open(output_path, 'w') as f:
            json.dump(transformed, f)

        logging.info(f"Transformed {len(transformed)} records")

        return output_path

    def flatten_dict(d, parent_key='', sep='_'):
        """Flatten nested dictionary."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                items.append((new_key, json.dumps(v)))
            else:
                items.append((new_key, v))
        return dict(items)

    def load_to_warehouse(source_name: str, endpoint_config: dict, **context):
        """
        Load transformed data to warehouse.
        Uses MERGE for idempotent upserts.
        """
        from airflow.providers.postgres.hooks.postgres import PostgresHook

        ti = context['ti']
        task_id = f"ingest_{source_name}.transform_{endpoint_config['name']}"
        input_path = ti.xcom_pull(task_ids=task_id)

        if not input_path:
            raise AirflowSkipException("No transformed data to load")

        with open(input_path, 'r') as f:
            records = json.load(f)

        if not records:
            raise AirflowSkipException("Empty dataset, skipping load")

        hook = PostgresHook(postgres_conn_id='warehouse_postgres')

        table_name = f"raw_{source_name}.{endpoint_config['name']}"

        # Create table if not exists (auto-schema detection)
        sample_record = records[0]
        columns = list(sample_record.keys())

        # Simple load - in production use proper MERGE/UPSERT
        for record in records:
            values = [record.get(col) for col in columns]
            placeholders = ', '.join(['%s'] * len(columns))

            insert_sql = f"""
                INSERT INTO {table_name} ({', '.join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (id) DO UPDATE SET
                {', '.join(f"{col} = EXCLUDED.{col}" for col in columns if col != 'id')}
            """

            hook.run(insert_sql, parameters=values)

        logging.info(f"Loaded {len(records)} records to {table_name}")

        return len(records)

    def generate_ingestion_summary(**context):
        """
        Generate summary of all API ingestions.
        """
        ti = context['ti']
        summary = {
            'execution_date': context['ds'],
            'sources': {}
        }

        for source_name, config in API_SOURCES.items():
            source_summary = {'endpoints': {}, 'total_records': 0}

            for endpoint in config['endpoints']:
                task_id = f"ingest_{source_name}.fetch_{endpoint['name']}"
                record_count = ti.xcom_pull(task_ids=task_id, key='record_count') or 0

                source_summary['endpoints'][endpoint['name']] = record_count
                source_summary['total_records'] += record_count

            summary['sources'][source_name] = source_summary

        total_records = sum(s['total_records'] for s in summary['sources'].values())
        summary['total_records'] = total_records

        logging.info(f"Ingestion Summary: {json.dumps(summary, indent=2)}")

        return summary

    # Create task groups for each API source
    all_task_groups = []

    for source_name, config in API_SOURCES.items():
        with TaskGroup(group_id=f'ingest_{source_name}') as source_group:

            # Health check first
            health_check = PythonOperator(
                task_id='health_check',
                python_callable=check_api_health,
                op_kwargs={'source_name': source_name},
            )

            endpoint_tasks = []

            for endpoint in config['endpoints']:
                # Fetch
                fetch = PythonOperator(
                    task_id=f"fetch_{endpoint['name']}",
                    python_callable=fetch_api_data,
                    op_kwargs={
                        'source_name': source_name,
                        'endpoint_config': endpoint,
                    },
                )

                # Transform
                transform = PythonOperator(
                    task_id=f"transform_{endpoint['name']}",
                    python_callable=transform_api_data,
                    op_kwargs={
                        'source_name': source_name,
                        'endpoint_config': endpoint,
                    },
                )

                # Load
                load = PythonOperator(
                    task_id=f"load_{endpoint['name']}",
                    python_callable=load_to_warehouse,
                    op_kwargs={
                        'source_name': source_name,
                        'endpoint_config': endpoint,
                    },
                )

                health_check >> fetch >> transform >> load
                endpoint_tasks.append(load)

        all_task_groups.append(source_group)

    # Summary task
    summary = PythonOperator(
        task_id='generate_summary',
        python_callable=generate_ingestion_summary,
    )

    # All source groups run in parallel, then summary
    for tg in all_task_groups:
        tg >> summary


"""
Key Concepts Demonstrated:
=========================
1. Multi-Source Ingestion: Configuration-driven for multiple APIs
2. Rate Limiting: Respect API rate limits to avoid throttling
3. Pagination Handling: Different pagination strategies (cursor, offset, token)
4. Incremental Extraction: Date-based filtering for efficient data pulls
5. Retry with Exponential Backoff: Handle transient failures gracefully
6. Data Flattening: Normalize nested API responses
7. Idempotent Loading: UPSERT pattern for safe re-runs
8. Parallel Processing: Multiple API sources fetched simultaneously
9. Health Checks: Validate API availability before extraction
10. AirflowSkipException: Gracefully skip tasks with no data
"""

