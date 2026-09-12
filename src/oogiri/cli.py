"""Typer エントリ。`generate` はパイプラインを起動し、推敲後の 1 案を出す。"""

from __future__ import annotations

import typer

from oogiri.config import ConfigError, load_config
from oogiri.llm import LLMError, configure_gateway
from oogiri.secrets import SecretError, require_openrouter_api_key

app = typer.Typer(
    name="oogiri",
    help="お題を与えると、大喜利の回答を返す。",
    no_args_is_help=True,
)

DEFAULT_RESPONDENT_NUM = 3
IMAGE_UNSUPPORTED_MESSAGE = "画像出力は MVP の対象外です。"


@app.callback()
def main() -> None:
    """お題を与えると、大喜利の回答を返す。"""


def _reject_image_flag(value: bool) -> bool:
    """`--image` は製品機能ではない。指定されたら生成せず非 0 で終える。"""
    if value:
        typer.echo(IMAGE_UNSUPPORTED_MESSAGE, err=True)
        raise typer.Exit(code=1)
    return value


def handle_generate(*, theme: str, respondent_num: int) -> None:
    """フラグ解析後の受け渡し。キーが無ければ生成しない。"""
    from oogiri.pipeline import PipelineError, generate_answer

    try:
        api_key = require_openrouter_api_key()
        config = load_config()
        configure_gateway(api_key=api_key, base_url=config.openrouter.base_url)
        answer = generate_answer(theme, respondent_num, config=config)
    except (SecretError, ConfigError, LLMError, PipelineError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None
    typer.echo(answer.text)


@app.command()
def generate(
    theme: str = typer.Option(
        ...,
        "--theme",
        help="お題",
        prompt=False,
    ),
    respondent_num: int = typer.Option(
        DEFAULT_RESPONDENT_NUM,
        "--respondent-num",
        help="回答者の数",
        min=1,
    ),
    image: bool = typer.Option(
        False,
        "--image",
        help="画像出力（MVP では非対応）",
        hidden=True,
        is_eager=True,
        callback=_reject_image_flag,
    ),
) -> None:
    """お題から大喜利の回答を生成する。"""
    handle_generate(theme=theme, respondent_num=respondent_num)
