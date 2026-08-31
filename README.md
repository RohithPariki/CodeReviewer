# AI Code Reviewer

Automated pull request code review powered by a multi-agent LangGraph pipeline and a Streamlit Web Interface.

This system leverages four specialized AI agents that execute in parallel to analyze pull requests across multiple dimensions: security, bugs, performance, and style. An orchestration layer synthesizes the findings into actionable insights.

---

## Technical Overview

When a pull request is submitted for review, the AI Code Reviewer initiates a parallel execution pipeline:

- **Security Analysis**: Scans for hardcoded secrets, SQL injection vectors, cross-site scripting (XSS), authentication bypasses, and insecure cryptography.
- **Defect Detection**: Identifies potential null pointer dereferences, off-by-one errors, unhandled exceptions, and resource leaks.
- **Performance Profiling**: Highlights N+1 query patterns, blocking asynchronous operations, missing database indexes, and potential memory leaks.
- **Style Verification**: Ensures compliance with styling standards, flagging missing docstrings, magic numbers, overly complex functions, and dead code.

The orchestrator deduplicates the findings and ranks them by severity. Results are dynamically rendered in the Streamlit web dashboard and can optionally be posted as inline GitHub PR comments.

---

## System Architecture

The application is built on a directed acyclic graph (DAG) architecture using LangGraph, allowing for highly concurrent agent execution.

1. **Diff Parsing**: The system splits unified diffs into per-file chunks, safely bypassing binary and lock files.
2. **Parallel Fan-out**: The parsed chunks are routed to four distinct AI agents simultaneously.
3. **Synthesis & Orchestration**: Findings from the agents are aggregated, deduplicated, and ranked by a central orchestrator node.
4. **Presentation Layer**: The Streamlit frontend visualizes the findings interactively.

---

## Quick Start

### 1. Installation

Ensure you have Python 3.11 or higher installed. Clone the repository and install the dependencies:

```bash
pip install -e .
```

### 2. Environment Configuration

Copy the example environment configuration:

```bash
cp .env.example .env
```

Configure the necessary API tokens in the `.env` file, or provide them dynamically via the web interface:

```env
ANTHROPIC_API_KEY=your_anthropic_api_key
GITHUB_TOKEN=your_github_token
```

### 3. Launch the Application

Start the Streamlit dashboard:

```bash
streamlit run app.py
```

Access the interface at `http://localhost:8501`. Enter the target repository (e.g., `owner/repo`) and the pull request number to initiate the review process.

---

## Configuration Variables

| Variable | Requirement | Description |
|----------|-------------|-------------|
| `ANTHROPIC_API_KEY` | Required | Authentication token for Anthropic Claude. |
| `ANTHROPIC_MODEL` | Optional | Specifies the model to use (default: `claude-haiku-20240307`). |
| `GITHUB_TOKEN` | Required | GitHub token with `repo` and `pull_requests` scope. |

---

## Technology Stack

- **Streamlit**: Interactive web interface.
- **LangGraph**: Parallel agent orchestration.
- **LangChain Anthropic**: Claude LLM integration.
- **PyGitHub**: GitHub API communication layer.
