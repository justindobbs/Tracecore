# Task Plugin Template

Use this template when creating an external task package that plugs into Agent Bench via the `agent_bench.tasks` entry point group.

## Directory layout
```
your_task_package/
  pyproject.toml
  your_task_package/
    __init__.py
    tasks/
      my_task/
        task.toml
        setup.py
        actions.py
        validate.py
```

## Entry point registration
`pyproject.toml` excerpt:
```toml
[project.entry-points."agent_bench.tasks"]
my_task = "your_task_package.tasks.my_task:register"
```

Your `register()` function should return a list of descriptors:
```python
from pathlib import Path

def register():
    root = Path(__file__).resolve().parent / "tasks" / "my_task"
    return [
        {
            "id": "my_task",
            "suite": "custom",
            "version": 1,
            "description": "Describe the scenario",
            "deterministic": True,
            "path": str(root),
        }
    ]
```

Note: `task.toml` is the preferred manifest format. The loader still understands legacy
`task.yaml`, but new plugins should ship TOML.

Alternatively, provide a callable loader instead of `path`:
```python
def register():
    def loader():
        # import modules dynamically, return dict with setup/actions/validate
        ...
    return [
        {
            "id": "my_task",
            "suite": "custom",
            "version": 1,
            "loader": loader,
        }
    ]
```
