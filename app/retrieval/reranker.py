from __future__ import annotations

from sentence_transformers import CrossEncoder

from app.core.config import settings
from app.retrieval.query_understanding import QueryIntent, analyze_query, metadata_boost


class CrossEncoderReranker:
    def __init__(self) -> None:
        self._model = None

    @property
    def model(self) -> CrossEncoder:
        if self._model is None:
            import logging
            logger = logging.getLogger(__name__)
            logger.info("Loading CrossEncoder")
            self._model = CrossEncoder(settings.reranker_model)
        return self._model

    def rerank(self, query: str, candidates: list[dict], top_n: int = 5, intent: QueryIntent | None = None) -> list[dict]:
        if not candidates:
            return []
        intent = intent or analyze_query(query)
        pairs = [(query, c["text"]) for c in candidates]
        scores = self.model.predict(pairs)

        rescored = []
        for idx, cand in enumerate(candidates):
            item = dict(cand)
            cross_score = float(scores[idx])
            item["cross_encoder_score"] = cross_score
            coverage_boost = 0.2 if intent.is_comparison and _organization(item) in intent.organizations else 0.0
            item["rerank_score"] = cross_score + coverage_boost + (0.35 * metadata_boost(intent, item)) + (0.25 * float(item.get("rrf_score", 0.0)))
            rescored.append(item)

        rescored.sort(key=lambda x: x["rerank_score"], reverse=True)
        if intent.is_comparison and len(intent.organizations) >= 2:
            return _preserve_entity_coverage(rescored, intent.organizations, top_n)
        return rescored[:top_n]


def _preserve_entity_coverage(items: list[dict], organizations: tuple[str, ...], top_n: int) -> list[dict]:
    selected: list[dict] = []
    selected_ids: set[str] = set()

    for org in organizations:
        for item in items:
            if _organization(item) != org or item["chunk_id"] in selected_ids:
                continue
            selected.append(item)
            selected_ids.add(item["chunk_id"])
            break

    for item in items:
        if len(selected) >= top_n:
            break
        if item["chunk_id"] in selected_ids:
            continue
        selected.append(item)
        selected_ids.add(item["chunk_id"])

    return selected[:top_n]


def _organization(item: dict) -> str:
    return str((item.get("metadata") or {}).get("organization", "Unknown"))
