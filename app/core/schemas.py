from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=3)
    max_sources: int = Field(default=5, ge=1, le=10)
    include_excerpts: bool = True
    filters: dict | None = None


class SourceCitation(BaseModel):
    document: str
    page: str
    excerpt: str
    highlight: list[str]
    section: str | None = None
    organization: str | None = None
    date: str | None = None
    doc_type: str | None = None
    download_link: str | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceCitation]
    confidence: float
    latency_ms: int
    status: Literal["ok", "no_answer", "review_required"] = "ok"
    review_flag: bool = False


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    document: str
    page_start: int
    page_end: int
    section: str | None = None
    organization: str | None = None
    date: str | None = None
    doc_type: str | None = None
    source_path: str | None = None
    dense_score: float = 0.0
    bm25_score: float = 0.0
    rrf_score: float = 0.0
    rerank_score: float = 0.0


class QueryLog(BaseModel):
    user_id: str
    question: str
    answer: str
    confidence: float
    latency_ms: int
    timestamp: datetime
    sources_json: str
    review_flag: bool
    status: str


class EvaluationRecord(BaseModel):
    run_date: str
    context_precision: float
    faithfulness: float
    answer_relevance: float
    context_recall: float
    p50_latency: float
    p95_latency: float
    p99_latency: float
    overall_score: float
    failed_queries: int
