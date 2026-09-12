"""OpenRouter への HTTPS と CrewAI の LLM 設定を集約するゲートウェイ。

試験は本モジュールを差し替える（docs/test-strategy.md）。
実呼び出しの実装は後続 Issue。
"""

from __future__ import annotations

from typing import Any


class LLMGateway:
    """OpenRouter / CrewAI 呼び出しの集約点。"""

    def complete(self, **kwargs: Any) -> str:
        raise NotImplementedError("OpenRouter 呼び出しは後続 Issue で実装する")


gateway = LLMGateway()
