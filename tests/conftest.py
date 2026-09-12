"""共通 pytest fixture。LLM モックの正本（docs/test-strategy.md）。"""

from __future__ import annotations

from typing import Any

import pytest

from oogiri.llm import LLMGateway


class FakeLLM(LLMGateway):
    """ARCHITECTURE のデータ契約に合う応答を後続試験が設定する Fake。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.responses: list[str] = []

    def complete(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("FakeLLM に応答が設定されていない")
        return self.responses.pop(0)


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    """LLM ゲートウェイ（oogiri.llm.gateway）を Fake に差し替える。"""
    fake = FakeLLM()
    monkeypatch.setattr("oogiri.llm.gateway", fake)
    return fake
