"""Streamlit interface for the FinSight capstone demo."""

from __future__ import annotations

import streamlit as st

from finsight.service import CopilotService


st.set_page_config(page_title="FinSight", layout="wide")
st.title("FinSight")
st.caption("Citation-grounded financial-report copilot for a hosted model of at most 8B parameters.")

if "service" not in st.session_state:
    st.session_state.service = CopilotService()
if "history" not in st.session_state:
    st.session_state.history = []

question = st.text_input("Ask a question about the sample filings")
if st.button("Ask", type="primary") and question:
    try:
        response = st.session_state.service.ask(question, "streamlit", "streamlit-user")
        st.session_state.history.append((question, response))
    except PermissionError as exc:
        st.error(str(exc))

for question, response in reversed(st.session_state.history):
    st.subheader(question)
    st.write(response.answer)
    columns = st.columns(4)
    columns[0].metric("Behavior", response.behavior)
    columns[1].metric("Latency", f"{response.latency_ms:.1f} ms")
    columns[2].metric("Tool calls", len(response.tool_calls))
    columns[3].metric("Tokens", response.token_estimate)
    if response.calculation:
        st.code(response.calculation)
    if response.citations:
        st.markdown("**Citations**")
        for citation in response.citations:
            st.write(f"{citation.document_id}, {citation.section}, page {citation.page}")
    if response.refusal_reason:
        st.warning(response.refusal_reason)
