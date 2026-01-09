"""
Demo DAG: Hello World Pipeline
==============================
A simple DAG to demonstrate Airflow basics.
No external dependencies required - runs out of the box!

This DAG demonstrates:
- Task dependencies
- Python operators
- Bash operators
- XCom (data passing between tasks)
- Branching
- Parallel execution
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
import random
import logging

default_args = {
    'owner': 'demo',
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

with DAG(
    dag_id='demo_hello_world',
    default_args=default_args,
    description='A simple demo DAG to learn Airflow basics',
    schedule_interval=None,  # Manual trigger only
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['demo', 'tutorial'],
) as dag:

    # Task 1: Start marker
    start = EmptyOperator(task_id='start')

    # Task 2: Print hello using Bash
    hello_bash = BashOperator(
        task_id='hello_bash',
        bash_command='echo "Hello from Bash! Today is $(date)"',
    )

    # Task 3: Python function that returns data
    def generate_random_number(**context):
        """Generate a random number and push to XCom."""
        number = random.randint(1, 100)
        logging.info(f"Generated random number: {number}")

        # This return value is automatically pushed to XCom
        return number

    generate_number = PythonOperator(
        task_id='generate_random_number',
        python_callable=generate_random_number,
    )

    # Task 4: Branch based on the random number
    def decide_branch(**context):
        """Decide which branch to take based on the number."""
        # Pull the number from the previous task
        ti = context['ti']
        number = ti.xcom_pull(task_ids='generate_random_number')

        logging.info(f"Deciding branch for number: {number}")

        if number > 50:
            return 'high_number_task'
        else:
            return 'low_number_task'

    branch = BranchPythonOperator(
        task_id='branch_on_number',
        python_callable=decide_branch,
    )

    # Task 5a: High number path
    def handle_high_number(**context):
        number = context['ti'].xcom_pull(task_ids='generate_random_number')
        message = f"🎉 HIGH number path! Got {number} which is > 50"
        logging.info(message)
        return message

    high_number_task = PythonOperator(
        task_id='high_number_task',
        python_callable=handle_high_number,
    )

    # Task 5b: Low number path
    def handle_low_number(**context):
        number = context['ti'].xcom_pull(task_ids='generate_random_number')
        message = f"📉 LOW number path! Got {number} which is <= 50"
        logging.info(message)
        return message

    low_number_task = PythonOperator(
        task_id='low_number_task',
        python_callable=handle_low_number,
    )

    # Task 6: Join both branches
    join = EmptyOperator(
        task_id='join',
        trigger_rule='none_failed_min_one_success',  # Run if at least one upstream succeeded
    )

    # Task 7: Final summary
    def print_summary(**context):
        """Print execution summary."""
        ti = context['ti']

        # Get data from XCom
        number = ti.xcom_pull(task_ids='generate_random_number')
        high_result = ti.xcom_pull(task_ids='high_number_task')
        low_result = ti.xcom_pull(task_ids='low_number_task')

        result = high_result or low_result

        summary = f"""
        ========================================
        EXECUTION SUMMARY
        ========================================
        Execution Date: {context['ds']}
        Run ID: {context['run_id']}
        Random Number: {number}
        Path Taken: {'HIGH' if number > 50 else 'LOW'}
        Result: {result}
        ========================================
        """
        logging.info(summary)
        print(summary)
        return summary

    summary = PythonOperator(
        task_id='print_summary',
        python_callable=print_summary,
    )

    # Task 8: End marker
    end = EmptyOperator(task_id='end')

    def xython(**context):
        text = "Python"
        text.lower().replace("p", "X")

        print(text)
        logging.info(text)
        return text

    # Task 9: Finally Final
    final = PythonOperator(
        task_id='finally',
        python_callable=xython)

    # Define the DAG structure
    #
    #                    ┌─── high_number_task ───┐
    #                    │                        │
    # start → hello_bash ─┬─ generate_number → branch ─┼─→ join → summary → end -> final
    #                                             │                        │
    #                                             └─── low_number_task ────┘

    start >> hello_bash >> generate_number >> branch
    branch >> high_number_task >> join
    branch >> low_number_task >> join
    join >> summary >> end >> final


"""
How to run this DAG:
====================
1. Go to http://localhost:8080
2. Find "demo_hello_world" in the DAG list
3. Toggle the switch to enable (unpause) the DAG
4. Click the play button (▶) → "Trigger DAG"
5. Watch the execution in the Graph view
6. Click on tasks to see their logs

What you'll learn:
- Task dependencies (>> operator)
- Python functions as tasks
- Bash commands as tasks
- XCom for passing data
- Branching logic
- Trigger rules
"""

