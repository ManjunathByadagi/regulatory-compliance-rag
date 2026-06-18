from __future__ import annotations

import re
from collections import Counter

from app.core.schemas import QueryResponse, SourceCitation
from app.retrieval.query_understanding import analyze_query, metadata_boost


COMPARE_HINTS = {"difference", "difference between", "compare", "contrast", "vs", "versus", "commercial", "cooperative"}
ORG_LABELS = {"Reserve Bank of India": "RBI", "BIS": "Basel III", "SEBI": "SEBI"}


def is_comparison_question(question: str) -> bool:
    q = question.lower()
    return any(h in q for h in COMPARE_HINTS)


def extract_highlights(text: str, question: str) -> list[str]:
    highlights: list[str] = []
    for token in re.findall(r"[A-Za-z0-9%\.]+", question):
        if len(token) < 3:
            continue
        if token.lower() in text.lower():
            highlights.append(token)
    for pat in [r"\b\d+(?:\.\d+)?%\b", r"\bCRAR\b", r"\bBasel\s*III\b"]:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            highlights.append(m.group(0))
    # Preserve order and uniqueness.
    seen = set()
    ordered = []
    for h in highlights:
        key = h.lower()
        if key not in seen:
            seen.add(key)
            ordered.append(h)
    return ordered[:8]


def build_extract_answer(question: str, contexts: list[dict]) -> QueryResponse:
    if not contexts:
        return QueryResponse(
            answer="I don't know based on the currently indexed regulatory documents.",
            sources=[],
            confidence=0.0,
            latency_ms=0,
            status="no_answer",
            review_flag=True,
        )

    intent = analyze_query(question)
    sentences_with_context: list[tuple[dict, str]] = []
    for item in contexts[:8]:
        for sentence in re.split(r"(?<=[.!?])\s+", item["text"]):
            clean = sentence.strip()
            if clean:
                sentences_with_context.append((item, clean))
    q_terms = {t.lower() for t in re.findall(r"[A-Za-z0-9]+", question) if len(t) > 2}

    scored: list[tuple[float, dict, str]] = []
    for item, s in sentences_with_context:
        s_terms = {t.lower() for t in re.findall(r"[A-Za-z0-9]+", s)}
        overlap = len(q_terms & s_terms)
        coverage = overlap / max(1, len(q_terms))
        regulatory_signal = 0.15 if re.search(r"\b(CRAR|capital adequacy|prudential|Basel|risk weighted|minimum capital|\d+(?:\.\d+)?%)\b", s, re.I) else 0.0
        raw_rank = float(item.get("rerank_score", item.get("rrf_score", 0.0)))
        rank_signal = min(0.2, max(raw_rank, 0.0) / 10)
        scored.append((coverage + regulatory_signal + rank_signal + (0.08 * metadata_boost(intent, item)), item, s.strip()))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_sentences = _select_diverse_sentences(scored, limit=4)

    if not best_sentences:
        return QueryResponse(
            answer="I don't know based on the currently indexed regulatory documents.",
            sources=[],
            confidence=0.1,
            latency_ms=0,
            status="no_answer",
            review_flag=True,
        )

    if is_comparison_question(question):
        return _comparison_answer(question, contexts)

    answer = _format_synthesized_answer(question, best_sentences)
    confidence = _estimate_confidence(scored, contexts, intent)

    citations = _build_citations(contexts, question)

    status = "ok" if confidence >= 0.6 else "review_required"
    review_flag = confidence < 0.6

    return QueryResponse(
        answer=answer,
        sources=citations,
        confidence=round(confidence, 3),
        latency_ms=0,
        status=status,
        review_flag=review_flag,
    )


def _select_diverse_sentences(scored: list[tuple[float, dict, str]], limit: int) -> list[tuple[dict, str]]:
    selected: list[tuple[dict, str]] = []
    seen_docs: Counter[str] = Counter()
    seen_sentences: set[str] = set()

    for score, item, sentence in scored:
        if score <= 0:
            continue
        normalized = " ".join(sentence.lower().split())
        if normalized in seen_sentences:
            continue
        doc = str((item.get("metadata") or {}).get("document", "Unknown"))
        if seen_docs[doc] >= 2 and len(selected) < limit:
            continue
        selected.append((item, sentence))
        seen_docs[doc] += 1
        seen_sentences.add(normalized)
        if len(selected) >= limit:
            break
    return selected


def _format_synthesized_answer(question: str, evidence: list[tuple[dict, str]]) -> str:
    if len(evidence) == 1:
        return evidence[0][1]

    lines = ["Based on the retrieved regulatory sources:"]
    for item, sentence in evidence:
        meta = item.get("metadata") or {}
        org = meta.get("organization") or "Source"
        page = meta.get("page_start", "?")
        lines.append(f"- {org}, p. {page}: {sentence}")
    if any(word in question.lower() for word in ["requirement", "requirements", "required", "adequacy"]):
        lines.append("This answer should be read with the cited circular or regulation because capital rules can vary by bank type and date.")
    return "\n".join(lines)


