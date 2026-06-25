from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from app.retrieval.query_understanding import QueryIntent, analyze_query, metadata_boost


def reciprocal_rank_fusion(rankings: list[list[dict]], k: int = 60, intent: QueryIntent | None = None) -> list[dict]:
    intent = intent or analyze_query("")
    scores: dict[str, float] = defaultdict(float)
    payload_map: dict[str, dict] = {}
    signal_map: dict[str, dict[str, float]] = defaultdict(dict)

    for source_idx, ranking in enumerate(rankings):
        for rank, item in enumerate(ranking, start=1):
            chunk_id = item["chunk_id"]
            raw_score = _item_score(item)
            normalized_score = _normalize_rank_score(raw_score, ranking)
            rrf = 1.0 / (k + rank)
            scores[chunk_id] += rrf + (0.025 * normalized_score)
            signal_map[chunk_id][f"ranker_{source_idx}_rrf"] = rrf
            signal_map[chunk_id][f"ranker_{source_idx}_score"] = raw_score

            existing = payload_map.get(chunk_id, {})
            merged = dict(existing)
            merged.update(item)
            payload_map[chunk_id] = merged

    for chunk_id, payload in payload_map.items():
        boost = metadata_boost(intent, payload)
        scores[chunk_id] += boost * 0.08
        signal_map[chunk_id]["metadata_boost"] = boost

    fused = []
    for chunk_id, score in scores.items():
        payload = dict(payload_map[chunk_id])
        payload["rrf_score"] = score
        payload["ranking_signals"] = signal_map[chunk_id]
        fused.append(payload)

    fused.sort(key=lambda x: x["rrf_score"], reverse=True)
    return fused


def diversify_by_document(items: list[dict], limit: int, per_document: int = 3) -> list[dict]:
    selected: list[dict] = []
    counts: dict[str, int] = defaultdict(int)

    for item in deduplicate_chunks(items):
        document = str((item.get("metadata") or {}).get("document", "Unknown"))
        if counts[document] >= per_document and len(selected) < limit:
            continue
        selected.append(item)
        counts[document] += 1
        if len(selected) >= limit:
            break
    return selected


def diversify_for_comparison(
    items: list[dict],
    required_organizations: tuple[str, ...],
    limit: int,
    per_document: int = 2,
    per_organization: int = 3,
    min_per_organization: int = 1,
) -> list[dict]:
    deduped = deduplicate_chunks(items)
    selected: list[dict] = []
    selected_ids: set[str] = set()
    doc_counts: dict[str, int] = defaultdict(int)
    org_counts: dict[str, int] = defaultdict(int)

    for org in required_organizations:
        for item in deduped:
            if _organization(item) != org or item["chunk_id"] in selected_ids:
                continue
            if doc_counts[_document(item)] >= per_document:
                continue
            selected.append(item)
            selected_ids.add(item["chunk_id"])
            doc_counts[_document(item)] += 1
            org_counts[org] += 1
            if org_counts[org] >= min_per_organization:
                break

    for item in deduped:
        if len(selected) >= limit:
            break
        chunk_id = item["chunk_id"]
        if chunk_id in selected_ids:
            continue
        doc = _document(item)
        org = _organization(item)
        if doc_counts[doc] >= per_document:
            continue
        if org_counts[org] >= per_organization:
            continue
        selected.append(item)
        selected_ids.add(chunk_id)
        doc_counts[doc] += 1
        org_counts[org] += 1

    return selected[:limit]


def deduplicate_chunks(items: Iterable[dict], similarity_threshold: float = 0.92) -> list[dict]:
    selected: list[dict] = []
    fingerprints: set[str] = set()

    for item in items:
        text = " ".join(str(item.get("text", "")).lower().split())
        if not text:
            continue
        fingerprint = f"{_organization(item)}::{_document(item)}::{text[:500]}"
        if fingerprint in fingerprints:
            continue
        if any(
            _same_source_identity(item, prev) and _jaccard(text, str(prev.get("text", "")).lower()) >= similarity_threshold
            for prev in selected
        ):
            continue
        fingerprints.add(fingerprint)
        selected.append(item)
    return selected


def _item_score(item: dict) -> float:
    for key in ("rerank_score", "score", "bm25_score", "dense_score"):
        if key in item:
            return float(item[key])
    return 0.0


def _normalize_rank_score(score: float, ranking: list[dict]) -> float:
    values = [_item_score(item) for item in ranking]
    if not values:
        return 0.0
    lo = min(values)
    hi = max(values)
    if hi <= lo:
        return 0.0
    return (score - lo) / (hi - lo)


def _jaccard(left: str, right: str) -> float:
    left_terms = set(left.split())
    right_terms = set(right.split())
    if not left_terms or not right_terms:
        return 0.0
    return len(left_terms & right_terms) / len(left_terms | right_terms)


def _document(item: dict) -> str:
    return str((item.get("metadata") or {}).get("document", "Unknown"))


def _organization(item: dict) -> str:
    return str((item.get("metadata") or {}).get("organization", "Unknown"))


def _same_source_identity(left: dict, right: dict) -> bool:
    return _organization(left) == _organization(right) and _document(left) == _document(right)
