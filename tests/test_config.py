"""config.toml の Pydantic 読み取りとエージェント別 LLM 設定。"""

from __future__ import annotations

from pathlib import Path

import pytest

from oogiri.config import ConfigError, load_config

ROOT = Path(__file__).resolve().parents[1]

_AGENT_ROLES = (
    "seated_writer",
    "coordinator",
    "respondent",
    "tsukkomi",
    "polisher",
)

_VALID_TOML = """
[openrouter]
base_url = "https://openrouter.ai/api/v1"

[agents.seated_writer]
model = "openrouter/writer-model"
temperature = 0.2

[agents.coordinator]
model = "openrouter/coordinator-model"
temperature = 0.4

[agents.respondent]
model = "openrouter/respondent-model"
temperature = 0.9

[agents.tsukkomi]
model = "openrouter/tsukkomi-model"
temperature = 0.2

[agents.polisher]
model = "openrouter/polisher-model"
temperature = 0.2

[eval.judge]
model = "openrouter/eval-judge-model"
temperature = 0.0
"""


def _write_toml(path: Path, body: str) -> Path:
    path.write_text(body.strip() + "\n", encoding="utf-8")
    return path


def test_repo_config_has_no_plaintext_key() -> None:
    text = (ROOT / "config.example.toml").read_text(encoding="utf-8")
    lowered = text.lower()
    assert "api_key" not in lowered
    assert "apikey" not in lowered.replace("-", "")


def test_repo_config_has_per_agent_llm_settings() -> None:
    cfg = load_config(ROOT / "config.example.toml")
    for role in _AGENT_ROLES:
        agent = getattr(cfg.agents, role)
        assert agent.model
        assert 0 <= agent.temperature <= 2
    assert cfg.openrouter.base_url.startswith("https://openrouter.ai/")
    assert cfg.eval is not None
    assert cfg.eval.judge.model
    assert 0 <= cfg.eval.judge.temperature <= 2


def test_each_agent_model_can_be_set_independently(tmp_path: Path) -> None:
    path = _write_toml(tmp_path / "config.toml", _VALID_TOML)
    cfg = load_config(path)
    models = [getattr(cfg.agents, role).model for role in _AGENT_ROLES]
    assert len(set(models)) == len(_AGENT_ROLES)
    assert cfg.agents.seated_writer.model == "openrouter/writer-model"
    assert cfg.agents.respondent.model == "openrouter/respondent-model"
    assert cfg.agents.respondent.temperature == 0.9
    assert cfg.agents.polisher.temperature == 0.2
    assert cfg.eval is not None
    assert cfg.eval.judge.model == "openrouter/eval-judge-model"
    assert cfg.eval.judge.temperature == 0.0


def test_eval_section_is_optional(tmp_path: Path) -> None:
    """生成経路は判定役を使わない。旧設定でも読める。"""
    body = _VALID_TOML.split("[eval.judge]")[0]
    path = _write_toml(tmp_path / "config.toml", body)
    cfg = load_config(path)
    assert cfg.eval is None


def test_api_key_in_config_is_rejected_without_leaking_value(
    tmp_path: Path,
) -> None:
    leaked = "oogiri-test-key-must-not-appear-in-errors"
    body = _VALID_TOML.replace(
        'base_url = "https://openrouter.ai/api/v1"',
        f'base_url = "https://openrouter.ai/api/v1"\napi_key = "{leaked}"',
    )
    path = _write_toml(tmp_path / "config.toml", body)
    with pytest.raises(ConfigError, match="API キー") as exc_info:
        load_config(path)
    assert leaked not in str(exc_info.value)
    cause = exc_info.value.__cause__
    if cause is not None:
        assert leaked not in str(cause)


def test_missing_config_file_fails(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="ありません"):
        load_config(tmp_path / "missing.toml")


def test_unreadable_config_is_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write_toml(tmp_path / "config.toml", _VALID_TOML)
    original_open = Path.open

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if self == path:
            raise PermissionError("denied")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    with pytest.raises(ConfigError, match="読めません"):
        load_config(path)


def test_load_config_does_not_write_api_key(tmp_path: Path) -> None:
    path = _write_toml(tmp_path / "config.toml", _VALID_TOML)
    before = path.read_text(encoding="utf-8")
    load_config(path)
    after = path.read_text(encoding="utf-8")
    assert after == before
    assert "api_key" not in after.lower()


@pytest.mark.parametrize(
    "base_url",
    [
        "http://openrouter.ai/api/v1",
        "https://evil.example/api/v1",
        "https://openrouter.ai.evil.example/api/v1",
        "https://user:pass@openrouter.ai/api/v1",
        "https://openrouter.ai:8443/api/v1",
    ],
)
def test_non_openrouter_base_url_is_rejected(tmp_path: Path, base_url: str) -> None:
    body = _VALID_TOML.replace(
        'base_url = "https://openrouter.ai/api/v1"',
        f'base_url = "{base_url}"',
    )
    path = _write_toml(tmp_path / "config.toml", body)
    with pytest.raises(ConfigError, match="検証に失敗") as exc_info:
        load_config(path)
    assert "api_key" not in str(exc_info.value).lower()
