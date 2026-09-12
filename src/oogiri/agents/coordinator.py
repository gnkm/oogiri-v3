"""回答者コーディネーター。実行ごとに軸を決め n 体を編成する（SRS-MVP-FN-011〜013）。"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

import oogiri.llm as llm
from oogiri.config import AppConfig, load_config
from oogiri.contracts.analysis import AnalysisMemo
from oogiri.contracts.roster import RespondentSpec, Roster, StyleAxis
from oogiri.prompts import load_prompt

PROMPT_FILE = "coordinator.md"
RESPONDENT_PROMPT_FILE = "respondent.md"
ROLE = "coordinator"
DEFAULT_RESPONDENT_NUM = 3
LOW_TEMPERATURE_MAX = 0.5
_PLACEHOLDER_RE = re.compile(r"\{\{([a-z_]+)\}\}")


class CoordinatorError(Exception):
    """回答者コーディネーターの編成に失敗した。メッセージに秘密を含めない。"""


class _RespondentDraft(BaseModel):
    """LLM 出力の 1 体分。system_prompt はコード側で組み立てる。"""

    model_config = ConfigDict(extra="ignore")

    respondent_id: str = Field(min_length=1)
    axis: StyleAxis | str
    style_instructions: str | None = None
    system_prompt: str | None = None

    @field_validator("respondent_id", mode="before")
    @classmethod
    def strip_id(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    def style_text(self) -> str:
        text = (self.style_instructions or self.system_prompt or "").strip()
        if not text:
            raise CoordinatorError("回答者の芸風指示が空です")
        return text


class _RosterDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    axes: list[StyleAxis] = Field(min_length=1)
    respondents: list[_RespondentDraft] = Field(min_length=1)


def coordinate(
    theme: str,
    analysis_memo: AnalysisMemo,
    respondent_num: int = DEFAULT_RESPONDENT_NUM,
    *,
    config: AppConfig | None = None,
) -> Roster:
    """お題と分析メモから、n 体分の `Roster` を返す。"""
    if respondent_num < 1:
        raise CoordinatorError("回答者数は 1 以上である必要があります")
    cfg = config if config is not None else load_config()
    _ensure_respondent_temperature_is_high(cfg)
    prompt = _render_prompt(theme, analysis_memo, respondent_num)
    raw = _call_llm(prompt, cfg)
    draft = _parse_draft(raw)
    return _to_roster(draft, theme, analysis_memo, respondent_num, cfg)


def _ensure_respondent_temperature_is_high(config: AppConfig) -> None:
    if config.agents.respondent.temperature < LOW_TEMPERATURE_MAX:
        raise CoordinatorError("回答者の温度は高温のままにする")


def _fill_placeholders(template: str, values: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        return values.get(match.group(1), match.group(0))

    return _PLACEHOLDER_RE.sub(replace, template)


def _render_prompt(theme: str, analysis_memo: AnalysisMemo, respondent_num: int) -> str:
    template = load_prompt(PROMPT_FILE)
    memo_json = json.dumps(analysis_memo.model_dump(), ensure_ascii=False)
    return _fill_placeholders(
        template,
        {
            "theme": theme,
            "respondent_num": str(respondent_num),
            "analysis_memo": memo_json,
        },
    )


def _call_llm(prompt: str, config: AppConfig) -> str:
    agent = config.agents.coordinator
    return llm.gateway.complete(
        prompt=prompt,
        model=agent.model,
        temperature=agent.temperature,
        role=ROLE,
    )


def _parse_draft(raw: str) -> _RosterDraft:
    data = _load_json_object(raw)
    try:
        return _RosterDraft.model_validate(data)
    except ValidationError as exc:
        raise CoordinatorError(
            "回答者コーディネーターの出力がスキーマに合いません"
        ) from exc


def _load_json_object(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CoordinatorError(
            "回答者コーディネーターの出力が JSON として読めません"
        ) from exc
    if not isinstance(data, dict):
        raise CoordinatorError(
            "回答者コーディネーターの出力がオブジェクトではありません"
        )
    return data


def _to_roster(
    draft: _RosterDraft,
    theme: str,
    analysis_memo: AnalysisMemo,
    respondent_num: int,
    config: AppConfig,
) -> Roster:
    _require_n_unique_respondents(draft, respondent_num)
    axes_by_name = _index_axes(draft.axes)
    _ensure_drafts_differ(draft.respondents, axes_by_name)
    specs = _build_specs(draft, axes_by_name, theme, analysis_memo, config)
    return _roster_from_parts(axes_by_name, specs)


def _require_n_unique_respondents(draft: _RosterDraft, respondent_num: int) -> None:
    if len(draft.respondents) != respondent_num:
        raise CoordinatorError("回答者数が n と一致しません")
    ids = [item.respondent_id for item in draft.respondents]
    if len(set(ids)) != len(ids):
        raise CoordinatorError("回答者 ID が重複しています")


def _build_specs(
    draft: _RosterDraft,
    axes_by_name: dict[str, StyleAxis],
    theme: str,
    analysis_memo: AnalysisMemo,
    config: AppConfig,
) -> tuple[RespondentSpec, ...]:
    respondent_template = load_prompt(RESPONDENT_PROMPT_FILE)
    memo_json = json.dumps(analysis_memo.model_dump(), ensure_ascii=False)
    return tuple(
        _build_spec(
            item,
            axes_by_name,
            theme,
            memo_json,
            respondent_template,
            config,
        )
        for item in draft.respondents
    )


def _roster_from_parts(
    axes_by_name: dict[str, StyleAxis], specs: tuple[RespondentSpec, ...]
) -> Roster:
    try:
        return Roster(axes=tuple(axes_by_name.values()), respondents=specs)
    except ValidationError as exc:
        raise CoordinatorError(
            "回答者コーディネーターの出力がスキーマに合いません"
        ) from exc


def _index_axes(axes: list[StyleAxis]) -> dict[str, StyleAxis]:
    indexed: dict[str, StyleAxis] = {}
    for axis in axes:
        _put_unique_axis(indexed, axis)
    return indexed


def _put_unique_axis(indexed: dict[str, StyleAxis], axis: StyleAxis) -> None:
    prev = indexed.get(axis.name)
    if prev is None:
        indexed[axis.name] = axis
        return
    if prev != axis:
        raise CoordinatorError("同名で異なる軸定義があります")


def _build_spec(
    draft: _RespondentDraft,
    axes_by_name: dict[str, StyleAxis],
    theme: str,
    memo_json: str,
    respondent_template: str,
    config: AppConfig,
) -> RespondentSpec:
    axis = _resolve_axis(draft.axis, axes_by_name)
    style = draft.style_text()
    system_prompt = _render_respondent_prompt(
        respondent_template,
        theme=theme,
        memo_json=memo_json,
        respondent_id=draft.respondent_id,
        axis=axis,
        style_instructions=style,
    )
    respondent_llm = config.agents.respondent
    try:
        return RespondentSpec(
            respondent_id=draft.respondent_id,
            axis=axis,
            system_prompt=system_prompt,
            model=respondent_llm.model,
            temperature=respondent_llm.temperature,
        )
    except ValidationError as exc:
        raise CoordinatorError(
            "回答者コーディネーターの出力がスキーマに合いません"
        ) from exc


def _resolve_axis(
    axis: StyleAxis | str, axes_by_name: dict[str, StyleAxis]
) -> StyleAxis:
    if isinstance(axis, StyleAxis):
        return _resolve_axis_object(axis, axes_by_name)
    return _resolve_axis_name(axis, axes_by_name)


def _resolve_axis_object(
    axis: StyleAxis, axes_by_name: dict[str, StyleAxis]
) -> StyleAxis:
    resolved = axes_by_name.get(axis.name)
    if resolved is None:
        raise CoordinatorError("回答者の軸が axes にありません")
    if resolved != axis:
        raise CoordinatorError("回答者の軸が axes と一致しません")
    return resolved


def _resolve_axis_name(name: str, axes_by_name: dict[str, StyleAxis]) -> StyleAxis:
    stripped = name.strip()
    if not stripped:
        raise CoordinatorError("回答者の軸が空です")
    resolved = axes_by_name.get(stripped)
    if resolved is None:
        raise CoordinatorError("回答者の軸が axes にありません")
    return resolved


def _render_respondent_prompt(
    template: str,
    *,
    theme: str,
    memo_json: str,
    respondent_id: str,
    axis: StyleAxis,
    style_instructions: str,
) -> str:
    return _fill_placeholders(
        template,
        {
            "theme": theme,
            "analysis_memo": memo_json,
            "respondent_id": respondent_id,
            "axis_name": axis.name,
            "axis_description": axis.description,
            "style_instructions": style_instructions,
        },
    )


def _ensure_drafts_differ(
    drafts: list[_RespondentDraft], axes_by_name: dict[str, StyleAxis]
) -> None:
    signatures = [
        (_resolve_axis(item.axis, axes_by_name).name, item.style_text())
        for item in drafts
    ]
    if len(set(signatures)) != len(signatures):
        raise CoordinatorError("回答者の軸と指示が重複しています")