def _estimate_confidence(scored: list[tuple[float, dict, str]], contexts: list[dict], intent) -> float:
    if not scored:
        return 0.0
    top_score = max(0.0, scored[0][0])
    source_count = min(3, len(contexts)) / 3
    org_match = 0.0
    if intent.organizations:
        org_match = 0.2 if any((c.get("metadata") or {}).get("organization") in intent.organizations for c in contexts[:3]) else -0.25
    confidence = 0.35 + min(0.35, top_score * 0.35) + (0.15 * source_count) + org_match
    return round(min(0.95, max(0.1, confidence)), 3)


def _build_citations(contexts: list[dict], question: str) -> list[SourceCitation]:
    citations = []
    seen = set()
    for item in contexts[:5]:
        meta = item["metadata"]
        key = (meta.get("document"), meta.get("page_start"), item["text"][:120])
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            SourceCitation(
                document=meta.get("document", "Unknown"),
                page=f"{meta.get('page_start', '?')}-{meta.get('page_end', '?')}",
                excerpt=item["text"][:500],
                highlight=extract_highlights(item["text"], question),
                section=meta.get("section"),
                organization=meta.get("organization"),
                date=meta.get("date"),
                doc_type=meta.get("doc_type"),
                download_link=meta.get("source_path"),
            )
        )
    return citations


def _comparison_answer(question: str, contexts: list[dict]) -> QueryResponse:
    intent = analyze_query(question)
    grouped: dict[str, list[tuple[float, dict, str]]] = {}
    for item in contexts[:10]:
        org = str((item.get("metadata") or {}).get("organization", "Unknown"))
        for sentence in _evidence_sentences(item["text"]):
            score = _comparison_sentence_score(question, sentence, item)
            if score > 0:
                grouped.setdefault(org, []).append((score, item, sentence))

    requested_orgs = intent.organizations or tuple(grouped.keys())
    table_lines = ["Comparison summary:", "", "| Entity | Capital adequacy requirement evidence | Source |", "|---|---|---|"]
    covered_orgs = set()

    for org in requested_orgs:
        evidence = sorted(grouped.get(org, []), key=lambda x: x[0], reverse=True)
        if not evidence:
            continue
        _, item, sentence = evidence[0]
        meta = item.get("metadata") or {}
        covered_orgs.add(org)
        label = ORG_LABELS.get(org, org)
        source = f"{meta.get('document', 'Unknown')}, p. {meta.get('page_start', '?')}"
        table_lines.append(f"| {label} | {_clean_table_cell(sentence)} | {source} |")

    if len(covered_orgs) >= 2:
        table_lines.extend(
            [
                "",
                "Key difference:",
                _comparison_takeaway(grouped, requested_orgs),
            ]
        )

    citations = _build_citations(contexts, question)
    confidence = 0.88 if len(covered_orgs) >= min(2, len(requested_orgs)) else 0.62

    answer = "\n".join(table_lines)
    return QueryResponse(
        answer=answer,
        sources=citations,
        confidence=confidence,
        latency_ms=0,
        status="ok" if confidence >= 0.8 else "review_required",
        review_flag=confidence < 0.8,
    )


def _evidence_sentences(text: str) -> list[str]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]
    if len(sentences) == 1 and len(sentences[0].split()) > 80:
        clauses = [s.strip() for s in re.split(r";\s+|,\s+(?=(?:and|with|including|requiring)\b)", sentences[0]) if s.strip()]
        return clauses or sentences
    return sentences


def _comparison_sentence_score(question: str, sentence: str, item: dict) -> float:
    q_terms = {t.lower() for t in re.findall(r"[A-Za-z0-9]+", question) if len(t) > 2}
    s_terms = {t.lower() for t in re.findall(r"[A-Za-z0-9]+", sentence)}
    overlap = len(q_terms & s_terms) / max(1, len(q_terms))
    regulatory_signal = 0.5 if re.search(r"\b(CRAR|capital adequacy|capital conservation|tier\s*1|common equity|risk weighted|minimum capital|\d+(?:\.\d+)?%)\b", sentence, re.I) else 0.0
    raw_rank = float(item.get("rerank_score", item.get("rrf_score", 0.0)))
    rank_signal = min(0.2, max(raw_rank, 0.0) / 10)
    return overlap + regulatory_signal + rank_signal


def _comparison_takeaway(grouped: dict[str, list[tuple[float, dict, str]]], requested_orgs: tuple[str, ...]) -> str:
    labels = [ORG_LABELS.get(org, org) for org in requested_orgs if grouped.get(org)]
    if len(labels) < 2:
        return "The available retrieved evidence does not cover every requested entity."
    return f"{labels[0]} evidence reflects the domestic regulatory requirement, while {labels[1]} evidence reflects the Basel framework or standard used for comparison."


def _clean_table_cell(text: str) -> str:
    return re.sub(r"\s+", " ", text).replace("|", "/")[:450]
