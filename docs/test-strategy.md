# 試験方針（MVP）

本文書は MVP の **試験の役割分担**（何を pytest で保証し、何を DeepEval に回すか、LLM をどこでモックするか）を定める。
**what**（shall）の正本は [`docs/source-of-truth/srs-mvp.md`](source-of-truth/srs-mvp.md) である。
**how**（モジュール境界）は [`ARCHITECTURE.md`](../ARCHITECTURE.md) である。
衝突する場合は SRS を優先する。SRS の件数 shall と禁止事項を緩めない。

実装 Issue は本文書のモック境界と置き場を使う。**Issue ごとに別のモックを発明しない。**

DeepEval の採点基準（メトリクス名・閾値・ルーブリック）は本文書の対象外である。それは Issue #10 に残す。

## 対象外

- ライブの OpenRouter を **既定の pytest の合格条件にしない**。secret が無い環境でも `uv run pytest` は通る。
- DeepEval の採点表をここで固定しない。
- 画像出力の試験経路は置かない。`--image` は製品機能ではなく、指定されたら非 0 で終える（SRS、`ARCHITECTURE.md`）。

## 三層

| 層 | 目的 | 実行 | LLM |
| --- | --- | --- | --- |
| ユニット試験 | 件数・書き換え禁止・相互非参照・Pydantic 契約 | `uv run pytest`（既定） | **モックする** |
| 契約試験 | パイプライン順・エージェント間ペイロードの受け渡し | `uv run pytest`（既定） | **モックする** |
| 品質評価 | 笑いの質（Analysis） | DeepEval。既定の pytest からは外す | ライブは **secret があるときだけ** |

SRS 3 の対応: 件数・禁止事項・インタフェースは Test / Inspection。出力の質（笑い）は DeepEval による Analysis。**DeepEval は品質評価であり、パイプライン契約試験の代わりにしない。**

## LLM は pytest でモックする

LLM（OpenRouter / CrewAI の実呼び出し）は pytest でモックする。

モックの正本境界は **`src/oogiri/llm.py`（LLM ゲートウェイ）** である。OpenRouter への HTTPS と CrewAI の LLM 設定はここに集約する（`ARCHITECTURE.md`）。試験はここを差し替える。

| してよいこと | してはいけないこと |
| --- | --- |
| `tests/conftest.py` の共通 fixture でゲートウェイを Fake LLM に差し替える | エージェント実装 Issue が CrewAI 内部・`httpx`・各 `agents/*.py` を別々にパッチする |
| `llm.py` 自体の試験だけ、そのモジュール内の HTTP クライアントをモックする | 本番コードに `MOCK=1` のような試験専用分岐を散らす |
| フィクスチャは `ARCHITECTURE.md` のデータ契約（Pydantic）に合う構造化出力を返す | 契約と違う形の「それっぽい文字列」をモック応答の正とする |

共通 fixture の名前と差し替え口は、pytest を導入する土台 Issue で `tests/conftest.py` に一度定義する。後続 Issue はそれを import して使う。

## ライブの OpenRouter 呼び出しは secret があるときだけ

| 実行 | 秘密 | LLM |
| --- | --- | --- |
| 既定の `uv run pytest` | 不要 | モック。ネットワークへ出ない |
| Cloud Agent のライブ評価 | Cursor Secret `OPENROUTER_API_KEY` があるときだけ | 実呼び出し可 |
| 製品実行（Podman） | `openrouter_api_key_oogiri` | 実呼び出し（試験ではない） |

secret が無いときにライブ試験を走らせない。キーを `config.toml`、プロンプト、ログ、コミットに書かない（SRS-MVP-QA-002）。

マーカー（pytest 導入後）:

- 既定収集: ユニット試験と契約試験のみ。ライブ無しで通る。
- ライブ / DeepEval は `@pytest.mark.live` 等で既定から外す。secret が無いときは skip する。

## ユニット試験の対象

件数・書き換え禁止・相互非参照はユニット試験の対象である。モック LLM で、実モデルの出来に依存させない。

