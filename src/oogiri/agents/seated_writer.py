"""座付き作家。分析担当・低温（SRS-MVP-FN-008〜010）。"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

import oogiri.llm as llm
from oogiri.config import AppConfig, load_config
from oogiri.contracts.analysis import AnalysisMemo
from oogiri.prompts import load_prompt

PROMPT_FILE = "seated_writer.md"
ROLE = "seated_writer"


class AnalysisError(Exception):
    """座付き作家の分析に失敗した。メッセージに秘密を含めない。"""


def analyze(theme: str, *, config: AppConfig | None = None) -> AnalysisMemo:
    """お題を分析し、後段へ配る `AnalysisMemo` を返す。"""
    cfg = config if config is not None else load_config()
    prompt = _render_prompt(theme)
    raw = _call_llm(prompt, cfg)
    return _parse_memo(raw)


def _render_prompt(theme: str) -> str:
    template = load_prompt(PROMPT_FILE)
    return template.replace("{{theme}}", theme)


def _call_llm(prompt: str, config: AppConfig) -> str:
    agent = config.agents.seated_writer
    return llm.gateway.complete(
        prompt=prompt,
        model=agent.model,
        temperature=agent.temperature,
        role=ROLE,
    )


def _parse_memo(raw: str) -> AnalysisMemo:
    data = _load_json_object(raw)
    try:
        return AnalysisMemo.model_validate(data)
    except ValidationError as exc:
        raise AnalysisError("座付き作家の出力がスキーマに合いません") from exc


def _load_json_object(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AnalysisError("座付き作家の出力が JSON として読めません") from exc
    if not isinstance(data, dict):
        raise AnalysisError("座付き作家の出力がオブジェクトではありません")
    return data
