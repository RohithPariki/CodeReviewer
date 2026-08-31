"""Orchestrator agent — synthesizes findings from all specialized agents."""

from __future__ import annotations

import logging

from ai_code_reviewer.agents import Finding

logger = logging.getLogger(__name__)

_SEVERITY_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}


class OrchestratorAgent:
    """Synthesizes, deduplicates, and prioritizes findings from all agents."""

    def synthesize(
        self,
        all_findings: list[Finding],
        max_findings: int = 50,
    ) -> list[Finding]:
        """Merge, deduplicate, and rank findings from all agents.

        Args:
            all_findings: Combined raw findings from all specialized agents.
            max_findings: Cap on total findings returned.

        Returns:
            Sorted, deduplicated list of findings (HIGH first).
        """
        if not all_findings:
            return []

        # Deduplicate: same file+line+category counts as one finding
        seen: set[tuple[str, int, str]] = set()
        unique: list[Finding] = []
        for f in all_findings:
            key = (f.file, f.line, f.category)
            if key not in seen:
                seen.add(key)
                unique.append(f)

        # Sort: HIGH first, then MEDIUM, then LOW; within each group by file+line
        unique.sort(
            key=lambda f: (
                -_SEVERITY_ORDER.get(f.severity, 0),
                f.file,
                f.line,
            )
        )

        result = unique[:max_findings]
        logger.info(
            "Orchestrator: %d raw → %d unique → %d returned (cap=%d)",
            len(all_findings),
            len(unique),
            len(result),
            max_findings,
        )
        return result

    def has_blocking_findings(self, findings: list[Finding]) -> bool:
        """Return True if any finding is HIGH severity (blocks CI)."""
        return any(f.severity == "HIGH" for f in findings)
