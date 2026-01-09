# Apache Airflow Core Concepts Deep Dive

## Table of Contents
1. [DAGs - The Building Blocks](#dags---the-building-blocks)
2. [Operators - Task Templates](#operators---task-templates)
3. [Sensors - Waiting for Conditions](#sensors---waiting-for-conditions)
4. [XCom - Cross-Task Communication](#xcom---cross-task-communication)
5. [Variables & Connections](#variables--connections)
6. [Hooks - External System Interfaces](#hooks---external-system-interfaces)
7. [Task Dependencies](#task-dependencies)
8. [Scheduling Deep Dive](#scheduling-deep-dive)
9. [Executors](#executors)

---

## DAGs - The Building Blocks

### What is a DAG?
A **Directed Acyclic Graph (DAG)** is a collection of tasks organized in a way that reflects their relationships and dependencies.

- **Directed**: Tasks flow in one direction
- **Acyclic**: No circular dependencies (Task A → Task B → Task A is NOT allowed)
- **Graph**: Collection of nodes (tasks) and edges (dependencies)

### DAG Definition Styles

```python
# Style 1: Context Manager (Recommended)
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

with DAG(
    dag_id='my_dag',
    start_date=datetime(2024, 1, 1),
    schedule_interval='@daily',
    catchup=False,
) as dag:

    task1 = PythonOperator(
        task_id='task1',
        python_callable=lambda: print("Hello")
    )

# Style 2: Decorator (Airflow 2.0+)
from airflow.decorators import dag, task

@dag(
    dag_id='taskflow_dag',
    start_date=datetime(2024, 1, 1),
    schedule_interval='@daily',
)
def my_taskflow_dag():

    @task
    def extract():
        return {"data": [1, 2, 3]}

    @task
    def transform(data):
        return [x * 2 for x in data["data"]]

    @task
    def load(data):
        print(f"Loading: {data}")

    # Define dependencies through function calls
    load(transform(extract()))

my_taskflow_dag()
```

### Key DAG Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `dag_id` | Unique identifier | `'daily_etl'` |
| `start_date` | When DAG becomes active | `datetime(2024, 1, 1)` |
| `schedule_interval` | How often to run | `'@daily'`, `'0 6 * * *'` |
| `catchup` | Backfill past runs | `False` |
| `max_active_runs` | Parallel DAG instances | `1` |
| `default_args` | Defaults for all tasks | `{'retries': 3}` |
| `tags` | UI organization | `['etl', 'production']` |

### Schedule Interval Presets

| Preset | Cron Equivalent | Description |
|--------|-----------------|-------------|
| `@once` | - | Run once only |
| `@hourly` | `0 * * * *` | Every hour |
| `@daily` | `0 0 * * *` | Midnight daily |
| `@weekly` | `0 0 * * 0` | Midnight Sunday |
| `@monthly` | `0 0 1 * *` | First of month |
| `@yearly` | `0 0 1 1 *` | January 1st |

---

## Operators - Task Templates

Operators define **what** a task does. Airflow provides many built-in operators.

### Core Operators

```python
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator

# Python function execution
def my_function(name, **context):
    print(f"Hello {name}!")
    return "success"

python_task = PythonOperator(
    task_id='run_python',
    python_callable=my_function,
    op_kwargs={'name': 'World'},
)

# Bash command execution
bash_task = BashOperator(
    task_id='run_bash',
    bash_command='echo "Hello World" && date',
)

# Placeholder (for grouping/dependencies)
start = EmptyOperator(task_id='start')
end = EmptyOperator(task_id='end')
```

### Database Operators

```python
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.mysql.operators.mysql import MySqlOperator

# Execute SQL
create_table = PostgresOperator(
    task_id='create_table',
    postgres_conn_id='my_postgres',
    sql="""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100)
        );
    """,
)

# Execute SQL from file
load_data = PostgresOperator(
    task_id='load_data',
    postgres_conn_id='my_postgres',
    sql='sql/load_users.sql',  # File path
)

# Templated SQL
query_data = PostgresOperator(
    task_id='query_data',
    postgres_conn_id='my_postgres',
    sql="SELECT * FROM orders WHERE order_date = '{{ ds }}'",
)
```

### Cloud Operators

```python
# AWS
from airflow.providers.amazon.aws.operators.s3 import S3CreateBucketOperator
from airflow.providers.amazon.aws.transfers.local_to_s3 import LocalFilesystemToS3Operator

# GCP
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator

# Azure
from airflow.providers.microsoft.azure.operators.wasb_delete_blob import WasbDeleteBlobOperator
```

### BranchPythonOperator - Conditional Execution

```python
from airflow.operators.python import BranchPythonOperator

def choose_branch(**context):
    value = context['ti'].xcom_pull(task_ids='previous_task')
    if value > 100:
        return 'high_value_path'
    return 'low_value_path'

branch = BranchPythonOperator(
    task_id='branch_logic',
    python_callable=choose_branch,
)

# Only one branch will execute based on return value
branch >> [high_value_task, low_value_task]
```

---

## Sensors - Waiting for Conditions

Sensors are special operators that **wait** for a condition to be true before proceeding.

### Common Sensors

```python
from airflow.sensors.filesystem import FileSensor
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.providers.http.sensors.http import HttpSensor
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor

# Wait for file to appear
wait_for_file = FileSensor(
    task_id='wait_for_file',
    filepath='/data/incoming/data.csv',
    poke_interval=60,  # Check every 60 seconds
    timeout=3600,      # Give up after 1 hour
    mode='poke',       # Keep worker slot while waiting
)

# Wait for another DAG's task to complete
wait_for_upstream = ExternalTaskSensor(
    task_id='wait_for_etl',
    external_dag_id='upstream_etl_dag',
    external_task_id='final_task',
    timeout=7200,
    mode='reschedule',  # Release worker while waiting
)

# Wait for API to be healthy
wait_for_api = HttpSensor(
    task_id='wait_for_api',
    http_conn_id='my_api',
    endpoint='/health',
    response_check=lambda response: response.json()['status'] == 'healthy',
    poke_interval=30,
    timeout=600,
)

# Wait for S3 file
wait_for_s3 = S3KeySensor(
    task_id='wait_for_s3_file',
    aws_conn_id='aws_default',
    bucket_name='my-bucket',
    bucket_key='data/{{ ds }}/file.csv',
    timeout=3600,
)
```

### Sensor Modes

| Mode | Description | Use When |
|------|-------------|----------|
| `poke` | Worker held while waiting | Short waits, resources available |
| `reschedule` | Worker released between checks | Long waits, limited workers |

---

## XCom - Cross-Task Communication

XCom (cross-communication) allows tasks to exchange small pieces of data.

### Pushing and Pulling XComs

```python
def push_data(**context):
    # Method 1: Return value (auto-pushed as 'return_value')
    return {'key': 'value', 'count': 42}

def push_explicit(**context):
    # Method 2: Explicit push with custom key
    context['ti'].xcom_push(key='my_data', value=[1, 2, 3])
    context['ti'].xcom_push(key='status', value='success')

def pull_data(**context):
    ti = context['ti']

    # Pull return value
    data = ti.xcom_pull(task_ids='push_task')

    # Pull specific key
    my_list = ti.xcom_pull(task_ids='push_explicit_task', key='my_data')

    # Pull from multiple tasks
    all_data = ti.xcom_pull(task_ids=['task1', 'task2'])

    print(f"Data: {data}, List: {my_list}")
```

### TaskFlow API (Cleaner XCom)

```python
from airflow.decorators import dag, task

@dag(dag_id='taskflow_xcom', start_date=datetime(2024, 1, 1))
def taskflow_example():

    @task
    def extract():
        return {'users': [1, 2, 3], 'orders': [100, 200]}

    @task
    def transform(data):  # Automatically receives XCom from extract
        return {
            'user_count': len(data['users']),
            'order_count': len(data['orders'])
        }

    @task
    def load(summary):  # Automatically receives XCom from transform
        print(f"Summary: {summary}")

    # Dependencies inferred from function calls
    load(transform(extract()))

taskflow_example()
```

### XCom Best Practices

⚠️ **XCom Limitations:**
- Stored in metadata database - keep data small (<48KB recommended)
- For large data: pass file paths/S3 keys instead of actual data
- Not suitable for binary data

```python
# Good: Pass file path
def extract(**context):
    df = fetch_large_data()
    path = f'/tmp/data_{context["ds"]}.parquet'
    df.to_parquet(path)
    return path  # Return path, not data

# Bad: Pass large data
def extract_bad(**context):
    df = fetch_large_data()
    return df.to_dict()  # Don't do this!
```

---

## Variables & Connections

### Variables - Global Configuration

```python
from airflow.models import Variable

# Get variable
api_key = Variable.get('my_api_key')

# Get with default
threshold = Variable.get('alert_threshold', default_var='100')

# Get JSON variable
config = Variable.get('etl_config', deserialize_json=True)

# Set variable (programmatically)
Variable.set('last_run', '2024-01-15')
```

**Setting Variables in UI:**
Admin → Variables → Create

### Connections - External System Credentials

Connections store credentials and connection info securely.

```python
from airflow.hooks.base import BaseHook

# Get connection
conn = BaseHook.get_connection('my_postgres')
print(f"Host: {conn.host}, Port: {conn.port}")

# In operators
PostgresOperator(
    task_id='query',
    postgres_conn_id='my_postgres',  # Reference by conn_id
    sql='SELECT 1',
)
```

**Setting Connections in UI:**
Admin → Connections → Create

| Field | Description | Example |
|-------|-------------|---------|
| Conn Id | Unique identifier | `my_postgres` |
| Conn Type | Type of connection | `Postgres` |
| Host | Server address | `db.example.com` |
| Schema | Database name | `analytics` |
| Login | Username | `airflow_user` |
| Password | Password | `secret123` |
| Port | Port number | `5432` |
| Extra | Additional JSON config | `{"sslmode": "require"}` |

---

## Hooks - External System Interfaces

Hooks provide interfaces to external systems. Used internally by operators.

```python
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.http.hooks.http import HttpHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook

def use_postgres_hook(**context):
    hook = PostgresHook(postgres_conn_id='my_postgres')

    # Execute query
    hook.run("INSERT INTO logs VALUES ('started')")

    # Get data as pandas DataFrame
    df = hook.get_pandas_df("SELECT * FROM users")

    # Get single record
    record = hook.get_first("SELECT COUNT(*) FROM users")

    return df.to_dict()

def use_http_hook(**context):
    hook = HttpHook(http_conn_id='my_api', method='GET')

    response = hook.run('/users', extra_options={'timeout': 30})
    return response.json()

def use_s3_hook(**context):
    hook = S3Hook(aws_conn_id='aws_default')

    # List files
    keys = hook.list_keys(bucket_name='my-bucket', prefix='data/')

    # Read file
    content = hook.read_key(key='data/file.txt', bucket_name='my-bucket')

    # Upload file
    hook.load_file(
        filename='/tmp/local.csv',
        key='data/remote.csv',
        bucket_name='my-bucket',
    )
```

---

## Task Dependencies

### Basic Dependencies

```python
# Bitshift operators (recommended)
task1 >> task2 >> task3        # task1 → task2 → task3
task1 >> [task2, task3]        # task1 → task2, task1 → task3
[task1, task2] >> task3        # task1 → task3, task2 → task3

# set_downstream/set_upstream
task1.set_downstream(task2)    # task1 → task2
task2.set_upstream(task1)      # task1 → task2
```

### Complex Dependencies

```python
from airflow.models.baseoperator import chain, cross_downstream

# Chain: Sequential execution
chain(task1, task2, task3, task4)
# task1 → task2 → task3 → task4

# Chain with lists: Parallel groups in sequence
chain(task1, [task2, task3], [task4, task5], task6)
# task1 → (task2, task3) → (task4, task5) → task6

# Cross downstream: Connect all in first list to all in second
cross_downstream([task1, task2], [task3, task4])
# task1 → task3, task1 → task4
# task2 → task3, task2 → task4
```

### Task Groups (Visual Organization)

```python
from airflow.utils.task_group import TaskGroup

with DAG(...) as dag:

    with TaskGroup(group_id='extract') as extract_group:
        extract_users = PythonOperator(task_id='users', ...)
        extract_orders = PythonOperator(task_id='orders', ...)

    with TaskGroup(group_id='transform') as transform_group:
        transform_users = PythonOperator(task_id='users', ...)
        transform_orders = PythonOperator(task_id='orders', ...)

    with TaskGroup(group_id='load') as load_group:
        load_users = PythonOperator(task_id='users', ...)
        load_orders = PythonOperator(task_id='orders', ...)

    # Dependencies between groups
    extract_group >> transform_group >> load_group
```

### Trigger Rules

Control when tasks run based on upstream task states.

```python
from airflow.utils.trigger_rule import TriggerRule

# Run only if all upstream succeed (default)
task = PythonOperator(
    task_id='on_success',
    trigger_rule=TriggerRule.ALL_SUCCESS,
    ...
)

# Run if any upstream fails
alert = EmailOperator(
    task_id='send_alert',
    trigger_rule=TriggerRule.ONE_FAILED,
    ...
)

# Always run (cleanup tasks)
cleanup = PythonOperator(
    task_id='cleanup',
    trigger_rule=TriggerRule.ALL_DONE,
    ...
)
```

| Trigger Rule | Description |
|--------------|-------------|
| `ALL_SUCCESS` | All parents succeeded (default) |
| `ALL_FAILED` | All parents failed |
| `ALL_DONE` | All parents completed (any state) |
| `ONE_SUCCESS` | At least one parent succeeded |
| `ONE_FAILED` | At least one parent failed |
| `NONE_FAILED` | No parent failed (includes skipped) |
| `NONE_SKIPPED` | No parent was skipped |

---

## Scheduling Deep Dive

### Understanding Execution Dates

```
|---------- data_interval_start
|                              |---------- data_interval_end
|                              |                             |---------- execution time
v                              v                             v
[==========DATA INTERVAL=======]                           [RUN]
2024-01-01 00:00              2024-01-02 00:00            2024-01-02 00:00
```

**Key concept:** A DAG run processes data from the **previous** interval.

```python
# For a daily DAG scheduled at midnight:
# Run at: 2024-01-02 00:00
# Processes data for: 2024-01-01

# In your task:
def my_task(**context):
    # The date of data to process
    ds = context['ds']                    # '2024-01-01'

    # Interval boundaries
    start = context['data_interval_start'] # 2024-01-01 00:00
    end = context['data_interval_end']     # 2024-01-02 00:00

    # Logical date (same as data_interval_start)
    logical_date = context['logical_date']
```

### Jinja Templating

```python
# Common template variables
templated_task = BashOperator(
    task_id='templated',
    bash_command='''
        echo "Execution date: {{ ds }}"
        echo "Previous date: {{ prev_ds }}"
        echo "Next date: {{ next_ds }}"
        echo "Run ID: {{ run_id }}"
        echo "DAG: {{ dag.dag_id }}"
        echo "Params: {{ params.my_param }}"
    ''',
    params={'my_param': 'value'},
)

# SQL templating
query_task = PostgresOperator(
    task_id='query',
    sql="""
        SELECT * FROM orders
        WHERE order_date = '{{ ds }}'
        AND region = '{{ var.value.default_region }}'
    """,
)
```

---

## Executors

Executors determine **how** tasks run.

### Executor Comparison

| Executor | Description | Use Case |
|----------|-------------|----------|
| `SequentialExecutor` | One task at a time | Development only |
| `LocalExecutor` | Parallel on single machine | Small deployments |
| `CeleryExecutor` | Distributed via Celery workers | Production, horizontal scaling |
| `KubernetesExecutor` | Each task in a K8s pod | Cloud-native, isolation |
| `CeleryKubernetesExecutor` | Hybrid of Celery + K8s | Mixed workloads |

### LocalExecutor Setup

```python
# airflow.cfg
[core]
executor = LocalExecutor
parallelism = 32  # Max parallel tasks

[database]
sql_alchemy_conn = postgresql+psycopg2://user:pass@localhost/airflow
```

### KubernetesExecutor

```python
from airflow.operators.python import PythonOperator
from kubernetes.client import models as k8s

# Custom pod configuration
task = PythonOperator(
    task_id='k8s_task',
    python_callable=heavy_computation,
    executor_config={
        "pod_override": k8s.V1Pod(
            spec=k8s.V1PodSpec(
                containers=[
                    k8s.V1Container(
                        name="base",
                        resources=k8s.V1ResourceRequirements(
                            requests={"memory": "2Gi", "cpu": "1"},
                            limits={"memory": "4Gi", "cpu": "2"},
                        ),
                    ),
                ],
            ),
        ),
    },
)
```

---

## Summary Cheat Sheet

```
DAG → Collection of tasks with dependencies
├── Operators → Define what tasks do
│   ├── PythonOperator → Run Python functions
│   ├── BashOperator → Run shell commands
│   ├── SQLOperator → Execute SQL
│   └── BranchPythonOperator → Conditional paths
│
├── Sensors → Wait for conditions
│   ├── FileSensor → Wait for files
│   ├── ExternalTaskSensor → Wait for other DAGs
│   └── HttpSensor → Wait for API health
│
├── Hooks → Interface with external systems
│   ├── PostgresHook → Database operations
│   ├── S3Hook → AWS S3 operations
│   └── HttpHook → HTTP requests
│
└── Communication
    ├── XCom → Pass data between tasks
    ├── Variables → Global key-value config
    └── Connections → Secure credentials storage
```

