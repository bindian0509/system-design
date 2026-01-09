# Apache Airflow - Complete Guide with Practical Examples

## What is Apache Airflow?

Apache Airflow is an **open-source workflow orchestration platform** that allows you to programmatically author, schedule, and monitor workflows. It was created at Airbnb in 2014 and became an Apache Top-Level Project in 2019.

### Core Philosophy: "Workflows as Code"

Unlike GUI-based tools, Airflow treats workflows as Python code, enabling:
- Version control for pipelines
- Code reviews for workflow changes
- Testing of workflow logic
- Reusability through templates

---

## Core Concepts

### 1. DAG (Directed Acyclic Graph)
A DAG is a collection of tasks with defined dependencies. "Acyclic" means no circular dependencies.

```
Task A → Task B → Task C
           ↘
             Task D
```

### 2. Tasks
Individual units of work. Each task is an instance of an Operator.

### 3. Operators
Templates for predefined tasks:
- **BashOperator**: Execute bash commands
- **PythonOperator**: Execute Python functions
- **EmailOperator**: Send emails
- **SQLOperator**: Execute SQL queries
- **HttpOperator**: Make HTTP requests
- **Sensors**: Wait for conditions to be met

### 4. XComs
Cross-communication mechanism for tasks to share small pieces of data.

### 5. Hooks
Interfaces to external systems (databases, APIs, cloud services).

### 6. Connections
Stored credentials and connection info for external systems.

### 7. Variables
Global key-value store for configuration.

---

## Important Use Cases

### 🔄 1. ETL/ELT Pipelines
Extract data from sources, transform it, and load to destinations.

### 📊 2. Data Warehouse Population
Schedule regular data loads from operational databases to analytics warehouses.

### 🤖 3. ML Pipeline Orchestration
Coordinate training, validation, and deployment of ML models.

### 📧 4. Report Generation & Distribution
Generate and email periodic business reports.

### 🔍 5. Data Quality Monitoring
Run validation checks and alert on data anomalies.

### ☁️ 6. Cloud Infrastructure Automation
Trigger cloud jobs (EMR, Dataflow, BigQuery).

### 🔗 7. API Data Ingestion
Pull data from external APIs on schedules.

### 🗃️ 8. Database Maintenance
Run periodic cleanup, archival, and optimization tasks.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        AIRFLOW ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│   │   Web Server │     │   Scheduler  │     │   Workers    │   │
│   │   (Flask)    │     │              │     │  (Celery/K8s)│   │
│   └──────┬───────┘     └──────┬───────┘     └──────┬───────┘   │
│          │                    │                     │           │
│          │                    │                     │           │
│          └────────────────────┼─────────────────────┘           │
│                               │                                  │
│                    ┌──────────┴──────────┐                      │
│                    │   Metadata Database │                      │
│                    │   (PostgreSQL)      │                      │
│                    └─────────────────────┘                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Using Docker (Recommended)

```bash
cd apache-airflow

# Start local Airflow with Docker
docker-compose up -d

# Access UI at http://localhost:8080
# Login: admin / admin
```

This starts:
- **Webserver**: UI at port 8080
- **Scheduler**: Runs DAGs on schedule
- **Triggerer**: Handles deferrable operators
- **PostgreSQL**: Metadata database

### Useful Commands

```bash
# View logs
docker-compose logs -f airflow-scheduler

# Stop Airflow
docker-compose down

# Stop and remove volumes (fresh start)
docker-compose down -v

# Run Airflow CLI commands
docker-compose exec airflow-webserver airflow dags list
docker-compose exec airflow-webserver airflow tasks list daily_sales_etl_pipeline
```

### Manual Installation (Alternative)

```bash
# Create virtual environment
python -m venv airflow_venv
source airflow_venv/bin/activate

# Install Airflow (check https://airflow.apache.org for latest constraint file)
AIRFLOW_VERSION=2.8.1
PYTHON_VERSION="$(python --version | cut -d " " -f 2 | cut -d "." -f 1-2)"
CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"
pip install "apache-airflow==${AIRFLOW_VERSION}" --constraint "${CONSTRAINT_URL}"

# Initialize database
airflow db init

# Create admin user
airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin

# Start scheduler (in one terminal)
airflow scheduler

# Start webserver (in another terminal)
airflow webserver --port 8080
```

---

## Project Structure

```
apache-airflow/
├── README.md                    # This file
├── dags/                        # DAG definitions
│   ├── example_etl_pipeline.py
│   ├── example_ml_pipeline.py
│   ├── example_data_quality.py
│   ├── example_api_ingestion.py
│   └── example_report_generation.py
├── plugins/                     # Custom operators, hooks, sensors
├── tests/                       # DAG tests
└── docker-compose.yml           # Local development setup
```

---

## Best Practices

1. **Idempotency**: Tasks should produce the same result if run multiple times
2. **Atomicity**: Tasks should be all-or-nothing
3. **No Side Effects in DAG Definition**: DAG parsing should be fast
4. **Use Variables/Connections**: Don't hardcode credentials
5. **Small Tasks**: Break complex logic into smaller, testable tasks
6. **Proper Retries**: Configure retry policies appropriately
7. **SLAs**: Set SLAs for critical pipelines
8. **Testing**: Test DAGs and tasks before deployment

---

## See Example DAGs

Check the `dags/` folder for practical examples covering:
- ETL pipelines
- ML workflows
- Data quality checks
- API data ingestion
- Report generation

