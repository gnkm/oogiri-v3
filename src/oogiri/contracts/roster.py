"""回答者コーディネーターの編成（SRS-MVP-FN-011〜013、QA-003）。"""

from __future__ import annotations

from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]

Axes = Annotated[tuple["StyleAxis", ...], Field(min_length=1)]
Respondents = Annotated[tuple["RespondentSpec", ...], Field(min_length=1)]


class StyleAxis(BaseModel):
    """実行ごとに決める芸風の軸。種類も件数も固定しない。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: NonEmptyStr
    description: NonEmptyStr


class RespondentSpec(BaseModel):
    """1 回答者のプロンプトとパラメータ。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    respondent_id: NonEmptyStr
    axis: StyleAxis
    system_prompt: NonEmptyStr
    model: NonEmptyStr
    temperature: float = Field(gt=0, le=2)

    @field_validator("temperature")
    @classmethod
    def temperature_must_be_high(cls, value: float) -> float:
        if value < 0.5:
            raise ValueError("回答者の温度は高温のままにする")
        return value


class Roster(BaseModel):
    """芸風の軸と n 体の回答者定義。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    axes: Axes
    respondents: Respondents

    @model_validator(mode="after")
    def axes_and_ids_are_consistent(self) -> Self:
        _reject_duplicate_ids(self.respondents)
        indexed = _axis_by_name(self.axes)
        for spec in self.respondents:
            _require_known_axis(spec.axis, indexed)
        return self


def _reject_duplicate_ids(respondents: tuple[RespondentSpec, ...]) -> None:
    ids = [item.respondent_id for item in respondents]
    if len(set(ids)) != len(ids):
        raise ValueError("回答者 ID が重複しています")


def _axis_by_name(axes: tuple[StyleAxis, ...]) -> dict[str, StyleAxis]:
    indexed: dict[str, StyleAxis] = {}
    for axis in axes:
        _put_unique_axis(indexed, axis)
    return indexed


def _put_unique_axis(indexed: dict[str, StyleAxis], axis: StyleAxis) -> None:
    prev = indexed.get(axis.name)
    if prev is None:
        indexed[axis.name] = axis
        return
    if prev != axis:
        raise ValueError("同名で異なる軸定義があります")


def _require_known_axis(axis: StyleAxis, indexed: dict[str, StyleAxis]) -> None:
    if indexed.get(axis.name) != axis:
        raise ValueError("回答者の軸が axes にありません")
