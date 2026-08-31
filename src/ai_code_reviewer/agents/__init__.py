"""Review agents for the ai-code-reviewer pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class Finding:
    """A single code review finding produced by an agent."""

    file: str
    line: int
    severity: Literal["HIGH", "MEDIUM", "LOW"]
    category: Literal["security", "bug", "performance", "style"]
    title: str
    description: str
    suggestion: str

    def __str__(self) -> str:
        return (
            f"[{self.severity}] {self.category.upper()} — {self.title}\n"
            f"  {self.file}:{self.line}\n"
            f"  {self.description}\n"
            f"  Suggestion: {self.suggestion}"
        )
