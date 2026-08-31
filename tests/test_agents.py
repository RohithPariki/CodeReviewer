"""Tests for review agents (LLM calls are mocked via constructor injection)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from ai_code_reviewer.agents import Finding
from ai_code_reviewer.agents.bug_agent import BugAgent
from ai_code_reviewer.agents.orchestrator import OrchestratorAgent
from ai_code_reviewer.agents.security_agent import SecurityAgent
from ai_code_reviewer.tools.diff_parser import parse_diff


def _make_mock_llm(findings: list[dict]) -> MagicMock:
    """Create a mock LLM that returns a JSON array of findings on .invoke()."""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps(findings)
    mock_llm.invoke.return_value = mock_response
    return mock_llm


def _make_error_llm(error: Exception) -> MagicMock:
    """Create a mock LLM that raises an exception on .invoke()."""
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = error
    return mock_llm


def _make_bad_json_llm() -> MagicMock:
    """Create a mock LLM that returns invalid JSON."""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "This is not valid JSON at all!"
    mock_llm.invoke.return_value = mock_response
    return mock_llm


@pytest.fixture
def auth_file_diff(sample_diff_text: str):
    """Return only the auth.py FileDiff from the sample."""
    files = parse_diff(sample_diff_text)
    match = next((f for f in files if "auth.py" in f.path), None)
    assert match is not None, "Expected auth.py in sample diff"
    return match


class TestSecurityAgent:
    def test_finds_hardcoded_secret(self, auth_file_diff) -> None:
        """SecurityAgent detects hardcoded secrets in auth.py."""
        mock_findings = [
            {
                "file": "src/auth.py",
                "line": 4,
                "severity": "HIGH",
                "category": "security",
                "title": "Hardcoded secret key",
                "description": "SECRET_KEY is hardcoded in source code",
                "suggestion": "Use os.environ.get('SECRET_KEY') instead",
            }
        ]
        agent = SecurityAgent(llm=_make_mock_llm(mock_findings))
        findings = agent.review_file(auth_file_diff)

        assert len(findings) == 1
        assert findings[0].severity == "HIGH"
        assert findings[0].category == "security"

    def test_returns_empty_for_clean_file(self) -> None:
        """SecurityAgent returns no findings for a clean file."""
        clean_diff = """\
diff --git a/utils.py b/utils.py
--- a/utils.py
+++ b/utils.py
@@ -1,3 +1,5 @@
+def add(a: int, b: int) -> int:
+    \"\"\"Add two numbers.\"\"\"
+    return a + b
"""
        files = parse_diff(clean_diff)
        agent = SecurityAgent(llm=_make_mock_llm([]))
        findings = agent.review_file(files[0])
        assert findings == []

    def test_handles_malformed_json(self, auth_file_diff) -> None:
        """Agent gracefully handles malformed LLM JSON response."""
        agent = SecurityAgent(llm=_make_bad_json_llm())
        findings = agent.review_file(auth_file_diff)
        assert findings == []

    def test_handles_llm_exception(self, auth_file_diff) -> None:
        """Agent returns empty list when LLM raises an exception."""
        agent = SecurityAgent(llm=_make_error_llm(Exception("API error")))
        findings = agent.review_file(auth_file_diff)
        assert findings == []


class TestBugAgent:
    def test_detects_division_by_zero(self) -> None:
        """BugAgent detects potential division by zero."""
        diff = """\
diff --git a/calc.py b/calc.py
--- a/calc.py
+++ b/calc.py
@@ -0,0 +1,4 @@
+def divide(x, y):
+    result = x / y
+    return result
"""
        files = parse_diff(diff)
        mock_findings = [
            {
                "file": "calc.py",
                "line": 2,
                "severity": "HIGH",
                "category": "bug",
                "title": "Potential division by zero",
                "description": "y is not checked before division",
                "suggestion": "Add: if y == 0: raise ValueError('Cannot divide by zero')",
            }
        ]
        agent = BugAgent(llm=_make_mock_llm(mock_findings))
        findings = agent.review_file(files[0])
        assert len(findings) == 1
        assert findings[0].severity == "HIGH"


class TestOrchestratorAgent:
    def test_deduplicates_findings(self) -> None:
        """Orchestrator removes duplicate findings (same file+line+category)."""
        orch = OrchestratorAgent()
        findings = [
            Finding("a.py", 10, "HIGH", "security", "Issue", "desc", "fix"),
            Finding("a.py", 10, "HIGH", "security", "Issue dup", "desc2", "fix2"),
            Finding("b.py", 5, "LOW", "style", "Style", "desc3", "fix3"),
        ]
        result = orch.synthesize(findings)
        assert len(result) == 2  # Deduped

    def test_sorts_by_severity(self) -> None:
        """Orchestrator returns HIGH findings before MEDIUM before LOW."""
        orch = OrchestratorAgent()
        findings = [
            Finding("a.py", 1, "LOW", "style", "Low", "", ""),
            Finding("b.py", 2, "HIGH", "security", "High", "", ""),
            Finding("c.py", 3, "MEDIUM", "bug", "Med", "", ""),
        ]
        result = orch.synthesize(findings)
        assert result[0].severity == "HIGH"
        assert result[1].severity == "MEDIUM"
        assert result[2].severity == "LOW"

    def test_has_blocking_findings(self) -> None:
        """has_blocking_findings returns True when HIGH findings exist."""
        orch = OrchestratorAgent()
        findings = [
            Finding("a.py", 1, "HIGH", "security", "Critical", "", ""),
        ]
        assert orch.has_blocking_findings(findings) is True
        assert orch.has_blocking_findings([]) is False

    def test_respects_max_findings_cap(self) -> None:
        """synthesize respects the max_findings cap."""
        orch = OrchestratorAgent()
        findings = [
            Finding(f"file{i}.py", i, "LOW", "style", f"Issue {i}", "", "")
            for i in range(100)
        ]
        result = orch.synthesize(findings, max_findings=10)
        assert len(result) == 10

    def test_empty_findings(self) -> None:
        """synthesize handles empty input gracefully."""
        orch = OrchestratorAgent()
        assert orch.synthesize([]) == []
