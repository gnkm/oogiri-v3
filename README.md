# 大喜利ジェネレーター

お題を与えると、大喜利の回答を返す。

## Cloud Agents

実装は GitHub Feature Issue を単位に、Cursor Cloud Agents で進める。

1. このリポジトリを Cursor の GitHub 連携に通し、[Cloud Agents](https://cursor.com/dashboard/cloud-agents) で Environment を作る（`.cursor/environment.json`）。
2. Secrets に `OPENROUTER_API_KEY` を登録する（製品実行時の Podman secret 名は `openrouter_api_key_oogiri`）。
3. 成功した Build があることを確認する。
4. 未完了の **Blocked by** が無い Feature Issue を 1 件選び、Cloud Agent に渡す（GitHub では Issue に `@cursor`）。
5. PR が来たら `verifier` が Issue の **検証** 欄を実行してからマージする。

正本: [`docs/source-of-truth/srs-mvp.md`](docs/source-of-truth/srs-mvp.md)

## ライセンス

[MIT](LICENSE)
