from __future__ import annotations

from rank_bm25 import BM25Okapi


class BM25Index:
    def __init__(self) -> None:
        self._corpus_tokens: list[list[str]] = []
        self._payloads: list[dict] = []
        self._index: BM25Okapi | None = None

    def build(self, chunks: list[dict]) -> None:
        self._payloads = chunks
        self._corpus_tokens = [c["text"].lower().split() for c in chunks]
        self._index = BM25Okapi(self._corpus_tokens) if self._corpus_tokens else None

    def search(
    self,
    query: str,
    k: int = 50,
    intent: dict | None = None,
) -> list[dict]:
        if self._index is None:
            return []
        q_tokens = query.lower().split()
        scores = self._index.get_scores(q_tokens)
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

        out: list[dict] = []
        for idx in ranked_indices:
            payload = dict(self._payloads[idx])
            payload["score"] = float(scores[idx])
            out.append(payload)
        return out
