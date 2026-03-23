"""Auto-generated LangChain adapter for TraceCore.

Generated via agent_bench.integrations.langchain_adapter.generate_agent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict

from agent_bench.integrations import BudgetViolation, DeterministicLLMShim, LLMBudget
from agent_bench.telemetry import LLMCallRequest, LLMCallResponse, LLMCallTelemetry


_ACTION_SCHEMA: dict[str, list[str]] = {
  "extract_value": [
    "content",
    "key"
  ],
  "list_dir": [
    "path"
  ],
  "read_file": [
    "path"
  ],
  "set_output": [
    "key",
    "value"
  ]
}
_PROMPT_TEMPLATE = "You are a LangChain-backed adapter driving TraceCore task filesystem_hidden_config@1.\nTask description: Extract API_KEY from a constrained filesystem.\n\nAvailable actions (exact names + required params):\n  - extract_value(content, key)\\n  - list_dir(path)\\n  - read_file(path)\\n  - set_output(key, value)\n\nEvery response MUST be a single JSON object with keys \"type\" and \"args\".\n- Use only actions listed above.\n- If you lack information, prefer observation-first actions or wait.\n- Never emit prose outside the JSON payload."
_DEFAULT_SHIM_FIXTURE = "C:\\Users\\justi\\benchmark\\tests\\fixtures\\langchain\\filesystem_hidden_config.json"


def _lazy_import_langchain():
    try:
        from langchain_core.output_parsers import JsonOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.runnables import RunnableLambda
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "LangChain core packages are required. Install with `pip install langchain-core`."
        ) from exc
    return ChatPromptTemplate, JsonOutputParser, RunnableLambda


@dataclass
class _ShimConfig:
    provider: str
    model: str
    max_calls: int
    max_tokens: int


class LangChainDeterministicAgent:
    """TraceCore agent that funnels observations through a LangChain prompt."""

    def __init__(
        self,
        *,
        shim_fixture: str | None = _DEFAULT_SHIM_FIXTURE,
        shim_responses: dict[str, str] | None = None,
        provider: str = 'openai',
        model: str = 'gpt-4o-mini',
        max_calls: int = 4,
        max_tokens: int = 2048,
    ) -> None:
        ChatPromptTemplate, JsonOutputParser, RunnableLambda = _lazy_import_langchain()
        self.prompt = ChatPromptTemplate.from_template(_PROMPT_TEMPLATE)
        self.parser = JsonOutputParser()
        self._shim_cfg = _ShimConfig(provider=provider, model=model, max_calls=max_calls, max_tokens=max_tokens)
        self._provider_budget = LLMBudget(max_calls=max_calls, max_tokens=max_tokens)
        self.llm_trace: list[dict] = []
        self._shim = self._build_shim(shim_fixture, shim_responses)
        self._chain = self.prompt | RunnableLambda(self._invoke_llm) | self.parser
        self.reset({})

    def _build_shim(
        self,
        shim_fixture: str | None,
        shim_responses: dict[str, str] | None,
    ) -> DeterministicLLMShim | None:
        budget = LLMBudget(max_calls=self._shim_cfg.max_calls, max_tokens=self._shim_cfg.max_tokens)
        if shim_responses:
            return DeterministicLLMShim(shim_responses, budget=budget, name="langchain-adapter")
        if shim_fixture:
            return DeterministicLLMShim.from_fixture(shim_fixture, budget=budget, name="langchain-adapter")
        return None

    def reset(self, task_spec: dict) -> None:
        self.task_spec = task_spec or {}
        self._observation = None
        self._provider_budget.reset()
        if self._shim:
            self._shim.reset()

    def observe(self, observation: dict) -> None:
        self._observation = observation

    def _invoke_llm(self, prompt: Dict[str, Any]) -> dict:
        rendered = prompt["text"] if isinstance(prompt, dict) else str(prompt)
        telemetry_req = LLMCallRequest(
            provider=self._shim_cfg.provider,
            model=self._shim_cfg.model,
            prompt=rendered,
            shim_used=bool(self._shim),
        )
        error = None
        completion: str | None = None
        if self._shim:
            completion = self._shim.complete(rendered, metadata={"response_key": self._shim_cfg.provider})
        else:
            try:
                completion = self._call_provider(rendered)
            except Exception as exc:  # pragma: no cover - defensive network path
                error = str(exc)
        # JsonOutputParser expects a JSON string; coerce dicts and guard bad outputs.
        if isinstance(completion, dict):
            completion_str = json.dumps(completion)
        elif isinstance(completion, str):
            try:
                json.loads(completion)
                completion_str = completion
            except json.JSONDecodeError:
                completion_str = json.dumps({"type": "wait", "args": {}})
        else:
            completion_str = json.dumps({"type": "wait", "args": {}})
        telemetry_resp = LLMCallResponse(
            provider=self._shim_cfg.provider,
            model=self._shim_cfg.model,
            shim_used=bool(self._shim),
            completion=completion_str,
            success=error is None,
            error=error,
        )
        self.llm_trace.append(LLMCallTelemetry(request=telemetry_req, response=telemetry_resp).as_dict())
        return completion_str

    def _call_provider(self, prompt: str) -> str:
        self._provider_budget.consume(prompt, "")  # reserve a call slot before the network round-trip
        if self._shim_cfg.provider == "openai":
            try:
                from openai import OpenAI
            except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
                raise RuntimeError(
                    "Install openai>=1.0 to call OpenAI APIs or provide a deterministic shim fixture."
                ) from exc
            client = OpenAI()
            response = client.responses.create(
                model=self._shim_cfg.model,
                input=prompt,
                max_output_tokens=512,
            )
            completion = getattr(response, "output_text", None) or ""
            if not completion:
                chunks: list[str] = []
                for item in (getattr(response, "output", None) or []):
                    for block in (getattr(item, "content", None) or []):
                        if getattr(block, "text", None):
                            chunks.append(block.text)
                completion = "".join(chunks)
        elif self._shim_cfg.provider == "anthropic":
            try:
                import anthropic
            except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
                raise RuntimeError(
                    "Install anthropic to call Anthropic APIs or provide a deterministic shim fixture."
                ) from exc
            client = anthropic.Anthropic()
            response = client.messages.create(
                model=self._shim_cfg.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
                temperature=0,
            )
            completion = "".join(
                block.text for block in response.content if getattr(block, "type", "") == "text"
            )
        else:
            raise ValueError(f"Unsupported provider: {self._shim_cfg.provider}")
        self._provider_budget.consume(prompt, completion)
        return completion

    def act(self) -> dict:
        if not self._observation:
            return {"type": "wait", "args": {}}
        payload = {
            "text": self._render_prompt(self._observation),
        }
        try:
            action = self._chain.invoke(payload)
        except BudgetViolation:
            return {"type": "wait", "args": {}}
        if not isinstance(action, dict) or "type" not in action:
            return {"type": "wait", "args": {}}
        if action["type"] not in _ACTION_SCHEMA:
            return {"type": "wait", "args": {}}
        return action

    def _render_prompt(self, obs: dict) -> str:
        budget = obs.get("budget_remaining", {})
        return (
            _PROMPT_TEMPLATE
            + "\n\n"
            + json.dumps({
                "step": obs.get("step"),
                "last_action": obs.get("last_action"),
                "last_action_result": obs.get("last_action_result"),
                "visible_state": obs.get("visible_state"),
                "budget_remaining": budget,
            }, ensure_ascii=False, indent=2)
        )

