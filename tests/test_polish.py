"""推敲役（SRS-MVP-FN-022〜027、QA-003）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from oogiri.agents.polisher import PolishError, polish
from oogiri.config import (
    AgentLLMConfig,
    AgentsConfig,
    AppConfig,
    EvalConfig,
    OpenRouterConfig,
    load_config,
)
from oogiri.contracts.candidates import Candidate
from oogiri.contracts.polished import PolishedAnswer
from oogiri.contracts.shortlist import Shortlist, TsukkomiNote

ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "prompts" / "polisher.md"
PROMPT_MARKER = "選ばなかった 4 案の要素を混ぜて新しい内容を作ってはならない。"
THEME = "こんなAIはいやだ。どんなAI？"

# 検出用フィクスチャ。5 案のいずれにも含まれない固有名詞・事実。
FORBIDDEN_ADDITIONS = (
    "ニューヨーク証券取引所",
    "消費税率は八パーセント",
    "NASA火星基地の食堂",
)

SELECTED_TEXTS = (
    "朝のアラームを二度寝の権利と誤認するAI",
    "傘を差したまま満員電車に乗るAI",
    "充電器を挿したまま外出するAI",
    "既読無視を省エネだと主張するAI",
    "エスカレーターの片側を歩き続けるAI",
)
POLISHED_TEXT = "アラームを二度寝の権利と誤認するAI"
DROPPED_TSUKKOMI = "この案はツッコミ不能だから落とす"
LOSER_TSUKKOMI = "形が他と重なるので選ばない"


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
            tsukkomi=low,
            polisher=_agent_cfg(model=model, temperature=temperature),
        ),
        eval=EvalConfig(
            judge=_agent_cfg(model="openrouter/eval-judge", temperature=0.0)
        ),
    )


def _candidate(candidate_id: str, text: str) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        respondent_id="r1",
        text=text,
    )


def _note(
    candidate_id: str,
    tsukkomi: str,
    *,
    dropped: bool = False,
    score: float = 8.0,
) -> TsukkomiNote:
    return TsukkomiNote(
        candidate_id=candidate_id,
        tsukkomi=tsukkomi,
        dropped=dropped,
        score=score,
    )


def _shortlist() -> Shortlist:
    selected = tuple(
        _candidate(f"r1-{index}", text)
        for index, text in enumerate(SELECTED_TEXTS, start=1)
    )
    notes = tuple(
        _note(item.candidate_id, f"{item.candidate_id}へのツッコミ")
        for item in selected
    ) + (
        _note("r1-6", DROPPED_TSUKKOMI, dropped=True, score=0.0),
        _note("r1-7", LOSER_TSUKKOMI, dropped=False, score=3.0),
    )
    return Shortlist(selected=selected, notes=notes)


def _queue_answer(fake_llm, text: str = POLISHED_TEXT) -> None:
    fake_llm.responses.append(json.dumps({"text": text}, ensure_ascii=False))


def test_polished_answer_is_one_nonempty_text() -> None:
    answer = PolishedAnswer.model_validate({"text": POLISHED_TEXT})
    assert answer.text == POLISHED_TEXT


def test_empty_text_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PolishedAnswer.model_validate({"text": "   "})


def test_extra_fields_on_answer_are_rejected() -> None:
    with pytest.raises(ValidationError):
        PolishedAnswer.model_validate({"text": POLISHED_TEXT, "image": "画像"})


def test_polished_answer_is_frozen() -> None:
    answer = PolishedAnswer(text=POLISHED_TEXT)
    with pytest.raises(ValidationError):
        answer.text = "書き換え"  # type: ignore[misc]


def test_polisher_temperature_is_low_in_config() -> None:
    cfg = load_config(ROOT / "config.toml")
    assert cfg.agents.polisher.temperature == 0.2


def test_polish_returns_exactly_one_text(fake_llm) -> None:
    _queue_answer(fake_llm)
    answer = polish(THEME, _shortlist())
    assert answer.text == POLISHED_TEXT
    assert answer.text.count("AI") >= 1


def test_forbidden_additions_are_absent_from_output(fake_llm) -> None:
    shortlist = _shortlist()
    blob = " ".join(item.text for item in shortlist.selected)
    for noun in FORBIDDEN_ADDITIONS:
        assert noun not in blob
    _queue_answer(fake_llm)
    answer = polish(THEME, shortlist)
    prompt = fake_llm.calls[0]["prompt"]
    for noun in FORBIDDEN_ADDITIONS:
        assert noun not in answer.text
        assert noun not in prompt


def test_prompt_and_code_limit_edits_to_three_operations() -> None:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert "削る" in prompt
    assert "オチ" in prompt
    assert "語尾" in prompt
    assert "内容を追加" in prompt
    source = (ROOT / "src" / "oogiri" / "agents" / "polisher.py").read_text(
        encoding="utf-8"
    )
    assert "低温" in source
    assert "PolishedAnswer" in source
    assert "image" not in source.lower()


def test_prompt_excludes_dropped_and_losing_notes(fake_llm) -> None:
    _queue_answer(fake_llm)
    shortlist = _shortlist()
    polish(THEME, shortlist)
    prompt = fake_llm.calls[0]["prompt"]
    for item in shortlist.selected:
        assert item.candidate_id in prompt
        assert item.text in prompt
        assert f"{item.candidate_id}へのツッコミ" in prompt
    assert DROPPED_TSUKKOMI not in prompt
    assert LOSER_TSUKKOMI not in prompt
    assert "{{theme}}" not in prompt
    assert "{{shortlist}}" not in prompt


def test_polish_reads_temperature_and_model_from_config(fake_llm) -> None:
    _queue_answer(fake_llm)
    cfg = _app_config(temperature=0.15, model="openrouter/polisher-test")
    polish(THEME, _shortlist(), config=cfg)
    assert fake_llm.calls[0]["temperature"] == 0.15
    assert fake_llm.calls[0]["model"] == "openrouter/polisher-test"
    assert fake_llm.calls[0]["role"] == "polisher"
    assert "api_key" not in fake_llm.calls[0]


def test_theme_placeholder_text_is_not_resubstituted(fake_llm) -> None:
    theme = "これは {{shortlist}} を含むお題"
    _queue_answer(fake_llm)
    polish(theme, _shortlist())
    prompt = fake_llm.calls[0]["prompt"]
    assert theme in prompt


def test_llm_list_output_is_rejected(fake_llm) -> None:
    fake_llm.responses.append(json.dumps(["案A", "案B"], ensure_ascii=False))
    with pytest.raises(PolishError, match="オブジェクト"):
        polish(THEME, _shortlist())


def test_llm_two_field_answers_are_rejected(fake_llm) -> None:
    fake_llm.responses.append(
        json.dumps({"text": POLISHED_TEXT, "second": "別案"}, ensure_ascii=False)
    )
    with pytest.raises(PolishError, match="スキーマ"):
        polish(THEME, _shortlist())


def test_llm_non_json_is_rejected(fake_llm) -> None:
    fake_llm.responses.append("これは JSON ではない")
    with pytest.raises(PolishError, match="JSON"):
        polish(THEME, _shortlist())


def test_prompt_file_exists_with_schema_and_placeholders() -> None:
    assert PROMPT_PATH.is_file()
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert "{{theme}}" in text
    assert "{{shortlist}}" in text
    assert "`text`" in text
    assert "内容を追加" in text
    assert "画像" in text
    assert "temperature=" not in text.lower()
    assert PROMPT_MARKER in text


def test_prompt_body_is_not_embedded_in_src() -> None:
    assert PROMPT_MARKER in PROMPT_PATH.read_text(encoding="utf-8")
    for path in (ROOT / "src").rglob("*.py"):
        assert PROMPT_MARKER not in path.read_text(encoding="utf-8")


def test_prompt_strips_quotes_and_picks_shortest() -> None:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert "引用符" in text
    assert "導入" in text
    assert "最短" in text
    assert "別案の語" in text
    assert "体言止め" in text
