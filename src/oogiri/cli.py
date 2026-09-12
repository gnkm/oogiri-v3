"""Typer エントリ。生成パイプラインは後続 Issue。"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="oogiri",
    help="お題を与えると、大喜利の回答を返す。",
    no_args_is_help=True,
)

DEFAULT_RESPONDENT_NUM = 3
IMAGE_UNSUPPORTED_MESSAGE = "画像出力は MVP の対象外です。"
PIPELINE_UNWIRED_MESSAGE = "生成パイプラインは未実装です。"


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
    """フラグ解析後の受け渡し。パイプライン本体は後続 Issue。"""
    _ = (theme, respondent_num)
    typer.echo(PIPELINE_UNWIRED_MESSAGE, err=True)
    raise typer.Exit(code=1)


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
