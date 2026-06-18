from __future__ import annotations

import re
from dataclasses import dataclass


ORG_ALIASES: dict[str, set[str]] = {
    "Reserve Bank of India": {"rbi", "reserve bank", "reserve bank of india"},
    "SEBI": {"sebi", "securities and exchange board", "securities and exchange board of india"},
    "BIS": {"bis", "basel", "basel iii", "basel 3", "basel committee", "bcbs"},
}

ORG_DISPLAY_NAMES: dict[str, str] = {
    "Reserve Bank of India": "RBI",
    "SEBI": "SEBI",
    "BIS": "Basel III",
}

TOPIC_ALIASES: dict[str, set[str]] = {
    "capital adequacy": {"capital adequacy", "crar", "capital to risk weighted assets", "capital requirement"},
    "prudential norms": {"prudential norms", "prudential guidelines", "prudential regulation"},
    "portfolio managers": {"portfolio managers", "portfolio manager"},
    "foreign portfolio investors": {"foreign portfolio investors", "fpi", "fpIs"},
}

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "for",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "under",
    "what",
    "which",
    "who",
    "with",
}

COMPARISON_PATTERNS = (
    r"\bcompare\b",
    r"\bdifference\s+between\b",
    r"\bversus\b",
    r"\bvs\.?\b",
    r"\bcontrast\b",
)


@dataclass(frozen=True)
class QueryIntent:
    raw_query: str
    organizations: tuple[str, ...]
    topics: tuple[str, ...]
    keywords: tuple[str, ...]
    expanded_query: str
    is_comparison: bool = False
    comparison_entities: tuple[str, ...] = ()

    @property
    def primary_organization(self) -> str | None:
        return self.organizations[0] if self.organizations else None


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?", text)]


def normalize_text(text: str) -> str:
    return " ".join(tokenize(text))


def analyze_query(query: str) -> QueryIntent:
    normalized = normalize_text(query)
    organization_hits: list[tuple[int, str]] = []
    topics: list[str] = []
    is_comparison = any(re.search(pattern, query, flags=re.IGNORECASE) for pattern in COMPARISON_PATTERNS)

    for org, aliases in ORG_ALIASES.items():
        positions = [_phrase_index(normalized, alias) for alias in aliases]
        positions = [pos for pos in positions if pos >= 0]
        if positions:
            organization_hits.append((min(positions), org))
    organizations = [org for _, org in sorted(organization_hits, key=lambda x: x[0])]

    for topic, aliases in TOPIC_ALIASES.items():
        if any(_contains_phrase(normalized, alias) for alias in aliases):
            topics.append(topic)

    keywords = tuple(t for t in tokenize(query) if len(t) > 2 and t not in STOP_WORDS)
    expanded_parts = [query]
    for org in organizations:
        expanded_parts.extend(sorted(ORG_ALIASES[org], key=len, reverse=True)[:2])
    for topic in topics:
        expanded_parts.extend(sorted(TOPIC_ALIASES[topic], key=len, reverse=True))

    return QueryIntent(
        raw_query=query,
        organizations=tuple(organizations),
        topics=tuple(topics),
        keywords=keywords,
        expanded_query=" ".join(expanded_parts),
        is_comparison=is_comparison,
        comparison_entities=tuple(ORG_DISPLAY_NAMES.get(org, org) for org in organizations) if is_comparison else (),
    )


def intent_for_organization(intent: QueryIntent, organization: str) -> QueryIntent:
    expanded_parts = [intent.raw_query, organization]
    expanded_parts.extend(sorted(ORG_ALIASES.get(organization, {organization}), key=len, reverse=True))
    for topic in intent.topics:
        expanded_parts.extend(sorted(TOPIC_ALIASES.get(topic, {topic}), key=len, reverse=True))

    return QueryIntent(
        raw_query=intent.raw_query,
        organizations=(organization,),
        topics=intent.topics,
        keywords=intent.keywords,
        expanded_query=" ".join(expanded_parts),
        is_comparison=intent.is_comparison,
        comparison_entities=intent.comparison_entities,
    )


def metadata_boost(intent: QueryIntent, item: dict) -> float:
    metadata = item.get("metadata") or {}
    haystacks = [
        str(metadata.get("organization", "")),
        str(metadata.get("document", "")),
        str(metadata.get("section", "")),
        str(metadata.get("doc_type", "")),
        str(metadata.get("source_path", "")),
    ]
    joined = normalize_text(" ".join(haystacks))
    text = normalize_text(str(item.get("text", ""))[:1200])

    boost = 0.0
    for org in intent.organizations:
        aliases = ORG_ALIASES.get(org, {org})
        if normalize_text(str(metadata.get("organization", ""))) == normalize_text(org):
            boost += 1.2
        elif any(_contains_phrase(joined, alias) for alias in aliases):
            boost += 0.85
        elif any(_contains_phrase(text, alias) for alias in aliases):
            boost += 0.35
        else:
            boost -= 0.65

    for topic in intent.topics:
        aliases = TOPIC_ALIASES.get(topic, {topic})
        if any(_contains_phrase(joined, alias) for alias in aliases):
            boost += 0.55
        if any(_contains_phrase(text, alias) for alias in aliases):
            boost += 0.4

    title_hits = sum(1 for term in intent.keywords if _contains_phrase(joined, term))
    boost += min(0.45, title_hits * 0.08)
    return boost


def organization_filter(intent: QueryIntent) -> dict | None:
    if not intent.primary_organization:
        return None
    return {"organization": intent.primary_organization}


def _contains_phrase(normalized_haystack: str, phrase: str) -> bool:
    normalized_phrase = normalize_text(phrase)
    if not normalized_phrase:
        return False
    return re.search(rf"(?<!\w){re.escape(normalized_phrase)}(?!\w)", normalized_haystack) is not None


def _phrase_index(normalized_haystack: str, phrase: str) -> int:
    normalized_phrase = normalize_text(phrase)
    if not normalized_phrase:
        return -1
    match = re.search(rf"(?<!\w){re.escape(normalized_phrase)}(?!\w)", normalized_haystack)
    return match.start() if match else -1
