"""Podman secret と API キー漏洩防止。"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from oogiri.secrets import (
    ENV_API_KEY,
    PODMAN_SECRET_NAME,
    MissingAPIKeyError,
    load_openrouter_api_key,
    require_openrouter_api_key,
)

ROOT = Path(__file__).resolve().parents[1]
TEST_KEY = "oogiri-test-openrouter-key-unique"


def _write_secret(secret_dir: Path, value: str) -> Path:
    secret_dir.mkdir(parents=True, exist_ok=True)
    path = secret_dir / PODMAN_SECRET_NAME
    path.write_text(value, encoding="utf-8")
    return path


def test_podman_secret_name_is_stable() -> None:
    assert PODMAN_SECRET_NAME == "openrouter_api_key_oogiri"


def test_containerfile_uses_podman_secret_name() -> None:
    text = (ROOT / "Containerfile").read_text(encoding="utf-8")
    assert PODMAN_SECRET_NAME in text
    assert "OPENROUTER_API_KEY=" not in text
    assert "ENV OPENROUTER_API_KEY" not in text


def test_readme_documents_podman_secret_name() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert PODMAN_SECRET_NAME in text


def test_load_key_from_podman_secret_file(tmp_path: Path) -> None:
    _write_secret(tmp_path, TEST_KEY + "\n")
    got = load_openrouter_api_key(secret_dir=tmp_path, environ={})
    assert got == TEST_KEY


def test_fallback_to_openrouter_api_key_env(tmp_path: Path) -> None:
    got = load_openrouter_api_key(
        secret_dir=tmp_path,
        environ={ENV_API_KEY: TEST_KEY},
    )
    assert got == TEST_KEY


def test_podman_secret_wins_over_env(tmp_path: Path) -> None:
    _write_secret(tmp_path, "from-secret")
    got = load_openrouter_api_key(
        secret_dir=tmp_path,
        environ={ENV_API_KEY: "from-env"},
    )
    assert got == "from-secret"


def test_generation_fails_without_api_key(tmp_path: Path) -> None:
    with pytest.raises(MissingAPIKeyError, match="openrouter_api_key_oogiri"):
        require_openrouter_api_key(secret_dir=tmp_path, environ={})


def test_empty_secret_and_env_fail(tmp_path: Path) -> None:
    _write_secret(tmp_path, "   \n")
    with pytest.raises(MissingAPIKeyError):
        load_openrouter_api_key(
            secret_dir=tmp_path,
            environ={ENV_API_KEY: "  "},
        )


def test_api_key_does_not_appear_in_logs_or_stdout(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_secret(tmp_path, TEST_KEY)
    with caplog.at_level(logging.DEBUG):
        got = load_openrouter_api_key(secret_dir=tmp_path, environ={})
    assert got == TEST_KEY
    captured = capsys.readouterr()
    blob = "\n".join((caplog.text, captured.out, captured.err))
    assert TEST_KEY not in blob


def test_missing_key_error_does_not_embed_env_value() -> None:
    err = MissingAPIKeyError()
    assert TEST_KEY not in str(err)
    assert "OPENROUTER_API_KEY" in str(err)


def test_loading_key_does_not_write_config(tmp_path: Path) -> None:
    config_path = ROOT / "config.toml"
    before = config_path.read_text(encoding="utf-8")
    _write_secret(tmp_path, TEST_KEY)
    load_openrouter_api_key(secret_dir=tmp_path, environ={})
    after = config_path.read_text(encoding="utf-8")
    assert after == before
    assert "api_key" not in after.lower()
