"""回答者コーディネーターの編成（SRS-MVP-FN-011〜013、QA-003）。"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

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
