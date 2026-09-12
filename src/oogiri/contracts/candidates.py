"""回答者の案（SRS-MVP-FN-015、016、QA-003）。"""

from __future__ import annotations

from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]

Candidates = Annotated[tuple["Candidate", ...], Field(min_length=7)]


class Candidate(BaseModel):
    """大喜利の回答本文 1 本。後段で書き換えない。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: NonEmptyStr
    respondent_id: NonEmptyStr
    text: NonEmptyStr


class CandidateBatch(BaseModel):
    """1 回答者の案。7 件以上。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    respondent_id: NonEmptyStr
    candidates: Candidates

    @model_validator(mode="after")
    def candidates_match_respondent(self) -> Self:
        _reject_mismatched_respondent_ids(self)
        _reject_duplicate_candidate_ids(self.candidates)
        return self


def _reject_mismatched_respondent_ids(batch: CandidateBatch) -> None:
    for candidate in batch.candidates:
        if candidate.respondent_id != batch.respondent_id:
            raise ValueError("案の回答者 ID がバッチと一致しません")


def _reject_duplicate_candidate_ids(candidates: tuple[Candidate, ...]) -> None:
    ids = [item.candidate_id for item in candidates]
    if len(set(ids)) != len(ids):
        raise ValueError("案 ID が重複しています")
