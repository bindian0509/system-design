"""
Example 2: ML Pipeline Orchestration
=====================================
A complete ML pipeline that:
1. Fetches training data
2. Preprocesses and validates features
3. Trains multiple model variants
4. Evaluates models and selects best
5. Deploys to production (with approval gate)
6. Monitors model performance

Use Case: Weekly retraining of a fraud detection model
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.task_group import TaskGroup
from airflow.models import Variable
import logging

default_args = {
    'owner': 'ml-engineering',
    'depends_on_past': False,
    'email': ['ml-team@company.com'],
    'email_on_failure': True,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
}

with DAG(
    dag_id='weekly_fraud_model_training',
    default_args=default_args,
    description='Weekly ML pipeline for fraud detection model',
    schedule_interval='0 2 * * 0',  # Every Sunday at 2 AM
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['ml', 'fraud', 'weekly'],
    max_active_runs=1,
) as dag:

    # ========== DATA PREPARATION STAGE ==========

    # Wait for upstream ETL to complete
    wait_for_etl = ExternalTaskSensor(
        task_id='wait_for_daily_etl',
        external_dag_id='daily_sales_etl_pipeline',
        external_task_id='cleanup_temp_files',
        timeout=3600,  # Wait up to 1 hour
        poke_interval=300,  # Check every 5 minutes
        mode='reschedule',  # Release worker while waiting
    )

    def fetch_training_data(**context):
        """
        Fetch historical transaction data for training.
        Includes both fraud and legitimate transactions.
        """
        # Simulate fetching data
        # In production: query data warehouse, apply sampling strategy

        training_config = {
            'start_date': '2023-01-01',
            'end_date': context['ds'],
            'fraud_sample_ratio': 0.1,  # Oversample fraud cases
            'total_samples': 1000000,
        }

        logging.info(f"Fetching training data with config: {training_config}")

        # Return path to training data
        output_path = f"/data/ml/fraud_training_{context['ds']}.parquet"

        context['ti'].xcom_push(key='training_rows', value=1000000)
        context['ti'].xcom_push(key='fraud_ratio', value=0.02)

        return output_path

    fetch_data = PythonOperator(
        task_id='fetch_training_data',
        python_callable=fetch_training_data,
    )

    def preprocess_features(**context):
        """
        Feature engineering pipeline:
        - Transaction velocity features
        - Amount statistics
        - Time-based features
        - Device/location features
        """
        input_path = context['ti'].xcom_pull(task_ids='fetch_training_data')

        features_created = [
            'txn_count_1h', 'txn_count_24h', 'txn_count_7d',
            'amount_zscore', 'amount_pct_vs_avg',
            'hour_of_day', 'day_of_week', 'is_weekend',
            'device_age_days', 'new_device_flag',
            'distance_from_home', 'unusual_location_flag',
        ]

        logging.info(f"Created {len(features_created)} features")

        output_path = f"/data/ml/fraud_features_{context['ds']}.parquet"

        context['ti'].xcom_push(key='feature_count', value=len(features_created))
        return output_path

    preprocess = PythonOperator(
        task_id='preprocess_features',
        python_callable=preprocess_features,
    )

    def validate_features(**context):
        """
        Validate feature distributions haven't drifted significantly.
        Compare against baseline statistics.
        """
        feature_path = context['ti'].xcom_pull(task_ids='preprocess_features')

        # Check for feature drift
        drift_checks = {
            'txn_count_1h': {'mean_shift': 0.05, 'variance_shift': 0.1},
            'amount_zscore': {'mean_shift': 0.02, 'variance_shift': 0.05},
        }

        drift_detected = False
        drift_features = []

        # Simulate drift check
        for feature, thresholds in drift_checks.items():
            # In production: compare current stats vs baseline
            pass

        if drift_detected:
            context['ti'].xcom_push(key='drift_features', value=drift_features)
            return 'alert_feature_drift'

        return 'train_models'

    validate = BranchPythonOperator(
        task_id='validate_features',
        python_callable=validate_features,
    )

    alert_drift = PythonOperator(
        task_id='alert_feature_drift',
        python_callable=lambda: logging.warning("Feature drift detected!"),
    )

    # ========== MODEL TRAINING STAGE ==========

    # Use TaskGroup to organize parallel training tasks
    with TaskGroup(group_id='train_models') as train_models_group:

        def train_model(model_type: str, **context):
            """Generic model training function."""
            feature_path = context['ti'].xcom_pull(
                task_ids='preprocess_features',
                key='return_value'
            )

            # Hyperparameters from Airflow Variables
            hyperparams = Variable.get(
                f'fraud_model_{model_type}_params',
                deserialize_json=True,
                default_var={'n_estimators': 100}
            )

            logging.info(f"Training {model_type} with params: {hyperparams}")

            # Simulate training metrics
            metrics = {
                'model_type': model_type,
                'auc_roc': 0.92 + (hash(model_type) % 10) / 100,
                'precision': 0.85 + (hash(model_type) % 10) / 100,
                'recall': 0.78 + (hash(model_type) % 10) / 100,
                'training_time_minutes': 15 + (hash(model_type) % 20),
            }

            model_path = f"/models/fraud_{model_type}_{context['ds']}.pkl"

            context['ti'].xcom_push(key=f'{model_type}_metrics', value=metrics)
            context['ti'].xcom_push(key=f'{model_type}_path', value=model_path)

            return metrics

        # Train multiple model variants in parallel
        train_xgboost = PythonOperator(
            task_id='train_xgboost',
            python_callable=train_model,
            op_kwargs={'model_type': 'xgboost'},
        )

        train_lightgbm = PythonOperator(
            task_id='train_lightgbm',
            python_callable=train_model,
            op_kwargs={'model_type': 'lightgbm'},
        )

        train_catboost = PythonOperator(
            task_id='train_catboost',
            python_callable=train_model,
            op_kwargs={'model_type': 'catboost'},
        )

        # Neural network variant
        train_nn = PythonOperator(
            task_id='train_neural_net',
            python_callable=train_model,
            op_kwargs={'model_type': 'neural_net'},
        )

    # ========== MODEL EVALUATION STAGE ==========

    def evaluate_and_select_model(**context):
        """
        Compare all trained models and select the best one.
        Uses multiple metrics with business-weighted scoring.
        """
        ti = context['ti']

        model_types = ['xgboost', 'lightgbm', 'catboost', 'neural_net']
        all_metrics = {}

        for model_type in model_types:
            metrics = ti.xcom_pull(
                task_ids=f'train_models.train_{model_type}',
                key=f'{model_type}_metrics'
            )
            # Handle None case in simulation
            if metrics is None:
                metrics = {
                    'model_type': model_type,
                    'auc_roc': 0.92,
                    'precision': 0.85,
                    'recall': 0.78,
                }
            all_metrics[model_type] = metrics

        # Calculate composite score (business-weighted)
        # For fraud: recall is very important (catch fraud)
        # Precision matters too (avoid false positives)
        weights = {'auc_roc': 0.3, 'precision': 0.3, 'recall': 0.4}

        best_model = None
        best_score = 0

        for model_type, metrics in all_metrics.items():
            score = sum(
                metrics.get(metric, 0) * weight
                for metric, weight in weights.items()
            )
            logging.info(f"{model_type}: composite_score={score:.4f}")

            if score > best_score:
                best_score = score
                best_model = model_type

        logging.info(f"Selected model: {best_model} with score {best_score:.4f}")

        # Get model path - in simulation just construct it
        model_path = f"/models/fraud_{best_model}_{context['ds']}.pkl"

        ti.xcom_push(key='best_model', value=best_model)
        ti.xcom_push(key='best_model_path', value=model_path)
        ti.xcom_push(key='best_score', value=best_score)

        return best_model

    evaluate_models = PythonOperator(
        task_id='evaluate_and_select_model',
        python_callable=evaluate_and_select_model,
    )

    def check_model_quality(**context):
        """
        Gate: Check if model meets minimum quality bar.
        """
        ti = context['ti']
        best_score = ti.xcom_pull(task_ids='evaluate_and_select_model', key='best_score')

        # In simulation, set a default
        if best_score is None:
            best_score = 0.87

        min_score = float(Variable.get('fraud_model_min_score', default_var='0.85'))

        if best_score >= min_score:
            logging.info(f"Model quality check passed: {best_score} >= {min_score}")
            return 'deploy_model'
        else:
            logging.warning(f"Model below quality bar: {best_score} < {min_score}")
            return 'skip_deployment'

    quality_gate = BranchPythonOperator(
        task_id='check_model_quality',
        python_callable=check_model_quality,
    )

    skip_deploy = EmptyOperator(
        task_id='skip_deployment',
    )

    # ========== DEPLOYMENT STAGE ==========

    with TaskGroup(group_id='deploy_model') as deploy_model_group:

        def deploy_to_staging(**context):
            """Deploy model to staging environment."""
            model_path = context['ti'].xcom_pull(
                task_ids='evaluate_and_select_model',
                key='best_model_path'
            )

            logging.info(f"Deploying {model_path} to staging")

            # Simulate: upload to model registry, update staging endpoint
            staging_endpoint = "https://staging.ml.company.com/fraud/v2"

            return staging_endpoint

        def run_shadow_test(**context):
            """
            Run shadow test: compare new model predictions
            against current production model.
            """
            shadow_results = {
                'agreement_rate': 0.94,
                'new_model_better_count': 1250,
                'new_model_worse_count': 320,
                'inconclusive': 430,
            }

            logging.info(f"Shadow test results: {shadow_results}")
            return shadow_results

        def deploy_to_production(**context):
            """
            Deploy to production with canary rollout.
            """
            model_path = context['ti'].xcom_pull(
                task_ids='evaluate_and_select_model',
                key='best_model_path'
            )

            rollout_config = {
                'canary_percentage': 10,
                'ramp_up_hours': 24,
                'rollback_on_error_rate': 0.05,
            }

            logging.info(f"Deploying to production: {model_path}")
            logging.info(f"Rollout config: {rollout_config}")

            production_version = f"fraud-model-{context['ds']}"
            return production_version

        staging = PythonOperator(
            task_id='deploy_staging',
            python_callable=deploy_to_staging,
        )

        shadow = PythonOperator(
            task_id='shadow_test',
            python_callable=run_shadow_test,
        )

        production = PythonOperator(
            task_id='deploy_production',
            python_callable=deploy_to_production,
        )

        staging >> shadow >> production

    # ========== POST-DEPLOYMENT MONITORING ==========

    def setup_monitoring(**context):
        """
        Configure monitoring dashboards and alerts for new model.
        """
        new_version = context['ti'].xcom_pull(
            task_ids='deploy_model.deploy_production'
        )

        monitoring_config = {
            'model_version': new_version or f"fraud-model-{context['ds']}",
            'metrics': ['precision', 'recall', 'latency_p99', 'throughput'],
            'alert_thresholds': {
                'precision_drop': 0.05,
                'recall_drop': 0.05,
                'latency_p99_ms': 50,
            },
            'dashboard_url': f"https://grafana.company.com/d/fraud-model?version={new_version}",
        }

        logging.info(f"Monitoring configured: {monitoring_config}")
        return monitoring_config

    setup_monitoring_task = PythonOperator(
        task_id='setup_monitoring',
        python_callable=setup_monitoring,
        trigger_rule='none_failed_min_one_success',
    )

    # ========== DEFINE DEPENDENCIES ==========

    # Data preparation flow
    wait_for_etl >> fetch_data >> preprocess >> validate

    # Branch from validation
    validate >> [alert_drift, train_models_group]

    # Evaluation flow
    train_models_group >> evaluate_models >> quality_gate

    # Deployment branch
    quality_gate >> [skip_deploy, deploy_model_group]

    # Monitoring for all paths
    [skip_deploy, deploy_model_group] >> setup_monitoring_task


"""
Key Concepts Demonstrated:
=========================
1. ExternalTaskSensor: Wait for upstream DAG completion
2. TaskGroup: Organize related tasks (training, deployment)
3. Parallel Training: Multiple models trained simultaneously
4. Variables: Store configuration outside code
5. Quality Gates: BranchPythonOperator for conditional deployment
6. Shadow Testing: Safe deployment pattern
7. Canary Deployment: Gradual production rollout
8. Comprehensive Monitoring: Post-deployment observability
"""

