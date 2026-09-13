"""端的さのプロンプト契約（Inspection）。文字数判定器と軸 Enum は置かない。"""

from __future__ import annotations

from pathlib import Path

from oogiri.contracts.candidates import Candidate
from oogiri.contracts.polished import PolishedAnswer
from oogiri.contracts.roster import StyleAxis

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "docs" / "prompt-design.md"


def test_prompt_design_requires_brevity_and_type_premises() -> None:
    text = DESIGN.read_text(encoding="utf-8")
    assert "端的" in text
    assert "1 句" in text
    assert "型の条件" in text
    assert "文字数の Pydantic 上限" in text
    assert "軸の固定 Enum" in text
    prompts = "\n".join(
        (ROOT / "prompts" / name).read_text(encoding="utf-8")
        for name in (
            "seated_writer.md",
            "coordinator.md",
            "respondent.md",
            "tsukkomi.md",
            "polisher.md",
        )
    )
    assert "端的" in prompts
    assert "1 句" in prompts
    assert "型の条件" in prompts


def test_answer_text_has_no_character_cap() -> None:
    long_text = "あ" * 500
    candidate = Candidate(candidate_id="c1", respondent_id="r1", text=long_text)
    answer = PolishedAnswer(text=long_text)
    assert candidate.text == long_text
    assert answer.text == long_text
    source = (ROOT / "src" / "oogiri" / "contracts" / "candidates.py").read_text(
        encoding="utf-8"
    )
    polished = (ROOT / "src" / "oogiri" / "contracts" / "polished.py").read_text(
        encoding="utf-8"
    )
    assert "max_length" not in source
    assert "max_length" not in polished


def test_style_axis_is_not_a_fixed_enum() -> None:
    roster = (ROOT / "src" / "oogiri" / "contracts" / "roster.py").read_text(
        encoding="utf-8"
    )
    assert "Enum" not in roster
    axis = StyleAxis(name="実行固有の新しい軸", description="今回だけ使う笑い方")
    assert axis.name == "実行固有の新しい軸"
