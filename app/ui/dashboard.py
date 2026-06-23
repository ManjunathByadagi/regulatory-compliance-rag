from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from app.core.db import EvaluationDB


st.set_page_config(page_title="RAGAS Dashboard", layout="wide")
st.title("RAG Performance Dashboard")

db = EvaluationDB()
runs = db.get_latest_runs(days=30)

if not runs:
    st.warning("No evaluation runs found. Run daily evaluation first.")
    st.stop()

df = pd.DataFrame(runs)
df = df.sort_values("id")
latest = df.iloc[-1]

st.metric("Overall Score", f"{latest['overall_score']:.2f}")

metric_table = pd.DataFrame(
    [
        {"Metric": "Context Precision", "Score": latest["context_precision"], "Target": 0.75},
        {"Metric": "Faithfulness", "Score": latest["faithfulness"], "Target": 0.70},
        {"Metric": "Answer Relevance", "Score": latest["answer_relevance"], "Target": 0.72},
        {"Metric": "Context Recall", "Score": latest["context_recall"], "Target": 0.75},
    ]
)
metric_table["Status"] = metric_table.apply(lambda r: "PASS" if r["Score"] >= r["Target"] else "FAIL", axis=1)
st.dataframe(metric_table, use_container_width=True)

st.subheader("Latency")
lat_col1, lat_col2, lat_col3 = st.columns(3)
lat_col1.metric("p50", f"{latest['p50_latency']:.1f} ms")
lat_col2.metric("p95", f"{latest['p95_latency']:.1f} ms")
lat_col3.metric("p99", f"{latest['p99_latency']:.1f} ms")

st.subheader("7-day Trend")
trend_cols = ["context_precision", "faithfulness", "answer_relevance", "context_recall", "overall_score"]
st.line_chart(df[trend_cols])

st.subheader("Failed Queries")
notes = json.loads(latest["notes_json"])
for item in notes.get("failed", []):
    st.error(f"Q: {item['question']}")
    st.caption(f"Root cause: {item['root_cause']}")
