"""ツッコミ役。審査担当・低温（SRS-MVP-FN-017〜021）。"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

import oogiri.llm as llm
from oogiri.config import AppConfig, load_config
from oogiri.contracts.analysis import AnalysisMemo
from oogiri.contracts.candidates import Candidate, CandidateBatch
from oogiri.contracts.shortlist import Shortlist, TsukkomiNote
from oogiri.prompts import load_prompt

PROMPT_FILE = "tsukkomi.md"
ROLE = "tsukkomi"
SELECTED_COUNT = 5
_PLACEHOLDER_RE = re.compile(r"\{\{([a-z_]+)\}\}")


class TsukkomiError(Exception):
    """ツッコミ役の審査に失敗した。メッセージに秘密を含めない。"""


class _NoteDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    candidate_id: str = Field(min_length=1)
    tsukkomi: str = Field(min_length=1)
    dropped: bool
    score: float

    @field_validator("candidate_id", "tsukkomi", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class _SelectedDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    candidate_id: str = Field(min_length=1)

    @field_validator("candidate_id", mode="before")
    @classmethod
    def strip_id(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class _ShortlistDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    notes: list[_NoteDraft] = Field(min_length=1)
    selected: list[_SelectedDraft] = Field(min_length=1)

    @field_validator("selected", mode="before")
    @classmethod
    def coerce_selected(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [_as_selected_item(item) for item in value]


def review(
    theme: str,
    analysis_memo: AnalysisMemo,
    batches: Sequence[CandidateBatch],
    *,
    config: AppConfig | None = None,
) -> Shortlist:
    """残存全案にツッコミを付け、原案のまま 5 案を返す。"""
    cfg = config if config is not None else load_config()
    candidates = _flatten_candidates(batches)
    prompt = _render_prompt(theme, analysis_memo, candidates)
    raw = _call_llm(prompt, cfg)
    draft = _parse_draft(raw)
    return _assemble(draft, candidates)


def _flatten_candidates(batches: Sequence[CandidateBatch]) -> tuple[Candidate, ...]:
    candidates = tuple(item for batch in batches for item in batch.candidates)
    if not candidates:
        raise TsukkomiError("審査する案がありません")
    ids = [item.candidate_id for item in candidates]
    if len(ids) != len(set(ids)):
        raise TsukkomiError("案 ID が重複しています")
    return candidates


def _fill_placeholders(template: str, values: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        return values.get(match.group(1), match.group(0))

    return _PLACEHOLDER_RE.sub(replace, template)


def _render_prompt(
    theme: str, analysis_memo: AnalysisMemo, candidates: tuple[Candidate, ...]
) -> str:
    template = load_prompt(PROMPT_FILE)
    memo_json = json.dumps(analysis_memo.model_dump(), ensure_ascii=False)
    batch_json = json.dumps(
        [item.model_dump() for item in candidates], ensure_ascii=False
    )
    return _fill_placeholders(
        template,
        {
            "theme": theme,
            "analysis_memo": memo_json,
            "candidate_batch": batch_json,
        },
    )


def _call_llm(prompt: str, config: AppConfig) -> str:
    agent = config.agents.tsukkomi
    return llm.gateway.complete(
        prompt=prompt,
        model=agent.model,
        temperature=agent.temperature,
        role=ROLE,
    )


def _parse_draft(raw: str) -> _ShortlistDraft:
    data = _load_json_object(raw)
    try:
        return _ShortlistDraft.model_validate(data)
    except ValidationError as exc:
        raise TsukkomiError("ツッコミ役の出力がスキーマに合いません") from exc


def _load_json_object(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TsukkomiError("ツッコミ役の出力が JSON として読めません") from exc
    if not isinstance(data, dict):
        raise TsukkomiError("ツッコミ役の出力がオブジェクトではありません")
    return data


def _assemble(draft: _ShortlistDraft, originals: tuple[Candidate, ...]) -> Shortlist:
    by_id = {item.candidate_id: item for item in originals}
    notes = tuple(_note_from_draft(item, by_id) for item in draft.notes)
    selected = tuple(
        _pick_original(item.candidate_id, by_id, notes) for item in draft.selected
    )
    shortlist = _shortlist_from_parts(selected, notes)
    _require_full_coverage(shortlist.notes, by_id)
    _require_unique_forms(shortlist.selected)
    return shortlist


def _note_from_draft(item: _NoteDraft, by_id: dict[str, Candidate]) -> TsukkomiNote:
    _require_known_id(item.candidate_id, by_id)
    try:
        return TsukkomiNote(
            candidate_id=item.candidate_id,
            tsukkomi=item.tsukkomi,
            dropped=item.dropped,
            score=item.score,
        )
    except ValidationError as exc:
        raise TsukkomiError("ツッコミ役の出力がスキーマに合いません") from exc


def _pick_original(
    candidate_id: str,
    by_id: dict[str, Candidate],
    notes: tuple[TsukkomiNote, ...],
) -> Candidate:
    _require_known_id(candidate_id, by_id)
    dropped = {note.candidate_id for note in notes if note.dropped}
    if candidate_id in dropped:
        raise TsukkomiError("ツッコミ不能の案は選べません")
    return by_id[candidate_id]


def _shortlist_from_parts(
    selected: tuple[Candidate, ...], notes: tuple[TsukkomiNote, ...]
) -> Shortlist:
    try:
        return Shortlist(selected=selected, notes=notes)
    except ValidationError as exc:
        raise TsukkomiError("ツッコミ役の出力がスキーマに合いません") from exc


def _require_known_id(candidate_id: str, by_id: dict[str, Candidate]) -> None:
    if candidate_id not in by_id:
        raise TsukkomiError("未知の案 ID があります")


def _require_full_coverage(
    notes: tuple[TsukkomiNote, ...], by_id: dict[str, Candidate]
) -> None:
    note_ids = {note.candidate_id for note in notes}
    if note_ids != set(by_id):
        raise TsukkomiError("残存全案にツッコミがありません")


def _require_unique_forms(selected: tuple[Candidate, ...]) -> None:
    texts = [item.text for item in selected]
    if len(set(texts)) != SELECTED_COUNT:
        raise TsukkomiError("同じ形の案が重なっています")


def _as_selected_item(item: object) -> object:
    if isinstance(item, str):
        return {"candidate_id": item}
    return item
