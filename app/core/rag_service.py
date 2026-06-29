from __future__ import annotations

import time
from pathlib import Path

from app.core.answering import build_extract_answer
from app.core.config import settings
from app.core.db import QueryAuditDB
from app.core.schemas import QueryRequest, QueryResponse
from app.ingestion.chunking import build_chunks
from app.ingestion.pdf_parser import parse_pdf
from app.retrieval.hybrid import deduplicate_chunks, diversify_by_document, diversify_for_comparison, reciprocal_rank_fusion
from app.retrieval.keyword_search import BM25Index
from app.retrieval.query_understanding import analyze_query, intent_for_organization
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.vector_store import VectorStore


class RAGService:
    def __init__(self) -> None:
        self.vector_store = VectorStore()
        self.bm25 = BM25Index()
        self.reranker = CrossEncoderReranker()
        self.audit_db = QueryAuditDB()
        self._logged_ready = False

    @property
    def bm25_index(self) -> BM25Index:
        if not self.bm25.is_built:
            self._refresh_bm25_index()
        return self.bm25

    def _refresh_bm25_index(self) -> None:
        all_docs = self.vector_store.all_docs()
        self.bm25.build(all_docs)

    def ingest_pdf(self, pdf_path: str, strategy: str | None = None) -> int:
        strategy = strategy or settings.chunk_strategy
        parsed = parse_pdf(pdf_path)
        page_texts = [(p.page_num, p.text) for p in parsed.pages if p.text.strip()]

        if not page_texts:
            return 0

        normalized_path = pdf_path.lower()
        normalized_title = parsed.title.lower()
        if "rbi" in normalized_path or "reserve_bank" in normalized_path or "reserve bank" in normalized_title:
            doc_type = "Regulatory Circular"
            org = "Reserve Bank of India"
        elif "sebi" in normalized_path or "securities" in normalized_title:
            doc_type = "Regulation"
            org = "SEBI"
        else:
            doc_type = "Basel Guidance"
            org = "BIS"

        chunks = build_chunks(parsed.title, page_texts, strategy=strategy)
        count = self.vector_store.upsert_chunks(chunks, source_path=pdf_path, doc_type=doc_type, organization=org)
        self._refresh_bm25_index()
        return count

    def batch_ingest(self, root_dir: str) -> dict:
        root = Path(root_dir)
        summary = {"files": 0, "chunks": 0, "failed": []}
        for pdf in root.rglob("*.pdf"):
            try:
                added = self.ingest_pdf(str(pdf))
                summary["files"] += 1
                summary["chunks"] += added
            except Exception as exc:  # noqa: BLE001
                summary["failed"].append({"file": str(pdf), "error": str(exc)})
        return summary

    def query(self, request: QueryRequest, user_id: str = "api_user") -> QueryResponse:
        started = time.perf_counter()
        intent = analyze_query(request.question)

        if intent.is_comparison and len(intent.organizations) >= 2 and request.filters is None:
            candidates = self._comparison_candidates(request.question, intent)
            reranked = self.reranker.rerank(
                request.question,
                candidates,
                top_n=max(request.max_sources * 3, len(intent.organizations) * 3),
                intent=intent,
            )
            contexts = diversify_for_comparison(
                reranked,
                required_organizations=intent.organizations,
                limit=request.max_sources,
                per_document=2,
                per_organization=3,
                min_per_organization=1,
            )
        else:
            dense = self.vector_store.dense_search(request.question, k=120, intent=intent, filters=request.filters)
            keyword = self.bm25_index.search(request.question, k=120, intent=intent, filters=request.filters)
            fused = reciprocal_rank_fusion([dense, keyword], intent=intent)
            candidates = diversify_by_document(deduplicate_chunks(fused), limit=80, per_document=5)
            reranked = self.reranker.rerank(request.question, candidates, top_n=max(request.max_sources * 2, request.max_sources), intent=intent)
            contexts = diversify_by_document(reranked, limit=request.max_sources, per_document=3)

        response = build_extract_answer(request.question, contexts)

        latency_ms = int((time.perf_counter() - started) * 1000)
        response.latency_ms = latency_ms

        self.audit_db.log_query(
            user_id=user_id,
            question=request.question,
            answer=response.answer,
            confidence=response.confidence,
            latency_ms=latency_ms,
            status=response.status,
            review_flag=response.review_flag,
            sources=[s.model_dump() for s in response.sources],
        )

        if not self._logged_ready:
            if (
                self.vector_store._embedder is not None
                and self.reranker._model is not None
                and self.bm25.is_built
            ):
                import logging
                logger = logging.getLogger(__name__)
                logger.info("RAG Ready")
                self._logged_ready = True

        return response

    def _comparison_candidates(self, question: str, intent) -> list[dict]:
        rankings: list[list[dict]] = []
        branch_items: list[dict] = []

        for org in intent.organizations:
            branch_intent = intent_for_organization(intent, org)
            dense = self.vector_store.dense_search(question, k=60, intent=branch_intent, filters={"organization": org})
            keyword = self.bm25_index.search(question, k=60, intent=branch_intent, filters={"organization": org})
            fused_branch = reciprocal_rank_fusion([dense, keyword], intent=branch_intent)
            for item in fused_branch:
                item = dict(item)
                item["retrieval_branch"] = org
                branch_items.append(item)
            rankings.append(fused_branch)

        global_dense = self.vector_store.dense_search(question, k=80, intent=intent)
        global_keyword = self.bm25_index.search(question, k=80, intent=intent)
        rankings.extend([global_dense, global_keyword, branch_items])
        fused = reciprocal_rank_fusion(rankings, intent=intent)
        return diversify_for_comparison(
            fused,
            required_organizations=intent.organizations,
            limit=80,
            per_document=2,
            per_organization=20,
            min_per_organization=8,
        )
