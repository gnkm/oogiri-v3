"""座付き作家（SRS-MVP-FN-008〜010、QA-003）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from oogiri.agents.seated_writer import AnalysisError, analyze
from oogiri.config import (
    AgentLLMConfig,
    AgentsConfig,
    AppConfig,
    EvalConfig,
    OpenRouterConfig,
    load_config,
)
from oogiri.contracts.analysis import AnalysisMemo

ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "prompts" / "seated_writer.md"
PROMPT_MARKER = "座付き作家は分析だけを行い回答本文を書かない"


def _valid_payload() -> dict[str, object]:
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


def _agent_cfg(*, model: str, temperature: float) -> AgentLLMConfig:
    return AgentLLMConfig(model=model, temperature=temperature)


def _app_config(*, writer_temperature: float, writer_model: str) -> AppConfig:
    writer = _agent_cfg(model=writer_model, temperature=writer_temperature)
    other_low = _agent_cfg(model="openrouter/other", temperature=0.2)
    return AppConfig(
        openrouter=OpenRouterConfig(base_url="https://openrouter.ai/api/v1"),
        agents=AgentsConfig(
            seated_writer=writer,
            coordinator=other_low,
            respondent=_agent_cfg(model="openrouter/respondent", temperature=0.9),
            tsukkomi=other_low,
            polisher=other_low,
        ),
        eval=EvalConfig(
            judge=_agent_cfg(model="openrouter/eval-judge", temperature=0.0)
        ),
    )


def test_analysis_memo_has_required_fields() -> None:
    memo = AnalysisMemo.model_validate(_valid_payload())
    assert memo.theme_type == "定義付け"
    assert memo.humor_direction == "日常の不便を極端化する"
    assert len(memo.premises) == 3
    assert len(memo.banal_ideas) == 5


@pytest.mark.parametrize("count", [2, 4])
def test_premises_must_be_exactly_three(count: int) -> None:
    data = _valid_payload()
    data["premises"] = [f"前提{i}" for i in range(count)]
    with pytest.raises(ValidationError):
        AnalysisMemo.model_validate(data)


@pytest.mark.parametrize("count", [4, 6])
def test_banal_ideas_must_be_exactly_five(count: int) -> None:
    data = _valid_payload()
    data["banal_ideas"] = [f"凡庸{i}" for i in range(count)]
    with pytest.raises(ValidationError):
        AnalysisMemo.model_validate(data)


def test_empty_theme_type_is_rejected() -> None:
    data = _valid_payload()
    data["theme_type"] = "   "
    with pytest.raises(ValidationError):
        AnalysisMemo.model_validate(data)


def test_extra_fields_are_rejected() -> None:
    data = _valid_payload()
    data["final_answer"] = "これは回答案"
    with pytest.raises(ValidationError):
        AnalysisMemo.model_validate(data)


def test_memo_is_identical_for_every_respondent() -> None:
    memo = AnalysisMemo.model_validate(_valid_payload())
    dumped = memo.model_dump()
    copies = [AnalysisMemo.model_validate(dumped) for _ in range(3)]
    assert copies[0] == copies[1] == copies[2] == memo


def test_shared_memo_collections_are_immutable() -> None:
    memo = AnalysisMemo.model_validate(_valid_payload())
    assert isinstance(memo.premises, tuple)
    assert isinstance(memo.banal_ideas, tuple)
    with pytest.raises(AttributeError):
        memo.premises.append("追加の前提")  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        memo.banal_ideas.append("追加の凡庸案")  # type: ignore[attr-defined]


def test_seated_writer_temperature_is_low_in_config() -> None:
    cfg = load_config(ROOT / "config.toml")
    assert cfg.agents.seated_writer.temperature == 0.2


def test_analyze_returns_memo_via_fake_llm(fake_llm) -> None:
    payload = _valid_payload()
    fake_llm.responses.append(json.dumps(payload, ensure_ascii=False))
    memo = analyze("こんなAIはいやだ。どんなAI？")
    assert memo == AnalysisMemo.model_validate(payload)
    assert len(memo.premises) == 3
    assert len(memo.banal_ideas) == 5


def test_analyze_reads_temperature_and_model_from_config(fake_llm) -> None:
    fake_llm.responses.append(json.dumps(_valid_payload(), ensure_ascii=False))
    cfg = _app_config(writer_temperature=0.15, writer_model="openrouter/writer-test")
    analyze("お題", config=cfg)
    assert fake_llm.calls[0]["temperature"] == 0.15
    assert fake_llm.calls[0]["model"] == "openrouter/writer-test"
    assert fake_llm.calls[0]["role"] == "seated_writer"


def test_analyze_uses_llm_gateway_mock(fake_llm) -> None:
    fake_llm.responses.append(json.dumps(_valid_payload(), ensure_ascii=False))
    theme = "こんなAIはいやだ。どんなAI？"
    analyze(theme)
    assert len(fake_llm.calls) == 1
    prompt = fake_llm.calls[0]["prompt"]
    assert theme in prompt
    assert "{{theme}}" not in prompt
    assert "api_key" not in fake_llm.calls[0]


def test_llm_wrong_premise_count_is_rejected(fake_llm) -> None:
    payload = _valid_payload()
    payload["premises"] = ["前提A", "前提B"]
    fake_llm.responses.append(json.dumps(payload, ensure_ascii=False))
    with pytest.raises(AnalysisError, match="スキーマ"):
        analyze("お題")


def test_llm_non_json_is_rejected(fake_llm) -> None:
    fake_llm.responses.append("これは JSON ではない")
    with pytest.raises(AnalysisError, match="JSON"):
        analyze("お題")


def test_prompt_file_exists_with_schema_and_placeholder() -> None:
    assert PROMPT_PATH.is_file()
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert "{{theme}}" in text
    assert "theme_type" in text
    assert "humor_direction" in text
    assert "premises" in text
    assert "banal_ideas" in text
    assert "temperature=" not in text.lower()
    assert PROMPT_MARKER in text


def test_prompt_body_is_not_embedded_in_src() -> None:
    assert PROMPT_MARKER in PROMPT_PATH.read_text(encoding="utf-8")
    for path in (ROOT / "src").rglob("*.py"):
        assert PROMPT_MARKER not in path.read_text(encoding="utf-8")


def test_prompt_treats_premises_as_type_conditions() -> None:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert "型の条件" in text
    assert "こんな X はいやだ。どんな X？" in text
    assert "定義付け" in text
    assert "笑いの仕組み" in text
    assert "すぐ嘘" in text
    assert "毎回間違える" in text
    assert "逆を言う" in text
    assert "命令無視" in text
    assert "対話で説明する" in text
