"""推敲役。低温（SRS-MVP-FN-022〜027）。"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

import oogiri.llm as llm
from oogiri.config import AppConfig, load_config
from oogiri.contracts.polished import PolishedAnswer
from oogiri.contracts.shortlist import Shortlist, TsukkomiNote
from oogiri.prompts import load_prompt

PROMPT_FILE = "polisher.md"
ROLE = "polisher"
_PLACEHOLDER_RE = re.compile(r"\{\{([a-z_]+)\}\}")


class PolishError(Exception):
    """推敲役の推敲に失敗した。メッセージに秘密を含めない。"""


def polish(
    theme: str,
    shortlist: Shortlist,
    *,
    config: AppConfig | None = None,
) -> PolishedAnswer:
    """採択 5 案を磨き、テキスト 1 案の `PolishedAnswer` を返す。"""
    cfg = config if config is not None else load_config()
    prompt = _render_prompt(theme, shortlist)
    raw = _call_llm(prompt, cfg)
    return _parse_answer(raw)


def _fill_placeholders(template: str, values: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        return values.get(match.group(1), match.group(0))

    return _PLACEHOLDER_RE.sub(replace, template)


def _render_prompt(theme: str, shortlist: Shortlist) -> str:
    template = load_prompt(PROMPT_FILE)
    projection = json.dumps(_project_shortlist(shortlist), ensure_ascii=False)
    return _fill_placeholders(template, {"theme": theme, "shortlist": projection})


def _project_shortlist(shortlist: Shortlist) -> dict[str, Any]:
    notes = _notes_for_selected(shortlist)
    return {
        "selected": [item.model_dump() for item in shortlist.selected],
        "notes": [note.model_dump() for note in notes],
    }


def _notes_for_selected(shortlist: Shortlist) -> tuple[TsukkomiNote, ...]:
    notes_by_id = {note.candidate_id: note for note in shortlist.notes}
    return tuple(notes_by_id[item.candidate_id] for item in shortlist.selected)


def _call_llm(prompt: str, config: AppConfig) -> str:
    agent = config.agents.polisher
    return llm.gateway.complete(
        prompt=prompt,
        model=agent.model,
        temperature=agent.temperature,
        role=ROLE,
    )


def _parse_answer(raw: str) -> PolishedAnswer:
    data = _load_json_object(raw)
    try:
        return PolishedAnswer.model_validate(data)
    except ValidationError as exc:
        raise PolishError("推敲役の出力がスキーマに合いません") from exc


def _load_json_object(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PolishError("推敲役の出力が JSON として読めません") from exc
    if not isinstance(data, dict):
        raise PolishError("推敲役の出力がオブジェクトではありません")
    return data
