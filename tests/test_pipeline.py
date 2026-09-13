"""generate パイプライン契約（SRS-MVP-FN-002、FN-007、DC-005）。"""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import click
import pytest
from crewai import Process
from typer.testing import CliRunner

from oogiri.cli import app
from oogiri.config import AppConfig, load_config
from oogiri.pipeline import (
    ROLE_COORDINATOR,
    ROLE_POLISHER,
    ROLE_SEATED_WRITER,
    ROLE_TSUKKOMI,
    build_crew,
    generate_answer,
    pipeline_roles,
)
from oogiri.progress import ProgressReporter
from oogiri.secrets import ENV_API_KEY

ROOT = Path(__file__).resolve().parents[1]
THEME = "こんなAIはいやだ。どんなAI？"
POLISHED_TEXT = "アラームを二度寝の権利と誤認するAI"
TEST_KEY = "oogiri-pipeline-test-key"
runner = CliRunner()


def _plain(result: click.testing.Result) -> str:
    blob = "\n".join(
        part for part in (result.stdout, result.stderr, result.output) if part
    )
    return click.unstyle(blob)


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


def _axis(name: str, description: str) -> dict[str, str]:
    return {"name": name, "description": description}


def _roster_payload(*, n: int) -> dict[str, object]:
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
    chosen = axes[:n] if n > 1 else axes[:1]
    respondents = []
    for index in range(n):
        axis = chosen[index % len(chosen)]
        respondents.append(
            {
                "respondent_id": f"r{index + 1}",
                "axis": axis,
                "style_instructions": styles[index % len(styles)],
            }
        )
    return {"axes": chosen, "respondents": respondents}


def _batch_payload(respondent_id: str) -> dict[str, object]:
    candidates = [
        {
            "candidate_id": str(index),
            "respondent_id": respondent_id,
            "text": f"{respondent_id}の案{index}",
        }
        for index in range(1, 8)
    ]
    return {"respondent_id": respondent_id, "candidates": candidates}


def _note(candidate_id: str, *, dropped: bool = False) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "tsukkomi": "不能" if dropped else f"{candidate_id}へのツッコミ",
        "dropped": dropped,
        "score": 0.0 if dropped else 8.0,
    }


def _shortlist_payload(*, n: int) -> dict[str, object]:
    ids = [f"r{r}:{index}" for r in range(1, n + 1) for index in range(1, 8)]
    selected_ids = ids[:5]
    notes = [_note(candidate_id) for candidate_id in ids]
    return {
        "notes": notes,
        "selected": [{"candidate_id": item} for item in selected_ids],
    }


def _queue_pipeline(fake_llm, *, n: int) -> None:
    fake_llm.responses.append(json.dumps(_memo_payload(), ensure_ascii=False))
    fake_llm.responses.append(json.dumps(_roster_payload(n=n), ensure_ascii=False))
    for index in range(1, n + 1):
        fake_llm.responses.append(
            json.dumps(_batch_payload(f"r{index}"), ensure_ascii=False)
        )
    fake_llm.responses.append(json.dumps(_shortlist_payload(n=n), ensure_ascii=False))
    fake_llm.responses.append(json.dumps({"text": POLISHED_TEXT}, ensure_ascii=False))


def _enable_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_API_KEY, TEST_KEY)


def _config() -> AppConfig:
    return load_config(ROOT / "config.toml")


def test_crew_order_matches_srs() -> None:
    crew = build_crew(theme=THEME, respondent_num=3, config=_config())
    expected = pipeline_roles(3)
    assert [agent.role for agent in crew.agents] == list(expected)
    assert [task.agent.role for task in crew.tasks] == list(expected)
    assert crew.process == Process.sequential
    assert expected[0] == ROLE_SEATED_WRITER
    assert expected[1] == ROLE_COORDINATOR
    assert expected[-2] == ROLE_TSUKKOMI
    assert expected[-1] == ROLE_POLISHER


def test_crew_respondent_count_follows_n() -> None:
    crew = build_crew(theme=THEME, respondent_num=2, config=_config())
    roles = [agent.role for agent in crew.agents]
    assert roles == list(pipeline_roles(2))
    assert [
        role for role in roles if role.startswith("回答者") and role != ROLE_COORDINATOR
    ] == ["回答者1", "回答者2"]
    respondent_tasks = [task for task in crew.tasks if task.async_execution]
    assert len(respondent_tasks) == 2


def test_generate_answer_returns_one_text(fake_llm) -> None:
    _queue_pipeline(fake_llm, n=3)
    answer = generate_answer(THEME, 3, config=_config())
    assert answer.text == POLISHED_TEXT


def test_generate_call_order_matches_srs(fake_llm) -> None:
    _queue_pipeline(fake_llm, n=3)
    generate_answer(THEME, 3, config=_config())
    roles = [call["role"] for call in fake_llm.calls]
    assert roles[0] == "seated_writer"
    assert roles[1] == "coordinator"
    assert roles[-2] == "tsukkomi"
    assert roles[-1] == "polisher"
    assert roles[2:-2] == ["respondent"] * 3


