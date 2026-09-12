"""エージェント間ペイロードの Pydantic モデル。"""

from oogiri.contracts.analysis import AnalysisMemo
from oogiri.contracts.candidates import Candidate, CandidateBatch
from oogiri.contracts.polished import PolishedAnswer
from oogiri.contracts.roster import RespondentSpec, Roster, StyleAxis
from oogiri.contracts.shortlist import Shortlist, TsukkomiNote

__all__ = [
    "AnalysisMemo",
    "Candidate",
    "CandidateBatch",
    "PolishedAnswer",
    "RespondentSpec",
    "Roster",
    "Shortlist",
    "StyleAxis",
    "TsukkomiNote",
]
