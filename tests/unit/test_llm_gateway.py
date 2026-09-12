"""LLM ゲートウェイの Fake 差し替え口。"""

from __future__ import annotations

import oogiri.llm as llm


def test_fake_llm_replaces_gateway(fake_llm) -> None:
    fake_llm.responses.append("ok")
    assert llm.gateway.complete(prompt="x") == "ok"
    assert fake_llm.calls == [{"prompt": "x"}]
