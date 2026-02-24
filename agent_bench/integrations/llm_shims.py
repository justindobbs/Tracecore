"""Deterministic LLM shims with explicit budget enforcement."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from typing import Mapping, MutableSequence, Sequence


class BudgetViolation(RuntimeError):
    """Raised when an LLM shim exceeds the configured budget."""


@dataclass
class LLMBudget:
    """Simple accounting helper for LLM usage.

    The adapter approximates token usage by char-count * 0.25 which is good
    enough to cap runaway loops without requiring tokenizer dependencies.
    """

    max_calls: int | None = None
    max_tokens: int | None = None
    _calls_used: int = 0
    _tokens_used: int = 0

    def reset(self) -> None:
        self._calls_used = 0
        self._tokens_used = 0

    def fork(self) -> "LLMBudget":
        clone = replace(self)
        clone.reset()
        return clone

    def _estimate_tokens(self, prompt: str, completion: str) -> int:
        return int((len(prompt) + len(completion)) * 0.25)

    def consume(self, prompt: str, completion: str) -> None:
        self._calls_used += 1
        if self.max_calls is not None and self._calls_used > self.max_calls:
            raise BudgetViolation(
                f"LLM call budget exceeded (allowed={self.max_calls}, used={self._calls_used})"
            )
        tokens = self._estimate_tokens(prompt, completion)
        self._tokens_used += tokens
        if self.max_tokens is not None and self._tokens_used > self.max_tokens:
            raise BudgetViolation(
                f"LLM token budget exceeded (allowed={self.max_tokens}, used={self._tokens_used})"
            )


class DeterministicLLMShim:
    """Returns pre-recorded completions keyed by prompt fingerprints."""

    def __init__(
        self,
        responses: Mapping[str, str] | Sequence[str],
        *,
        budget: LLMBudget | None = None,
        name: str = "shim",
    ) -> None:
        if not responses:
            raise ValueError("responses must not be empty")
        self._source = responses
        self._queue: MutableSequence[str] | None = None
        self.name = name
        self._budget_template = budget or LLMBudget()
        self._budget = self._budget_template.fork()
        self._reset_queue()

    def _reset_queue(self) -> None:
        if isinstance(self._source, Mapping):
            self._queue = None
        else:
            self._queue = list(self._source)

    def reset(self) -> None:
        self._budget = self._budget_template.fork()
        self._reset_queue()

    @staticmethod
    def _hash_prompt(prompt: str) -> str:
        return sha256(prompt.encode("utf-8")).hexdigest()

    def complete(self, prompt: str, *, metadata: dict | None = None) -> str:
        key = (metadata or {}).get("response_key")
        if key is None:
            key = self._hash_prompt(prompt)
        response: str | None = None
        if isinstance(self._source, Mapping):
            response = self._source.get(key)
            if response is None:
                available = ", ".join(list(self._source.keys())[:5])
                raise KeyError(
                    f"No deterministic response recorded for key={key}. "
                    f"Available keys (first 5): {available}"
                )
        else:
            if not self._queue:
                raise KeyError("Deterministic queue exhausted; record more responses")
            response = self._queue.pop(0)
        if self._budget:
            self._budget.consume(prompt, response)
        return response

    @classmethod
    def from_fixture(
        cls,
        path: str | Path,
        *,
        budget: LLMBudget | None = None,
        name: str = "shim",
    ) -> "DeterministicLLMShim":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Fixture must be a JSON object mapping keys to responses")
        return cls(data, budget=budget, name=name)

    def available_queue(self) -> int:
        if self._queue is None:
            return len(self._source)  # type: ignore[arg-type]
        return len(self._queue)
