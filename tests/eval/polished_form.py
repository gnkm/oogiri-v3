"""推敲後 1 案向け DeepEval メトリクス（SRS-MVP-DC-008）。

笑いの絶対基準は置かない。お題に対する単一回答の形だけを見る。
"""

from __future__ import annotations

import os

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "1")
os.environ.setdefault("DEEPEVAL_DISABLE_DOTENV", "1")

from deepeval.metrics import GEval
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from pydantic import BaseModel

from oogiri.contracts.polished import PolishedAnswer

# GEval の公開スコアは 0–1。内部 judge は 0–10。threshold は公開スコア側。
METRIC_NAME = "PolishedAnswerForm"
THRESHOLD = 0.5
THEME = "こんなAIはいやだ。どんなAI？"
POLISHED_TEXT = "アラームを二度寝の権利と誤認するAI"

CRITERIA = (
    "お題（input）に対する大喜利の回答（actual_output）として成立しているかを見る。"
    "単一の回答本文であること。分析メモ・ツッコミ・落選案・選評が混ざっていないこと。"
    "面白さや笑いの絶対点は採点しない。お題に対する回答の形をしていれば高くする。"
)
EVALUATION_STEPS = [
    "actual_output が空でない単一の回答本文かを確認する",
    "input のお題に対する回答になっているかを確認する",
    "分析メモ・ツッコミ・落選案・選評が混ざっていないかを確認する",
    "面白さは点に反映しない",
]


class MockJudge(DeepEvalBaseLLM):
    """既定 pytest 用。GEval が期待する ReasonScore / Steps を返す。"""

    def __init__(self, score: float = 10, reason: str = "ok") -> None:
        self._score = score
        self._reason = reason
        super().__init__(model="mock-judge")

    def load_model(self, *args: object, **kwargs: object) -> MockJudge:
        return self

    def generate(
        self, prompt: str, schema: type[BaseModel] | None = None
    ) -> str | BaseModel:
        if schema is None:
            return f'{{"score": {self._score}, "reason": "{self._reason}"}}'
        payload: dict[str, object] = {}
        fields = schema.model_fields
        if "steps" in fields:
            payload["steps"] = list(EVALUATION_STEPS)
        if "score" in fields:
            payload["score"] = self._score
        if "reason" in fields:
            payload["reason"] = self._reason
        return schema(**payload)

    async def a_generate(
        self, prompt: str, schema: type[BaseModel] | None = None
    ) -> str | BaseModel:
        return self.generate(prompt, schema)

    def get_model_name(self, *args: object, **kwargs: object) -> str:
        return "mock-judge"


def make_form_metric(
    *,
    model: DeepEvalBaseLLM | None = None,
    judge_score: float = 10,
    judge_reason: str = "ok",
) -> GEval:
    """推敲後 1 案の形を見る GEval。既定は MockJudge。"""
    judge = (
        model
        if model is not None
        else MockJudge(score=judge_score, reason=judge_reason)
    )
    return GEval(
        name=METRIC_NAME,
        criteria=CRITERIA,
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        evaluation_steps=EVALUATION_STEPS,
        threshold=THRESHOLD,
        model=judge,
        async_mode=False,
    )


def polished_test_case(*, text: str = POLISHED_TEXT) -> LLMTestCase:
    """評価対象は推敲後テキスト 1 案（PolishedAnswer フィクスチャ）。"""
    answer = PolishedAnswer(text=text)
    return LLMTestCase(input=THEME, actual_output=answer.text)


def openrouter_model_id(raw: str) -> str:
    """CrewAI 用の `openrouter/` 接頭辞を OpenRouter のモデル ID から外す。"""
    return raw.removeprefix("openrouter/")
