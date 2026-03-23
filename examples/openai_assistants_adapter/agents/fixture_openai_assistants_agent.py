from __future__ import annotations

import json

from agent_bench.telemetry import LLMCallRequest, LLMCallResponse, LLMCallTelemetry


class FixtureOpenAIAssistantsAgent:
    def __init__(self) -> None:
        self.reset({})

    def reset(self, task_spec) -> None:
        self.task_spec = task_spec or {}
        self.obs = None
        self.completed = False
        self.llm_trace = []
        self._listed_app = False
        self._read_hidden = False
        self._extracted = False
        self._hidden_path = None
        self._secret = None

    def observe(self, observation) -> None:
        self.obs = observation

    def _record_trace(self, prompt: str, completion: dict) -> None:
        request = LLMCallRequest(
            provider="openai",
            model="assistants-fixture",
            prompt=prompt,
            shim_used=True,
            metadata={"surface": "assistants"},
        )
        response = LLMCallResponse(
            provider="openai",
            model="assistants-fixture",
            shim_used=True,
            completion=json.dumps(completion),
            success=True,
        )
        self.llm_trace.append(LLMCallTelemetry(request=request, response=response).as_dict())

    def act(self) -> dict:
        if self.obs is None:
            return {"type": "wait", "args": {}}

        last_result = self.obs.get("last_action_result") or {}

        if not self._listed_app:
            action = {"type": "list_dir", "args": {"path": "/app"}}
            self._record_trace("List available files for the assistant thread context.", action)
            self._listed_app = True
            return action

        if self._hidden_path is None:
            files = last_result.get("files") or []
            hidden_candidates = [path for path in files if isinstance(path, str) and "/.config_" in path]
            if hidden_candidates:
                self._hidden_path = hidden_candidates[0]

        if self._hidden_path and not self._read_hidden:
            action = {"type": "read_file", "args": {"path": self._hidden_path}}
            self._record_trace("Read the hidden assistant config file from the resolved workspace.", action)
            self._read_hidden = True
            return action

        if self._read_hidden and not self._extracted:
            content = last_result.get("content")
            if isinstance(content, str):
                action = {"type": "extract_value", "args": {"content": content, "key": "API_KEY"}}
                self._record_trace("Extract the API_KEY value from the assistant file contents.", action)
                self._extracted = True
                return action

        if self._extracted and not self.completed:
            value = last_result.get("value")
            if isinstance(value, str):
                self._secret = value
                action = {"type": "set_output", "args": {"key": "API_KEY", "value": value}}
                self._record_trace("Submit the final assistant answer from the resolved thread state.", action)
                self.completed = True
                return action

        return {"type": "wait", "args": {}}
