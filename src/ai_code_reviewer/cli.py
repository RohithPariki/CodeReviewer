"""Click CLI for ai-code-reviewer."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich import box

from ai_code_reviewer.agents import Finding

console = Console()
logging.basicConfig(level=logging.WARNING)


def _print_findings_table(findings: list[Finding]) -> None:
    """Render findings in a rich table."""
    if not findings:
        console.print("[bold green]✅ No issues found![/bold green]")
        return

    severity_color = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "cyan"}
    category_icon = {
        "security": "🔒",
        "bug": "🐛",
        "performance": "⚡",
        "style": "✨",
    }

    table = Table(
        title="[bold]AI Code Review Results[/bold]",
        box=box.ROUNDED,
        show_lines=True,
    )
    table.add_column("Severity", style="bold", width=10)
    table.add_column("Category", width=12)
    table.add_column("File:Line", width=30)
    table.add_column("Title", width=32)
    table.add_column("Suggestion", width=40)

    for f in findings:
        color = severity_color.get(f.severity, "white")
        icon = category_icon.get(f.category, "📝")
        table.add_row(
            f"[{color}]{f.severity}[/{color}]",
            f"{icon} {f.category}",
            f"[dim]{f.file}[/dim]:{f.line}",
            f.title,
            f.suggestion,
        )

    console.print(table)

    high = sum(1 for f in findings if f.severity == "HIGH")
    med = sum(1 for f in findings if f.severity == "MEDIUM")
    low = sum(1 for f in findings if f.severity == "LOW")
    console.print(
        f"\n[bold]Summary:[/bold] "
        f"[red]{high} HIGH[/red] · [yellow]{med} MEDIUM[/yellow] · [cyan]{low} LOW[/cyan] "
        f"· {len(findings)} total"
    )


@click.group()
def main() -> None:
    """AI Code Reviewer — multi-agent LangGraph PR review pipeline."""


@main.command()
@click.option("--repo", "-r", help="GitHub repo (owner/repo)", default=None)
@click.option("--pr", "-p", "pr_number", type=int, help="PR number", default=None)
@click.option("--diff", "-d", "diff_file", type=click.Path(exists=True), help="Local diff file", default=None)
@click.option("--dry-run", is_flag=True, default=False, help="Don't post to GitHub; print results only")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable verbose logging")
def review(
    repo: str | None,
    pr_number: int | None,
    diff_file: str | None,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Run the multi-agent code review pipeline.

    Examples:
        # Review a GitHub PR
        ai-code-reviewer review --repo owner/repo --pr 42

        # Dry run (no GitHub posting)
        ai-code-reviewer review --repo owner/repo --pr 42 --dry-run

        # Review a local diff file
        ai-code-reviewer review --diff changes.patch --dry-run
    """
    if verbose:
        logging.getLogger().setLevel(logging.INFO)

    # Validate inputs
    if not diff_file and not (repo and pr_number):
        raise click.UsageError("Provide either --diff or both --repo and --pr")

    # Import here to keep startup fast
    from ai_code_reviewer.graph import review_graph
    from ai_code_reviewer.tools.github_tools import fetch_pr_diff, post_review_comments

    # Fetch diff
    if diff_file:
        diff_text = Path(diff_file).read_text(encoding="utf-8")
        console.print(f"[dim]Reviewing local diff: {diff_file}[/dim]")
    else:
        console.print(f"[dim]Fetching diff for {repo}#{pr_number}...[/dim]")
        try:
            diff_text = fetch_pr_diff(repo, pr_number)  # type: ignore[arg-type]
        except Exception as exc:
            console.print(f"[red]Failed to fetch PR diff: {exc}[/red]")
            sys.exit(1)

    if not diff_text.strip():
        console.print("[yellow]No diff content to review.[/yellow]")
        sys.exit(0)

    console.print("[bold cyan]🤖 Running multi-agent review...[/bold cyan]")

    with console.status("[bold green]Analyzing with 4 specialized agents..."):
        result = review_graph.invoke({
            "diff_text": diff_text,
            "repo": repo or "",
            "pr_number": pr_number,
            "findings": [],
        })

    findings: list[Finding] = result.get("final_findings", [])
    _print_findings_table(findings)

    # Post to GitHub
    if not dry_run and repo and pr_number and findings:
        console.print("\n[dim]Posting findings to GitHub...[/dim]")
        try:
            posted = post_review_comments(repo, pr_number, findings, dry_run=False)
            console.print(f"[green]Posted {posted} comments to {repo}#{pr_number}[/green]")
        except Exception as exc:
            console.print(f"[red]Failed to post comments: {exc}[/red]")

    # Exit 1 if blocking findings (for CI gating)
    if result.get("has_blocking"):
        console.print("\n[red bold]❌ HIGH severity findings detected — blocking CI[/red bold]")
        sys.exit(1)
    else:
        console.print("\n[green bold]✅ Review complete[/green bold]")


if __name__ == "__main__":
    main()
