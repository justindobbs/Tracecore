from __future__ import annotations

from pathlib import Path

from agent_bench.integrations.langchain_adapter import generate_agent

_GENERATED = None


def _load_generated_class():
    global _GENERATED
    if _GENERATED is not None:
        return _GENERATED
    output_path = Path(__file__).with_name("_generated_fixture_langchain_agent.py")
    fixture_path = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "langchain" / "filesystem_hidden_config.json"
    generate_agent(
        "filesystem_hidden_config@1",
        provider="openai",
        model="gpt-4o-mini",
        shim_fixture=str(fixture_path),
        require_fixture=True,
        output_path=output_path,
        max_calls=4,
        max_tokens=2048,
    )

    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("fixture_langchain_generated", output_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load generated LangChain example agent from {output_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _GENERATED = module.LangChainDeterministicAgent
    return _GENERATED


class FixtureLangChainAgent:
    def __init__(self) -> None:
        generated_cls = _load_generated_class()
        self._delegate = generated_cls(
            shim_responses=[
                '{"type": "list_dir", "args": {"path": "/app"}}',
                '{"type": "read_file", "args": {"path": "/app/.config_7311"}}',
                '{"type": "extract_value", "args": {"content": "API_KEY=correct_value", "key": "API_KEY"}}',
                '{"type": "set_output", "args": {"key": "API_KEY", "value": "correct_value"}}',
            ]
        )

    def reset(self, task_spec):
        return self._delegate.reset(task_spec)

    def observe(self, observation):
        return self._delegate.observe(observation)

    def act(self):
        return self._delegate.act()

    @property
    def llm_trace(self):
        return self._delegate.llm_trace
