from __future__ import annotations

from sentence_transformers import CrossEncoder

from app.core.config import settings


class CrossEncoderReranker:
    def __init__(self) -> None:
        self.model = CrossEncoder(settings.reranker_model)

    def rerank(self, query: str, candidates: list[dict], top_n: int = 5) -> list[dict]:
        if not candidates:
            return []
        pairs = [(query, c["text"]) for c in candidates]
        scores = self.model.predict(pairs)

        rescored = []
        for idx, cand in enumerate(candidates):
            item = dict(cand)
            item["rerank_score"] = float(scores[idx])
            rescored.append(item)

        rescored.sort(key=lambda x: x["rerank_score"], reverse=True)
        return rescored[:top_n]
