"""
Airflow Plugins Directory
=========================

Place custom operators, hooks, and sensors here.

Example custom operator:

```python
# plugins/operators/custom_operator.py
from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults

class CustomOperator(BaseOperator):
    @apply_defaults
    def __init__(self, my_param, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.my_param = my_param

    def execute(self, context):
        self.log.info(f"Custom operator with param: {self.my_param}")
        return "success"
```

Usage in DAG:
```python
from plugins.operators.custom_operator import CustomOperator

task = CustomOperator(
    task_id='custom_task',
    my_param='value',
)
```
"""

