"""OpenRouter API キーを Podman secret から読む。

秘密名は `openrouter_api_key_oogiri`（SRS-MVP-IF-005）。
Cloud / 試験では環境変数 `OPENROUTER_API_KEY` をフォールバックにする。
キーをログ・設定・プロンプトへ平文で出さない（SRS-MVP-QA-002）。
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

PODMAN_SECRET_NAME = "openrouter_api_key_oogiri"
DEFAULT_SECRET_DIR = Path("/run/secrets")
ENV_API_KEY = "OPENROUTER_API_KEY"


class MissingAPIKeyError(Exception):
    """生成に必要な OpenRouter API キーが無い。メッセージにキーを含めない。"""

    def __init__(self) -> None:
        super().__init__(
            "OpenRouter API キーが見つかりません。"
            f" Podman secret `{PODMAN_SECRET_NAME}` を投入するか、"
            f"試験用に環境変数 {ENV_API_KEY} を設定してください。"
        )


def load_openrouter_api_key(
    *,
    secret_dir: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> str:
    """キーを返す。無ければ生成処理を始められない。"""
    env = os.environ if environ is None else environ
    from_secret = _read_podman_secret(secret_dir or DEFAULT_SECRET_DIR)
    if from_secret:
        return from_secret
    from_env = env.get(ENV_API_KEY, "").strip()
    if from_env:
        return from_env
    raise MissingAPIKeyError()


def require_openrouter_api_key(
    *,
    secret_dir: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> str:
    """生成処理の前提として API キーを確保する。無ければ失敗する。"""
    return load_openrouter_api_key(secret_dir=secret_dir, environ=environ)


def _read_podman_secret(secret_dir: Path) -> str | None:
    path = secret_dir / PODMAN_SECRET_NAME
    if not path.is_file():
        return None
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None
