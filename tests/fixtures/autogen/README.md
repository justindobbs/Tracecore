# AutoGen fixtures

This folder stores snapshot and helper fixtures for the AutoGen adapter tests.

Contents:
- `autogen_adapter_expected.py`: Golden snapshot of the generated adapter source.
- `stub_task.py`: Minimal deterministic task helpers for integration tests.

Update the golden snapshot by regenerating it with the same parameters used in
`tests/test_autogen_adapter.py::test_source_matches_golden_snapshot`.
