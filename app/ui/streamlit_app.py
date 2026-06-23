from __future__ import annotations

import time

import streamlit as st

from app.core.config import settings
from app.core.db import QueryAuditDB
from app.core.rag_service import RAGService
from app.core.schemas import QueryRequest


st.set_page_config(page_title="Regulatory Compliance RAG Assistant", layout="wide")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "filter_doc_type" not in st.session_state:
    st.session_state.filter_doc_type = "All"


def login() -> None:
    st.title("Regulatory Compliance RAG Assistant")
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username == settings.ui_username and password == settings.ui_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Invalid credentials")


def confidence_label(value: float) -> tuple[str, str]:
    if value >= 0.8:
        return "High", "green"
    if value >= 0.6:
        return "Medium", "orange"
    return "Low", "red"


def main() -> None:
    st.title("Regulatory Compliance RAG Assistant")
    st.caption("Ask questions about RBI circulars, Basel III, and SEBI regulations")

    with st.sidebar:
        st.header("Filters")
        st.session_state.filter_doc_type = st.selectbox("Document Type", ["All", "RBI", "SEBI", "Basel"])
        st.date_input("Date Range")
        if st.button("Dark Mode Toggle"):
            st.info("Use Streamlit theme config for full dark mode in deployment")

        st.subheader("Recent Queries")
        logs = QueryAuditDB().get_recent_queries(limit=10)
        for log in logs:
            st.write(f"- {log['question'][:60]}")

    rag = RAGService()
    question = st.text_area("Enter your compliance question", height=120)

    col1, col2 = st.columns([1, 1])
    with col1:
        ask = st.button("Get Answer", use_container_width=True)
    with col2:
        if st.button("Clear", use_container_width=True):
            st.rerun()

    if ask and question.strip():
        started = time.perf_counter()
        req = QueryRequest(question=question, max_sources=5, include_excerpts=True)
        res = rag.query(req, user_id="streamlit_user")
        elapsed = int((time.perf_counter() - started) * 1000)

        st.success(f"Answer ({elapsed} ms)")
        st.markdown(res.answer)

        label, color = confidence_label(res.confidence)
        st.markdown(f"Confidence: :{color}[{int(res.confidence*100)}% ({label})]")
        st.markdown("### Source Documents")

        for src in res.sources:
            with st.expander(f"{src.document} (Page {src.page})"):
                excerpt = src.excerpt
                for h in src.highlight:
                    excerpt = excerpt.replace(h, f"**{h}**")
                st.markdown(excerpt)
                if src.download_link:
                    st.caption(f"Source file: {src.download_link}")

        if res.latency_ms <= 2000:
            st.success("Latency status: under 2 seconds")
        else:
            st.warning("Latency status: above 2 seconds")


if not st.session_state.authenticated:
    login()
else:
    main()
