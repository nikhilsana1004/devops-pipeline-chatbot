"""
DevOps Pipeline Chatbot — Enhanced with AWS Strands Agents
==========================================================
Original by: Nikhil Sana (@nikhilsana1004)
v2 upgrade: Strands Agents SDK · multi-tool · conversation memory · MCP server

Preserves the original UX ("Chat with your CI/CD pipelines") while adding:
  - Agentic tool selection (Athena + CloudWatch + CodePipeline + SNS)
  - Conversation memory across turns
  - Sidebar tool toggles & model picker
  - Tool-call inspector per response
  - Quick-stats dashboard row
"""

import streamlit as st
import os
from datetime import datetime
from dotenv import load_dotenv

from agents.pipeline_agent import PipelineAgent
from utils.session import init_session_state, add_to_history
from utils.formatters import format_agent_response, format_tool_calls

load_dotenv()

# ── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DevOps Pipeline Chatbot",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.2rem;
        color: white;
    }
    .main-header h1 { margin: 0 0 0.3rem 0; font-size: 1.8rem; }
    .main-header p  { margin: 0; opacity: 0.75; font-size: 0.9rem; }
    .agent-thinking { color: #888; font-style: italic; font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)

# ── Session State ──────────────────────────────────────────────────────────────
init_session_state()

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configuration")

    aws_region = st.selectbox(
        "AWS Region",
        ["us-west-2", "us-east-1", "eu-west-1", "ap-southeast-1"],
        index=0,
    )

    model_id = st.selectbox(
        "Bedrock Model",
        [
            "anthropic.claude-3-sonnet-20240229-v1:0",   # original default
            "anthropic.claude-sonnet-4-5",
            "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "us.amazon.nova-premier-v1:0",
        ],
        index=0,
    )

    st.markdown("---")
    st.markdown("### 🛠️ Active Tools")
    use_athena       = st.toggle("Athena (pipeline data)",    value=True)
    use_cloudwatch   = st.toggle("CloudWatch (metrics)",      value=True)
    use_codepipeline = st.toggle("CodePipeline (live status)", value=True)
    use_s3           = st.toggle("S3 Artifacts",               value=False)
    use_sns          = st.toggle("SNS Alerts",                 value=False)

    st.markdown("---")
    st.markdown("### 🧠 Memory")
    memory_enabled = st.toggle("Conversation Memory", value=True)
    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history = []
        st.session_state.agent_memory = []
        st.rerun()

    st.markdown("---")
    st.markdown("### Stack")
    st.markdown("""
`Strands Agents SDK`  
`AWS Bedrock` · `Athena`  
`CloudWatch` · `CodePipeline`  
`MCP Server` · `Streamlit`
    """)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🚀 Chat with your CI/CD pipelines</h1>
    <p>Powered by AWS Strands Agents · Bedrock · Athena · CloudWatch · CodePipeline</p>
</div>
""", unsafe_allow_html=True)

# ── Quick Stats (populated after a summary query) ──────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Events",   st.session_state.get("stat_events", "—"))
c2.metric("Unique Pipelines", st.session_state.get("stat_pipelines", "—"))
c3.metric("Failures (24h)", st.session_state.get("stat_failed", "—"))
c4.metric("Success Rate",   st.session_state.get("stat_success_rate", "—"))

st.markdown("---")

# ── Chat History ───────────────────────────────────────────────────────────────
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("tool_calls"):
            with st.expander("🔧 Tools Used", expanded=False):
                st.code(format_tool_calls(msg["tool_calls"]), language="json")
        if msg.get("timestamp"):
            st.caption(f"🕐 {msg['timestamp']}")

# ── Suggested Prompts (shown on first load) ────────────────────────────────────
if not st.session_state.chat_history:
    st.markdown("#### 💡 Try asking:")
    suggestions = [
        "What is the status of the latest pipeline execution?",
        "Which pipelines failed in the last 24 hours?",
        "Show all pipelines running in us-east-1",
        "Which pipeline has the most failures?",
        "Give me a summary of all pipeline activity",
        "Which stage causes the most failures?",
    ]
    cols = st.columns(3)
    for i, s in enumerate(suggestions):
        with cols[i % 3]:
            if st.button(s, key=f"sug_{i}", use_container_width=True):
                st.session_state.pending_prompt = s
                st.rerun()

# ── Chat Input ─────────────────────────────────────────────────────────────────
prompt = st.chat_input("What would you like to know about the CI/CD pipeline?")

if "pending_prompt" in st.session_state:
    prompt = st.session_state.pop("pending_prompt")

if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)
    add_to_history("user", prompt)

    tool_config = {
        "use_athena":       use_athena,
        "use_cloudwatch":   use_cloudwatch,
        "use_codepipeline": use_codepipeline,
        "use_s3":           use_s3,
        "use_sns":          use_sns,
        "aws_region":       aws_region,
        "model_id":         model_id,
        "memory_enabled":   memory_enabled,
        "chat_history":     st.session_state.agent_memory if memory_enabled else [],
    }

    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown('<p class="agent-thinking">🧠 Agent is thinking…</p>', unsafe_allow_html=True)

        try:
            agent = PipelineAgent(tool_config)
            result = agent.run(prompt)
            placeholder.empty()

            response_text = format_agent_response(result)
            st.markdown(response_text)

            tool_calls = result.get("tool_calls", [])
            if tool_calls:
                with st.expander("🔧 Tools Used", expanded=False):
                    st.code(format_tool_calls(tool_calls), language="json")

            ts = datetime.now().strftime("%H:%M:%S")
            st.caption(f"🕐 {ts} · {model_id.split('/')[-1]}")

            # Update memory
            if memory_enabled:
                st.session_state.agent_memory.append({"role": "user", "content": [{"text": prompt}]})
                st.session_state.agent_memory.append({"role": "assistant", "content": [{"text": response_text}]})
                st.session_state.agent_memory = st.session_state.agent_memory[-40:]

            add_to_history("assistant", response_text, tool_calls=tool_calls, timestamp=ts)

            # Update quick-stats if summary data is present
            stats = result.get("stats", {})
            if stats:
                st.session_state.stat_events    = stats.get("total_events", "—")
                st.session_state.stat_pipelines = stats.get("unique_pipelines", "—")
                st.session_state.stat_failed    = stats.get("failed", "—")
                total = int(stats.get("total_events", 0) or 0)
                succ  = int(stats.get("succeeded", 0) or 0)
                if total:
                    st.session_state.stat_success_rate = f"{round(succ/total*100)}%"

        except Exception as e:
            placeholder.empty()
            st.error(f"❌ Agent error: {str(e)}")
            st.info("💡 Check your AWS credentials and `.env` variables. See `.env.example` for reference.")
