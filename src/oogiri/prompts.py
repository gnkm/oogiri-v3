"""プロンプト本文は `prompts/` からのみ読む（SRS-MVP-IF-007、FN-005）。"""

from __future__ import annotations

from pathlib import Path


class PromptError(Exception):
    """プロンプトの読み取りに失敗した。"""


def default_prompts_dir() -> Path:
    cwd_prompts = Path.cwd() / "prompts"
    if cwd_prompts.is_dir():
        return cwd_prompts
    return Path(__file__).resolve().parents[2] / "prompts"


def load_prompt(filename: str, *, prompts_dir: Path | None = None) -> str:
    """`prompts/<filename>` の本文を返す。`src/` には埋め込まない。"""
    if prompts_dir is None:
        directory = default_prompts_dir().resolve()
    else:
        directory = prompts_dir.resolve()
    path = _resolve_prompt_path(directory, filename)
    return _read_prompt(path)


def _resolve_prompt_path(directory: Path, filename: str) -> Path:
    path = (directory / filename).resolve()
    if path.parent != directory:
        raise PromptError("プロンプト名が不正です")
    if not path.is_file():
        raise PromptError(f"プロンプトがありません: {path}")
    return path


def _read_prompt(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PromptError(f"プロンプトを読めません: {path}") from exc
