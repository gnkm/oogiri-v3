"""CrewAI 上の generate パイプライン（SRS-MVP-FN-002、FN-007、DC-005）。"""

from __future__ import annotations

import os

os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_DISABLE_TRACKING", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from crewai import Agent, Crew, Process, Task

from oogiri.agents.coordinator import CoordinatorError, coordinate
from oogiri.agents.polisher import PolishError, polish
from oogiri.agents.respondent import RespondentError, respond
from oogiri.agents.seated_writer import AnalysisError, analyze
from oogiri.agents.tsukkomi import TsukkomiError, review
from oogiri.config import AgentLLMConfig, AppConfig, ConfigError, load_config
from oogiri.contracts.analysis import AnalysisMemo
from oogiri.contracts.candidates import CandidateBatch
from oogiri.contracts.polished import PolishedAnswer
from oogiri.contracts.roster import Roster
from oogiri.contracts.shortlist import Shortlist
from oogiri.llm import llm_for_role
from oogiri.progress import (
    ProgressReporter,
    batches_lines,
    memo_lines,
    polished_lines,
    roster_lines,
    shortlist_lines,
)
from oogiri.prompts import PromptError

DEFAULT_RESPONDENT_NUM = 3
ROLE_SEATED_WRITER = "座付き作家"
ROLE_COORDINATOR = "回答者コーディネーター"
ROLE_TSUKKOMI = "ツッコミ役"
ROLE_POLISHER = "推敲役"

_STAGE_ERRORS = (
    AnalysisError,
    CoordinatorError,
    RespondentError,
    TsukkomiError,
    PolishError,
    ConfigError,
    PromptError,
)


class PipelineError(Exception):
    """パイプラインの実行に失敗した。メッセージに秘密を含めない。"""


def pipeline_roles(respondent_num: int) -> tuple[str, ...]:
    """SRS 2.2.3 の役割順。回答者だけ n 体。"""
    _require_positive_n(respondent_num)
    respondents = tuple(
        _respondent_role(index) for index in range(1, respondent_num + 1)
    )
    return (
        ROLE_SEATED_WRITER,
        ROLE_COORDINATOR,
        *respondents,
        ROLE_TSUKKOMI,
        ROLE_POLISHER,
    )


def build_crew(
    *,
    theme: str,
    respondent_num: int = DEFAULT_RESPONDENT_NUM,
    config: AppConfig | None = None,
) -> Crew:
    """処理順を固定した CrewAI Crew を組む。"""
    _require_positive_n(respondent_num)
    cfg = config if config is not None else load_config()
    agents = _agents(respondent_num, cfg)
    tasks = _tasks(theme, agents, respondent_num)
    return Crew(agents=agents, tasks=tasks, process=Process.sequential, verbose=False)


def generate_answer(
    theme: str,
    respondent_num: int = DEFAULT_RESPONDENT_NUM,
    *,
    config: AppConfig | None = None,
    verbose: bool = False,
    progress: ProgressReporter | None = None,
) -> PolishedAnswer:
    """座付き作家から推敲役までを走らせ、テキスト 1 案を返す。"""
    _require_positive_n(respondent_num)
    cfg = config if config is not None else load_config()
    reporter = progress if progress is not None else ProgressReporter(enabled=verbose)
    build_crew(theme=theme, respondent_num=respondent_num, config=cfg)
    try:
        return _run_stages(theme, respondent_num, cfg, reporter)
    except _STAGE_ERRORS as exc:
        raise PipelineError(str(exc)) from exc


def _require_positive_n(respondent_num: int) -> None:
    if respondent_num < 1:
        raise PipelineError("回答者数は 1 以上である必要があります")


def _run_stages(
    theme: str,
    respondent_num: int,
    config: AppConfig,
    reporter: ProgressReporter,
) -> PolishedAnswer:
    memo = _stage_analyze(theme, config, reporter)
    roster = _stage_coordinate(theme, memo, respondent_num, config, reporter)
    batches = _stage_respond(memo, roster, reporter)
    shortlist = _stage_review(theme, memo, batches, config, reporter)
    return _stage_polish(theme, shortlist, config, reporter)


def _stage_analyze(
    theme: str, config: AppConfig, reporter: ProgressReporter
) -> AnalysisMemo:
    reporter.start(ROLE_SEATED_WRITER)
    memo = analyze(theme, config=config)
    reporter.lines(memo_lines(memo))
    reporter.done(ROLE_SEATED_WRITER)
    return memo


