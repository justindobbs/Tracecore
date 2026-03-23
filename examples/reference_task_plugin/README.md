# Reference TraceCore Task Plugin

This package is the repository's reference example for publishing external TraceCore tasks through the `agent_bench.tasks` entry-point group.

## What it demonstrates

- packaging an external deterministic task as a normal Python distribution
- registering the task via `[project.entry-points."agent_bench.tasks"]`
- shipping a task directory with `task.toml`, `setup.py`, `actions.py`, and `validate.py`
- validating the task with `tracecore tasks validate` / `tracecore tasks lint`
- producing a signed build artifact in CI for distribution review

## Layout

```text
tracecore_reference_task_plugin/
  __init__.py
  tasks/
    reference_echo_task/
      task.toml
      setup.py
      actions.py
      validate.py
```

## Local workflow

```bash
pip install -e .
tracecore tasks validate --path tracecore_reference_task_plugin/tasks/reference_echo_task
tracecore tasks lint --path tracecore_reference_task_plugin/tasks/reference_echo_task
tracecore run --agent agents/toy_agent.py --task reference_echo_task@1 --seed 0 --strict-spec
```

## Signing note

The repository CI signs the built wheel and source distribution by hashing them and producing an Ed25519 signature document alongside the artifacts. This is a maintainer-facing integrity example for plugin releases; real external plugin publishers should document where signatures are stored and how operators verify them before enabling the package in CI.
