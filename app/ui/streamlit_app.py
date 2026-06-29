from __future__ import annotations

import html
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.core.db import QueryAuditDB
from app.core.rag_service import RAGService
from app.core.schemas import QueryRequest
from app.utils.logging_utils import configure_logging

configure_logging()


APP_VERSION = "v1.0.0"
SOURCE_FILTERS = {
    "All Sources": None,
    "RBI Circulars": {"organization": "Reserve Bank of India"},
    "Basel III": {"organization": "BIS"},
    "SEBI Regulations": {"organization": "SEBI"},
}


st.set_page_config(
    page_title="Regulatory Compliance AI Assistant",
    page_icon=":material/policy:",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #0F172A;
            --panel: #1E293B;
            --panel-soft: #273449;
            --accent: #3B82F6;
            --success: #22C55E;
            --warning: #F59E0B;
            --danger: #EF4444;
            --text: #FFFFFF;
            --muted: #94A3B8;
            --border: rgba(148, 163, 184, 0.22);
            --shadow: 0 18px 45px rgba(2, 6, 23, 0.28);
        }

        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            background: var(--bg);
            color: var(--text);
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }

        [data-testid="stHeader"] {
            height: 0;
        }

        .block-container {
            max-width: 1240px;
            padding: 2.2rem 2.4rem 5.8rem;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #111C31 0%, #0B1220 100%);
            border-right: 1px solid var(--border);
        }

        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] span {
            color: var(--text);
        }

        h1, h2, h3, p {
            color: var(--text);
        }

        .app-header {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1.5rem;
            margin-bottom: 1.5rem;
        }

        .eyebrow {
            color: var(--accent);
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0;
            text-transform: uppercase;
            margin-bottom: 0.45rem;
        }

        .app-title {
            font-size: 2.15rem;
            font-weight: 760;
            line-height: 1.1;
            margin: 0;
        }

        .subtitle {
            color: var(--muted);
            font-size: 1.02rem;
            margin-top: 0.55rem;
            max-width: 720px;
        }

        .logo-lockup {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 1rem;
        }

        .logo-mark {
            align-items: center;
            background: linear-gradient(135deg, var(--accent), #60A5FA);
            border-radius: 14px;
            box-shadow: 0 14px 34px rgba(59, 130, 246, 0.28);
            color: white;
            display: flex;
            font-size: 0.95rem;
            font-weight: 800;
            height: 42px;
            justify-content: center;
            width: 42px;
        }

        .logo-title {
            font-size: 1rem;
            font-weight: 750;
            line-height: 1.2;
        }

        .logo-subtitle {
            color: var(--muted);
            font-size: 0.78rem;
            margin-top: 0.2rem;
        }

        .section-label {
            color: var(--muted);
            font-size: 0.72rem;
            font-weight: 760;
            letter-spacing: 0;
            margin: 1.25rem 0 0.55rem;
            text-transform: uppercase;
        }

        .source-row, .history-row, .setting-row, .footer-row {
            align-items: center;
            background: rgba(30, 41, 59, 0.58);
            border: 1px solid var(--border);
            border-radius: 12px;
            color: var(--text);
            display: flex;
            justify-content: space-between;
            margin-bottom: 0.48rem;
            padding: 0.68rem 0.78rem;
        }

        .history-row {
            align-items: flex-start;
            display: block;
        }

        .history-title {
            font-size: 0.86rem;
            font-weight: 650;
            line-height: 1.35;
        }

        .history-meta {
            color: var(--muted);
            font-size: 0.72rem;
            margin-top: 0.24rem;
        }

        .check {
            color: var(--success);
            font-weight: 800;
        }

        .metric-grid {
            display: grid;
            gap: 0.8rem;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            margin: 1.15rem 0 1.55rem;
        }

        .metric-card {
            background: rgba(30, 41, 59, 0.8);
            border: 1px solid var(--border);
            border-radius: 16px;
            box-shadow: var(--shadow);
            padding: 0.95rem;
        }

        .metric-label {
            color: var(--muted);
            font-size: 0.74rem;
            font-weight: 700;
            margin-bottom: 0.45rem;
        }

        .metric-value {
            color: var(--text);
            font-size: 1.08rem;
            font-weight: 760;
        }

        .chat-shell {
            display: flex;
            flex-direction: column;
            gap: 1rem;
            margin-top: 0.7rem;
        }

        .message-row {
            animation: fadeIn 220ms ease-out;
            display: flex;
            width: 100%;
        }

        .message-row.user {
            justify-content: flex-end;
        }

        .message-row.assistant {
            justify-content: flex-start;
        }

        .user-bubble {
            background: var(--accent);
            border-radius: 18px 18px 4px 18px;
            box-shadow: 0 16px 36px rgba(59, 130, 246, 0.22);
            color: white;
            max-width: min(760px, 78%);
            padding: 0.95rem 1.05rem;
            white-space: pre-wrap;
        }

        .assistant-card {
            background: rgba(30, 41, 59, 0.94);
            border: 1px solid var(--border);
            border-radius: 18px 18px 18px 4px;
            box-shadow: var(--shadow);
            max-width: min(900px, 88%);
            padding: 1.05rem;
        }

        .answer-copy {
            color: #E5E7EB;
            font-size: 0.98rem;
            line-height: 1.68;
            margin-top: 0.75rem;
            white-space: pre-wrap;
        }

        .badge-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 0.85rem;
        }

        .badge {
            align-items: center;
            border-radius: 999px;
            display: inline-flex;
            font-size: 0.75rem;
            font-weight: 760;
            gap: 0.35rem;
            padding: 0.34rem 0.58rem;
        }

        .badge.success {
            background: rgba(34, 197, 94, 0.14);
            color: #86EFAC;
        }

        .badge.warning {
            background: rgba(245, 158, 11, 0.14);
            color: #FCD34D;
        }

        .badge.danger {
            background: rgba(239, 68, 68, 0.14);
            color: #FCA5A5;
        }

        .badge.info {
            background: rgba(59, 130, 246, 0.14);
            color: #93C5FD;
        }

        .sources-grid {
            display: grid;
            gap: 0.75rem;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            margin-top: 1rem;
        }

        .source-card {
            background: rgba(15, 23, 42, 0.66);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 0.92rem;
            transition: border-color 160ms ease, transform 160ms ease, background 160ms ease;
        }

        .source-card:hover {
            background: rgba(15, 23, 42, 0.86);
            border-color: rgba(59, 130, 246, 0.62);
            transform: translateY(-2px);
        }

        .source-title {
            color: var(--text);
            font-size: 0.95rem;
            font-weight: 760;
            line-height: 1.3;
        }

        .source-meta {
            color: var(--muted);
            font-size: 0.76rem;
            margin: 0.34rem 0 0.7rem;
        }

        .source-excerpt {
            color: #CBD5E1;
            font-size: 0.83rem;
            line-height: 1.5;
        }

        .pdf-link {
            border: 1px solid rgba(59, 130, 246, 0.45);
            border-radius: 10px;
            color: #BFDBFE;
            display: inline-flex;
            font-size: 0.78rem;
            font-weight: 760;
            margin-top: 0.75rem;
            padding: 0.42rem 0.64rem;
            text-decoration: none;
            transition: background 160ms ease, border-color 160ms ease, transform 160ms ease;
        }

        .pdf-link:hover {
            background: rgba(59, 130, 246, 0.16);
            border-color: rgba(59, 130, 246, 0.72);
            color: white;
            transform: translateY(-1px);
        }

        mark {
            background: rgba(59, 130, 246, 0.32);
            border-radius: 4px;
            color: white;
            padding: 0.04rem 0.16rem;
        }

        .empty-state {
            background: rgba(30, 41, 59, 0.72);
            border: 1px solid var(--border);
            border-radius: 18px;
            box-shadow: var(--shadow);
            margin-top: 1.2rem;
            padding: 2.2rem;
        }

        .empty-title {
            color: var(--text);
            font-size: 1.25rem;
            font-weight: 760;
            margin-bottom: 0.45rem;
        }

        .empty-copy {
            color: var(--muted);
            max-width: 640px;
        }

        div.stButton > button,
        div.stDownloadButton > button,
        [data-testid="stBaseButton-secondary"],
        [data-testid="stBaseButton-primary"] {
            background: rgba(30, 41, 59, 0.9);
            border: 1px solid var(--border);
            border-radius: 12px;
            color: var(--text);
            font-weight: 730;
            transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
        }

        div.stButton > button:hover,
        div.stDownloadButton > button:hover,
        [data-testid="stBaseButton-secondary"]:hover,
        [data-testid="stBaseButton-primary"]:hover {
            background: rgba(59, 130, 246, 0.16);
            border-color: rgba(59, 130, 246, 0.62);
            color: white;
            transform: translateY(-1px);
        }

        [data-testid="stChatInput"] {
            background: rgba(30, 41, 59, 0.96);
            border: 1px solid var(--border);
            border-radius: 18px;
            box-shadow: 0 20px 55px rgba(2, 6, 23, 0.38);
        }

        [data-testid="stTextInput"] input,
        [data-testid="stPasswordInput"] input,
        [data-testid="stSelectbox"] div {
            color: var(--text);
        }

        .login-card {
            background: rgba(30, 41, 59, 0.88);
            border: 1px solid var(--border);
            border-radius: 20px;
            box-shadow: var(--shadow);
            margin: 9vh auto 0;
            max-width: 440px;
            padding: 1.4rem;
        }

        .login-title {
            font-size: 1.55rem;
            font-weight: 780;
            margin-bottom: 0.35rem;
        }

        .login-copy {
            color: var(--muted);
            margin-bottom: 1rem;
        }

        @keyframes fadeIn {
            from {
                opacity: 0;
                transform: translateY(6px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @media (max-width: 1080px) {
            .metric-grid, .sources-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
            }
        }

        @media (max-width: 760px) {
            .app-header {
                display: block;
            }
            .metric-grid, .sources-grid {
                grid-template-columns: 1fr;
            }
            .assistant-card, .user-bubble {
                max-width: 100%;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource(show_spinner=False)
def get_rag_service() -> RAGService:
    return RAGService()


@st.cache_resource
def get_lightweight_vector_store():
    return None


def init_state() -> None:
    defaults = {
        "authenticated": False,
        "selected_source": "All Sources",
        "conversations": [],
        "active_chat_id": None,
        "last_latency_ms": None,
        "service_error": None,
        "service_initialized": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if not st.session_state.conversations:
        create_new_chat()


def create_new_chat() -> None:
    chat = {
        "id": str(uuid4()),
        "title": "New compliance chat",
        "created_at": datetime.now().strftime("%b %d, %H:%M"),
        "messages": [],
    }
    st.session_state.conversations.insert(0, chat)
    st.session_state.active_chat_id = chat["id"]


def get_active_chat() -> dict:
    for chat in st.session_state.conversations:
        if chat["id"] == st.session_state.active_chat_id:
            return chat
    create_new_chat()
    return st.session_state.conversations[0]


def login() -> None:
    inject_css()
    st.markdown(
        """
        <div class="login-card">
            <div class="logo-lockup">
                <div class="logo-mark">RC</div>
                <div>
                    <div class="logo-title">Regulatory Compliance AI</div>
                    <div class="logo-subtitle">Secure assistant console</div>
                </div>
            </div>
            <div class="login-title">Welcome back</div>
            <div class="login-copy">Sign in to search RBI Circulars, Basel III, and SEBI Regulations.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.container():
        username = st.text_input("Username", placeholder="Username")
        password = st.text_input("Password", type="password", placeholder="Password")
        if st.button("Sign in", use_container_width=True):
            if username == settings.ui_username and password == settings.ui_password:
                st.session_state.authenticated = True
                st.rerun()
            st.error("Invalid credentials")


def safe_service() -> RAGService | None:
    if not st.session_state.get("service_initialized", False):
        return None
    try:
        service = get_rag_service()
        st.session_state.service_error = None
        return service
    except Exception as exc:  # noqa: BLE001
        st.session_state.service_error = str(exc)
        return None


def collect_index_stats(service: RAGService | None) -> dict[str, str]:
    if service is None:
        if st.session_state.get("service_error"):
            return {
                "api_status": "Offline",
                "documents": "0",
                "chunks": "0",
                "vector_status": "Unavailable",
                "avg_latency": average_latency_label(),
                "model": settings.embedding_model.split("/")[-1],
            }

        return {
            "api_status": "Standby",
            "documents": "-",
            "chunks": "-",
            "vector_status": "Not Loaded",
            "avg_latency": average_latency_label(),
            "model": settings.embedding_model.split("/")[-1],
        }

    docs = service.vector_store.all_docs()
    document_count = len(
        {
            str((doc.get("metadata") or {}).get("document", ""))
            for doc in docs
            if doc.get("metadata")
        }
    )

    return {
        "api_status": "Online",
        "documents": str(document_count),
        "chunks": str(len(docs)),
        "vector_status": "Ready",
        "avg_latency": average_latency_label(),
        "model": settings.embedding_model.split("/")[-1],
    }
    try:
        docs = service.vector_store.all_docs()
        document_count = len({str((doc.get("metadata") or {}).get("document", "")) for doc in docs if doc.get("metadata")})
        return {
            "api_status": "Online",
            "documents": str(document_count),
            "chunks": str(len(docs)),
            "vector_status": "Ready",
            "avg_latency": average_latency_label(),
            "model": settings.embedding_model.split("/")[-1],
        }
    except Exception as exc:  # noqa: BLE001
        st.session_state.service_error = str(exc)
        return {
            "api_status": "Degraded",
            "documents": "-",
            "chunks": "-",
            "vector_status": "Check index",
            "avg_latency": average_latency_label(),
            "model": settings.embedding_model.split("/")[-1],
        }


def average_latency_label() -> str:
    latencies = [
        message["response"].get("latency_ms", 0)
        for chat in st.session_state.conversations
        for message in chat["messages"]
        if message["role"] == "assistant" and message.get("response")
    ]
    if not latencies:
        try:
            recent = QueryAuditDB().get_recent_queries(limit=10)
            latencies = [int(row["latency_ms"]) for row in recent if row.get("latency_ms") is not None]
        except Exception:  # noqa: BLE001
            latencies = []
    if not latencies:
        return "-"
    return f"{sum(latencies) / len(latencies) / 1000:.1f}s"


def render_sidebar(stats: dict[str, str]) -> None:
    with st.sidebar:
        st.markdown(
            """
            <div class="logo-lockup">
                <div class="logo-mark">RC</div>
                <div>
                    <div class="logo-title">Regulatory Compliance AI</div>
                    <div class="logo-subtitle">Enterprise RAG workspace</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("New Chat", use_container_width=True):
            create_new_chat()
            st.rerun()

        st.markdown('<div class="section-label">Conversation History</div>', unsafe_allow_html=True)
        active_chat = get_active_chat()
        for chat in st.session_state.conversations[:12]:
            selected = chat["id"] == active_chat["id"]
            title = html.escape(chat["title"])
            meta = f"{len(chat['messages']) // 2} questions"
            st.markdown(
                f"""
                <div class="history-row">
                    <div class="history-title">{title}</div>
                    <div class="history-meta">{html.escape(chat["created_at"])} &middot; {meta}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Open" if not selected else "Current", key=f"chat-{chat['id']}", use_container_width=True):
                st.session_state.active_chat_id = chat["id"]
                st.rerun()

        if st.button("Clear History", use_container_width=True):
            st.session_state.conversations = []
            create_new_chat()
            st.rerun()

        st.markdown('<div class="section-label">Data Sources</div>', unsafe_allow_html=True)
        for label in ("RBI Circulars", "Basel III", "SEBI Regulations"):
            st.markdown(
                f'<div class="source-row"><span><span class="check">&#10003;</span> {label}</span><span>Indexed</span></div>',
                unsafe_allow_html=True,
            )

        st.session_state.selected_source = st.selectbox(
            "Source filter",
            list(SOURCE_FILTERS),
            index=list(SOURCE_FILTERS).index(st.session_state.selected_source),
        )

        st.markdown('<div class="section-label">Settings</div>', unsafe_allow_html=True)
        setting_rows = {
            "API Status": stats["api_status"],
            "Documents Indexed": stats["documents"],
            "Chunks Indexed": stats["chunks"],
            "Latency": stats["avg_latency"],
            "Model Name": stats["model"],
        }
        for label, value in setting_rows.items():
            st.markdown(
                f'<div class="setting-row"><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></div>',
                unsafe_allow_html=True,
            )

        st.markdown('<div class="section-label">Footer</div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="footer-row"><span>Version</span><strong>{APP_VERSION}</strong></div>
            <div class="footer-row"><span>GitHub</span><strong>Repository</strong></div>
            <div class="footer-row"><span>Documentation</span><strong>User Guide</strong></div>
            """,
            unsafe_allow_html=True,
        )


def render_header() -> None:
    st.markdown(
        """
        <div class="app-header">
            <div>
                <div class="eyebrow">Regulatory intelligence workspace</div>
                <h1 class="app-title">Regulatory Compliance AI Assistant</h1>
                <div class="subtitle">Ask questions about RBI Circulars, Basel III, and SEBI Regulations.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_cards(stats: dict[str, str]) -> None:
    metrics = [
        ("Documents Indexed", stats["documents"]),
        ("Chunks Indexed", stats["chunks"]),
        ("Vector Database Status", stats["vector_status"]),
        ("API Status", stats["api_status"]),
        ("Average Latency", stats["avg_latency"]),
    ]
    cards = "".join(
        f'<div class="metric-card"><div class="metric-label">{html.escape(label)}</div><div class="metric-value">{html.escape(value)}</div></div>'
        for label, value in metrics
    )
    st.markdown(f'<div class="metric-grid">{cards}</div>', unsafe_allow_html=True)


def render_chat(chat: dict) -> None:
    if not chat["messages"]:
        st.markdown(
            """
            <div class="empty-state">
                <div class="empty-title">Start with a compliance question</div>
                <div class="empty-copy">
                    Try asking about capital adequacy, CRAR, Basel III reforms, SEBI portfolio manager rules,
                    or RBI circular requirements. Answers include source citations and review signals.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    st.markdown('<div class="chat-shell">', unsafe_allow_html=True)
    for message in chat["messages"]:
        if message["role"] == "user":
            render_user_message(message["content"])
        else:
            render_assistant_message(message["response"])
    st.markdown("</div>", unsafe_allow_html=True)


def render_user_message(content: str) -> None:
    st.markdown(
        f"""
        <div class="message-row user">
            <div class="user-bubble">{html.escape(content)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_assistant_message(response: dict) -> None:
    confidence = float(response.get("confidence", 0.0))
    confidence_class = "success" if confidence >= 0.8 else "warning" if confidence >= 0.6 else "danger"
    latency_ms = int(response.get("latency_ms", 0))
    review_required = bool(response.get("review_flag", False))
    review_class = "danger" if review_required else "success"
    answer = html.escape(str(response.get("answer", "")))

    st.markdown(
        f"""
        <div class="message-row assistant">
            <div class="assistant-card">
                <div class="badge-row">
                    <span class="badge {confidence_class}">Confidence: {confidence * 100:.0f}%</span>
                    <span class="badge info">Latency: {latency_ms / 1000:.1f} sec</span>
                    <span class="badge {review_class}">Review Required: {"Yes" if review_required else "No"}</span>
                </div>
                <div class="answer-copy">{answer}</div>
        """,
        unsafe_allow_html=True,
    )
    render_sources(response.get("sources", []))
    st.markdown("</div></div>", unsafe_allow_html=True)


def render_sources(sources: list[dict]) -> None:
    if not sources:
        st.markdown('<div class="source-meta">No source documents returned.</div>', unsafe_allow_html=True)
        return

    st.markdown('<div class="sources-grid">', unsafe_allow_html=True)
    for source in sources:
        document = html.escape(str(source.get("document") or "Unknown document"))
        organization = html.escape(str(source.get("organization") or "Unknown"))
        page = html.escape(str(source.get("page") or "-"))
        section = html.escape(str(source.get("section") or "General"))
        excerpt = highlight_excerpt(str(source.get("excerpt") or ""), source.get("highlight") or [])
        pdf_link = pdf_button_html(source.get("download_link"))
        st.markdown(
            f"""
            <div class="source-card">
                <div class="source-title">{document}</div>
                <div class="source-meta">{organization} &middot; Page {page} &middot; {section}</div>
                <div class="source-excerpt">{excerpt}</div>
                {pdf_link}
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def highlight_excerpt(excerpt: str, highlights: list[str]) -> str:
    escaped = html.escape(excerpt)
    for term in sorted({h for h in highlights if h}, key=len, reverse=True):
        escaped_term = html.escape(term)
        pattern = re.compile(re.escape(escaped_term), flags=re.IGNORECASE)
        escaped = pattern.sub(lambda match: f"<mark>{match.group(0)}</mark>", escaped)
    return escaped


def pdf_button_html(download_link: str | None) -> str:
    if not download_link:
        return ""
    path = Path(download_link)
    if not path.is_absolute():
        path = ROOT / path
    if path.exists():
        return f'<a class="pdf-link" href="{html.escape(path.as_uri())}" target="_blank">Open PDF</a>'
    return ""


def submit_question(service: RAGService, question: str) -> None:
    clean_question = question.strip()
    if not clean_question:
        return

    chat = get_active_chat()
    if chat["title"] == "New compliance chat":
        chat["title"] = clean_question[:52] + ("..." if len(clean_question) > 52 else "")
    chat["messages"].append({"role": "user", "content": clean_question})

    filters = SOURCE_FILTERS.get(st.session_state.selected_source)
    request = QueryRequest(
        question=clean_question,
        max_sources=5,
        include_excerpts=True,
        filters=filters,
    )

    started = time.perf_counter()
    response = service.query(request, user_id="streamlit_user")
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    response.latency_ms = response.latency_ms or elapsed_ms
    st.session_state.last_latency_ms = response.latency_ms
    chat["messages"].append({"role": "assistant", "response": response.model_dump()})


def render_input_area(service: RAGService | None) -> None:
    controls = st.columns([1, 1, 6])
    with controls[0]:
        if st.button("Clear Chat", use_container_width=True):
            get_active_chat()["messages"] = []
            st.rerun()
    with controls[1]:
        if st.button("New Chat", use_container_width=True):
            create_new_chat()
            st.rerun()

    is_disabled = st.session_state.get("service_error") is not None
    prompt = st.chat_input("Ask a compliance question...", disabled=is_disabled)
    if prompt:
        if service is None:
            with st.spinner("Initializing RAG models (first-time startup)..."):
                st.session_state.service_initialized = True
                service = safe_service()
        
        if service is not None:
            with st.spinner("Reviewing regulatory sources..."):
                submit_question(service, prompt)
            st.rerun()
        else:
            st.rerun()


def scroll_to_bottom() -> None:
    components.html(
        """
        <script>
        const scroll = () => window.parent.scrollTo({ top: window.parent.document.body.scrollHeight, behavior: "smooth" });
        setTimeout(scroll, 120);
        </script>
        """,
        height=0,
    )


def main() -> None:
    inject_css()
    service = safe_service()
    stats = collect_index_stats(service)
    render_sidebar(stats)
    render_header()
    render_metric_cards(stats)

    if st.session_state.service_error:
        st.warning(f"Backend service status: {st.session_state.service_error}")

    active_chat = get_active_chat()
    render_chat(active_chat)
    render_input_area(service)
    scroll_to_bottom()


init_state()
if not st.session_state.authenticated:
    login()
else:
    main()
