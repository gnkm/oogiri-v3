"""診断用の段階進捗。`--verbose` のときだけ標準エラーへ出す。"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterable
from typing import TextIO

from oogiri.contracts.analysis import AnalysisMemo
from oogiri.contracts.candidates import CandidateBatch
from oogiri.contracts.polished import PolishedAnswer
from oogiri.contracts.roster import RespondentSpec, Roster
from oogiri.contracts.shortlist import Shortlist

PREFIX = "[oogiri]"


class ProgressReporter:
    """段階の開始・完了と中間成果の要約。既定は無出力。"""

    def __init__(self, *, enabled: bool = False, stream: TextIO | None = None) -> None:
        self.enabled = enabled
        self._stream = sys.stderr if stream is None else stream

    def start(self, role: str, extra: str = "") -> None:
        if not self.enabled:
            return
        self._emit(_status_line(role, "開始", extra))

    def done(self, role: str, extra: str = "") -> None:
        if not self.enabled:
            return
        self._emit(_status_line(role, "完了", extra))

    def report(self, formatter: Callable[..., Iterable[str]], *args: object) -> None:
        if not self.enabled:
            return
        self.lines(formatter(*args))

    def lines(self, rows: Iterable[str]) -> None:
        if not self.enabled:
            return
        for row in rows:
            self._emit(row)

    def _emit(self, line: str) -> None:
        print(line, file=self._stream, flush=True)


def memo_lines(memo: AnalysisMemo) -> tuple[str, ...]:
    premises = " / ".join(memo.premises)
    banals = " / ".join(memo.banal_ideas)
    return (
        f"  お題の型: {memo.theme_type}",
        f"  笑いの方向: {memo.humor_direction}",
        f"  前提 ({len(memo.premises)}): {premises}",
        f"  凡庸案 ({len(memo.banal_ideas)}): {banals}",
    )


def roster_lines(roster: Roster) -> tuple[str, ...]:
    axes = ", ".join(axis.name for axis in roster.axes)
    header = (
        f"  軸 ({len(roster.axes)}): {axes}",
        f"  回答者: {len(roster.respondents)} 体",
    )
    members = tuple(_respondent_line(spec) for spec in roster.respondents)
    return (*header, *members)


def batch_lines(batch: CandidateBatch) -> tuple[str, ...]:
    header = f"  {batch.respondent_id}: {len(batch.candidates)} 案"
    texts = tuple(f"    - {item.text}" for item in batch.candidates)
    return (header, *texts)


def batches_lines(batches: tuple[CandidateBatch, ...]) -> tuple[str, ...]:
    total = sum(len(batch.candidates) for batch in batches)
    header = (f"  合計: {len(batches)} 体 / {total} 案",)
    body = tuple(line for batch in batches for line in batch_lines(batch))
    return (*header, *body)


def shortlist_lines(shortlist: Shortlist) -> tuple[str, ...]:
    dropped = sum(1 for note in shortlist.notes if note.dropped)
    header = (
        f"  審査 {len(shortlist.notes)} 案 / 落選 {dropped}"
        f" / 採択 {len(shortlist.selected)}"
    )
    selected = tuple(f"    - {item.text}" for item in shortlist.selected)
    return (header, "  採択:", *selected)


def polished_lines(answer: PolishedAnswer) -> tuple[str, ...]:
    return (f"  推敲後: {answer.text}",)


def _status_line(role: str, status: str, extra: str) -> str:
    suffix = f" {extra}" if extra else ""
    return f"{PREFIX} {role}: {status}{suffix}"


def _respondent_line(spec: RespondentSpec) -> str:
    return f"    - {spec.respondent_id} / {spec.axis.name}"