def test_respondent_num_two_creates_two_respondents(fake_llm) -> None:
    _queue_pipeline(fake_llm, n=2)
    generate_answer(THEME, 2, config=_config())
    respondent_calls = [call for call in fake_llm.calls if call["role"] == "respondent"]
    assert len(respondent_calls) == 2
    ids = {call["respondent_id"] for call in respondent_calls}
    assert ids == {"r1", "r2"}


def test_analysis_memo_is_shared_with_all_respondents(fake_llm) -> None:
    _queue_pipeline(fake_llm, n=3)
    generate_answer(THEME, 3, config=_config())
    memo = json.dumps(_memo_payload(), ensure_ascii=False)
    respondent_prompts = [
        call["prompt"] for call in fake_llm.calls if call["role"] == "respondent"
    ]
    assert len(respondent_prompts) == 3
    for prompt in respondent_prompts:
        assert memo in prompt


def test_cli_generate_prints_only_polished_text(
    fake_llm, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_key(monkeypatch)
    _queue_pipeline(fake_llm, n=3)
    result = runner.invoke(app, ["generate", "--theme", THEME])
    assert result.exit_code == 0
    assert result.stdout.strip() == POLISHED_TEXT
    blob = _plain(result)
    assert "theme_type" not in blob
    assert "banal_ideas" not in blob
    assert "ツッコミ" not in result.stdout
    assert "AnalysisMemo" not in blob
    assert ROLE_SEATED_WRITER not in blob
    assert ROLE_COORDINATOR not in blob
    assert ROLE_TSUKKOMI not in blob
    assert ROLE_POLISHER not in blob
    assert "[oogiri]" not in blob


def test_cli_verbose_prints_stages_to_stderr(
    fake_llm, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_key(monkeypatch)
    _queue_pipeline(fake_llm, n=3)
    result = runner.invoke(app, ["generate", "--theme", THEME, "--verbose"])
    assert result.exit_code == 0
    assert result.stdout.strip() == POLISHED_TEXT
    assert result.stdout.strip().splitlines()[-1] == POLISHED_TEXT
    err = click.unstyle(result.stderr)
    assert ROLE_SEATED_WRITER in err
    assert ROLE_COORDINATOR in err
    assert "回答者: 開始" in err
    assert "回答者: 完了" in err
    assert ROLE_TSUKKOMI in err
    assert ROLE_POLISHER in err
    assert "お題の型" in err
    assert "極端な具体" in err
    assert "r1の案1" in err
    assert "採択" in err
    assert POLISHED_TEXT in err
    assert TEST_KEY not in _plain(result)
    assert TEST_KEY not in result.stdout
    assert TEST_KEY not in result.stderr


def test_generate_answer_verbose_false_is_silent(
    fake_llm, capsys: pytest.CaptureFixture[str]
) -> None:
    _queue_pipeline(fake_llm, n=3)
    generate_answer(THEME, 3, config=_config())
    captured = capsys.readouterr()
    blob = captured.out + captured.err
    assert ROLE_SEATED_WRITER not in blob
    assert "[oogiri]" not in blob


def test_generate_answer_verbose_reports_stages(fake_llm) -> None:
    _queue_pipeline(fake_llm, n=2)
    buf = StringIO()
    reporter = ProgressReporter(enabled=True, stream=buf)
    answer = generate_answer(THEME, 2, config=_config(), progress=reporter)
    assert answer.text == POLISHED_TEXT
    err = buf.getvalue()
    assert f"{ROLE_SEATED_WRITER}: 開始" in err
    assert f"{ROLE_COORDINATOR}: 開始" in err
    assert "回答者: 開始 (2 体)" in err
    assert f"{ROLE_TSUKKOMI}: 開始" in err
    assert f"{ROLE_POLISHER}: 開始" in err
    assert "前提 (3)" in err
    assert "回答者: 2 体" in err
    assert "r1: 7 案" in err
    assert "採択 5" in err
    assert f"推敲後: {POLISHED_TEXT}" in err
    assert "system_prompt" not in err


def test_cli_respondent_num_two(fake_llm, monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_key(monkeypatch)
    _queue_pipeline(fake_llm, n=2)
    result = runner.invoke(app, ["generate", "--theme", THEME, "--respondent-num", "2"])
    assert result.exit_code == 0
    assert result.stdout.strip() == POLISHED_TEXT
    respondent_calls = [call for call in fake_llm.calls if call["role"] == "respondent"]
    assert len(respondent_calls) == 2


def test_cli_without_api_key_does_not_generate(
    fake_llm, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(ENV_API_KEY, raising=False)
    monkeypatch.setattr("oogiri.secrets.DEFAULT_SECRET_DIR", tmp_path)
    result = runner.invoke(app, ["generate", "--theme", THEME])
    assert result.exit_code != 0
    assert fake_llm.calls == []
    assert POLISHED_TEXT not in _plain(result)


def test_crewai_is_runtime_dependency() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "crewai" in text
    assert (ROOT / "src" / "oogiri" / "pipeline.py").is_file()
