"""回答者コーディネーター（SRS-MVP-FN-011〜013、QA-003）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from oogiri.agents.coordinator import CoordinatorError, coordinate
from oogiri.config import (
    AgentLLMConfig,
    AgentsConfig,
    AppConfig,
    OpenRouterConfig,
    load_config,
)
from oogiri.contracts.analysis import AnalysisMemo
from oogiri.contracts.roster import RespondentSpec, Roster, StyleAxis

ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "prompts" / "coordinator.md"
RESPONDENT_PROMPT_PATH = ROOT / "prompts" / "respondent.md"
PROMPT_MARKER = "軸の種類と数は固定しない。事前定義のリストからだけ選んではならない。"
RESPONDENT_MARKER = "他回答者の案は見ない。"
SEED_EXAMPLE_AXES = ("地味にリアル", "ずらし", "ワード")


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


def _axis(name: str, description: str) -> dict[str, str]:
    return {"name": name, "description": description}


def _valid_roster_payload(*, n: int = 3) -> dict[str, object]:
    axes = [
        _axis("極端な具体", "日常の細部を過剰に拾って落とす"),
        _axis("視点の逆転", "主語と被害を入れ替える"),
        _axis("語の衝突", "漢字と外来語をぶつける"),
    ]
    styles = [
        "小物と手順だけを積み、オチは最後の名詞に置く",
        "機械側の都合を主語にし、人間を環境として書く",
        "熟語の読みとカタカナを一文で交差させる",
        "同じ部屋の備品だけを使い、時間だけをずらす",
        "聞き手の予想する主語を最後まで出さない",
    ]
    chosen_axes = axes[: min(3, n)] if n > 1 else axes[:1]
    respondents = []
    for i in range(n):
        axis = chosen_axes[i % len(chosen_axes)]
        respondents.append(
            {
                "respondent_id": f"r{i + 1}",
                "axis": axis,
                "style_instructions": styles[i % len(styles)],
            }
        )
    return {"axes": chosen_axes, "respondents": respondents}


def _agent_cfg(*, model: str, temperature: float) -> AgentLLMConfig:
    return AgentLLMConfig(model=model, temperature=temperature)


def _app_config(
    *,
    coordinator_temperature: float = 0.4,
    coordinator_model: str = "openrouter/coordinator-test",
    respondent_temperature: float = 0.9,
    respondent_model: str = "openrouter/respondent-test",
) -> AppConfig:
    low = _agent_cfg(model="openrouter/other", temperature=0.2)
    return AppConfig(
        openrouter=OpenRouterConfig(base_url="https://openrouter.ai/api/v1"),
        agents=AgentsConfig(
            seated_writer=low,
            coordinator=_agent_cfg(
                model=coordinator_model, temperature=coordinator_temperature
            ),
            respondent=_agent_cfg(
                model=respondent_model, temperature=respondent_temperature
            ),
            tsukkomi=low,
            polisher=low,
        ),
    )


def test_roster_has_required_fields() -> None:
    payload = _valid_roster_payload()
    roster = Roster.model_validate(
        {
            "axes": payload["axes"],
            "respondents": [
                {
                    "respondent_id": item["respondent_id"],
                    "axis": item["axis"],
                    "system_prompt": f"prompt-{item['respondent_id']}",
                    "model": "openrouter/respondent-test",
                    "temperature": 0.9,
                }
                for item in payload["respondents"]
            ],
        }
    )
    assert len(roster.axes) >= 1
    assert len(roster.respondents) == 3
    for spec in roster.respondents:
        assert spec.system_prompt
        assert spec.model
        assert spec.temperature == 0.9


def test_axes_count_is_not_fixed() -> None:
    one = StyleAxis(name="極端な具体", description="細部を拾う")
    four = [
        StyleAxis(name=f"軸{i}", description=f"説明{i}") for i in range(1, 5)
    ]
    spec = RespondentSpec(
        respondent_id="r1",
        axis=one,
        system_prompt="p",
        model="openrouter/x",
        temperature=0.9,
    )
    Roster(axes=(one,), respondents=(spec,))
    specs = tuple(
        spec.model_copy(update={"respondent_id": f"r{i}", "axis": axis})
        for i, axis in enumerate(four, start=1)
    )
    Roster(axes=tuple(four), respondents=specs)


def test_empty_axis_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        StyleAxis(name="   ", description="説明")


def test_low_respondent_temperature_is_rejected() -> None:
    axis = StyleAxis(name="極端な具体", description="細部を拾う")
    with pytest.raises(ValidationError, match="高温"):
        RespondentSpec(
            respondent_id="r1",
            axis=axis,
            system_prompt="p",
            model="openrouter/x",
            temperature=0.2,
        )


def test_extra_fields_on_roster_are_rejected() -> None:
    payload = _valid_roster_payload()
    with pytest.raises(ValidationError):
        Roster.model_validate(
            {
                "axes": payload["axes"],
                "respondents": [
                    {
                        "respondent_id": "r1",
                        "axis": payload["axes"][0],
                        "system_prompt": "p",
                        "model": "openrouter/x",
                        "temperature": 0.9,
                    }
                ],
                "image_prompt": "画像を描け",
            }
        )


def test_coordinate_returns_n_specs_via_fake_llm(fake_llm) -> None:
    payload = _valid_roster_payload(n=3)
    fake_llm.responses.append(json.dumps(payload, ensure_ascii=False))
    roster = coordinate("こんなAIはいやだ。どんなAI？", _memo())
    assert len(roster.respondents) == 3
    ids = [spec.respondent_id for spec in roster.respondents]
    assert ids == ["r1", "r2", "r3"]
    for spec in roster.respondents:
        assert spec.system_prompt
        assert spec.model
        assert spec.temperature >= 0.5


def test_coordinate_honors_respondent_num(fake_llm) -> None:
    payload = _valid_roster_payload(n=5)
    fake_llm.responses.append(json.dumps(payload, ensure_ascii=False))
    roster = coordinate("お題", _memo(), respondent_num=5)
    assert len(roster.respondents) == 5


def test_respondents_are_split_by_axes(fake_llm) -> None:
    payload = _valid_roster_payload(n=3)
    fake_llm.responses.append(json.dumps(payload, ensure_ascii=False))
    roster = coordinate("お題", _memo())
    axis_names = {spec.axis.name for spec in roster.respondents}
    assert len(axis_names) == 3
    roster_axis_names = {axis.name for axis in roster.axes}
    for spec in roster.respondents:
        assert spec.axis.name in roster_axis_names


def test_custom_axes_are_accepted(fake_llm) -> None:
    payload = {
        "axes": [
            _axis("擬人化の過剰", "物に人格を足しすぎる"),
            _axis("手続きの欠落", "いちばん大事な手順を落とす"),
        ],
        "respondents": [
            {
                "respondent_id": "a",
                "axis": "擬人化の過剰",
                "style_instructions": "家電を先輩として敬語で責めさせる",
            },
            {
                "respondent_id": "b",
                "axis": "手続きの欠落",
                "style_instructions": "結論の手順だけが無いマニュアルにする",
            },
            {
                "respondent_id": "c",
                "axis": "擬人化の過剰",
                "style_instructions": "配線が愚痴を言うが中身は電圧の話にする",
            },
        ],
    }
    fake_llm.responses.append(json.dumps(payload, ensure_ascii=False))
    roster = coordinate("お題", _memo(), respondent_num=3)
    names = {axis.name for axis in roster.axes}
    assert names == {"擬人化の過剰", "手続きの欠落"}
    for banned in SEED_EXAMPLE_AXES:
        assert banned not in names


def test_seed_example_axes_are_not_forced_in_code() -> None:
    blob = (ROOT / "config.toml").read_text(encoding="utf-8")
    for path in (ROOT / "src").rglob("*.py"):
        blob += path.read_text(encoding="utf-8")
    for name in SEED_EXAMPLE_AXES:
        assert name not in blob
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert "次の三軸" not in prompt
    for name in SEED_EXAMPLE_AXES:
        assert name not in prompt


def test_system_prompt_uses_respondent_frame(fake_llm) -> None:
    payload = _valid_roster_payload(n=3)
    fake_llm.responses.append(json.dumps(payload, ensure_ascii=False))
    theme = "こんなAIはいやだ。どんなAI？"
    roster = coordinate(theme, _memo())
    frame = RESPONDENT_PROMPT_PATH.read_text(encoding="utf-8")
    assert "{{theme}}" in frame
    for spec, item in zip(roster.respondents, payload["respondents"], strict=True):
        assert theme in spec.system_prompt
        assert spec.respondent_id in spec.system_prompt
        assert item["style_instructions"] in spec.system_prompt
        assert item["axis"]["name"] in spec.system_prompt
        assert "{{style_instructions}}" not in spec.system_prompt
        assert "{{axis_name}}" not in spec.system_prompt


def test_coordinate_does_not_write_prompts(fake_llm) -> None:
    before_coordinator = PROMPT_PATH.read_text(encoding="utf-8")
    before_respondent = RESPONDENT_PROMPT_PATH.read_text(encoding="utf-8")
    src_py = {path: path.read_text(encoding="utf-8") for path in (ROOT / "src").rglob("*.py")}
    payload = _valid_roster_payload(n=3)
    fake_llm.responses.append(json.dumps(payload, ensure_ascii=False))
    coordinate("お題", _memo())
    assert PROMPT_PATH.read_text(encoding="utf-8") == before_coordinator
    assert RESPONDENT_PROMPT_PATH.read_text(encoding="utf-8") == before_respondent
    for path, text in src_py.items():
        assert path.read_text(encoding="utf-8") == text


def test_parameters_come_from_respondent_config(fake_llm) -> None:
    payload = _valid_roster_payload(n=3)
    payload["respondents"][0]["temperature"] = 0.1
    payload["respondents"][0]["model"] = "openrouter/should-not-stick"
    fake_llm.responses.append(json.dumps(payload, ensure_ascii=False))
    cfg = _app_config(
        respondent_temperature=0.9, respondent_model="openrouter/respondent-from-config"
    )
    roster = coordinate("お題", _memo(), config=cfg)
    for spec in roster.respondents:
        assert spec.temperature == 0.9
        assert spec.model == "openrouter/respondent-from-config"


def test_low_config_respondent_temperature_is_rejected(fake_llm) -> None:
    fake_llm.responses.append(json.dumps(_valid_roster_payload(), ensure_ascii=False))
    cfg = _app_config(respondent_temperature=0.2)
    with pytest.raises(CoordinatorError, match="高温"):
        coordinate("お題", _memo(), config=cfg)
    assert fake_llm.calls == []


def test_coordinate_reads_temperature_and_model_from_config(fake_llm) -> None:
    fake_llm.responses.append(json.dumps(_valid_roster_payload(), ensure_ascii=False))
    cfg = _app_config(
        coordinator_temperature=0.35, coordinator_model="openrouter/coord-test"
    )
    coordinate("お題", _memo(), config=cfg)
    assert fake_llm.calls[0]["temperature"] == 0.35
    assert fake_llm.calls[0]["model"] == "openrouter/coord-test"
    assert fake_llm.calls[0]["role"] == "coordinator"


def test_coordinate_uses_llm_gateway_mock(fake_llm) -> None:
    fake_llm.responses.append(json.dumps(_valid_roster_payload(), ensure_ascii=False))
    theme = "こんなAIはいやだ。どんなAI？"
    memo = _memo()
    coordinate(theme, memo)
    assert len(fake_llm.calls) == 1
    prompt = fake_llm.calls[0]["prompt"]
    assert theme in prompt
    assert "3" in prompt
    assert "{{theme}}" not in prompt
    assert "{{respondent_num}}" not in prompt
    assert "{{analysis_memo}}" not in prompt
    assert memo.theme_type in prompt
    assert "api_key" not in fake_llm.calls[0]


def test_wrong_respondent_count_is_rejected(fake_llm) -> None:
    fake_llm.responses.append(
        json.dumps(_valid_roster_payload(n=2), ensure_ascii=False)
    )
    with pytest.raises(CoordinatorError, match="回答者数"):
        coordinate("お題", _memo(), respondent_num=3)


def test_duplicate_ids_are_rejected(fake_llm) -> None:
    payload = _valid_roster_payload(n=3)
    payload["respondents"][2]["respondent_id"] = "r1"
    fake_llm.responses.append(json.dumps(payload, ensure_ascii=False))
    with pytest.raises(CoordinatorError, match="重複"):
        coordinate("お題", _memo())


def test_unknown_axis_is_rejected(fake_llm) -> None:
    payload = _valid_roster_payload(n=3)
    payload["respondents"][0]["axis"] = "存在しない軸"
    fake_llm.responses.append(json.dumps(payload, ensure_ascii=False))
    with pytest.raises(CoordinatorError, match="axes"):
        coordinate("お題", _memo())


def test_identical_axis_and_prompt_is_rejected(fake_llm) -> None:
    axis = _axis("極端な具体", "細部を拾う")
    payload = {
        "axes": [axis],
        "respondents": [
            {
                "respondent_id": "r1",
                "axis": axis,
                "style_instructions": "同じ指示",
            },
            {
                "respondent_id": "r2",
                "axis": axis,
                "style_instructions": "同じ指示",
            },
            {
                "respondent_id": "r3",
                "axis": axis,
                "style_instructions": "同じ指示",
            },
        ],
    }
    fake_llm.responses.append(json.dumps(payload, ensure_ascii=False))
    with pytest.raises(CoordinatorError, match="固ま"):
        coordinate("お題", _memo())


def test_llm_non_json_is_rejected(fake_llm) -> None:
    fake_llm.responses.append("これは JSON ではない")
    with pytest.raises(CoordinatorError, match="JSON"):
        coordinate("お題", _memo())


def test_prompt_file_exists_with_schema_and_placeholders() -> None:
    assert PROMPT_PATH.is_file()
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert "{{theme}}" in text
    assert "{{respondent_num}}" in text
    assert "{{analysis_memo}}" in text
    assert "axes" in text
    assert "respondents" in text
    assert "style_instructions" in text
    assert "temperature=" not in text.lower()
    assert PROMPT_MARKER in text


def test_respondent_prompt_file_has_placeholders() -> None:
    assert RESPONDENT_PROMPT_PATH.is_file()
    text = RESPONDENT_PROMPT_PATH.read_text(encoding="utf-8")
    for placeholder in (
        "{{theme}}",
        "{{analysis_memo}}",
        "{{respondent_id}}",
        "{{axis_name}}",
        "{{axis_description}}",
        "{{style_instructions}}",
    ):
        assert placeholder in text
    assert "temperature=" not in text.lower()
    assert RESPONDENT_MARKER in text


def test_prompt_body_is_not_embedded_in_src() -> None:
    assert PROMPT_MARKER in PROMPT_PATH.read_text(encoding="utf-8")
    assert RESPONDENT_MARKER in RESPONDENT_PROMPT_PATH.read_text(encoding="utf-8")
    for path in (ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert PROMPT_MARKER not in text
        assert RESPONDENT_MARKER not in text


def test_coordinator_temperature_is_configurable() -> None:
    cfg = load_config(ROOT / "config.toml")
    assert cfg.agents.coordinator.temperature == 0.4
    assert cfg.agents.respondent.temperature == 0.9
