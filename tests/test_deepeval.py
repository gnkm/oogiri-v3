"""DeepEval による出力評価（SRS-MVP-DC-008 / Issue #10・#28）。

メトリクス:
- GEval `PolishedAnswerForm`（形の検査）
- GEval `HumorQuality`（おもしろさの質。相対観点のみ）

閾値: いずれも 0.5（公開スコア 0–1。未満なら `assert_test` が失敗し pytest は非 0）
面白さの絶対点は見ない。

既定の pytest は MockJudge でメトリクスを実行する（ライブ API 不要）。
ライブの OpenRouter 判定は `@pytest.mark.live`（secret があるときだけ）。
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "1")
os.environ.setdefault("DEEPEVAL_DISABLE_DOTENV", "1")

import pytest
from deepeval import assert_test

from oogiri.secrets import ENV_API_KEY


def _load_eval_module(filename: str, module_name: str) -> ModuleType:
    path = Path(__file__).resolve().parent / "eval" / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_polished_form = _load_eval_module("polished_form.py", "oogiri_eval_polished_form")
METRIC_NAME = _polished_form.METRIC_NAME
THRESHOLD = _polished_form.THRESHOLD
make_form_metric = _polished_form.make_form_metric
openrouter_model_id = _polished_form.openrouter_model_id
polished_test_case = _polished_form.polished_test_case

_humor_quality = _load_eval_module("humor_quality.py", "oogiri_eval_humor_quality")
HUMOR_METRIC_NAME = _humor_quality.METRIC_NAME
HUMOR_THRESHOLD = _humor_quality.THRESHOLD
HUMOR_CRITERIA = _humor_quality.CRITERIA
HUMOR_STEPS = _humor_quality.EVALUATION_STEPS
GOLDENS = _humor_quality.GOLDENS
GOOD_GOLDEN = _humor_quality.GOOD_GOLDEN
BAD_GOLDEN = _humor_quality.BAD_GOLDEN
make_humor_metric = _humor_quality.make_humor_metric
humor_test_case = _humor_quality.humor_test_case


def test_polished_form_runs_on_fixture() -> None:
    """推敲後テキスト 1 案のフィクスチャに対し DeepEval が 1 本走る。"""
    metric = make_form_metric(judge_score=10)
    test_case = polished_test_case()
    assert_test(test_case, [metric], run_async=False)
    assert metric.success is True
    assert metric.score is not None
    assert metric.score >= THRESHOLD
    assert METRIC_NAME in metric.__name__
    assert METRIC_NAME == "PolishedAnswerForm"


def test_polished_form_below_threshold_fails() -> None:
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


def test_humor_quality_goldens_include_good_and_bad() -> None:
    """良い例と悪い例を少なくとも 1 組ずつ置く。"""
    assert any(golden.expect_pass for golden in GOLDENS)
    assert any(not golden.expect_pass for golden in GOLDENS)
    assert GOOD_GOLDEN.expect_pass is True
    assert BAD_GOLDEN.expect_pass is False
    assert GOOD_GOLDEN.text != BAD_GOLDEN.text


def test_humor_quality_rubric_is_relative() -> None:
    """面白さの絶対点は見ない。お題との噛み・オチ位置・凡庸回避がある。"""
    rubric = HUMOR_CRITERIA + "\n".join(HUMOR_STEPS)
    assert "面白さの絶対点は見ない" in rubric
    assert "お題との噛み" in rubric
    assert "オチ位置" in rubric
    assert "凡庸回避" in rubric
    assert HUMOR_METRIC_NAME == "HumorQuality"


def test_humor_quality_good_golden_passes() -> None:
    """良い例は MockJudge で HumorQuality が閾値以上になる。"""
    metric = make_humor_metric(judge_score=10)
    assert_test(humor_test_case(GOOD_GOLDEN), [metric], run_async=False)
    assert metric.success is True
    assert metric.score is not None
    assert metric.score >= HUMOR_THRESHOLD
    assert HUMOR_METRIC_NAME in metric.__name__


def test_humor_quality_bad_golden_fails_below_threshold() -> None:
    """悪い例は閾値未満で assert_test が失敗する。"""
    metric = make_humor_metric(judge_score=0, judge_reason="fail")
    with pytest.raises(AssertionError, match=r"threshold: 0\.5"):
        assert_test(humor_test_case(BAD_GOLDEN), [metric], run_async=False)
    assert metric.success is False
    assert metric.score is not None
    assert metric.score < HUMOR_THRESHOLD


@pytest.mark.live
def test_polished_form_live_openrouter() -> None:
    """secret があるときだけ OpenRouter で同じメトリクスを実行する。"""
    api_key = os.environ.get(ENV_API_KEY, "").strip()
    if not api_key:
        pytest.skip(f"{ENV_API_KEY} が無い")

    from deepeval.models import OpenRouterModel

    from oogiri.config import load_config

    model_id = openrouter_model_id(load_config().agents.polisher.model)
    metric = make_form_metric(
        model=OpenRouterModel(
            model=model_id,
            api_key=api_key,
            temperature=0,
        )
    )
    assert_test(polished_test_case(), [metric], run_async=False)
    assert metric.success is True
    assert metric.score is not None
    assert metric.score >= THRESHOLD


def _live_openrouter_model():
    api_key = os.environ.get(ENV_API_KEY, "").strip()
    if not api_key:
        pytest.skip(f"{ENV_API_KEY} が無い")

    from deepeval.models import OpenRouterModel

    from oogiri.config import load_config

    model_id = openrouter_model_id(load_config().agents.polisher.model)
    return OpenRouterModel(model=model_id, api_key=api_key, temperature=0)


@pytest.mark.live
def test_humor_quality_live_openrouter() -> None:
    """secret があるときだけ OpenRouter で HumorQuality を実行する。"""
    metric = make_humor_metric(model=_live_openrouter_model())
    assert_test(humor_test_case(GOOD_GOLDEN), [metric], run_async=False)
    assert metric.success is True
    assert metric.score is not None
    assert metric.score >= HUMOR_THRESHOLD
