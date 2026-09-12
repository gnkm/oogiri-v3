"""Typer エントリ。生成パイプラインは後続 Issue。"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="oogiri",
    help="お題を与えると、大喜利の回答を返す。",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """お題を与えると、大喜利の回答を返す。"""
