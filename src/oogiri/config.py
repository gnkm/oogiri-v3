"""ルートの `config.toml` を Pydantic で読む。

エージェントごとのモデル・温度など。API キーは置かない（SRS-MVP-QA-002）。
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

CONFIG_FILENAME = "config.toml"
_SECRET_FIELD_MARKERS = ("api_key", "apikey")
_NO_PLAINTEXT_KEY = (
    "設定ファイルに API キーを書いてはいけません。"
    " Podman secret `openrouter_api_key_oogiri` を使ってください。"
)


class ConfigError(Exception):
    """設定の読み取りまたは検証に失敗した。メッセージに秘密を含めない。"""


class AgentLLMConfig(BaseModel):
    """1 エージェントの LLM 設定。"""

    model_config = ConfigDict(extra="forbid")

    model: str = Field(min_length=1)
    temperature: float = Field(ge=0, le=2)


class AgentsConfig(BaseModel):
    """役割ごとの LLM。個別に変えられる（SRS-MVP-FN-029）。"""

    model_config = ConfigDict(extra="forbid")

    seated_writer: AgentLLMConfig
    coordinator: AgentLLMConfig
    respondent: AgentLLMConfig
    tsukkomi: AgentLLMConfig
    polisher: AgentLLMConfig


class OpenRouterConfig(BaseModel):
    """OpenRouter の接続先。キーはここではなく secret から読む。"""

    model_config = ConfigDict(extra="forbid")

    base_url: str = Field(min_length=1)


class AppConfig(BaseModel):
    """`config.toml` の全体。"""

    model_config = ConfigDict(extra="forbid")

    openrouter: OpenRouterConfig
    agents: AgentsConfig

    @model_validator(mode="before")
    @classmethod
    def reject_plaintext_keys(cls, data: object) -> object:
        _reject_secret_fields(data)
        return data


def default_config_path() -> Path:
    return Path.cwd() / CONFIG_FILENAME


def load_config(path: Path | None = None) -> AppConfig:
    """`config.toml` を読み、Pydantic で検証する。"""
    config_path = path if path is not None else default_config_path()
    data = _read_toml(config_path)
    _reject_secret_fields(data)
    return _validate_config(config_path, data)


def _read_toml(config_path: Path) -> dict[str, Any]:
    if not config_path.is_file():
        raise ConfigError(f"設定ファイルがありません: {config_path}")
    try:
        return _load_toml_bytes(config_path)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(
            f"設定ファイルを TOML として読めません: {config_path}"
        ) from exc
    except OSError as exc:
        raise ConfigError(f"設定ファイルを読めません: {config_path}") from exc


def _load_toml_bytes(config_path: Path) -> dict[str, Any]:
    with config_path.open("rb") as fh:
        return tomllib.load(fh)


def _validate_config(config_path: Path, data: object) -> AppConfig:
    try:
        return AppConfig.model_validate(data)
    except ConfigError:
        raise
    except ValidationError as exc:
        raise ConfigError(f"設定ファイルの検証に失敗しました: {config_path}") from exc


def _looks_like_secret_field(name: object) -> bool:
    if not isinstance(name, str):
        return False
    normalized = name.lower().replace("-", "_")
    return any(marker in normalized for marker in _SECRET_FIELD_MARKERS)


def _reject_secret_fields(value: object) -> None:
    if isinstance(value, dict):
        _reject_secret_fields_in_mapping(value)
        return
    if isinstance(value, list):
        for child in value:
            _reject_secret_fields(child)


def _pop_secret_fields(value: dict[str, Any]) -> bool:
    secret_keys = [key for key in value if _looks_like_secret_field(key)]
    for key in secret_keys:
        value.pop(key, None)
    return bool(secret_keys)


def _reject_secret_fields_in_mapping(value: dict[str, Any]) -> None:
    if _pop_secret_fields(value):
        raise ConfigError(_NO_PLAINTEXT_KEY)
    for child in value.values():
        _reject_secret_fields(child)
