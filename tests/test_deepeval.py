"""DeepEval による出力評価（SRS-MVP-DC-008 / Issue #10）。

メトリクス: GEval `PolishedAnswerForm`
閾値: 0.5（公開スコア 0–1。未満なら `assert_test` が失敗し pytest は非 0）
ルーブリック: お題に対する単一の大喜利回答か。中間成果物が混ざっていないか。
面白さの絶対点は見ない。

既定の pytest は MockJudge でメトリクスを実行する（ライブ API 不要）。
ライブの OpenRouter 判定は `@pytest.mark.live`（secret があるときだけ）。
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "1")
os.environ.setdefault("DEEPEVAL_DISABLE_DOTENV", "1")

import pytest
from deepeval import assert_test

from oogiri.secrets import ENV_API_KEY


def _load_polished_form() -> ModuleType:
    path = Path(__file__).resolve().parent / "eval" / "polished_form.py"
    spec = importlib.util.spec_from_file_location("oogiri_eval_polished_form", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_polished_form = _load_polished_form()
METRIC_NAME = _polished_form.METRIC_NAME
THRESHOLD = _polished_form.THRESHOLD
make_form_metric = _polished_form.make_form_metric
openrouter_model_id = _polished_form.openrouter_model_id
polished_test_case = _polished_form.polished_test_case


def test_deepeval_runs_on_polished_fixture() -> None:
    """推敲後テキスト 1 案のフィクスチャに対し DeepEval が 1 本走る。"""
    metric = make_form_metric(judge_score=10)
    test_case = polished_test_case()
    assert_test(test_case, [metric], run_async=False)
    assert metric.success is True
    assert metric.score is not None
    assert metric.score >= THRESHOLD
    assert METRIC_NAME in metric.__name__


def test_deepeval_below_threshold_fails_pytest() -> None:
    """評価が閾値未満なら assert_test が失敗し、pytest は非 0 になりうる。"""
    metric = make_form_metric(judge_score=0, judge_reason="fail")
    with pytest.raises(AssertionError, match=r"threshold: 0\.5"):
        assert_test(polished_test_case(), [metric], run_async=False)
    assert metric.success is False
    assert metric.score is not None
    assert metric.score < THRESHOLD


def test_openrouter_prefix_is_stripped() -> None:
    assert openrouter_model_id("openrouter/openai/gpt-4o-mini") == "openai/gpt-4o-mini"
    assert openrouter_model_id("openai/gpt-4o-mini") == "openai/gpt-4o-mini"


@pytest.mark.live
def test_deepeval_live_openrouter_on_polished_fixture() -> None:
    """secret があるときだけ OpenRouter で同じメトリクスを実行する。"""
    api_key = os.environ.get(ENV_API_KEY, "").strip()
    if not api_key:
        pytest.skip(f"{ENV_API_KEY} が無い")

    from deepeval.models import OpenRouterModel

    from oogiri.config import load_config

    judge = load_config().eval.judge
    model_id = openrouter_model_id(judge.model)
    metric = make_form_metric(
        model=OpenRouterModel(
            model=model_id,
            api_key=api_key,
            temperature=judge.temperature,
        )
    )
    assert_test(polished_test_case(), [metric], run_async=False)
    assert metric.success is True
    assert metric.score is not None
    assert metric.score >= THRESHOLD
