"""oogiri generate のフラグ・既定値・拒否（SRS-MVP-IF-001〜004, QA-001, FN-028）。"""

from __future__ import annotations

import click
import pytest
from typer.main import get_command
from typer.testing import CliRunner

from oogiri.cli import DEFAULT_RESPONDENT_NUM, IMAGE_UNSUPPORTED_MESSAGE, app

runner = CliRunner()


def _plain(result: click.testing.Result) -> str:
    """Rich の ANSI を除く。CI では `--theme` のハイフン間に色が入る。"""
    blob = "\n".join(
        part for part in (result.stdout, result.stderr, result.output) if part
    )
    return click.unstyle(blob)


def test_generate_help_exits_zero() -> None:
    result = runner.invoke(app, ["generate", "--help"])
    assert result.exit_code == 0
    output = _plain(result)
    assert "Usage" in output
    assert "--theme" in output
    assert "--respondent-num" in output


def test_generate_help_matches_srs_flags() -> None:
    result = runner.invoke(app, ["generate", "--help"])
    assert result.exit_code == 0
    output = _plain(result)
    assert "--text" not in output
    assert "--image" not in output
    assert str(DEFAULT_RESPONDENT_NUM) in output


def test_theme_is_required() -> None:
    result = runner.invoke(app, ["generate"])
    assert result.exit_code != 0
    assert "theme" in _plain(result).lower()


def test_theme_flag_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_handle(*, theme: str, respondent_num: int) -> None:
        captured["theme"] = theme
        captured["respondent_num"] = respondent_num

    monkeypatch.setattr("oogiri.cli.handle_generate", fake_handle)
    result = runner.invoke(app, ["generate", "--theme", "猫がスマホを見ている"])
    assert result.exit_code == 0
    assert captured["theme"] == "猫がスマホを見ている"
    assert captured["respondent_num"] == DEFAULT_RESPONDENT_NUM


def test_respondent_num_defaults_to_three() -> None:
    command = get_command(app).commands["generate"]
    param = next(p for p in command.params if "--respondent-num" in p.opts)
    assert param.default == 3


def test_respondent_num_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_handle(*, theme: str, respondent_num: int) -> None:
        captured["theme"] = theme
        captured["respondent_num"] = respondent_num

    monkeypatch.setattr("oogiri.cli.handle_generate", fake_handle)
    result = runner.invoke(
        app,
        ["generate", "--theme", "お題", "--respondent-num", "5"],
    )
    assert result.exit_code == 0
    assert captured["respondent_num"] == 5


def test_image_flag_exits_nonzero_without_image_output() -> None:
    result = runner.invoke(app, ["generate", "--theme", "お題", "--image"])
    assert result.exit_code != 0
    blob = _plain(result)
    assert IMAGE_UNSUPPORTED_MESSAGE in blob
    encoded = blob.encode("utf-8", errors="replace")
    assert b"\x89PNG" not in encoded
    assert b"\xff\xd8\xff" not in encoded


def test_text_flag_is_not_provided() -> None:
    help_output = _plain(runner.invoke(app, ["generate", "--help"]))
    assert "--text" not in help_output

    result = runner.invoke(app, ["generate", "--theme", "お題", "--text"])
    assert result.exit_code != 0
    assert "no such option" in _plain(result).lower()
