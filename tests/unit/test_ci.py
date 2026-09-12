"""CI ワークフロー（pytest / ruff / radon / xenon / import-linter）と README バッジ。"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
README = ROOT / "README.md"
PYPROJECT = ROOT / "pyproject.toml"

_REQUIRED_RUN_COMMANDS = (
    "uv sync --all-groups --frozen",
    "uv run ruff check src tests",
    "uv run ruff format --check src tests",
    "uv run lint-imports",
    "uv run radon cc src --show-complexity --average",
    "uv run radon mi src --show",
    "uv run xenon src --max-absolute A --max-modules A --max-average A",
    "uv run pytest",
)

_REQUIRED_DEV_PACKAGES = (
    "import-linter",
    "pytest",
    "radon",
    "ruff",
    "xenon",
)


def _run_scripts(workflow_text: str) -> list[str]:
    """GitHub Actions の各 step の `run` 値を順に取り出す。"""
    scripts: list[str] = []
    lines = workflow_text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.lstrip()
        if not stripped.startswith("run:"):
            i += 1
            continue
        key_indent = len(raw) - len(stripped)
        rest = stripped[len("run:") :].strip()
        if rest in {"|", ">", "|-", ">-", "|+", ">+"}:
            i += 1
            block: list[str] = []
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() == "":
                    i += 1
                    continue
                nxt_indent = len(nxt) - len(nxt.lstrip())
                if nxt_indent <= key_indent:
                    break
                block.append(nxt.strip())
                i += 1
            scripts.append("\n".join(block))
            continue
        if rest:
            scripts.append(rest)
        i += 1
    return scripts


def _run_command_lines(workflow_text: str) -> set[str]:
    commands: set[str] = set()
    for script in _run_scripts(workflow_text):
        for line in script.splitlines():
            command = line.strip()
            if command:
                commands.add(command)
    return commands


def _requirement_name(requirement: str) -> str:
    return re.split(r"[<>=!\[]", requirement, maxsplit=1)[0].strip()


def test_ci_workflow_exists() -> None:
    assert WORKFLOW.is_file()


def test_ci_run_steps_execute_required_tools() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    commands = _run_command_lines(text)
    missing = [cmd for cmd in _REQUIRED_RUN_COMMANDS if cmd not in commands]
    assert missing == [], missing
    assert all("uv pip" not in command for command in commands)


def test_actions_are_pinned_to_commit_sha() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    uses = re.findall(r"^\s+uses:\s+(\S+)", text, flags=re.MULTILINE)
    assert uses
    for ref in uses:
        _action, at, digest = ref.partition("@")
        assert at == "@", ref
        assert re.fullmatch(r"[0-9a-f]{40}", digest), ref


def test_readme_has_ci_badge() -> None:
    text = README.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert any("actions/workflows/ci.yml/badge.svg" in line for line in lines[:10])


def test_dev_dependencies_include_ci_tools() -> None:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    dev = data["dependency-groups"]["dev"]
    names = {_requirement_name(item) for item in dev}
    missing = [name for name in _REQUIRED_DEV_PACKAGES if name not in names]
    assert missing == [], missing
    assert all("uv pip" not in item for item in dev)
