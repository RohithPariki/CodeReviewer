"""GitHub API tools — fetch PR diffs, post inline review comments."""

from __future__ import annotations

import logging

from github import Github, GithubException
from github.PullRequest import PullRequest

from ai_code_reviewer.agents import Finding
from ai_code_reviewer.config import settings

logger = logging.getLogger(__name__)


def get_github_client() -> Github:
    """Return an authenticated GitHub client."""
    if not settings.github_token:
        raise ValueError(
            "GITHUB_TOKEN is required. Set it in .env or as an environment variable."
        )
    return Github(settings.github_token)


def fetch_pr_diff(repo_name: str, pr_number: int) -> str:
    """Fetch the unified diff for a GitHub pull request.

    Args:
        repo_name: Full repo name, e.g. "owner/repo".
        pr_number: The pull request number.

    Returns:
        Raw unified diff string.

    Raises:
        GithubException: On API errors (bad token, repo not found, etc.)
        ValueError: If GITHUB_TOKEN is not configured.
    """
    gh = get_github_client()
    try:
        repo = gh.get_repo(repo_name)
        pr: PullRequest = repo.get_pull(pr_number)
        # PyGitHub doesn't expose the raw diff directly; use the files API
        diff_lines: list[str] = []
        for f in pr.get_files():
            if f.patch:
                diff_lines.append(f"diff --git a/{f.filename} b/{f.filename}")
                if f.status == "added":
                    diff_lines.append(f"--- /dev/null")
                    diff_lines.append(f"+++ b/{f.filename}")
                elif f.status == "removed":
                    diff_lines.append(f"--- a/{f.filename}")
                    diff_lines.append(f"+++ /dev/null")
                else:
                    diff_lines.append(f"--- a/{f.filename}")
                    diff_lines.append(f"+++ b/{f.filename}")
                diff_lines.append(f.patch)
                diff_lines.append("")
        return "\n".join(diff_lines)
    except GithubException as exc:
        logger.error("GitHub API error fetching PR %s#%d: %s", repo_name, pr_number, exc)
        raise


def post_review_comments(
    repo_name: str,
    pr_number: int,
    findings: list[Finding],
    dry_run: bool = False,
) -> int:
    """Post findings as inline review comments on a GitHub PR.

    Args:
        repo_name: Full repo name, e.g. "owner/repo".
        pr_number: The pull request number.
        findings: List of findings to post.
        dry_run: If True, log what would be posted but don't actually post.

    Returns:
        Number of comments successfully posted.
    """
    if not findings:
        logger.info("No findings to post.")
        return 0

    if dry_run:
        logger.info("[DRY RUN] Would post %d findings:", len(findings))
        for f in findings:
            logger.info("  %s", f)
        return len(findings)

    gh = get_github_client()
    try:
        repo = gh.get_repo(repo_name)
        pr: PullRequest = repo.get_pull(pr_number)
        latest_commit = list(pr.get_commits())[-1]
    except GithubException as exc:
        logger.error("Failed to access PR: %s", exc)
        raise

    severity_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}
    category_emoji = {
        "security": "🔒",
        "bug": "🐛",
        "performance": "⚡",
        "style": "✨",
    }

    posted = 0
    for finding in findings:
        emoji_s = severity_emoji.get(finding.severity, "⚪")
        emoji_c = category_emoji.get(finding.category, "📝")
        body = (
            f"{emoji_s} **[{finding.severity}] {emoji_c} {finding.title}**\n\n"
            f"{finding.description}\n\n"
            f"**Suggestion:** {finding.suggestion}"
        )
        try:
            pr.create_review_comment(
                body=body,
                commit=latest_commit,
                path=finding.file,
                line=finding.line,
            )
            posted += 1
            logger.debug("Posted comment on %s:%d", finding.file, finding.line)
        except GithubException as exc:
            logger.warning(
                "Failed to post comment on %s:%d — %s", finding.file, finding.line, exc
            )

    logger.info("Posted %d/%d findings as PR comments", posted, len(findings))
    return posted
