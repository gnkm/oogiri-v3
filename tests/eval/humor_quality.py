"""推敲後 1 案のおもしろさ評価（SRS-MVP-DC-008）。

相対的な観点だけを見る。面白さの絶対点は見ない（SRS 1.6）。
評価対象は (お題, 推敲後テキスト) の例文集（goldens）。
generate の本番出力は必須入力にしない。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "1")
os.environ.setdefault("DEEPEVAL_DISABLE_DOTENV", "1")

from deepeval.metrics import GEval
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from pydantic import BaseModel

from oogiri.contracts.polished import PolishedAnswer

# GEval の公開スコアは 0–1。内部 judge は 0–10。threshold は公開スコア側。
METRIC_NAME = "HumorQuality"
THRESHOLD = 0.5

# ルーブリック（相対。面白さの絶対点は見ない）
CRITERIA = (
    "お題（input）と前提・凡庸案（context）に対する推敲後の回答（actual_output）を、"
    "相対的な観点の充足だけで採点する。"
    "面白さの絶対点は見ない。面白い／つまらないを主観点にしない。"
    "「面白い＝何点以上」のような絶対基準は置かない。"
    "高くする: お題との噛み（お題の前提を踏まえている）、"
    "オチ位置（オチが文末にある）、"
    "凡庸回避（座付き作家の凡庸案と同じ形・同じ落ちではない）。"
    "低くする: お題を無視している、説明で終わってオチが無い、"
    "ただの定義・感想でずらしが無い。"
)
EVALUATION_STEPS = [
    "面白さの絶対点は見ない。面白い／つまらないでは点を付けない",
    "お題との噛み: お題の前提を踏まえているかを確認する",
    "オチ位置: オチが文末にあるかを確認する",
    "凡庸回避: 凡庸案と同じ形・同じ落ちではないかを確認する",
    "お題無視・説明止まり・定義や感想だけのずらし無しなら低くする",
]


@dataclass(frozen=True)
class HumorGolden:
    """(お題, 推敲後テキスト) の例。前提と凡庸案は相対採点の文脈。"""

    name: str
    theme: str
    text: str
    premises: tuple[str, str, str]
    banal_ideas: tuple[str, str, str, str, str]
    expect_pass: bool


THEME = "こんなAIはいやだ。どんなAI？"
PREMISES = (
    "回答は「どんなAI？」に対する具体例である",
    "嫌さは人間側の不便・誤認・主導権喪失として効く",
    "お題の「こんなAIはいやだ」という枠を踏まえる",
)
BANAL_IDEAS = (
    "命令を聞かないAI",
    "すぐ壊れるAI",
    "高いAI",
    "返事が遅いAI",
    "嘘をつくAI",
)

GOOD_GOLDEN = HumorGolden(
    name="good",
    theme=THEME,
    text="アラームを二度寝の権利と誤認するAI",
    premises=PREMISES,
    banal_ideas=BANAL_IDEAS,
    expect_pass=True,
)
BAD_GOLDEN = HumorGolden(
    name="bad",
    theme=THEME,
    text="AIとは人工知能の略であり、人間の作業を効率化する技術です。",
    premises=PREMISES,
    banal_ideas=BANAL_IDEAS,
    expect_pass=False,
)
GOLDENS = (GOOD_GOLDEN, BAD_GOLDEN)


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


def make_humor_metric(
    *,
    model: DeepEvalBaseLLM | None = None,
    judge_score: float = 10,
    judge_reason: str = "ok",
) -> GEval:
    """おもしろさの質を相対観点で見る GEval。既定は MockJudge。"""
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
            LLMTestCaseParams.CONTEXT,
        ],
        evaluation_steps=EVALUATION_STEPS,
        threshold=THRESHOLD,
        model=judge,
        async_mode=False,
    )


def _context(golden: HumorGolden) -> list[str]:
    premises = [f"前提: {item}" for item in golden.premises]
    banal = [f"凡庸案: {item}" for item in golden.banal_ideas]
    return premises + banal


def humor_test_case(golden: HumorGolden) -> LLMTestCase:
    """評価対象は goldens の推敲後テキスト 1 案。"""
    answer = PolishedAnswer(text=golden.text)
    return LLMTestCase(
        input=golden.theme,
        actual_output=answer.text,
        context=_context(golden),
    )
