from app.core.answering import build_extract_answer
from app.retrieval.hybrid import diversify_for_comparison
from app.retrieval.query_understanding import analyze_query


QUESTION = "Compare Basel III and RBI capital adequacy requirements"


def test_comparison_query_detects_multiple_entities() -> None:
    intent = analyze_query(QUESTION)

    assert intent.is_comparison
    assert intent.organizations == ("BIS", "Reserve Bank of India")
    assert intent.comparison_entities == ("Basel III", "RBI")


def test_comparison_diversification_preserves_entity_coverage() -> None:
    items = [
        _chunk("basel-1", "basel3_summary", "BIS", 9.0),
        _chunk("basel-2", "finalising_basel3", "BIS", 8.0),
        _chunk("basel-3", "basel3_summary", "BIS", 7.0),
        _chunk("rbi-1", "capital_adequacy", "Reserve Bank of India", 3.0),
    ]

    selected = diversify_for_comparison(
        items,
        required_organizations=("Reserve Bank of India", "BIS"),
        limit=5,
        per_document=2,
        per_organization=3,
        min_per_organization=1,
    )
    orgs = {(item["metadata"] or {}).get("organization") for item in selected}

    assert "Reserve Bank of India" in orgs
    assert "BIS" in orgs


def test_comparison_answer_includes_rbi_and_basel_sources() -> None:
    contexts = [
        {
            "chunk_id": "basel-1",
            "text": "Basel III requires banks to hold minimum common equity tier 1 capital, tier 1 capital, total capital, and capital conservation buffers against risk weighted assets.",
            "metadata": {"document": "basel3_summary", "page_start": 4, "page_end": 4, "organization": "BIS"},
            "rerank_score": 9.0,
        },
        {
            "chunk_id": "rbi-1",
            "text": "RBI capital adequacy prudential norms require banks to maintain CRAR on an ongoing basis, including minimum capital against risk weighted assets.",
            "metadata": {"document": "capital_adequacy", "page_start": 7, "page_end": 7, "organization": "Reserve Bank of India"},
            "rerank_score": 8.5,
        },
    ]

    response = build_extract_answer(QUESTION, contexts)
    source_orgs = {source.organization for source in response.sources}

    assert "Reserve Bank of India" in source_orgs
    assert "BIS" in source_orgs
    assert "Comparison summary" in response.answer
    assert "Not stated" not in response.answer
    assert response.confidence > 0.8


def _chunk(chunk_id: str, document: str, organization: str, score: float) -> dict:
    return {
        "chunk_id": chunk_id,
        "text": "capital adequacy requirements and risk weighted assets",
        "metadata": {"document": document, "organization": organization},
        "rerank_score": score,
    }
