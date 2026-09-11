# AGENTS.md

Cursor Cloud Agents 向けの作業ルール。アプリ固有のルールはプロジェクト側で追記する。

## タスク管理

- タスクと完了基準は **GitHub Issue** のみ。着手前に対象 Issue を読む（`gh issue view`）。
- Issue の **Blocked by** に未完了の依存がある場合は着手しない。
- セッション引き継ぎは Issue / PR の本文とコメントで行う。リポジトリ内の progress ファイルは使わない。

## 完了の定義

- Issue のクローズは、`verifier` が Issue の **検証** 欄のコマンドを実行して通ったあとだけ。
- 自分で完了と主張した直後は `verifier` を起動する。

## 調査

- ウェブ調査は親が直接 scrape / WebFetch / Firecrawl せず、`web-reader` に委譲する。

## CI バッジ

- CI ワークフロー（`.github/workflows/`）を追加・変更したら、README 先頭付近にそのワークフローの状況バッジを必ず出す。無ければ追加する。
- 例: `![CI](https://github.com/<owner>/<repo>/actions/workflows/<file>.yml/badge.svg)`