def _stage_coordinate(
    theme: str,
    memo: AnalysisMemo,
    respondent_num: int,
    config: AppConfig,
    reporter: ProgressReporter,
) -> Roster:
    reporter.start(ROLE_COORDINATOR)
    roster = coordinate(theme, memo, respondent_num, config=config)
    reporter.lines(roster_lines(roster))
    reporter.done(ROLE_COORDINATOR)
    return roster


def _stage_respond(
    memo: AnalysisMemo, roster: Roster, reporter: ProgressReporter
) -> tuple[CandidateBatch, ...]:
    n = len(roster.respondents)
    reporter.start("回答者", f"({n} 体)")
    batches = respond(memo, roster)
    reporter.lines(batches_lines(batches))
    reporter.done("回答者", f"({n} 体)")
    return batches


def _stage_review(
    theme: str,
    memo: AnalysisMemo,
    batches: tuple[CandidateBatch, ...],
    config: AppConfig,
    reporter: ProgressReporter,
) -> Shortlist:
    reporter.start(ROLE_TSUKKOMI)
    shortlist = review(theme, memo, batches, config=config)
    reporter.lines(shortlist_lines(shortlist))
    reporter.done(ROLE_TSUKKOMI)
    return shortlist


def _stage_polish(
    theme: str,
    shortlist: Shortlist,
    config: AppConfig,
    reporter: ProgressReporter,
) -> PolishedAnswer:
    reporter.start(ROLE_POLISHER)
    answer = polish(theme, shortlist, config=config)
    reporter.lines(polished_lines(answer))
    reporter.done(ROLE_POLISHER)
    return answer


def _agents(respondent_num: int, config: AppConfig) -> list[Agent]:
    writer = _make_agent(
        ROLE_SEATED_WRITER,
        "お題を分析する",
        "分析担当。低温。",
        config.agents.seated_writer,
    )
    coordinator = _make_agent(
        ROLE_COORDINATOR,
        "回答者 n 体を編成する",
        "編成担当。軸は実行ごとに決める。",
        config.agents.coordinator,
    )
    respondents = _respondent_agents(respondent_num, config.agents.respondent)
    tsukkomi = _make_agent(
        ROLE_TSUKKOMI,
        "残存全案を審査し 5 案を選ぶ",
        "審査担当。低温。本文は書き換えない。",
        config.agents.tsukkomi,
    )
    polisher = _make_agent(
        ROLE_POLISHER,
        "5 案を磨き 1 案にする",
        "推敲担当。低温。内容は足さない。",
        config.agents.polisher,
    )
    return [writer, coordinator, *respondents, tsukkomi, polisher]


def _respondent_agents(respondent_num: int, llm_config: AgentLLMConfig) -> list[Agent]:
    return [
        _make_agent(
            _respondent_role(index),
            "お題に対する案を出す",
            "回答担当。高温。互いの出力は見ない。",
            llm_config,
        )
        for index in range(1, respondent_num + 1)
    ]


def _respondent_role(index: int) -> str:
    return f"回答者{index}"


def _make_agent(
    role: str, goal: str, backstory: str, llm_config: AgentLLMConfig
) -> Agent:
    return Agent(
        role=role,
        goal=goal,
        backstory=backstory,
        llm=llm_for_role(model=llm_config.model, temperature=llm_config.temperature),
        verbose=False,
        allow_delegation=False,
        memory=False,
    )


def _tasks(theme: str, agents: list[Agent], respondent_num: int) -> list[Task]:
    writer, coordinator, *rest = agents
    respondents = rest[:respondent_num]
    tsukkomi, polisher = rest[respondent_num:]
    writer_task = _task("お題を分析する", "AnalysisMemo", writer)
    coordinator_task = _task(
        f"{theme} の回答者 {respondent_num} 体を編成する",
        "Roster",
        coordinator,
        context=[writer_task],
    )
    respondent_tasks = [
        _task(
            f"{agent.role} が案を出す",
            "CandidateBatch",
            agent,
            context=[writer_task, coordinator_task],
            async_execution=True,
        )
        for agent in respondents
    ]
    tsukkomi_task = _task(
        "残存全案を審査する",
        "Shortlist",
        tsukkomi,
        context=respondent_tasks,
    )
    polisher_task = _task(
        "1 案に推敲する",
        "PolishedAnswer",
        polisher,
        context=[tsukkomi_task],
    )
    return [
        writer_task,
        coordinator_task,
        *respondent_tasks,
        tsukkomi_task,
        polisher_task,
    ]


def _task(
    description: str,
    expected_output: str,
    agent: Agent,
    *,
    context: list[Task] | None = None,
    async_execution: bool = False,
) -> Task:
    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
        context=context,
        async_execution=async_execution,
    )
