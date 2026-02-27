"""Generator for LangChain-focused TraceCore agents.

These adapters wrap a LangChain runnable chain (prompt -> LLM -> parser)
inside the TraceCore ``reset/observe/act`` contract while enforcing
DeterministicLLMShim budgets.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

from ._task_helpers import load_task_metadata


def _format_schema(schema: dict[str, list[str]]) -> str:
    parts: list[str] = []
    for name, params in sorted(schema.items()):
        if params:
            required = ", ".join(params)
            parts.append(f"  - {name}({required})")
        else:
            parts.append(f"  - {name} (no args)")
    return "\\n".join(parts)


def _build_agent_source(
    *,
    class_name: str,
    task_meta: dict,
    model: str,
    provider: str,
    default_fixture: str | None,
    max_calls: int,
    max_tokens: int,
) -> str:
    schema_literal = json.dumps(task_meta["action_schema"], indent=2, sort_keys=True)
    prompt_listing = _format_schema(task_meta["action_schema"])
    task_ref = f"{task_meta['task_id']}@{task_meta['version']}"
    prompt_template = dedent(
        f"""
        You are a LangChain-backed adapter driving TraceCore task {task_ref}.
        Task description: {task_meta['description'].strip() or 'n/a'}

        Available actions (exact names + required params):
        {prompt_listing}

        Every response MUST be a single JSON object with keys "type" and "args".
        - Use only actions listed above.
        - If you lack information, prefer observation-first actions or wait.
        - Never emit prose outside the JSON payload.
        """
    ).strip()

    default_fixture_literal = json.dumps(default_fixture) if default_fixture else "None"

    template = (
f'"""Auto-generated LangChain adapter for TraceCore.\n'
f'\n'
f'Generated via agent_bench.integrations.langchain_adapter.generate_agent.\n'
f'"""\n'
f'\n'
f'from __future__ import annotations\n'
f'\n'
f'import json\n'
f'from dataclasses import dataclass\n'
f'from typing import Any, Dict\n'
f'\n'
f'from agent_bench.integrations import BudgetViolation, DeterministicLLMShim, LLMBudget\n'
f'\n'
f'\n'
f'_ACTION_SCHEMA: dict[str, list[str]] = {schema_literal}\n'
f'_PROMPT_TEMPLATE = {json.dumps(prompt_template)}\n'
f'_DEFAULT_SHIM_FIXTURE = {default_fixture_literal}\n'
f'\n'
f'\n'
f'def _lazy_import_langchain():\n'
f'    try:\n'
f'        from langchain_core.output_parsers import JsonOutputParser\n'
f'        from langchain_core.prompts import ChatPromptTemplate\n'
f'        from langchain_core.runnables import RunnableLambda\n'
f'    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency\n'
f'        raise RuntimeError(\n'
f'            "LangChain core packages are required. Install with `pip install langchain-core`."\n'
f'        ) from exc\n'
f'    return ChatPromptTemplate, JsonOutputParser, RunnableLambda\n'
f'\n'
f'\n'
f'@dataclass\n'
f'class _ShimConfig:\n'
f'    provider: str\n'
f'    model: str\n'
f'    max_calls: int\n'
f'    max_tokens: int\n'
f'\n'
f'\n'
f'class {class_name}:\n'
f'    """TraceCore agent that funnels observations through a LangChain prompt."""\n'
f'\n'
f'    def __init__(\n'
f'        self,\n'
f'        *,\n'
f'        shim_fixture: str | None = _DEFAULT_SHIM_FIXTURE,\n'
f'        shim_responses: dict[str, str] | None = None,\n'
f'        provider: str = {provider!r},\n'
f'        model: str = {model!r},\n'
f'        max_calls: int = {max_calls},\n'
f'        max_tokens: int = {max_tokens},\n'
f'    ) -> None:\n'
f'        ChatPromptTemplate, JsonOutputParser, RunnableLambda = _lazy_import_langchain()\n'
f'        self.prompt = ChatPromptTemplate.from_template(_PROMPT_TEMPLATE)\n'
f'        self.parser = JsonOutputParser()\n'
f'        self._shim_cfg = _ShimConfig(provider=provider, model=model, max_calls=max_calls, max_tokens=max_tokens)\n'
f'        self._provider_budget = LLMBudget(max_calls=max_calls, max_tokens=max_tokens)\n'
f'        self._shim = self._build_shim(shim_fixture, shim_responses)\n'
f'        self._chain = self.prompt | RunnableLambda(self._invoke_llm) | self.parser\n'
f'        self.reset({{}})\n'
f'\n'
f'    def _build_shim(\n'
f'        self,\n'
f'        shim_fixture: str | None,\n'
f'        shim_responses: dict[str, str] | None,\n'
f'    ) -> DeterministicLLMShim | None:\n'
f'        budget = LLMBudget(max_calls=self._shim_cfg.max_calls, max_tokens=self._shim_cfg.max_tokens)\n'
f'        if shim_responses:\n'
f'            return DeterministicLLMShim(shim_responses, budget=budget, name="langchain-adapter")\n'
f'        if shim_fixture:\n'
f'            return DeterministicLLMShim.from_fixture(shim_fixture, budget=budget, name="langchain-adapter")\n'
f'        return None\n'
f'\n'
f'    def reset(self, task_spec: dict) -> None:\n'
f'        self.task_spec = task_spec or {{}}\n'
f'        self._observation = None\n'
f'        self._provider_budget.reset()\n'
f'        if self._shim:\n'
f'            self._shim.reset()\n'
f'\n'
f'    def observe(self, observation: dict) -> None:\n'
f'        self._observation = observation\n'
f'\n'
f'    def _invoke_llm(self, prompt: Dict[str, Any]) -> dict:\n'
f'        rendered = prompt["text"] if isinstance(prompt, dict) else str(prompt)\n'
f'        if self._shim:\n'
f'            completion = self._shim.complete(rendered, metadata={{"response_key": self._shim_cfg.provider}})\n'
f'        else:\n'
f'            completion = self._call_provider(rendered)\n'
f'        # JsonOutputParser expects a JSON string; coerce dicts and guard bad outputs.\n'
f'        if isinstance(completion, dict):\n'
f'            return json.dumps(completion)\n'
f'        if isinstance(completion, str):\n'
f'            try:\n'
f'                json.loads(completion)\n'
f'                return completion\n'
f'            except json.JSONDecodeError:\n'
f'                return json.dumps({{"type": "wait", "args": {{}}}})\n'
f'        return json.dumps({{"type": "wait", "args": {{}}}})\n'
f'\n'
f'    def _call_provider(self, prompt: str) -> str:\n'
f'        self._provider_budget.consume(prompt, "")  # reserve a call slot before the network round-trip\n'
f'        if self._shim_cfg.provider == "openai":\n'
f'            try:\n'
f'                from openai import OpenAI\n'
f'            except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency\n'
f'                raise RuntimeError(\n'
f'                    "Install openai>=1.0 to call OpenAI APIs or provide a deterministic shim fixture."\n'
f'                ) from exc\n'
f'            client = OpenAI()\n'
f'            response = client.responses.create(\n'
f'                model=self._shim_cfg.model,\n'
f'                input=prompt,\n'
f'                temperature=0,\n'
f'                max_output_tokens=512,\n'
f'            )\n'
f'            chunks: list[str] = []\n'
f'            for item in response.output:\n'
f'                for block in getattr(item, "content", []):\n'
f'                    if getattr(block, "text", None):\n'
f'                        chunks.append(block.text)\n'
f'            completion = "".join(chunks)\n'
f'        elif self._shim_cfg.provider == "anthropic":\n'
f'            try:\n'
f'                import anthropic\n'
f'            except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency\n'
f'                raise RuntimeError(\n'
f'                    "Install anthropic to call Anthropic APIs or provide a deterministic shim fixture."\n'
f'                ) from exc\n'
f'            client = anthropic.Anthropic()\n'
f'            response = client.messages.create(\n'
f'                model=self._shim_cfg.model,\n'
f'                messages=[{{"role": "user", "content": prompt}}],\n'
f'                max_tokens=512,\n'
f'                temperature=0,\n'
f'            )\n'
f'            completion = "".join(\n'
f'                block.text for block in response.content if getattr(block, "type", "") == "text"\n'
f'            )\n'
f'        else:\n'
f'            raise ValueError(f"Unsupported provider: {{self._shim_cfg.provider}}")\n'
f'        self._provider_budget.consume(prompt, completion)\n'
f'        return completion\n'
f'\n'
f'    def act(self) -> dict:\n'
f'        if not self._observation:\n'
f'            return {{"type": "wait", "args": {{}}}}\n'
f'        payload = {{\n'
f'            "text": self._render_prompt(self._observation),\n'
f'        }}\n'
f'        try:\n'
f'            action = self._chain.invoke(payload)\n'
f'        except BudgetViolation:\n'
f'            return {{"type": "wait", "args": {{}}}}\n'
f'        if not isinstance(action, dict) or "type" not in action:\n'
f'            return {{"type": "wait", "args": {{}}}}\n'
f'        if action["type"] not in _ACTION_SCHEMA:\n'
f'            return {{"type": "wait", "args": {{}}}}\n'
f'        return action\n'
f'\n'
f'    def _render_prompt(self, obs: dict) -> str:\n'
f'        budget = obs.get("budget_remaining", {{}})\n'
f'        return (\n'
f'            _PROMPT_TEMPLATE\n'
f'            + "\\n\\n"\n'
f'            + json.dumps({{\n'
f'                "step": obs.get("step"),\n'
f'                "last_action": obs.get("last_action"),\n'
f'                "last_action_result": obs.get("last_action_result"),\n'
f'                "visible_state": obs.get("visible_state"),\n'
f'                "budget_remaining": budget,\n'
f'            }}, ensure_ascii=False, indent=2)\n'
f'        )\n'
    )

    return template + "\n"


def generate_agent(
    task_ref: str,
    *,
    class_name: str = "LangChainDeterministicAgent",
    model: str = "gpt-4o-mini",
    provider: str = "openai",
    shim_fixture: str | None = None,
    max_calls: int | None = None,
    max_tokens: int | None = None,
    require_fixture: bool = True,
    output_path: str | Path = "agents/langchain_adapter_agent.py",
) -> Path:
    """Generate a TraceCore LangChain adapter for *task_ref* and return the file path."""

    meta = load_task_metadata(task_ref)

    if require_fixture and not shim_fixture:
        raise ValueError(
            "LangChain adapters must supply a deterministic shim fixture (set require_fixture=False "
            "to allow direct LLM calls)."
        )

    budget_defaults = meta.get("default_budget") or {}
    resolved_calls = max_calls if max_calls is not None else int(budget_defaults.get("tool_calls", 4))
    resolved_tokens = max_tokens if max_tokens is not None else 2000

    source = _build_agent_source(
        class_name=class_name,
        task_meta=meta,
        model=model,
        provider=provider,
        default_fixture=shim_fixture,
        max_calls=resolved_calls,
        max_tokens=resolved_tokens,
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["generate_agent", "_build_agent_source"]
