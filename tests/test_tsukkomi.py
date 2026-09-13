"""ツッコミ役（SRS-MVP-FN-017〜021、QA-003）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from oogiri.agents.tsukkomi import TsukkomiError, review
from oogiri.config import (
    AgentLLMConfig,
    AgentsConfig,
    AppConfig,
    EvalConfig,
    OpenRouterConfig,
    load_config,
)
from oogiri.contracts.analysis import AnalysisMemo
from oogiri.contracts.candidates import Candidate, CandidateBatch
from oogiri.contracts.shortlist import Shortlist, TsukkomiNote

ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "prompts" / "tsukkomi.md"
PROMPT_MARKER = "案本文の誤字修正・読点・語尾の変更も書き換えである。"
THEME = "こんなAIはいやだ。どんなAI？"


def _memo_payload() -> dict[str, object]:
    return {
        "theme_type": "定義付け",
        "humor_direction": "日常の不便を極端化する",
        "premises": ["聞き手はお題を知っている", "回答は一言で返す", "AI が主語になる"],
        "banal_ideas": [
            "ロボットみたいなAI",
            "冷たいAI",
            "仕事を奪うAI",
            "すぐバグるAI",
            "人の言うことを聞かないAI",
        ],
    }


def _memo() -> AnalysisMemo:
    return AnalysisMemo.model_validate(_memo_payload())


def _agent_cfg(*, model: str, temperature: float) -> AgentLLMConfig:
    return AgentLLMConfig(model=model, temperature=temperature)


def _app_config(*, temperature: float, model: str) -> AppConfig:
    low = _agent_cfg(model="openrouter/other", temperature=0.2)
    return AppConfig(
        openrouter=OpenRouterConfig(base_url="https://openrouter.ai/api/v1"),
        agents=AgentsConfig(
            seated_writer=low,
            coordinator=low,
            respondent=_agent_cfg(model="openrouter/respondent", temperature=0.9),
            tsukkomi=_agent_cfg(model=model, temperature=temperature),
            polisher=low,
        ),
        eval=EvalConfig(
            judge=_agent_cfg(model="openrouter/eval-judge", temperature=0.0)
        ),
    )


def _candidate_payload(
    respondent_id: str, index: int, *, text: str | None = None
) -> dict[str, str]:
    idea = text if text is not None else f"案-{respondent_id}-{index}"
    return {
        "candidate_id": f"{respondent_id}-{index}",
        "respondent_id": respondent_id,
        "text": idea,
    }


def _batch_payload(respondent_id: str, *, n: int = 7) -> dict[str, object]:
    return {
        "respondent_id": respondent_id,
        "candidates": [_candidate_payload(respondent_id, i) for i in range(1, n + 1)],
    }


def _batch(respondent_id: str, *, n: int = 7) -> CandidateBatch:
    return CandidateBatch.model_validate(_batch_payload(respondent_id, n=n))


def _all_candidates(
    *batches: CandidateBatch,
) -> tuple[Candidate, ...]:
    return tuple(item for batch in batches for item in batch.candidates)


def _note_payload(
    candidate: Candidate,
    *,
    dropped: bool = False,
    score: float = 8.0,
    tsukkomi: str | None = None,
) -> dict[str, object]:
    if tsukkomi is not None:
        comment = tsukkomi
    elif dropped:
        comment = f"{candidate.candidate_id}はツッコミ不能"
    else:
        comment = f"{candidate.candidate_id}へのツッコミ"
    return {
        "candidate_id": candidate.candidate_id,
        "tsukkomi": comment,
        "dropped": dropped,
        "score": score,
    }


def _selected_payload(
    candidate: Candidate, *, text: str | None = None
) -> dict[str, str]:
    return {
        "candidate_id": candidate.candidate_id,
        "respondent_id": candidate.respondent_id,
        "text": candidate.text if text is None else text,
    }


def _shortlist_payload(
    candidates: tuple[Candidate, ...],
    *,
    drop_ids: set[str] | None = None,
    selected_ids: list[str] | None = None,
    rewrite_text: str | None = None,
    notes: list[dict[str, object]] | None = None,
    selected: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    dropped = drop_ids if drop_ids is not None else set()
    kept = [item for item in candidates if item.candidate_id not in dropped]
    chosen_ids = (
        selected_ids
        if selected_ids is not None
        else [item.candidate_id for item in kept[:5]]
    )
    by_id = {item.candidate_id: item for item in candidates}
    if notes is None:
        notes = [
            _note_payload(item, dropped=item.candidate_id in dropped)
            for item in candidates
        ]
    if selected is None:
        selected = []
        for candidate_id in chosen_ids:
            original = by_id[candidate_id]
            selected.append(
                _selected_payload(
                    original,
                    text=rewrite_text if rewrite_text is not None else None,
                )
            )
    return {"notes": notes, "selected": selected}


def _queue_review(fake_llm, payload: dict[str, object]) -> None:
    fake_llm.responses.append(json.dumps(payload, ensure_ascii=False))


def test_shortlist_requires_exactly_five_selected() -> None:
    candidates = _all_candidates(_batch("r1"))
    payload = _shortlist_payload(candidates)
    shortlist = Shortlist.model_validate(payload)
    assert len(shortlist.selected) == 5
    assert len(shortlist.notes) == 7
    assert all(note.tsukkomi for note in shortlist.notes)


@pytest.mark.parametrize("count", [4, 6])
def test_shortlist_rejects_selected_count_other_than_five(count: int) -> None:
    candidates = _all_candidates(_batch("r1"))
    payload = _shortlist_payload(
        candidates,
        selected_ids=[item.candidate_id for item in candidates[:count]],
    )
    with pytest.raises(ValidationError):
        Shortlist.model_validate(payload)


def test_shortlist_rejects_dropped_selected() -> None:
    candidates = _all_candidates(_batch("r1"))
    payload = _shortlist_payload(
        candidates,
        drop_ids={candidates[0].candidate_id},
        selected_ids=[item.candidate_id for item in candidates[:5]],
    )
    with pytest.raises(ValidationError, match="ツッコミ不能"):
        Shortlist.model_validate(payload)


def test_empty_tsukkomi_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TsukkomiNote.model_validate(
            {
                "candidate_id": "r1-1",
                "tsukkomi": "   ",
                "dropped": False,
                "score": 1.0,
            }
        )


@pytest.mark.parametrize("score", [0.0, 10.0, 8])
def test_score_in_range_is_accepted(score: float) -> None:
    note = TsukkomiNote.model_validate(
        {
            "candidate_id": "r1-1",
            "tsukkomi": "ツッコミ",
            "dropped": False,
            "score": score,
        }
    )
    assert note.score == score


@pytest.mark.parametrize("score", [-0.1, 10.1, float("nan"), float("inf")])
def test_score_out_of_range_is_rejected(score: float) -> None:
    with pytest.raises(ValidationError):
        TsukkomiNote.model_validate(
            {
                "candidate_id": "r1-1",
                "tsukkomi": "ツッコミ",
                "dropped": False,
                "score": score,
            }
        )


def test_extra_fields_on_shortlist_are_rejected() -> None:
    candidates = _all_candidates(_batch("r1"))
    payload = _shortlist_payload(candidates)
    payload["new_joke"] = "足したネタ"
    with pytest.raises(ValidationError):
        Shortlist.model_validate(payload)


def test_shortlist_models_are_frozen() -> None:
    candidates = _all_candidates(_batch("r1"))
    shortlist = Shortlist.model_validate(_shortlist_payload(candidates))
    with pytest.raises(ValidationError):
        shortlist.selected[0].text = "書き換え"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        shortlist.notes[0].tsukkomi = "別文"  # type: ignore[misc]


def test_tsukkomi_temperature_is_low_in_config() -> None:
    cfg = load_config(ROOT / "config.toml")
    assert cfg.agents.tsukkomi.temperature == 0.2


def test_review_returns_five_with_notes_for_all(fake_llm) -> None:
    batch = _batch("r1")
    candidates = _all_candidates(batch)
    drop_ids = {candidates[5].candidate_id, candidates[6].candidate_id}
    _queue_review(fake_llm, _shortlist_payload(candidates, drop_ids=drop_ids))
    shortlist = review(THEME, _memo(), (batch,))
    assert len(shortlist.selected) == 5
    assert len(shortlist.notes) == 7
    note_ids = {note.candidate_id for note in shortlist.notes}
    assert note_ids == {item.candidate_id for item in candidates}
    assert all(note.tsukkomi.strip() for note in shortlist.notes)
    dropped = {note.candidate_id for note in shortlist.notes if note.dropped}
    assert dropped == drop_ids
    selected_ids = {item.candidate_id for item in shortlist.selected}
    assert selected_ids.isdisjoint(dropped)


def test_dropped_candidates_are_not_selected(fake_llm) -> None:
    batch = _batch("r1")
    candidates = _all_candidates(batch)
    drop_ids = {candidates[0].candidate_id}
    _queue_review(
        fake_llm,
        _shortlist_payload(
            candidates,
            drop_ids=drop_ids,
            selected_ids=[item.candidate_id for item in candidates[:5]],
        ),
    )
    with pytest.raises(TsukkomiError, match="ツッコミ不能"):
        review(THEME, _memo(), (batch,))


def test_selected_texts_match_input_even_if_llm_rewrites(fake_llm) -> None:
    batch = _batch("r1")
    candidates = _all_candidates(batch)
    originals = {item.candidate_id: item.text for item in candidates}
    _queue_review(
        fake_llm,
        _shortlist_payload(candidates, rewrite_text="言い換えた本文"),
    )
    shortlist = review(THEME, _memo(), (batch,))
    assert len(shortlist.selected) == 5
    for item in shortlist.selected:
        assert item.text == originals[item.candidate_id]
        assert item.text != "言い換えた本文"


def test_review_reads_temperature_and_model_from_config(fake_llm) -> None:
    batch = _batch("r1")
    candidates = _all_candidates(batch)
    _queue_review(fake_llm, _shortlist_payload(candidates))
    cfg = _app_config(temperature=0.15, model="openrouter/tsukkomi-test")
    review(THEME, _memo(), (batch,), config=cfg)
    assert fake_llm.calls[0]["temperature"] == 0.15
    assert fake_llm.calls[0]["model"] == "openrouter/tsukkomi-test"
    assert fake_llm.calls[0]["role"] == "tsukkomi"
    assert "api_key" not in fake_llm.calls[0]


def test_prompt_includes_theme_memo_and_all_candidates(fake_llm) -> None:
    batches = (_batch("r1"), _batch("r2"))
    candidates = _all_candidates(*batches)
    _queue_review(fake_llm, _shortlist_payload(candidates))
    memo = _memo()
    review(THEME, memo, batches)
    prompt = fake_llm.calls[0]["prompt"]
    assert THEME in prompt
    assert "{{theme}}" not in prompt
    assert "{{analysis_memo}}" not in prompt
    assert "{{candidate_batch}}" not in prompt
    dumped = json.dumps(memo.model_dump(), ensure_ascii=False)
    assert dumped in prompt
    for item in candidates:
        assert item.candidate_id in prompt
        assert item.text in prompt


def test_missing_note_is_rejected(fake_llm) -> None:
    batch = _batch("r1")
    candidates = _all_candidates(batch)
    payload = _shortlist_payload(candidates)
    payload["notes"] = [
        note
        for note in payload["notes"]
        if note["candidate_id"] != candidates[-1].candidate_id
    ]
    _queue_review(fake_llm, payload)
    with pytest.raises(TsukkomiError, match="残存全案"):
        review(THEME, _memo(), (batch,))


def test_fewer_than_five_selected_from_llm_is_rejected(fake_llm) -> None:
    batch = _batch("r1")
    candidates = _all_candidates(batch)
    payload = _shortlist_payload(
        candidates,
        selected_ids=[item.candidate_id for item in candidates[:4]],
    )
    _queue_review(fake_llm, payload)
    with pytest.raises(TsukkomiError, match="スキーマ"):
        review(THEME, _memo(), (batch,))


def test_duplicate_selected_forms_are_rejected(fake_llm) -> None:
    payload = _batch_payload("r1")
    payload["candidates"][1]["text"] = payload["candidates"][0]["text"]
    batch = CandidateBatch.model_validate(payload)
    candidates = _all_candidates(batch)
    _queue_review(
        fake_llm,
        _shortlist_payload(
            candidates,
            selected_ids=[item.candidate_id for item in candidates[:5]],
        ),
    )
    with pytest.raises(TsukkomiError, match="同じ形"):
        review(THEME, _memo(), (batch,))


def test_unknown_selected_id_is_rejected(fake_llm) -> None:
    batch = _batch("r1")
    candidates = _all_candidates(batch)
    payload = _shortlist_payload(candidates)
    payload["selected"][0]["candidate_id"] = "unknown"
    _queue_review(fake_llm, payload)
    with pytest.raises(TsukkomiError, match="未知"):
        review(THEME, _memo(), (batch,))


def test_llm_non_json_is_rejected(fake_llm) -> None:
    fake_llm.responses.append("これは JSON ではない")
    with pytest.raises(TsukkomiError, match="JSON"):
        review(THEME, _memo(), (_batch("r1"),))


def test_prompt_file_exists_with_schema_and_placeholders() -> None:
    assert PROMPT_PATH.is_file()
    text = PROMPT_PATH.read_text(encoding="utf-8")
    for placeholder in ("{{theme}}", "{{analysis_memo}}", "{{candidate_batch}}"):
        assert placeholder in text
    assert "notes" in text
    assert "selected" in text
    assert "5" in text
    assert "temperature=" not in text.lower()
    assert PROMPT_MARKER in text
    assert "同じ軸" in text
    assert "同じ形" in text


def test_prompt_body_is_not_embedded_in_src() -> None:
    assert PROMPT_MARKER in PROMPT_PATH.read_text(encoding="utf-8")
    for path in (ROOT / "src").rglob("*.py"):
        assert PROMPT_MARKER not in path.read_text(encoding="utf-8")


def test_prompt_drops_long_and_template_answers() -> None:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert "落とす" in text
    assert "逆張り" in text
    assert "時事" in text
    assert "説明が長い" in text
    assert "短縮" in text
    assert "対話" in text
