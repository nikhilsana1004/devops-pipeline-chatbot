"""Streamlit session state helpers."""
import streamlit as st


def init_session_state():
    defaults = {
        "chat_history": [],
        "agent_memory": [],
        "stat_active": "—",
        "stat_failed": "—",
        "stat_success_rate": "—",
        "stat_avg_duration": "—",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def add_to_history(role: str, content: str, **kwargs):
    entry = {"role": role, "content": content}
    entry.update(kwargs)
    st.session_state.chat_history.append(entry)
