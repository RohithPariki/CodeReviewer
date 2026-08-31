"""LangGraph StateGraph definition for the ai-code-reviewer pipeline."""

from __future__ import annotations

import logging
import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

from ai_code_reviewer.agents import Finding
from ai_code_reviewer.agents.bug_agent import BugAgent
from ai_code_reviewer.agents.orchestrator import OrchestratorAgent
from ai_code_reviewer.agents.performance_agent import PerformanceAgent
from ai_code_reviewer.agents.security_agent import SecurityAgent
from ai_code_reviewer.agents.style_agent import StyleAgent
from ai_code_reviewer.config import settings
from ai_code_reviewer.tools.diff_parser import FileDiff, parse_diff

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State — TypedDict with Annotated reducer for parallel fan-out
# ---------------------------------------------------------------------------

class ReviewState(TypedDict, total=False):
    """State flowing through the LangGraph pipeline.

    The `findings` key uses operator.add as a reducer so that all 4 parallel
    agents can append to it concurrently without LangGraph raising a conflict.
    """

    # Input
    diff_text: str
    repo: str
    pr_number: int | None

    # Intermediate
    file_diffs: list[FileDiff]

    # Accumulated findings — Annotated with operator.add for parallel writes
    findings: Annotated[list[Finding], operator.add]

    # Final
    final_findings: list[Finding]
    has_blocking: bool


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

def parse_diff_node(state: dict[str, Any]) -> dict[str, Any]:
    """Node 1 — Parse the raw diff text into FileDiff objects."""
    diff_text: str = state.get("diff_text", "")
    file_diffs = parse_diff(diff_text)
    logger.info("Parsed %d reviewable files from diff", len(file_diffs))
    return {"file_diffs": file_diffs, "findings": []}


def _run_agent_on_files(
    agent: SecurityAgent | BugAgent | PerformanceAgent | StyleAgent,
    file_diffs: list[FileDiff],
) -> list[Finding]:
    """Helper: run a single agent across all files, collect findings."""
    findings: list[Finding] = []
    for fd in file_diffs:
        found = agent.review_file(fd)
        findings.extend(found)
        if len(findings) >= settings.max_findings_per_agent:
            break
    return findings


def security_node(state: dict[str, Any]) -> dict[str, Any]:
    """Node 2a — Run SecurityAgent on all files."""
    agent = SecurityAgent()
    return {"findings": _run_agent_on_files(agent, state["file_diffs"])}


def bug_node(state: dict[str, Any]) -> dict[str, Any]:
    """Node 2b — Run BugAgent on all files."""
    agent = BugAgent()
    return {"findings": _run_agent_on_files(agent, state["file_diffs"])}


def performance_node(state: dict[str, Any]) -> dict[str, Any]:
    """Node 2c — Run PerformanceAgent on all files."""
    agent = PerformanceAgent()
    return {"findings": _run_agent_on_files(agent, state["file_diffs"])}


def style_node(state: dict[str, Any]) -> dict[str, Any]:
    """Node 2d — Run StyleAgent on all files."""
    agent = StyleAgent()
    return {"findings": _run_agent_on_files(agent, state["file_diffs"])}


def orchestrate_node(state: dict[str, Any]) -> dict[str, Any]:
    """Node 3 — Synthesize and deduplicate findings from all agents."""
    orch = OrchestratorAgent()
    final = orch.synthesize(state.get("findings", []))
    return {
        "final_findings": final,
        "has_blocking": orch.has_blocking_findings(final),
    }


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph() -> Any:
    """Build and compile the LangGraph review pipeline.

    Graph structure:
        parse_diff
            │
            ├─→ security_agent ─┐
            ├─→ bug_agent      ─┤
            ├─→ perf_agent     ─┤→ orchestrate → END
            └─→ style_agent    ─┘

    Returns:
        Compiled LangGraph app (call with .invoke(state)).
    """
    graph = StateGraph(ReviewState)

    # Nodes
    graph.add_node("parse_diff", parse_diff_node)
    graph.add_node("security", security_node)
    graph.add_node("bug", bug_node)
    graph.add_node("performance", performance_node)
    graph.add_node("style", style_node)
    graph.add_node("orchestrate", orchestrate_node)

    # Entry
    graph.set_entry_point("parse_diff")

    # Fan-out: parse_diff → all 4 agents in parallel
    graph.add_edge("parse_diff", "security")
    graph.add_edge("parse_diff", "bug")
    graph.add_edge("parse_diff", "performance")
    graph.add_edge("parse_diff", "style")

    # Fan-in: all agents → orchestrate
    graph.add_edge("security", "orchestrate")
    graph.add_edge("bug", "orchestrate")
    graph.add_edge("performance", "orchestrate")
    graph.add_edge("style", "orchestrate")

    # Finish
    graph.add_edge("orchestrate", END)

    return graph.compile()


# Singleton compiled graph
review_graph = build_graph()
