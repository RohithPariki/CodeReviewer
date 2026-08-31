"""Base class for all review agents."""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol, runtime_checkable

from langchain_core.messages import HumanMessage, SystemMessage

from ai_code_reviewer.agents import Finding
from ai_code_reviewer.config import settings
from ai_code_reviewer.tools.diff_parser import FileDiff

logger = logging.getLogger(__name__)

_EXTRACT_JSON = __import__("re").compile(r"\[.*\]", __import__("re").DOTALL)


@runtime_checkable
class LLMProtocol(Protocol):
    """Minimal protocol for an LLM client (injectable for testing)."""

    def invoke(self, messages: list) -> Any: ...


def _make_default_llm() -> LLMProtocol:
    """Create the default ChatAnthropic client (lazy import avoids import-time errors)."""
    from langchain_anthropic import ChatAnthropic

    api_key = settings.anthropic_api_key or "placeholder-set-ANTHROPIC_API_KEY"
    return ChatAnthropic(  # type: ignore[return-value]
        model=settings.anthropic_model,
        api_key=api_key,  # type: ignore[arg-type]
        max_tokens=2048,
        temperature=0,
    )


class BaseReviewAgent:
    """Base class providing LLM call + JSON parsing for review agents."""

    category: str = "base"
    system_prompt: str = ""

    def __init__(self, llm: LLMProtocol | None = None) -> None:
        """Initialize the agent with an optional injected LLM (for testing).

        Args:
            llm: LLM client to use. If None, creates the default ChatAnthropic client.
        """
        self._llm: LLMProtocol = llm if llm is not None else _make_default_llm()

    def _build_user_prompt(self, file_diff: FileDiff) -> str:
        """Build the user prompt for a given file diff."""
        added = file_diff.added_lines()
        if not added:
            return ""

        lines_block = "\n".join(f"{lineno:>4} | {content}" for lineno, content in added)
        return (
            f"File: {file_diff.path}\n\n"
            f"Added/modified lines:\n```\n{lines_block}\n```\n\n"
            "Return a JSON array of findings. If none, return []. "
            "Each finding: {file, line, severity, category, title, description, suggestion}"
        )

    def _parse_response(self, raw: str, file_path: str) -> list[Finding]:
        """Extract findings from LLM JSON response."""
        match = _EXTRACT_JSON.search(raw)
        if not match:
            return []
        try:
            items: list[dict[str, Any]] = json.loads(match.group())
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from agent response")
            return []

        findings: list[Finding] = []
        for item in items:
            try:
                findings.append(
                    Finding(
                        file=item.get("file", file_path),
                        line=int(item.get("line", 1)),
                        severity=item.get("severity", "LOW"),
                        category=self.category,  # type: ignore[arg-type]
                        title=item.get("title", ""),
                        description=item.get("description", ""),
                        suggestion=item.get("suggestion", ""),
                    )
                )
            except (KeyError, ValueError) as exc:
                logger.debug("Skipping malformed finding: %s", exc)
        return findings

    def review_file(self, file_diff: FileDiff) -> list[Finding]:
        """Run the agent on a single file diff and return findings.

        Args:
            file_diff: The parsed diff for one file.

        Returns:
            List of findings for this file.
        """
        prompt = self._build_user_prompt(file_diff)
        if not prompt:
            return []

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt),
        ]
        try:
            response = self._llm.invoke(messages)
            return self._parse_response(str(response.content), file_diff.path)
        except Exception as exc:  # noqa: BLE001
            logger.error("Agent %s failed for %s: %s", self.category, file_diff.path, exc)
            return []
