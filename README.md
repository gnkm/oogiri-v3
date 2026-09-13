# 大喜利ジェネレーター

![CI](https://github.com/gnkm/oogiri-v3/actions/workflows/ci.yml/badge.svg)

お題を与えると、大喜利の回答を返す。

## 開発

Python 3.13 と [uv](https://docs.astral.sh/uv/) を使う。`uv pip` は使わない。

```sh
uv python install 3.13
uv sync --all-groups
uv run oogiri --help
uv run pytest
uv run ruff check src tests
uv run ruff format --check src tests
uv run lint-imports
uv run radon cc src --show-complexity --average
uv run xenon src --max-absolute A --max-modules A --max-average A
```

配置はコード `src/`、プロンプト `prompts/`、設定 `config.toml`。秘密は設定ファイルに書かない。

## 出力評価（DeepEval）

評価は **開発機の pytest** で行う。Podman 上では動かさない。製品コンテナは `uv sync --no-dev` で DeepEval を入れておらず、`oogiri generate` は大喜利を出すだけである（[`ARCHITECTURE.md`](ARCHITECTURE.md)）。

このリポジトリに評価用の画面（Web UI）は無い。結果はターミナルの pytest 出力である。DeepEval 公式のクラウド画面（[Confident AI](https://deepeval.com/docs/evaluation-introduction)）は、`deepeval login` 後に使えるが、ここでは pytest プラグインを切っているため接続していない。

### コマンド

いつもの試験（MockJudge。API キー不要。CI と同じ）:

```sh
uv run pytest
```

本物の OpenRouter で同じメトリクスを回す（キーが無ければ skip）:

```sh
export OPENROUTER_API_KEY=...
uv run pytest -o "addopts=-p no:deepeval" -m live tests/test_deepeval.py
```

判定モデルは `config.toml` の `[eval.judge]` である。GEval は logprobs を使うため、推論モデル（`gpt-6` など）は 400 になる。推敲役のモデルとは別にする。

`-o addopts=...` は、既定の「ライブ試験を集めない」設定を外すため。`-p no:deepeval` は DeepEval の pytest プラグインを使わないため（契約試験と混ぜない）。

見るもの: 推敲後 1 案が「お題に対する単一の回答の形か」（GEval `PolishedAnswerForm`、閾値 0.5）。面白さの点数は見ない。今はフィクスチャを採点する。`generate` の本番出力を評価するサブコマンドは無い。

方針: [`docs/test-strategy.md`](docs/test-strategy.md)。コード: `tests/eval/polished_form.py`、`tests/test_deepeval.py`。

## 製品実行（Podman）

OpenRouter API キーは `config.toml` に書かず、Podman secret `openrouter_api_key_oogiri` で渡す。

```sh
op item get 'OpenRouter API Key - oogiri' --field '認証情報' --reveal | podman secret create openrouter_api_key_oogiri -
podman build -t oogiri -f Containerfile
podman run --rm --secret openrouter_api_key_oogiri oogiri --help
```

正本: [`docs/source-of-truth/srs-mvp.md`](docs/source-of-truth/srs-mvp.md)

## Cloud Agents

実装は GitHub Feature Issue を単位に、Cursor Cloud Agents で進める。

1. このリポジトリを Cursor の GitHub 連携に通し、[Cloud Agents](https://cursor.com/dashboard/cloud-agents) で Environment を作る（`.cursor/environment.json`）。
2. Secrets に `OPENROUTER_API_KEY` を登録する（製品実行時の Podman secret 名は `openrouter_api_key_oogiri`）。
3. 成功した Build があることを確認する。
4. 未完了の **Blocked by** が無い Feature Issue を 1 件選び、Cloud Agent に渡す（GitHub では Issue に `@cursor`）。
5. PR が来たら `verifier` が Issue の **検証** 欄を実行してからマージする。

## ライセンス

[MIT](LICENSE)
