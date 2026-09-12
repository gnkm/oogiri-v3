"""共通 pytest fixture。LLM モックの正本（docs/test-strategy.md）。"""

from __future__ import annotations

import os
import threading
from typing import Any

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "1")
os.environ.setdefault("DEEPEVAL_DISABLE_DOTENV", "1")

import pytest

from oogiri.llm import LLMGateway


class FakeLLM(LLMGateway):
    """ARCHITECTURE のデータ契約に合う応答を後続試験が設定する Fake。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.responses: list[str] = []
        self.max_in_flight = 0
        self.release_gate: threading.Barrier | None = None
        self._lock = threading.Lock()
        self._in_flight = 0

    def complete(self, **kwargs: Any) -> str:
        self._enter_call(kwargs)
        try:
            self._wait_if_gated()
            return self._next_response()
        finally:
            self._leave_call()

    def _enter_call(self, kwargs: dict[str, Any]) -> None:
        with self._lock:
            self._in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self._in_flight)
            self.calls.append(dict(kwargs))

    def _leave_call(self) -> None:
        with self._lock:
            self._in_flight -= 1

    def _wait_if_gated(self) -> None:
        gate = self.release_gate
        if gate is not None:
            gate.wait()

    def _next_response(self) -> str:
        with self._lock:
            if not self.responses:
                raise AssertionError("FakeLLM に応答が設定されていない")
            return self.responses.pop(0)


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    """LLM ゲートウェイ（oogiri.llm.gateway）を Fake に差し替える。"""
    fake = FakeLLM()
    monkeypatch.setattr("oogiri.llm.gateway", fake)
    return fake
