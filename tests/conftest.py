"""Shared test fixtures for ai-code-reviewer tests."""

from __future__ import annotations

from pathlib import Path

import pytest

SAMPLE_DIFF_PATH = Path(__file__).parent.parent / "examples" / "sample.diff"


@pytest.fixture
def sample_diff_text() -> str:
    """Load the sample diff from the examples directory."""
    return SAMPLE_DIFF_PATH.read_text(encoding="utf-8")


@pytest.fixture
def simple_diff_text() -> str:
    """A minimal unified diff for basic testing."""
    return """\
diff --git a/main.py b/main.py
--- a/main.py
+++ b/main.py
@@ -1,3 +1,8 @@
+import os
+
+SECRET = "abc123"
+
 def main():
-    pass
+    query = "SELECT * FROM users WHERE id = " + os.getenv("USER_ID")
+    return query
"""
