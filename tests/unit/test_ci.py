"""CI ワークフロー（pytest / ruff / radon / xenon / import-linter）と README バッジ。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
README = ROOT / "README.md"
PYPROJECT = ROOT / "pyproject.toml"


def test_ci_workflow_exists() -> None:
    assert WORKFLOW.is_file()


def test_ci_runs_required_tools() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    for needle in ("pytest", "ruff", "radon", "xenon", "lint-imports"):
        assert needle in text, needle
    assert "uv pip" not in text


def test_readme_has_ci_badge() -> None:
    text = README.read_text(encoding="utf-8")
    assert "actions/workflows/ci.yml/badge.svg" in text


def test_dev_dependencies_include_ci_tools() -> None:
    text = PYPROJECT.read_text(encoding="utf-8")
    for needle in ("ruff", "radon", "xenon", "import-linter"):
        assert needle in text, needle
    assert "uv pip" not in text
