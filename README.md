# 大喜利ジェネレーター

![CI](https://github.com/gnkm/oogiri-v3/actions/workflows/ci.yml/badge.svg)

お題を与えると、大喜利の回答を返す。

## 開発

Python 3.13 と [uv](https://docs.astral.sh/uv/) を使う。`uv pip` は使わない。

```sh
uv python install 3.13
uv sync --all-groups
cp config.example.toml config.toml
uv run oogiri --help
uv run oogiri generate --theme 'お題' --verbose
uv run pytest
uv run ruff check src tests
uv run ruff format --check src tests
uv run lint-imports
uv run radon cc src --show-complexity --average
uv run xenon src --max-absolute A --max-modules A --max-average A
```

途中経過は `--verbose` で標準エラーへ出す。標準出力は推敲後の 1 案のまま。

配置はコード `src/`、プロンプト `prompts/`、設定 `config.toml`。秘密は設定ファイルに書かない。

## 出力評価

出力の質は DeepEval で見る（SRS-MVP-DC-008）。`oogiri generate` と Podman には載せない。
既定の `uv run pytest` は MockJudge で通る。ライブ判定は `OPENROUTER_API_KEY` があるときだけ。
面白さの絶対点は見ない。

判定モデルは `config.toml` の `[eval.judge]` である。GEval は logprobs を使うため、推論モデル（`gpt-6` など）は 400 になる。推敲役のモデルとは別にする。

このリポジトリに評価用の画面（Web UI）は無い。結果はターミナルの pytest 出力である。

### 形検査（PolishedAnswerForm）

お題に対する単一回答の形を見る。

```sh
uv run pytest tests/test_deepeval.py -k polished_form
```

### おもしろさ評価（HumorQuality）

お題との噛み・オチ位置・凡庸回避を相対的に見る。面白さの絶対点は見ない。

```sh
uv run pytest tests/test_deepeval.py -k humor_quality
```

ライブ（secret があるとき）:

```sh
export OPENROUTER_API_KEY=...
uv run pytest -o "addopts=-p no:deepeval" -m live tests/test_deepeval.py
```

`-o addopts=...` は、既定の「ライブ試験を集めない」設定を外すため。`-p no:deepeval` は DeepEval の pytest プラグインを使わないため（契約試験と混ぜない）。
方針: [`docs/test-strategy.md`](docs/test-strategy.md)。
## 製品実行（Podman）

OpenRouter API キーは `config.toml` に書かず、Podman secret `openrouter_api_key_oogiri` で渡す。

```sh
podman secret create openrouter_api_key_oogiri -
podman build -t oogiri -f Containerfile
podman run --rm --secret openrouter_api_key_oogiri oogiri --help
```

1Password を使う場合の例:

```sh
op item get 'OpenRouter API Key - oogiri' --field '認証情報' --reveal | podman secret create openrouter_api_key_oogiri -
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
