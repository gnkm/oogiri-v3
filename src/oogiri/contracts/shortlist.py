"""ツッコミ役の審査結果（SRS-MVP-FN-017〜021、QA-003）。"""

from __future__ import annotations

from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from oogiri.contracts.candidates import Candidate

NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
Score = Annotated[float, Field(ge=0, le=10, allow_inf_nan=False)]

Selected = Annotated[tuple[Candidate, ...], Field(min_length=5, max_length=5)]
Notes = Annotated[tuple["TsukkomiNote", ...], Field(min_length=5)]


class TsukkomiNote(BaseModel):
    """1 案へのツッコミ。不能なら落とし、理由を残す。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: NonEmptyStr
    tsukkomi: NonEmptyStr
    dropped: bool
    score: Score


class Shortlist(BaseModel):
    """ツッコミ付きの残存全案と、採択ちょうど 5。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    selected: Selected
    notes: Notes

    @model_validator(mode="after")
    def selected_are_kept_and_unique(self) -> Self:
        _reject_duplicate_note_ids(self.notes)
        _reject_duplicate_selected_ids(self.selected)
        notes_by_id = {note.candidate_id: note for note in self.notes}
        for candidate in self.selected:
            _require_kept_note(candidate, notes_by_id)
        return self


def _reject_duplicate_note_ids(notes: tuple[TsukkomiNote, ...]) -> None:
    ids = [item.candidate_id for item in notes]
    if len(set(ids)) != len(ids):
        raise ValueError("ツッコミ対象の案 ID が重複しています")


def _reject_duplicate_selected_ids(selected: tuple[Candidate, ...]) -> None:
    ids = [item.candidate_id for item in selected]
    if len(set(ids)) != len(ids):
        raise ValueError("採択の案 ID が重複しています")


def _require_kept_note(
    candidate: Candidate, notes_by_id: dict[str, TsukkomiNote]
) -> None:
    note = notes_by_id.get(candidate.candidate_id)
    if note is None:
        raise ValueError("採択案のツッコミがありません")
    if note.dropped:
        raise ValueError("ツッコミ不能の案は選べません")
