"""Tests for the unified diff parser."""

from __future__ import annotations

import pytest

from ai_code_reviewer.tools.diff_parser import FileDiff, parse_diff


def test_parse_simple_diff(simple_diff_text: str) -> None:
    """Parser returns one FileDiff for a single-file diff."""
    files = parse_diff(simple_diff_text)
    assert len(files) == 1
    assert files[0].path == "main.py"


def test_parse_sample_diff_skips_binary_and_lockfile(sample_diff_text: str) -> None:
    """Parser excludes binary files and lock files."""
    files = parse_diff(sample_diff_text)
    paths = [f.path for f in files]
    # Binary .png should be excluded
    assert not any(".png" in p for p in paths)
    # package-lock.json should be excluded
    assert not any("package-lock.json" in p for p in paths)
    # Python source files should be included
    assert any("auth.py" in p for p in paths)
    assert any("api.py" in p for p in paths)


def test_added_lines(simple_diff_text: str) -> None:
    """added_lines() returns only lines starting with '+'."""
    files = parse_diff(simple_diff_text)
    assert files
    added = files[0].added_lines()
    assert len(added) > 0
    # All added lines should have a line number
    assert all(isinstance(lineno, int) and lineno > 0 for lineno, _ in added)


def test_empty_diff() -> None:
    """Empty diff returns empty list."""
    assert parse_diff("") == []


def test_deleted_file_diff() -> None:
    """Parser handles deleted file diffs."""
    diff = """\
diff --git a/old.py b/old.py
--- a/old.py
+++ /dev/null
@@ -1,3 +0,0 @@
-def old_function():
-    pass
-
"""
    files = parse_diff(diff)
    assert len(files) == 1
    assert files[0].is_deleted is True


def test_new_file_diff() -> None:
    """Parser handles new file diffs."""
    diff = """\
diff --git a/new.py b/new.py
--- /dev/null
+++ b/new.py
@@ -0,0 +1,3 @@
+def new_function():
+    return 42
+
"""
    files = parse_diff(diff)
    assert len(files) == 1
    assert files[0].is_new is True


def test_renamed_file_diff() -> None:
    """Parser handles renamed files correctly."""
    diff = """\
diff --git a/old_name.py b/new_name.py
--- a/old_name.py
+++ b/new_name.py
@@ -1,3 +1,3 @@
 def unchanged():
-    return "old"
+    return "new"
"""
    files = parse_diff(diff)
    assert len(files) == 1


def test_skip_lock_files() -> None:
    """Lock files are skipped regardless of content."""
    for lock_file in ["package-lock.json", "yarn.lock", "poetry.lock", "Pipfile.lock"]:
        diff = f"""\
diff --git a/{lock_file} b/{lock_file}
--- a/{lock_file}
+++ b/{lock_file}
@@ -1,1 +1,1 @@
-old
+new
"""
        files = parse_diff(diff)
        assert files == [], f"Expected {lock_file} to be skipped"


def test_context_window(simple_diff_text: str) -> None:
    """context_window() returns non-empty string for valid line numbers."""
    files = parse_diff(simple_diff_text)
    assert files
    added = files[0].added_lines()
    if added:
        lineno, _ = added[0]
        window = files[0].context_window(lineno)
        assert len(window) > 0
