import os
import sys
import streamlit as st

st.set_page_config(page_title="AI Code Reviewer", page_icon="🤖", layout="wide")

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath("src"))

try:
    from ai_code_reviewer.graph import review_graph
    from ai_code_reviewer.tools.github_tools import fetch_pr_diff
except ImportError:
    st.error("Failed to import backend modules. Ensure you've run `pip install -e .`")
    st.stop()

st.title("🤖 AI Code Reviewer")
st.markdown("Automated pull request code review powered by a multi-agent LangGraph pipeline. Four specialized AI agents analyze your PR in parallel — **security**, **bugs**, **performance**, and **style** — then an orchestrator synthesizes the findings.")

with st.sidebar:
    st.header("⚙️ Configuration")
    github_token = st.text_input("GitHub Token (Required)", type="password", help="Needs repo and pull_requests scope")
    anthropic_api_key = st.text_input("Anthropic API Key (Required)", type="password")
    
    st.divider()
    st.header("🎯 Target")
    repo = st.text_input("Repository (owner/repo)", placeholder="e.g., owner/repo")
    pr_number = st.number_input("PR Number", min_value=1, step=1, value=1)
    
    run_btn = st.button("🚀 Run Review", type="primary", use_container_width=True)

if run_btn:
    if not github_token or not anthropic_api_key:
        st.warning("Please provide both GitHub Token and Anthropic API Key in the sidebar.")
    elif not repo:
        st.warning("Please specify the target repository.")
    else:
        # Set environment variables for the backend
        os.environ["GITHUB_TOKEN"] = github_token
        os.environ["ANTHROPIC_API_KEY"] = anthropic_api_key
        
        try:
            with st.spinner(f"Fetching diff for {repo}#{pr_number}..."):
                diff_text = fetch_pr_diff(repo, int(pr_number))
                
            if not diff_text or not diff_text.strip():
                st.info("No diff content found to review.")
            else:
                st.success("Diff fetched successfully! Running multi-agent review...")
                
                with st.spinner("Analyzing with 4 specialized agents in parallel..."):
                    result = review_graph.invoke({
                        "diff_text": diff_text,
                        "repo": repo,
                        "pr_number": int(pr_number),
                        "findings": [],
                    })
                
                findings = result.get("final_findings", [])
                
                if not findings:
                    st.balloons()
                    st.success("✅ No issues found! Clean PR.")
                else:
                    st.subheader("📊 Review Findings")
                    
                    high = sum(1 for f in findings if f.severity == "HIGH")
                    med = sum(1 for f in findings if f.severity == "MEDIUM")
                    low = sum(1 for f in findings if f.severity == "LOW")
                    
                    cols = st.columns(4)
                    cols[0].metric("Total", len(findings))
                    cols[1].metric("🔴 HIGH", high)
                    cols[2].metric("🟡 MEDIUM", med)
                    cols[3].metric("🔵 LOW", low)
                    
                    if result.get("has_blocking"):
                        st.error("❌ HIGH severity findings detected — this would block CI.")
                        
                    for f in findings:
                        color = "red" if f.severity == "HIGH" else "orange" if f.severity == "MEDIUM" else "blue"
                        with st.expander(f"{f.category.upper()} | {f.title} ({f.severity})"):
                            st.markdown(f"**File:** `{f.file}:{f.line}`")
                            st.markdown(f"**Suggestion:** {f.suggestion}")
                            
        except Exception as e:
            st.error(f"An error occurred: {e}")
