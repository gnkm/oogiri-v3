"""座付き作家の分析メモ（SRS-MVP-FN-009、QA-003）。"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]

Premises = Annotated[list[NonEmptyStr], Field(min_length=3, max_length=3)]
BanalIdeas = Annotated[list[NonEmptyStr], Field(min_length=5, max_length=5)]


class AnalysisMemo(BaseModel):
    """お題の型・笑いの方向・前提 3・凡庸案 5。後段の回答者全員に同じものを配る。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    theme_type: NonEmptyStr
    humor_direction: NonEmptyStr
    premises: Premises
    banal_ideas: BanalIdeas
