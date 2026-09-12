# 大喜利ジェネレーター

お題を与えると、大喜利の回答を返す。

## 開発準備

### 編集するファイル

| ファイル | すること |
| --- | --- |
| `.cursor/environment.json.template` | `{{INSTALL_CMD}}` と `{{START_CMD}}` を埋め、`.cursor/environment.json` にリネームする |
| `.cursorignore` | `{{STACK_SPECIFIC_PATTERNS}}` を自分のスタックの機密パターンに置き換える |
| Feature Issue | 機能名・実証可能な振る舞い・検証コマンド・Blocked by を書く |

## ライセンス

[MIT](LICENSE)