| 対象 | 保証すること | 要件 |
| --- | --- | --- |
| 件数 | 前提ちょうど 3、凡庸案ちょうど 5、回答者 1 体あたり 7 案以上、ツッコミ役の採択ちょうど 5、出力ちょうど 1 | SRS-MVP-FN-009、015、020、025、027 |
| 書き換え禁止 | ツッコミ役は案本文を書き換えない。`Shortlist.selected[].text` は原案のまま | SRS-MVP-FN-021 |
| 相互非参照 | ある回答者へ他回答者の案・プロンプト・パラメータを渡さない | SRS-MVP-FN-016 |
| スキーマ | エージェント間ペイロードが Pydantic 検証に通る。不正件数は reject | SRS-MVP-QA-003 |

不正なフィクスチャ（前提 2 個、相互参照付き入力、書き換え済み shortlist など）を与えて **失敗すること** もユニット試験で見る。

笑いの面白さ、芸風の良さ、ツッコミの切れはユニット試験のアサーションにしない。

推敲の「内容を足さない」（SRS-MVP-FN-023、024）は **Inspection** とする。`PolishedAnswer` は `text` だけで、元案との対応や追加事実を表すフィールドを持たない。Pydantic 契約や Fake LLM のスキーマでは落とさない。実装 Issue ごとに意味的な追加検出器を発明しない。プロンプトとコードが削る・オチ位置・語尾の 3 操作に限っていることを見る。笑いの質としての評価は DeepEval（Issue #10）に残す。

## 契約試験

契約試験は、モック LLM でパイプラインを通し、**構造**を保証する。品質の代替ではない。

見るもの:

- 処理順: 座付き作家 → 回答者コーディネーター → 回答者 n 体（並列）→ ツッコミ役 → 推敲役 → テキスト 1 案（`ARCHITECTURE.md`）
- 座付き作家の `AnalysisMemo` が全回答者に同じ内容で配られる
- `Roster.respondents` の長さが `respondent_num`
- 標準出力は推敲後の 1 案だけ（中間メモ・ツッコミ・落選案は既定では出さない）
- `--image` は画像経路を走らせず非 0
- API キー無しでは生成せず非 0

モック応答は各段階の Pydantic モデルを満たす。DeepEval のスコアで「5 案選ばれた」ことを証明してはならない。

## DeepEval

DeepEval は出力評価（SRS-MVP-DC-008）であり、笑いの質の Analysis に使う。

- `generate` の標準出力経路には載せない（`ARCHITECTURE.md`）。
- パイプラインが件数を守ったか、本文を書き換えなかったか、相互非参照かは **pytest のユニット / 契約試験** で見る。DeepEval の合否で代用しない。
- 採点基準そのもの（何点以上、どのメトリクスか）は Issue #10 が決める。本文書は「品質評価に回す」ことだけを固定する。
- ライブの OpenRouter 呼び出しは secret があるときだけ。secret 無しの CI / 既定 pytest を赤にしない。

## 置き場と実行コマンド

テストの置き場は `tests/` とする（`ARCHITECTURE.md`）。

```text
tests/
  conftest.py          # LLM モックの共通 fixture（正本）
  unit/                # 件数・書き換え禁止・相互非参照・スキーマ
  contract/            # モック LLM によるパイプライン契約
  eval/                # DeepEval。既定の pytest から外す
```

実行コマンド:

```sh
uv run pytest
```

これが検証の主経路である。OpenRouter はモックする。`uv pip` は使わない。

`pyproject.toml` がまだ無い土台 Issue では pytest を走らせなくてよい。土台以降は `uv run pytest` が通る状態を維持する（`AGENTS.md`）。

## 実装 Issue への拘束

- モックは `src/oogiri/llm.py` と `tests/conftest.py` に集約する。役割ごとに新しいモック機構を足さない。
- 件数・書き換え禁止・相互非参照を DeepEval や人手デモだけに逃がさない。
- 推敲の内容追加禁止（FN-024）を Pydantic や独自の意味判定器で落とさない。Inspection とする。
- 既定の `uv run pytest` にライブ API を必須にしない。
- 採点表は #10 を先取りしてここにコピーしない。
- 本文書と SRS が衝突する場合は SRS に合わせ、本文書の修正 Issue を人間へ依頼する。`docs/source-of-truth/` は編集しない。
