"""Parse unified diff format into structured per-file chunks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# File extensions to skip (binary formats, lock files)
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2",
    ".ttf", ".eot", ".mp4", ".mp3", ".pdf", ".zip", ".tar", ".gz",
}
SKIP_FILENAMES = {
    "package-lock.json", "yarn.lock", "poetry.lock", "Pipfile.lock",
    "Cargo.lock", "go.sum", "pnpm-lock.yaml", "composer.lock",
}

_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass
class HunkLine:
    """A single line within a diff hunk."""

    content: str
    old_lineno: int | None
    new_lineno: int | None
    change_type: str  # "+" | "-" | " "


@dataclass
class FileDiff:
    """All changes for a single file."""

    old_path: str
    new_path: str
    is_new: bool
    is_deleted: bool
    is_binary: bool
    hunks: list[list[HunkLine]] = field(default_factory=list)

    @property
    def path(self) -> str:
        """Return the most relevant path for this file."""
        return self.new_path if self.new_path != "/dev/null" else self.old_path

    @property
    def should_skip(self) -> bool:
        """Return True if this file should be excluded from review."""
        import os
        name = os.path.basename(self.path)
        ext = os.path.splitext(name)[1].lower()
        return name in SKIP_FILENAMES or ext in SKIP_EXTENSIONS

    def added_lines(self) -> list[tuple[int, str]]:
        """Return (line_number, content) for all added lines."""
        result: list[tuple[int, str]] = []
        for hunk in self.hunks:
            for line in hunk:
                if line.change_type == "+" and line.new_lineno is not None:
                    result.append((line.new_lineno, line.content))
        return result

    def context_window(self, target_lineno: int, radius: int = 3) -> str:
        """Return a context snippet around a given new line number."""
        lines: list[tuple[int | None, str, str]] = []
        for hunk in self.hunks:
            for line in hunk:
                lines.append((line.new_lineno, line.change_type, line.content))

        # Find index of target
        idx = next(
            (i for i, (n, _, _) in enumerate(lines) if n == target_lineno), None
        )
        if idx is None:
            return ""

        window = lines[max(0, idx - radius) : idx + radius + 1]
        parts = []
        for lineno, change, content in window:
            marker = "→" if lineno == target_lineno else " "
            num = str(lineno) if lineno else "   "
            parts.append(f"{marker} {num:>4} {change} {content}")
        return "\n".join(parts)


def parse_diff(diff_text: str) -> list[FileDiff]:
    """Parse a unified diff string into a list of FileDiff objects.

    Args:
        diff_text: The raw unified diff string.

    Returns:
        List of FileDiff objects, one per changed file.
    """
    files: list[FileDiff] = []
    current: FileDiff | None = None
    current_hunk: list[HunkLine] | None = None
    old_lineno = 0
    new_lineno = 0

    for raw_line in diff_text.splitlines():
        # New file header
        if raw_line.startswith("diff --git "):
            if current is not None:
                if current_hunk is not None:
                    current.hunks.append(current_hunk)
                files.append(current)
            current = FileDiff(
                old_path="",
                new_path="",
                is_new=False,
                is_deleted=False,
                is_binary=False,
            )
            current_hunk = None
            continue

        if current is None:
            continue

        if raw_line.startswith("--- "):
            path = raw_line[4:].strip()
            current.old_path = path.removeprefix("a/") if path != "/dev/null" else path
            if path == "/dev/null":
                current.is_new = True
        elif raw_line.startswith("+++ "):
            path = raw_line[4:].strip()
            current.new_path = path.removeprefix("b/") if path != "/dev/null" else path
            if path == "/dev/null":
                current.is_deleted = True
        elif raw_line.startswith("Binary files"):
            current.is_binary = True
        elif m := _HUNK_HEADER.match(raw_line):
            if current_hunk is not None:
                current.hunks.append(current_hunk)
            current_hunk = []
            old_lineno = int(m.group(1))
            new_lineno = int(m.group(2))
        elif current_hunk is not None:
            if raw_line.startswith("+"):
                current_hunk.append(
                    HunkLine(raw_line[1:], None, new_lineno, "+")
                )
                new_lineno += 1
            elif raw_line.startswith("-"):
                current_hunk.append(
                    HunkLine(raw_line[1:], old_lineno, None, "-")
                )
                old_lineno += 1
            elif raw_line.startswith(" ") or raw_line == "":
                current_hunk.append(
                    HunkLine(raw_line[1:] if raw_line else "", old_lineno, new_lineno, " ")
                )
                old_lineno += 1
                new_lineno += 1

    # Flush last file
    if current is not None:
        if current_hunk is not None:
            current.hunks.append(current_hunk)
        files.append(current)

    return [f for f in files if not f.should_skip and not f.is_binary]
