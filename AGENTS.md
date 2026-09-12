# AGENTS.md

Cursor Cloud Agents 向けの作業ルール。アプリ固有のルールはプロジェクト側で追記する。

## 編集禁止（読み取り専用）

- `docs/source-of-truth/` 配下はソース・オブ・トゥルース。AI は読んでよいが、編集・削除・リネーム・移動は禁止。
- フロントマターに `ai.editable: false`（または `ai_editable: false`）があるファイルも同様。
- 内容変更が必要なら Issue で人間に依頼し、自分では触らない。

## タスク管理

- タスクと完了基準は **GitHub Issue** のみ。着手前に対象 Issue を読む（`gh issue view`）。
- Issue の **Blocked by** に未完了の依存がある場合は着手しない。
- セッション引き継ぎは Issue / PR の本文とコメントで行う。リポジトリ内の progress ファイルは使わない。
- **1 Issue = 1 PR**。複数 Issue を同時に実装しない。

## 完了の定義

- Issue のクローズは、`verifier` が Issue の **検証** 欄のコマンドを実行して通ったあとだけ。
- 自分で完了と主張した直後は `verifier` を起動する。

## 調査

- ウェブ調査は親が直接 scrape / WebFetch / Firecrawl せず、`web-reader` に委譲する。

## CI バッジ

- CI ワークフロー（`.github/workflows/`）を追加・変更したら、README 先頭付近にそのワークフローの状況バッジを必ず出す。無ければ追加する。
- 例: `![CI](https://github.com/<owner>/<repo>/actions/workflows/<file>.yml/badge.svg)`

## 正本と範囲

- 実装の正本は `docs/source-of-truth/srs-mvp.md`。着手前に該当要件 ID を読む。
- MVP の出力はテキストのみ。画像出力（`--image`）は対象外。指定されたら非 0 で終える。
- 画像を含む製品要件は後続。`docs/source-of-truth/srs.md` または `docs/reference/srs.md` が無い場合は人間に Issue で依頼する。自分で source-of-truth に作らない。

## 実装スタック

- 言語: Python 3.13
- パッケージマネージャ: uv（`uv pip` 禁止）
- CLI: Typer。エントリは `oogiri`
- 設定: `config.toml`（Pydantic で読む）
- プロンプト: `prompts/`（`src/` に埋め込まない）
- コード: `src/`
- マルチエージェント: CrewAI
- LLM API: OpenRouter
- 出力評価: DeepEval
- 製品コンテナ: Podman。秘密名は `openrouter_api_key_oogiri`

## Cursor Cloud specific instructions

- Cloud Agent の VM は Ubuntu + Docker。製品の実行形態は Podman のままにする（Containerfile は OCI 互換）。
- 検証の主経路は `uv run pytest`。OpenRouter はモックする。ライブ呼び出しは Cursor Secrets の `OPENROUTER_API_KEY` があるときだけ。
- 依存インストールは `uv sync`。`uv pip` を使わない。
- `pyproject.toml` が無い Issue（土台）以外では、`uv run pytest` が通る状態を維持する。
- 秘密を `config.toml`、プロンプト、ログ、コミットに書かない。
- GitHub の `@cursor` コメントや Automations で起動された場合も、対象 Issue の Blocked by を確認してから着手する。
