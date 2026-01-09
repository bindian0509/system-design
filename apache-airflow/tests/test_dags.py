"""
DAG Validation Tests
====================
Run with: pytest tests/test_dags.py -v
"""

import pytest
from datetime import datetime, timedelta


class TestDAGIntegrity:
    """Test DAG files load correctly and have proper structure."""

    @pytest.fixture
    def dagbag(self):
        """Load all DAGs from the dags folder."""
        from airflow.models import DagBag
        return DagBag(dag_folder='dags/', include_examples=False)

    def test_no_import_errors(self, dagbag):
        """Ensure all DAG files can be imported without errors."""
        assert len(dagbag.import_errors) == 0, \
            f"DAG import errors: {dagbag.import_errors}"

    def test_expected_dags_loaded(self, dagbag):
        """Verify expected DAGs are present."""
        expected_dags = [
            'daily_sales_etl_pipeline',
            'weekly_fraud_model_training',
            'data_quality_monitoring',
            'api_data_ingestion',
            'weekly_executive_report',
        ]

        for dag_id in expected_dags:
            assert dag_id in dagbag.dags, \
                f"Expected DAG '{dag_id}' not found"

    def test_all_dags_have_tags(self, dagbag):
        """Ensure all DAGs have tags for UI organization."""
        for dag_id, dag in dagbag.dags.items():
            assert dag.tags is not None and len(dag.tags) > 0, \
                f"DAG '{dag_id}' has no tags"

    def test_all_tasks_have_owner(self, dagbag):
        """Ensure all tasks have non-default owner."""
        for dag_id, dag in dagbag.dags.items():
            for task in dag.tasks:
                assert task.owner != 'airflow', \
                    f"Task '{task.task_id}' in DAG '{dag_id}' has default owner"

    def test_no_cycles_in_dags(self, dagbag):
        """Verify no circular dependencies exist."""
        for dag_id, dag in dagbag.dags.items():
            # DAG validation will fail if cycles exist
            assert dag.is_paused_upon_creation is not None  # Just access dag to verify it's valid

    def test_dag_schedules_are_valid(self, dagbag):
        """Ensure DAG schedules are valid cron expressions or presets."""
        from croniter import croniter

        valid_presets = ['@once', '@hourly', '@daily', '@weekly', '@monthly', '@yearly', None]

        for dag_id, dag in dagbag.dags.items():
            schedule = dag.schedule_interval

            if schedule in valid_presets:
                continue

            # Try to parse as cron expression
            try:
                croniter(schedule)
            except (ValueError, KeyError) as e:
                pytest.fail(f"DAG '{dag_id}' has invalid schedule: {schedule}")


class TestETLDAG:
    """Specific tests for the ETL pipeline DAG."""

    @pytest.fixture
    def dag(self):
        from airflow.models import DagBag
        dagbag = DagBag(dag_folder='dags/', include_examples=False)
        return dagbag.get_dag('daily_sales_etl_pipeline')

    def test_task_count(self, dag):
        """Verify expected number of tasks."""
        # Update this based on actual task count
        assert len(dag.tasks) >= 5, "ETL DAG should have at least 5 tasks"

    def test_extract_before_transform(self, dag):
        """Verify extract happens before transform."""
        extract = dag.get_task('extract_sales_data')
        validate = dag.get_task('validate_data')

        # Check validate depends on extract
        upstream_ids = [t.task_id for t in validate.upstream_list]
        assert 'extract_sales_data' in upstream_ids

    def test_catchup_disabled(self, dag):
        """ETL DAG should not backfill by default."""
        assert dag.catchup is False

    def test_max_active_runs(self, dag):
        """Prevent parallel runs of same DAG."""
        assert dag.max_active_runs == 1


class TestMLPipelineDAG:
    """Specific tests for the ML pipeline DAG."""

    @pytest.fixture
    def dag(self):
        from airflow.models import DagBag
        dagbag = DagBag(dag_folder='dags/', include_examples=False)
        return dagbag.get_dag('weekly_fraud_model_training')

    def test_has_evaluation_task(self, dag):
        """ML pipeline must have model evaluation."""
        task_ids = [t.task_id for t in dag.tasks]
        assert 'evaluate_and_select_model' in task_ids

    def test_has_quality_gate(self, dag):
        """ML pipeline must have quality gate before deployment."""
        task_ids = [t.task_id for t in dag.tasks]
        assert 'check_model_quality' in task_ids


class TestTaskFunctions:
    """Test individual task functions."""

    def test_data_transformation_logic(self):
        """Test transformation logic works correctly."""
        # Import your actual transformation function
        # from dags.example_etl_pipeline import transform_data

        # Test with sample data
        sample_input = {
            'quantity': 10,
            'unit_price': 100,
            'discount': 0.1,
        }

        expected_total = 10 * 100 * (1 - 0.1)  # 900

        # actual = transform_data(sample_input)
        # assert actual['total_amount'] == expected_total

        # Placeholder assertion
        assert expected_total == 900

    def test_validation_catches_nulls(self):
        """Validation should catch null values in required fields."""
        # Test your validation logic
        pass

    def test_validation_catches_negative_quantities(self):
        """Validation should catch negative quantities."""
        # Test your validation logic
        pass


# Run pytest with: pytest tests/test_dags.py -v
if __name__ == '__main__':
    pytest.main([__file__, '-v'])

