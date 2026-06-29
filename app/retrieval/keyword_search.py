from __future__ import annotations

from rank_bm25 import BM25Okapi

from app.retrieval.query_understanding import QueryIntent, metadata_boost


class BM25Index:
    def __init__(self) -> None:
        self._corpus_tokens: list[list[str]] = []
        self._payloads: list[dict] = []
        self._index: BM25Okapi | None = None

    @property
    def is_built(self) -> bool:
        return self._index is not None

    def build(self, chunks: list[dict]) -> None:
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Loading BM25")
        self._payloads = chunks
        self._corpus_tokens = [c["text"].lower().split() for c in chunks]
        self._index = BM25Okapi(self._corpus_tokens) if self._corpus_tokens else None

    def search(
        self,
        query: str,
        k: int = 50,
        intent: QueryIntent | None = None,
        filters: dict | None = None,
    ) -> list[dict]:
        if self._index is None:
            return []
        search_text = intent.expanded_query if intent is not None else query
        q_tokens = search_text.lower().split()
        scores = self._index.get_scores(q_tokens)
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

        out: list[dict] = []
        for idx in ranked_indices:
            payload = dict(self._payloads[idx])
            if filters and not _matches_filters(payload, filters):
                continue
            bm25_score = float(scores[idx])
            payload["score"] = bm25_score
            payload["bm25_score"] = bm25_score
            if intent is not None:
                payload["score"] += 0.35 * metadata_boost(intent, payload)
            out.append(payload)
            if len(out) >= k:
                break
        return out


def _matches_filters(payload: dict, filters: dict) -> bool:
    metadata = payload.get("metadata") or {}
    return all(metadata.get(key) == value for key, value in filters.items())
