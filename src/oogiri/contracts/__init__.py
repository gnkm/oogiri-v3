"""エージェント間ペイロードの Pydantic モデル。"""

from oogiri.contracts.analysis import AnalysisMemo
from oogiri.contracts.candidates import Candidate, CandidateBatch
from oogiri.contracts.roster import RespondentSpec, Roster, StyleAxis

__all__ = [
    "AnalysisMemo",
    "Candidate",
    "CandidateBatch",
    "RespondentSpec",
    "Roster",
    "StyleAxis",
]
