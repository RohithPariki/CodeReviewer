# 🤖 AI Code Reviewer

> Automated pull request code review powered by a multi-agent LangGraph pipeline with a sleek Streamlit Web Interface.
> Four specialized AI agents analyze your PR in parallel — security, bugs, performance, and style — then an orchestrator synthesizes the findings into inline GitHub comments.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-green.svg)](https://langchain-ai.github.io/langgraph/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red.svg)](https://streamlit.io/)

---

## 🎯 What it does

When a PR is provided, **AI Code Reviewer** runs 4 agents **in parallel**:

| Agent | Finds |
|-------|-------|
| 🔒 **Security** | Hardcoded secrets, SQL injection, XSS, auth bypasses, insecure crypto |
| 🐛 **Bug Detector** | Null pointer deref, off-by-one errors, unhandled exceptions, resource leaks |
| ⚡ **Performance** | N+1 queries, blocking async calls, missing indexes, memory leaks |
| ✨ **Style** | Missing docstrings, magic numbers, overly complex functions, dead code |

An **orchestrator** deduplicates and prioritizes findings. The results are displayed live in the Streamlit web dashboard and can optionally be posted as inline GitHub PR comments.

---

## 🏗 Architecture

```
  Pull Request
       │
       ▼
  ┌─────────────┐
  │  parse_diff  │  ← Splits unified diff into per-file chunks
  └──────┬───────┘    Skips binary files, lock files
         │
   ┌─────┼─────┬─────┐   (parallel fan-out via LangGraph)
   ▼     ▼     ▼     ▼
 [🔒]  [🐛]  [⚡]  [✨]   ← 4 agents run simultaneously
   │     │     │     │
   └─────┴──┬──┴─────┘
            ▼
    ┌───────────────┐
    │  orchestrate  │  ← Deduplicate, rank by severity
    └───────┬───────┘
            │
            ▼
     Streamlit UI  ← Visualizes findings interactively
```

---

## 🚀 Quick Start (Web UI)

### 1. Install Dependencies

Ensure you have Python 3.11+ installed, then run:

```bash
pip install -e .
```

### 2. Configure Environment

Create an environment file:

```bash
cp .env.example .env
```

Add your API keys to the `.env` file (or provide them dynamically via the Web UI sidebar):

```env
ANTHROPIC_API_KEY=your_api_key_here
GITHUB_TOKEN=your_github_token_here
```

### 3. Launch the Application

Start the Streamlit dashboard:

```bash
streamlit run app.py
```

Open your browser to `http://localhost:8501`, enter a target repository and PR number, and watch the agents analyze the code in real time!

---

## ⚙️ Configuration Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | required | Anthropic API key |
| `ANTHROPIC_MODEL` | `claude-haiku-20240307` | Model to use (haiku = cost-efficient) |
| `GITHUB_TOKEN` | required | GitHub token with `repo` + `pull_requests` scope |

---

## 🛠 Built With

- **[Streamlit](https://streamlit.io/)** — Web interface
- **[LangGraph](https://langchain-ai.github.io/langgraph/)** — parallel agent orchestration
- **[LangChain Anthropic](https://python.langchain.com/docs/integrations/chat/anthropic/)** — Claude integration
- **[PyGitHub](https://pygithub.readthedocs.io/)** — GitHub API
