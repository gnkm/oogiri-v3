---
title: 大喜利ジェネレーター SRS
description: テキストと画像出力を前提とする製品 SRS（ISO/IEC/IEEE 29148:2018 形式）
author: gnkm
ai:
  editable: true
  reason: 提案中
created: 2026-09-12
---

# 大喜利ジェネレーター SRS

本文書は **テキストと画像の両方の出力** を前提とする製品仕様である。パイプライン（座付き作家〜推敲役）は `docs/source-of-truth/srs-mvp.md` と同一とし、ここでは出力段と CLI の差分を定める。MVP の実装範囲は `srs-mvp.md` を優先する。

> `docs/source-of-truth/` へ移すのは人間が行う。AI は source-of-truth を編集しない。

## 1. Purpose / Scope

本ソフトウェアは、お題に対する大喜利回答を **テキストまたは画像** として返す。画像は推敲後の 1 案を入力とする出力段であり、座付き作家〜推敲の別パイプラインは作らない。

GUI、Web API、永続保存は対象外。

## 2. Requirements

識別子は `SRS-IMG-<AREA>-<NNN>`。パイプライン本体は `SRS-MVP-*` を再定義しない。

**SRS-IMG-IF-001** 次の CLI を提供するものとする。

```sh
oogiri generate --theme '<お題>' --text
oogiri generate --theme '<お題>' --image
oogiri generate --theme '<お題>' --text --respondent-num <n>
oogiri generate --theme '<お題>' --image --respondent-num <n>
```

**SRS-IMG-IF-002** `--text` と `--image` は排他とする。両方またはどちらも無い場合は非 0 で終える。

**SRS-IMG-IF-003** `--theme` / `--respondent-num` は SRS-MVP-IF-002 / SRS-MVP-IF-004 に従う。

**SRS-IMG-IF-004** 画像モデルは `config.toml` で個別指定できる。

**SRS-IMG-FN-001** `--text` / `--image` のいずれでも、パイプライン順は SRS-MVP 2.2.3 と同一とする。

**SRS-IMG-FN-002** 出力形式の違いで、ツッコミ役の書き換え禁止・推敲役の追加禁止を緩めてはならない。

**SRS-IMG-FN-003** `--text` 時は推敲後の 1 案をテキスト出力する。

**SRS-IMG-FN-004** `--image` 時は推敲後の 1 案に基づく画像を出力する。

**SRS-IMG-FN-005** 画像出力は推敲完了後。回答者は画像を直接出さず、互いの画像も見ない。

**SRS-IMG-FN-006** `--image` 時、テキストだけを成果として終えてはならない。

## 3. Verification

| ID | 検証の目安 |
| --- | --- |
| SRS-IMG-IF-001〜002 | `--text` と `--image` が排他 |
| SRS-IMG-FN-004〜006 | `--image` で画像が出る。回答者段に画像が混ざらない |

## 4. MVP との関係

実装順は MVP を先に完了し、その後に SRS-IMG-* を載せる。
