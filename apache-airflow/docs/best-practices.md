# Apache Airflow Best Practices

## Table of Contents
1. [DAG Design Principles](#dag-design-principles)
2. [Task Design](#task-design)
3. [Error Handling & Retries](#error-handling--retries)
4. [Performance Optimization](#performance-optimization)
5. [Testing](#testing)
6. [Monitoring & Alerting](#monitoring--alerting)
7. [Security](#security)
8. [Common Anti-Patterns](#common-anti-patterns)

---

## DAG Design Principles

### 1. Keep DAG Definition Files Light

DAG files are parsed frequently. Avoid heavy operations at module level.

```python
# ❌ BAD: Heavy operations at module level
import pandas as pd
df = pd.read_csv('/huge/file.csv')  # Runs on every parse!

with DAG(...) as dag:
    task = PythonOperator(...)

# ✅ GOOD: Heavy operations inside task functions
def process_data():
    import pandas as pd  # Import inside function
    df = pd.read_csv('/huge/file.csv')
    return df.shape[0]

with DAG(...) as dag:
    task = PythonOperator(
        task_id='process',
        python_callable=process_data,
    )
```

### 2. Avoid Top-Level Code That Queries External Systems

```python
# ❌ BAD: Database query at module level
from mydb import get_table_list
tables = get_table_list()  # Network call on every parse!

for table in tables:
    task = PythonOperator(...)

# ✅ GOOD: Use Variables or static configuration
from airflow.models import Variable

# Option 1: Configuration in Variable
# tables = Variable.get('etl_tables', deserialize_json=True)

# Option 2: Static config file
TABLES = ['users', 'orders', 'products']  # Or load from local config

for table in TABLES:
    task = PythonOperator(...)
```

### 3. Use Meaningful DAG and Task IDs

```python
# ❌ BAD: Vague names
with DAG(dag_id='dag1') as dag:
    t1 = PythonOperator(task_id='task1', ...)
    t2 = PythonOperator(task_id='task2', ...)

# ✅ GOOD: Descriptive names
with DAG(dag_id='daily_sales_etl_warehouse') as dag:
    extract_orders = PythonOperator(task_id='extract_orders_from_postgres', ...)
    transform_orders = PythonOperator(task_id='transform_orders_apply_discounts', ...)
```

### 4. Set Appropriate DAG Parameters

```python
with DAG(
    dag_id='production_etl',

    # Prevent backfill storms
    catchup=False,

    # Limit concurrent runs
    max_active_runs=1,

    # Allow manual triggers
    schedule_interval='@daily',

    # Set timeout for entire DAG
    dagrun_timeout=timedelta(hours=6),

    # Organize in UI
    tags=['production', 'etl', 'sales'],

    # Documentation
    doc_md="""
    ## Daily Sales ETL
    Processes yesterday's sales data and loads to warehouse.

    **Owner:** data-team@company.com
    **SLA:** 6 hours
    """,

    default_args={
        'owner': 'data-engineering',
        'retries': 3,
        'retry_delay': timedelta(minutes=5),
        'email': ['alerts@company.com'],
        'email_on_failure': True,
    },
) as dag:
    ...
```

---

## Task Design

### 1. Make Tasks Idempotent

Tasks should produce the same result when run multiple times with the same inputs.

```python
# ❌ BAD: Appends data (duplicates on re-run)
def load_data():
    df = get_transformed_data()
    df.to_sql('sales', engine, if_exists='append')

# ✅ GOOD: Upsert or delete-then-insert
def load_data(**context):
    execution_date = context['ds']

    # Delete existing data for this date first
    engine.execute(f"DELETE FROM sales WHERE date = '{execution_date}'")

    # Then insert
    df = get_transformed_data()
    df.to_sql('sales', engine, if_exists='append')
```

### 2. Make Tasks Atomic

Each task should be a complete unit of work that either fully succeeds or fails.

```python
# ❌ BAD: Partial state on failure
def process_all_files():
    for file in files:
        process(file)  # If 5th file fails, 4 are processed

# ✅ GOOD: Transaction-like behavior
def process_all_files():
    results = []
    for file in files:
        results.append(process(file))

    # Only commit if all succeed
    save_all_results(results)
```

### 3. Keep Tasks Small and Focused

```python
# ❌ BAD: Monolithic task
def do_everything():
    data = extract_from_db()
    transformed = apply_transformations(data)
    validated = validate_data(transformed)
    load_to_warehouse(validated)
    send_notification()

# ✅ GOOD: Separate tasks with clear responsibilities
extract_task >> transform_task >> validate_task >> load_task >> notify_task
```

### 4. Use Appropriate Task Timeouts

```python
PythonOperator(
    task_id='api_call',
    python_callable=call_external_api,
    execution_timeout=timedelta(minutes=30),  # Kill if takes > 30 min
)
```

---

## Error Handling & Retries

### 1. Configure Retries Appropriately

```python
default_args = {
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'retry_exponential_backoff': True,  # 5, 10, 20 minutes
    'max_retry_delay': timedelta(minutes=60),
}

# Task-specific retry for flaky API
api_task = PythonOperator(
    task_id='call_api',
    python_callable=call_flaky_api,
    retries=5,
    retry_delay=timedelta(seconds=30),
)
```

### 2. Use Callbacks for Custom Error Handling

```python
def task_failure_callback(context):
    """Called when task fails."""
    task_instance = context['task_instance']
    exception = context['exception']

    # Log to external system
    log_to_datadog({
        'dag_id': context['dag'].dag_id,
        'task_id': task_instance.task_id,
        'execution_date': str(context['execution_date']),
        'error': str(exception),
    })

    # Send Slack alert
    send_slack_alert(f"Task {task_instance.task_id} failed: {exception}")

def task_success_callback(context):
    """Called when task succeeds."""
    pass

def sla_miss_callback(dag, task_list, blocking_task_list, slas, blocking_tis):
    """Called when SLA is missed."""
    send_pagerduty_alert("SLA breach detected")

with DAG(
    dag_id='monitored_dag',
    on_failure_callback=dag_failure_callback,  # DAG level
    sla_miss_callback=sla_miss_callback,
    ...
) as dag:

    task = PythonOperator(
        task_id='critical_task',
        on_failure_callback=task_failure_callback,  # Task level
        on_success_callback=task_success_callback,
        sla=timedelta(hours=2),  # Must complete within 2 hours
        ...
    )
```

### 3. Use Trigger Rules for Cleanup Tasks

```python
from airflow.utils.trigger_rule import TriggerRule

# Always run cleanup, even if upstream fails
cleanup = PythonOperator(
    task_id='cleanup_temp_files',
    python_callable=cleanup_function,
    trigger_rule=TriggerRule.ALL_DONE,  # Run regardless of upstream state
)

# Alert only if something failed
alert = EmailOperator(
    task_id='send_failure_alert',
    trigger_rule=TriggerRule.ONE_FAILED,  # Only if at least one upstream failed
    ...
)
```

---

## Performance Optimization

### 1. Use Pools to Limit Concurrency

```python
# Limit connections to a resource
task = PostgresOperator(
    task_id='query_db',
    pool='postgres_pool',  # Max 5 concurrent queries (configured in UI)
    ...
)
```

Set up pools in UI: Admin → Pools → Create
- Name: `postgres_pool`
- Slots: 5

### 2. Optimize Sensor Performance

```python
# ❌ BAD: Holds worker slot while waiting
sensor = FileSensor(
    task_id='wait_for_file',
    mode='poke',           # Keeps worker occupied
    poke_interval=60,      # Checks every minute
    timeout=3600,
)

# ✅ GOOD: Releases worker between checks
sensor = FileSensor(
    task_id='wait_for_file',
    mode='reschedule',     # Frees worker between pokes
    poke_interval=300,     # Check every 5 minutes (less frequent OK)
    timeout=3600,
)
```

### 3. Use TaskFlow API for Better XCom Performance

```python
from airflow.decorators import dag, task

@dag(...)
def optimized_dag():

    @task
    def extract():
        return {"data": fetch_data()}

    @task
    def transform(data):
        return process(data)

    @task
    def load(data):
        save(data)

    # TaskFlow automatically handles XCom
    load(transform(extract()))
```

### 4. Parallelize Independent Tasks

```python
# ❌ BAD: Sequential when not needed
extract_users >> extract_orders >> extract_products >> transform

# ✅ GOOD: Parallel extraction
[extract_users, extract_orders, extract_products] >> transform
```

---

## Testing

### 1. Unit Test Task Functions

```python
# tests/test_tasks.py
import pytest
from dags.etl_dag import transform_data

def test_transform_data():
    input_data = {"value": 10}
    result = transform_data(input_data)
    assert result["value"] == 20

def test_transform_handles_null():
    input_data = {"value": None}
    result = transform_data(input_data)
    assert result["value"] == 0
```

### 2. Validate DAG Structure

```python
# tests/test_dags.py
import pytest
from airflow.models import DagBag

@pytest.fixture
def dagbag():
    return DagBag(dag_folder='dags/', include_examples=False)

def test_no_import_errors(dagbag):
    """Ensure DAGs have no import errors."""
    assert len(dagbag.import_errors) == 0, f"Import errors: {dagbag.import_errors}"

def test_dag_loaded(dagbag):
    """Ensure expected DAGs are loaded."""
    expected_dags = ['daily_etl', 'weekly_report']
    for dag_id in expected_dags:
        assert dag_id in dagbag.dags, f"DAG {dag_id} not found"

def test_dag_has_tags(dagbag):
    """Ensure all DAGs have tags for organization."""
    for dag_id, dag in dagbag.dags.items():
        assert dag.tags, f"DAG {dag_id} has no tags"

def test_dag_has_owner(dagbag):
    """Ensure all tasks have owners."""
    for dag_id, dag in dagbag.dags.items():
        for task in dag.tasks:
            assert task.owner != 'airflow', f"Task {task.task_id} has default owner"
```

### 3. Test DAG Integrity

```python
def test_dag_task_count(dagbag):
    """Verify expected task count."""
    dag = dagbag.get_dag('daily_etl')
    assert len(dag.tasks) == 5

def test_dag_dependencies(dagbag):
    """Verify task dependencies."""
    dag = dagbag.get_dag('daily_etl')

    extract = dag.get_task('extract')
    transform = dag.get_task('transform')

    # Check transform depends on extract
    assert extract.task_id in [t.task_id for t in transform.upstream_list]
```

---

## Monitoring & Alerting

### 1. Set Up SLAs

```python
from datetime import timedelta

critical_task = PythonOperator(
    task_id='critical_processing',
    sla=timedelta(hours=2),  # Must complete within 2 hours of scheduled time
    ...
)

# Handle SLA misses
def sla_miss_callback(dag, task_list, blocking_task_list, slas, blocking_tis):
    send_pagerduty_alert(
        f"SLA missed for DAG {dag.dag_id}. "
        f"Tasks: {[t.task_id for t in task_list]}"
    )

with DAG(
    dag_id='critical_dag',
    sla_miss_callback=sla_miss_callback,
    ...
) as dag:
    ...
```

### 2. Export Metrics to Monitoring Systems

```python
# airflow.cfg
[metrics]
statsd_on = True
statsd_host = statsd.monitoring.svc
statsd_port = 8125
statsd_prefix = airflow
```

### 3. Use Structured Logging

```python
import logging

def my_task(**context):
    logger = logging.getLogger(__name__)

    # Include context in logs
    logger.info(
        "Processing started",
        extra={
            'dag_id': context['dag'].dag_id,
            'task_id': context['task'].task_id,
            'execution_date': str(context['execution_date']),
        }
    )
```

---

## Security

### 1. Use Connections for Secrets

```python
# ❌ BAD: Hardcoded credentials
hook = PostgresHook(
    host='db.example.com',
    login='admin',
    password='secret123',  # Never do this!
)

# ✅ GOOD: Use connections
hook = PostgresHook(postgres_conn_id='production_db')
```

### 2. Use Secrets Backend

```python
# airflow.cfg - Use AWS Secrets Manager
[secrets]
backend = airflow.providers.amazon.aws.secrets.secrets_manager.SecretsManagerBackend
backend_kwargs = {"connections_prefix": "airflow/connections", "variables_prefix": "airflow/variables"}
```

### 3. Limit UI Access with RBAC

```python
# airflow.cfg
[webserver]
rbac = True
authenticate = True
```

---

## Common Anti-Patterns

### ❌ Anti-Pattern 1: Using Tasks for Control Flow

```python
# BAD: Task just to check a condition
check_task = PythonOperator(
    task_id='check_if_weekend',
    python_callable=lambda: datetime.now().weekday() >= 5,
)

# GOOD: Use ShortCircuitOperator or BranchPythonOperator
from airflow.operators.python import ShortCircuitOperator

skip_weekend = ShortCircuitOperator(
    task_id='skip_if_weekend',
    python_callable=lambda: datetime.now().weekday() < 5,
)
```

### ❌ Anti-Pattern 2: Passing Large Data via XCom

```python
# BAD: XCom with large data
def extract():
    df = pd.read_csv('huge_file.csv')  # 1GB file
    return df.to_dict()  # Stored in metadata DB!

# GOOD: Pass file references
def extract():
    df = pd.read_csv('huge_file.csv')
    path = '/tmp/extracted_data.parquet'
    df.to_parquet(path)
    return path  # Just the path
```

### ❌ Anti-Pattern 3: Dynamic Task Generation Based on Runtime Data

```python
# BAD: Number of tasks varies per run
def get_files():
    return s3_hook.list_keys(bucket='data', prefix='input/')

files = get_files()  # Called at parse time - may timeout or vary

for f in files:
    task = PythonOperator(task_id=f, ...)

# GOOD: Use expand() for dynamic task mapping (Airflow 2.3+)
@task
def process_file(file_path: str):
    ...

@task
def list_files():
    return s3_hook.list_keys(bucket='data', prefix='input/')

# Dynamic task expansion
process_file.expand(file_path=list_files())
```

### ❌ Anti-Pattern 4: Not Setting Timeouts

```python
# BAD: No timeout - task can hang forever
task = PythonOperator(
    task_id='call_api',
    python_callable=call_slow_api,
)

# GOOD: Always set execution timeout
task = PythonOperator(
    task_id='call_api',
    python_callable=call_slow_api,
    execution_timeout=timedelta(minutes=30),
)
```

### ❌ Anti-Pattern 5: Catching All Exceptions

```python
# BAD: Swallows all errors, task appears to succeed
def risky_task():
    try:
        do_something_risky()
    except Exception:
        pass  # Silent failure!

# GOOD: Let Airflow handle failures, or re-raise
def risky_task():
    try:
        do_something_risky()
    except ConnectionError:
        logging.warning("Connection failed, will retry")
        raise  # Let Airflow retry
    except ValidationError as e:
        logging.error(f"Validation failed: {e}")
        raise AirflowFailException(f"Invalid data: {e}")
```

---

## Checklist for Production DAGs

- [ ] `catchup=False` set (unless backfill needed)
- [ ] `max_active_runs` set to prevent resource exhaustion
- [ ] All tasks have meaningful names
- [ ] All tasks have owners set
- [ ] Retries configured appropriately
- [ ] Timeouts set on long-running tasks
- [ ] SLAs defined for critical tasks
- [ ] Failure callbacks configured
- [ ] Tasks are idempotent
- [ ] No hardcoded credentials
- [ ] Pools used for limited resources
- [ ] Tags added for organization
- [ ] Documentation added (`doc_md`)
- [ ] Unit tests written
- [ ] DAG validation tests pass

