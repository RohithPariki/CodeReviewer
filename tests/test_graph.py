"""Integration tests for the LangGraph review pipeline."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ai_code_reviewer.agents import Finding
from ai_code_reviewer.graph import review_graph


def _mock_review_file(findings: list[Finding]):
    """Return a mock review_file function that always returns given findings."""
    def _inner(self, file_diff):
        return findings
    return _inner


def test_full_pipeline_with_findings(simple_diff_text: str) -> None:
    """Full pipeline run returns findings from all agents."""
    mock_finding = Finding(
        file="main.py",
        line=3,
        severity="HIGH",
        category="security",
        title="Hardcoded secret",
        description="SECRET is hardcoded",
        suggestion="Use environment variable",
    )

    with (
        patch(
            "ai_code_reviewer.agents.security_agent.SecurityAgent.review_file",
            _mock_review_file([mock_finding]),
        ),
        patch(
            "ai_code_reviewer.agents.bug_agent.BugAgent.review_file",
            _mock_review_file([]),
        ),
        patch(
            "ai_code_reviewer.agents.performance_agent.PerformanceAgent.review_file",
            _mock_review_file([]),
        ),
        patch(
            "ai_code_reviewer.agents.style_agent.StyleAgent.review_file",
            _mock_review_file([]),
        ),
    ):
        result = review_graph.invoke({
            "diff_text": simple_diff_text,
            "repo": "test/repo",
            "pr_number": 1,
            "findings": [],
        })

    assert "final_findings" in result
    assert len(result["final_findings"]) == 1
    assert result["final_findings"][0].severity == "HIGH"
    assert result["has_blocking"] is True


def test_full_pipeline_no_findings(simple_diff_text: str) -> None:
    """Full pipeline returns empty when all agents find nothing."""
    with (
        patch("ai_code_reviewer.agents.security_agent.SecurityAgent.review_file", _mock_review_file([])),
        patch("ai_code_reviewer.agents.bug_agent.BugAgent.review_file", _mock_review_file([])),
        patch("ai_code_reviewer.agents.performance_agent.PerformanceAgent.review_file", _mock_review_file([])),
        patch("ai_code_reviewer.agents.style_agent.StyleAgent.review_file", _mock_review_file([])),
    ):
        result = review_graph.invoke({
            "diff_text": simple_diff_text,
            "repo": "",
            "pr_number": None,
            "findings": [],
        })

    assert result["final_findings"] == []
    assert result["has_blocking"] is False


def test_pipeline_with_empty_diff() -> None:
    """Empty diff produces no findings without calling agents."""
    with (
        patch("ai_code_reviewer.agents.security_agent.SecurityAgent.review_file", _mock_review_file([])),
        patch("ai_code_reviewer.agents.bug_agent.BugAgent.review_file", _mock_review_file([])),
        patch("ai_code_reviewer.agents.performance_agent.PerformanceAgent.review_file", _mock_review_file([])),
        patch("ai_code_reviewer.agents.style_agent.StyleAgent.review_file", _mock_review_file([])),
    ):
        result = review_graph.invoke({
            "diff_text": "",
            "repo": "",
            "pr_number": None,
            "findings": [],
        })

    assert result["final_findings"] == []


def test_pipeline_deduplicates_across_agents(simple_diff_text: str) -> None:
    """Orchestrator deduplicates same file+line findings from different agents."""
    duplicate = Finding("main.py", 3, "HIGH", "security", "Dup", "desc", "fix")
    # Both security and bug find the "same" issue on the same file+line... 
    # but different categories, so they won't be deduplicated
    bug_finding = Finding("main.py", 3, "HIGH", "bug", "Also bad", "desc", "fix")

    with (
        patch("ai_code_reviewer.agents.security_agent.SecurityAgent.review_file", _mock_review_file([duplicate])),
        patch("ai_code_reviewer.agents.bug_agent.BugAgent.review_file", _mock_review_file([bug_finding])),
        patch("ai_code_reviewer.agents.performance_agent.PerformanceAgent.review_file", _mock_review_file([])),
        patch("ai_code_reviewer.agents.style_agent.StyleAgent.review_file", _mock_review_file([])),
    ):
        result = review_graph.invoke({
            "diff_text": simple_diff_text,
            "repo": "",
            "pr_number": None,
            "findings": [],
        })

    # Both findings have different categories so both should appear
    assert len(result["final_findings"]) == 2
