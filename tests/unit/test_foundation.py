"""土台（Python 3.13 / 配置 / CLI --help / uv pip 不使用）。"""

from __future__ import annotations

import sys
from pathlib import Path

from typer.testing import CliRunner

from oogiri.cli import app

ROOT = Path(__file__).resolve().parents[2]
runner = CliRunner()


def test_python_version_is_3_13() -> None:
    assert sys.version_info[:2] == (3, 13)


def test_layout_separates_src_prompts_and_config() -> None:
    assert (ROOT / "src").is_dir()
    assert (ROOT / "prompts").is_dir()
    assert (ROOT / "config.example.toml").is_file()
    assert (ROOT / "config.toml").is_file()
    assert (ROOT / "pyproject.toml").is_file()


def test_help_exits_zero() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    output = result.stdout or result.output
    assert "Usage" in output
    assert "oogiri" in output


def test_pyproject_does_not_use_uv_pip() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "uv pip" not in text
