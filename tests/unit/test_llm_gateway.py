"""LLM ゲートウェイの Fake 差し替え口と送信先検証。"""

from __future__ import annotations

import urllib.request

import pytest

import oogiri.llm as llm


def test_fake_llm_replaces_gateway(fake_llm) -> None:
    fake_llm.responses.append("ok")
    assert llm.gateway.complete(prompt="x") == "ok"
    assert fake_llm.calls == [{"prompt": "x"}]


def test_complete_rejects_non_openrouter_host(monkeypatch: pytest.MonkeyPatch) -> None:
    isolated = llm.LLMGateway()
    isolated.configure(api_key="test-key", base_url="https://evil.example/api/v1")
    monkeypatch.setattr(llm, "gateway", isolated)

    def must_not_send(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("OpenRouter 以外へキーを送ってはいけない")

    monkeypatch.setattr(urllib.request, "build_opener", must_not_send)
    monkeypatch.setattr(urllib.request, "urlopen", must_not_send)
    with pytest.raises(llm.LLMError, match="OpenRouter 以外"):
        isolated.complete(prompt="x", model="openrouter/x", temperature=0.2)


def test_complete_rejects_http_openrouter(monkeypatch: pytest.MonkeyPatch) -> None:
    isolated = llm.LLMGateway()
    isolated.configure(api_key="test-key", base_url="http://openrouter.ai/api/v1")
    monkeypatch.setattr(llm, "gateway", isolated)

    def must_not_send(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("HTTP へキーを送ってはいけない")

    monkeypatch.setattr(urllib.request, "build_opener", must_not_send)
    with pytest.raises(llm.LLMError, match="HTTPS"):
        isolated.complete(prompt="x", model="openrouter/x", temperature=0.2)
