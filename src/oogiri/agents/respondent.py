"""回答者 n 体。並列・高温・相互非参照（SRS-MVP-FN-014〜016）。"""

from __future__ import annotations

import json
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from pydantic import ValidationError

import oogiri.llm as llm
from oogiri.contracts.analysis import AnalysisMemo
from oogiri.contracts.candidates import CandidateBatch
from oogiri.contracts.roster import RespondentSpec, Roster

ROLE = "respondent"


class RespondentError(Exception):
    """回答者の生成に失敗した。メッセージに秘密を含めない。"""


def respond(analysis_memo: AnalysisMemo, roster: Roster) -> tuple[CandidateBatch, ...]:
    """n 体を並列に走らせ、各体の `CandidateBatch` を編成順で返す。"""
    batches = _respond_parallel(analysis_memo, roster.respondents)
    _require_unique_candidate_ids(batches)
    return batches


def _respond_parallel(
    analysis_memo: AnalysisMemo, specs: tuple[RespondentSpec, ...]
) -> tuple[CandidateBatch, ...]:
    with ThreadPoolExecutor(max_workers=len(specs)) as pool:
        futures = [pool.submit(_respond_one, spec, analysis_memo) for spec in specs]
        return tuple(_future_batch(future) for future in futures)


def _future_batch(future: Future[CandidateBatch]) -> CandidateBatch:
    return future.result()


def _respond_one(spec: RespondentSpec, analysis_memo: AnalysisMemo) -> CandidateBatch:
    _ensure_memo_present(spec.system_prompt, analysis_memo)
    raw = _call_llm(spec)
    return _parse_batch(raw, spec.respondent_id)


def _ensure_memo_present(prompt: str, memo: AnalysisMemo) -> None:
    snippets = (
        memo.theme_type,
        memo.humor_direction,
        *memo.premises,
        *memo.banal_ideas,
    )
    if all(snippet in prompt for snippet in snippets):
        return
    raise RespondentError("座付き作家の分析メモが回答者入力にありません")


def _call_llm(spec: RespondentSpec) -> str:
    return llm.gateway.complete(
        prompt=spec.system_prompt,
        model=spec.model,
        temperature=spec.temperature,
        role=ROLE,
        respondent_id=spec.respondent_id,
    )


def _parse_batch(raw: str, respondent_id: str) -> CandidateBatch:
    data = _load_json_object(raw)
    data["respondent_id"] = respondent_id
    _overwrite_candidate_respondent_ids(data.get("candidates"), respondent_id)
    try:
        return CandidateBatch.model_validate(data)
    except ValidationError as exc:
        raise RespondentError("回答者の出力がスキーマに合いません") from exc


def _overwrite_candidate_respondent_ids(items: object, respondent_id: str) -> None:
    if not isinstance(items, list):
        return
    for item in items:
        if isinstance(item, dict):
            item["respondent_id"] = respondent_id


def _load_json_object(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RespondentError("回答者の出力が JSON として読めません") from exc
    if not isinstance(data, dict):
        raise RespondentError("回答者の出力がオブジェクトではありません")
    return data


def _require_unique_candidate_ids(batches: tuple[CandidateBatch, ...]) -> None:
    ids = [item.candidate_id for batch in batches for item in batch.candidates]
    if len(ids) != len(set(ids)):
        raise RespondentError("案 ID が重複しています")
