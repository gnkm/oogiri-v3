"""OpenRouter への HTTPS と CrewAI の LLM 設定を集約するゲートウェイ。

試験は本モジュールを差し替える（docs/test-strategy.md）。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

_OPENROUTER_PREFIX = "openrouter/"
_CHAT_PATH = "/chat/completions"
_TIMEOUT_SEC = 120
_CrewAILLM: type | None = None


class LLMError(Exception):
    """LLM 呼び出しに失敗した。メッセージに秘密を含めない。"""


class LLMGateway:
    """OpenRouter / CrewAI 呼び出しの集約点。"""

    def __init__(self) -> None:
        self._api_key: str | None = None
        self._base_url: str | None = None

    def configure(self, *, api_key: str, base_url: str) -> None:
        """接続先とキーを覚える。キーはログに出さない。"""
        self._api_key = api_key
        self._base_url = base_url

    def complete(self, **kwargs: Any) -> str:
        return _complete_openrouter(
            prompt=str(kwargs["prompt"]),
            model=str(kwargs["model"]),
            temperature=float(kwargs["temperature"]),
            api_key=self._api_key,
            base_url=self._base_url,
        )


gateway = LLMGateway()


def configure_gateway(*, api_key: str, base_url: str) -> None:
    """現在のゲートウェイへ接続情報を渡す。Fake には configure が無くてよい。"""
    method = getattr(gateway, "configure", None)
    if callable(method):
        method(api_key=api_key, base_url=base_url)


def llm_for_role(*, model: str, temperature: float) -> Any:
    """CrewAI Agent 用の LLM。実呼び出しは `gateway.complete` 側で行う。"""
    return _crewai_llm_class()(model=model, temperature=temperature)


def _crewai_llm_class() -> type:
    global _CrewAILLM
    if _CrewAILLM is None:
        _CrewAILLM = _define_crewai_llm()
    return _CrewAILLM


def _define_crewai_llm() -> type:
    from crewai import BaseLLM

    class CrewAILLM(BaseLLM):
        """構造用。kickoff は使わず、段階関数が gateway を呼ぶ。"""

        def call(
            self,
            messages: Any,
            tools: Any = None,
            callbacks: Any = None,
            available_functions: Any = None,
            **kwargs: Any,
        ) -> str:
            return "{}"

    return CrewAILLM


def _complete_openrouter(
    *,
    prompt: str,
    model: str,
    temperature: float,
    api_key: str | None,
    base_url: str | None,
) -> str:
    _require_connection(api_key, base_url)
    payload = _chat_payload(prompt, model, temperature)
    raw = _post_chat(base_url or "", api_key or "", payload)
    return _content_from_chat(raw)


def _require_connection(api_key: str | None, base_url: str | None) -> None:
    if not api_key or not base_url:
        raise LLMError("OpenRouter の接続情報がありません")


def _chat_payload(prompt: str, model: str, temperature: float) -> bytes:
    body = {
        "model": _public_model_id(model),
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }
    return json.dumps(body).encode("utf-8")


def _public_model_id(model: str) -> str:
    if model.startswith(_OPENROUTER_PREFIX):
        return model[len(_OPENROUTER_PREFIX) :]
    return model


def _post_chat(base_url: str, api_key: str, payload: bytes) -> str:
    request = urllib.request.Request(
        url=_chat_url(base_url),
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SEC) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise LLMError(_http_error_message(exc)) from exc
    except OSError as exc:
        raise LLMError("OpenRouter への接続に失敗しました") from exc


def _chat_url(base_url: str) -> str:
    return base_url.rstrip("/") + _CHAT_PATH


def _http_error_message(exc: urllib.error.HTTPError) -> str:
    detail = _public_http_detail(exc)
    if detail:
        return f"OpenRouter がエラーを返しました: {detail}"
    return "OpenRouter がエラーを返しました"


def _public_http_detail(exc: urllib.error.HTTPError) -> str:
    raw = exc.read().decode("utf-8", errors="replace")
    data = _try_json_object(raw)
    message = _error_message(data)
    if message:
        return message
    return f"HTTP {exc.code}"


def _try_json_object(raw: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        return data
    return None


def _error_message(data: dict[str, Any] | None) -> str:
    if data is None:
        return ""
    error = data.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return ""


def _content_from_chat(raw: str) -> str:
    data = _load_json_object(raw)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("OpenRouter の応答が読めません") from exc
    if not isinstance(content, str) or not content:
        raise LLMError("OpenRouter の応答が空です")
    return content


def _load_json_object(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError("OpenRouter の応答が JSON として読めません") from exc
    if not isinstance(data, dict):
        raise LLMError("OpenRouter の応答がオブジェクトではありません")
    return data
