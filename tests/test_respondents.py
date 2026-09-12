"""回答者 n 体（SRS-MVP-FN-014〜016、QA-003）。"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from pydantic import ValidationError

from oogiri.agents.respondent import RespondentError, respond
from oogiri.config import load_config
from oogiri.contracts.analysis import AnalysisMemo
from oogiri.contracts.candidates import Candidate, CandidateBatch
from oogiri.contracts.roster import RespondentSpec, Roster, StyleAxis

ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "prompts" / "respondent.md"
PROMPT_MARKER = "他回答者の案は見ない。"
ALLOWED_CALL_KEYS = {"prompt", "model", "temperature", "role", "respondent_id"}


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


def _axis(index: int) -> StyleAxis:
    return StyleAxis(name=f"軸{index}", description=f"笑い方{index}")


def _prompt_for(respondent_id: str, memo: AnalysisMemo) -> str:
    memo_json = json.dumps(memo.model_dump(), ensure_ascii=False)
    return (
        f"theme=こんなAIはいやだ。どんなAI？\n"
        f"memo={memo_json}\n"
        f"id={respondent_id}\n"
        f"style=STYLE_{respondent_id}\n"
    )


def _spec(
    respondent_id: str, memo: AnalysisMemo, *, temperature: float = 0.9
) -> RespondentSpec:
    index = int(respondent_id.removeprefix("r"))
    return RespondentSpec(
        respondent_id=respondent_id,
        axis=_axis(index),
        system_prompt=_prompt_for(respondent_id, memo),
        model="openrouter/respondent-test",
        temperature=temperature,
    )


def _roster(memo: AnalysisMemo, *, n: int = 3) -> Roster:
    specs = tuple(_spec(f"r{i}", memo) for i in range(1, n + 1))
    axes = tuple(spec.axis for spec in specs)
    return Roster(axes=axes, respondents=specs)


def _candidate(
    respondent_id: str, index: int, *, text: str | None = None
) -> dict[str, str]:
    idea = text if text is not None else f"IDEA_{respondent_id}_{index}"
    return {
        "candidate_id": f"{respondent_id}-{index}",
        "respondent_id": respondent_id,
        "text": idea,
    }


def _batch_payload(respondent_id: str, *, n: int = 7) -> dict[str, object]:
    return {
        "respondent_id": respondent_id,
        "candidates": [_candidate(respondent_id, i) for i in range(n)],
    }


def _batch_json(respondent_id: str, *, n: int = 7) -> str:
    return json.dumps(_batch_payload(respondent_id, n=n), ensure_ascii=False)


def _queue_batches(fake_llm, respondent_ids: list[str], *, n: int = 7) -> None:
    for respondent_id in respondent_ids:
        fake_llm.responses.append(_batch_json(respondent_id, n=n))


def _calls_by_id(fake_llm) -> dict[str, dict[str, object]]:
    return {call["respondent_id"]: call for call in fake_llm.calls}


def test_candidate_batch_requires_seven_or_more() -> None:
    payload = _batch_payload("r1", n=7)
    batch = CandidateBatch.model_validate(payload)
    assert len(batch.candidates) == 7
    payload_eight = _batch_payload("r1", n=8)
    assert len(CandidateBatch.model_validate(payload_eight).candidates) == 8


@pytest.mark.parametrize("count", [0, 6])
def test_candidate_batch_rejects_fewer_than_seven(count: int) -> None:
    with pytest.raises(ValidationError):
        CandidateBatch.model_validate(_batch_payload("r1", n=count))


def test_empty_candidate_text_is_rejected() -> None:
    payload = _batch_payload("r1")
    payload["candidates"][0]["text"] = "   "
    with pytest.raises(ValidationError):
        CandidateBatch.model_validate(payload)


def test_mismatched_candidate_respondent_id_is_rejected() -> None:
    payload = _batch_payload("r1")
    payload["candidates"][0]["respondent_id"] = "r2"
    with pytest.raises(ValidationError, match="回答者 ID"):
        CandidateBatch.model_validate(payload)


def test_duplicate_candidate_ids_in_batch_are_rejected() -> None:
    payload = _batch_payload("r1")
    payload["candidates"][1]["candidate_id"] = payload["candidates"][0]["candidate_id"]
    with pytest.raises(ValidationError, match="重複"):
        CandidateBatch.model_validate(payload)


def test_extra_fields_on_batch_are_rejected() -> None:
    payload = _batch_payload("r1")
    payload["peer_ideas"] = ["他回答者の案"]
    with pytest.raises(ValidationError):
        CandidateBatch.model_validate(payload)


def test_respond_returns_seven_or_more_per_respondent(fake_llm) -> None:
    memo = _memo()
    roster = _roster(memo)
    _queue_batches(fake_llm, ["r1", "r2", "r3"])
    batches = respond(memo, roster)
    assert len(batches) == 3
    assert [batch.respondent_id for batch in batches] == ["r1", "r2", "r3"]
    for batch in batches:
        assert len(batch.candidates) >= 7
        assert all(
            item.respondent_id == batch.respondent_id for item in batch.candidates
        )


def test_respondents_run_in_parallel(fake_llm) -> None:
    memo = _memo()
    roster = _roster(memo, n=3)
    fake_llm.release_gate = threading.Barrier(3, timeout=5)
    _queue_batches(fake_llm, ["r1", "r2", "r3"])
    respond(memo, roster)
    assert fake_llm.max_in_flight == 3
    assert len(fake_llm.calls) == 3


def test_each_call_uses_high_temperature(fake_llm) -> None:
    memo = _memo()
    roster = _roster(memo)
    _queue_batches(fake_llm, ["r1", "r2", "r3"])
    respond(memo, roster)
    for call in fake_llm.calls:
        assert call["temperature"] >= 0.5
        assert call["role"] == "respondent"
        assert call["model"] == "openrouter/respondent-test"


def test_respondent_temperature_is_high_in_config() -> None:
    cfg = load_config(ROOT / "config.toml")
    assert cfg.agents.respondent.temperature == 0.9


def test_analysis_memo_is_in_every_respondent_input(fake_llm) -> None:
    memo = _memo()
    roster = _roster(memo)
    _queue_batches(fake_llm, ["r1", "r2", "r3"])
    respond(memo, roster)
    dumped = json.dumps(memo.model_dump(), ensure_ascii=False)
    for call in fake_llm.calls:
        prompt = call["prompt"]
        assert dumped in prompt
        assert memo.theme_type in prompt
        for premise in memo.premises:
            assert premise in prompt
        for idea in memo.banal_ideas:
            assert idea in prompt


def test_missing_analysis_memo_is_rejected_before_llm(fake_llm) -> None:
    memo = _memo()
    specs = []
    for i in range(1, 4):
        spec = _spec(f"r{i}", memo)
        specs.append(spec.model_copy(update={"system_prompt": f"id=r{i} STYLE_r{i}"}))
    roster = Roster(axes=tuple(spec.axis for spec in specs), respondents=tuple(specs))
    with pytest.raises(RespondentError, match="分析メモ"):
        respond(memo, roster)
    assert fake_llm.calls == []


def test_input_does_not_include_other_respondents(fake_llm) -> None:
    memo = _memo()
    roster = _roster(memo)
    _queue_batches(fake_llm, ["r1", "r2", "r3"])
    respond(memo, roster)
    by_id = _calls_by_id(fake_llm)
    for spec in roster.respondents:
        call = by_id[spec.respondent_id]
        assert call["prompt"] == spec.system_prompt
        assert set(call) <= ALLOWED_CALL_KEYS
        for other in roster.respondents:
            if other.respondent_id == spec.respondent_id:
                continue
            assert other.respondent_id not in call["prompt"]
            assert f"STYLE_{other.respondent_id}" not in call["prompt"]


def test_input_does_not_include_peer_candidate_texts(fake_llm) -> None:
    memo = _memo()
    roster = _roster(memo)
    _queue_batches(fake_llm, ["r1", "r2", "r3"])
    batches = respond(memo, roster)
    peer_texts = [item.text for batch in batches for item in batch.candidates]
    for call in fake_llm.calls:
        for text in peer_texts:
            assert text not in call["prompt"]


def test_llm_respondent_id_is_overwritten_from_spec(fake_llm) -> None:
    memo = _memo()
    roster = _roster(memo, n=1)
    payload = _batch_payload("wrong-id", n=7)
    fake_llm.responses.append(json.dumps(payload, ensure_ascii=False))
    batches = respond(memo, roster)
    assert batches[0].respondent_id == "r1"
    assert all(item.respondent_id == "r1" for item in batches[0].candidates)


def test_fewer_than_seven_from_llm_is_rejected(fake_llm) -> None:
    memo = _memo()
    roster = _roster(memo)
    fake_llm.responses.extend(
        [
            _batch_json("r1", n=6),
            _batch_json("r2", n=7),
            _batch_json("r3", n=7),
        ]
    )
    with pytest.raises(RespondentError, match="スキーマ"):
        respond(memo, roster)


def test_simple_candidate_ids_are_namespaced_per_respondent(fake_llm) -> None:
    memo = _memo()
    roster = _roster(memo)
    shared = {
        "respondent_id": "ignored",
        "candidates": [
            {
                "candidate_id": str(index),
                "respondent_id": "ignored",
                "text": f"案{index}",
            }
            for index in range(1, 8)
        ],
    }
    fake_llm.responses.extend([json.dumps(shared, ensure_ascii=False)] * 3)
    batches = respond(memo, roster)
    ids = [item.candidate_id for batch in batches for item in batch.candidates]
    assert len(ids) == len(set(ids))
    for spec, batch in zip(roster.respondents, batches, strict=True):
        prefix = f"{spec.respondent_id}:"
        for item in batch.candidates:
            assert item.candidate_id.startswith(prefix)


def test_duplicate_ids_in_one_respondent_are_still_rejected(fake_llm) -> None:
    memo = _memo()
    roster = _roster(memo, n=1)
    payload = _batch_payload("r1")
    payload["candidates"][1]["candidate_id"] = payload["candidates"][0]["candidate_id"]
    fake_llm.responses.append(json.dumps(payload, ensure_ascii=False))
    with pytest.raises(RespondentError, match="スキーマ"):
        respond(memo, roster)


def test_llm_non_json_is_rejected(fake_llm) -> None:
    memo = _memo()
    roster = _roster(memo, n=1)
    fake_llm.responses.append("これは JSON ではない")
    with pytest.raises(RespondentError, match="JSON"):
        respond(memo, roster)


def test_prompt_file_exists_with_schema_and_placeholders() -> None:
    assert PROMPT_PATH.is_file()
    text = PROMPT_PATH.read_text(encoding="utf-8")
    for placeholder in (
        "{{theme}}",
        "{{analysis_memo}}",
        "{{respondent_id}}",
        "{{axis_name}}",
        "{{axis_description}}",
        "{{style_instructions}}",
    ):
        assert placeholder in text
    assert "candidates" in text
    assert "7" in text
    assert "temperature=" not in text.lower()
    assert PROMPT_MARKER in text


def test_prompt_body_is_not_embedded_in_src() -> None:
    assert PROMPT_MARKER in PROMPT_PATH.read_text(encoding="utf-8")
    for path in (ROOT / "src").rglob("*.py"):
        assert PROMPT_MARKER not in path.read_text(encoding="utf-8")


def test_candidate_model_is_frozen() -> None:
    candidate = Candidate.model_validate(_candidate("r1", 0))
    with pytest.raises(ValidationError):
        candidate.text = "書き換え"  # type: ignore[misc]
