"""推敲役の成果（SRS-MVP-FN-022〜027、QA-003）。"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]


class PolishedAnswer(BaseModel):
    """推敲後の大喜利回答本文 1 本。内容の追加はしない。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: NonEmptyStr
