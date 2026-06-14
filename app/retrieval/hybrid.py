from __future__ import annotations

from collections import defaultdict


def reciprocal_rank_fusion(rankings: list[list[dict]], k: int = 60) -> list[dict]:
    scores: dict[str, float] = defaultdict(float)
    payload_map: dict[str, dict] = {}

    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            chunk_id = item["chunk_id"]
            scores[chunk_id] += 1.0 / (k + rank)
            payload_map[chunk_id] = item

    fused = []
    for chunk_id, score in scores.items():
        payload = dict(payload_map[chunk_id])
        payload["rrf_score"] = score
        fused.append(payload)

    fused.sort(key=lambda x: x["rrf_score"], reverse=True)
    return fused
