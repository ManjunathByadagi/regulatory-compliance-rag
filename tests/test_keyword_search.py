from app.retrieval.keyword_search import BM25Index
from app.retrieval.query_understanding import analyze_query


def test_bm25_ranks_matching_organization_above_generic_keyword_hit() -> None:
    chunks = [
        {
            "chunk_id": "sebi-1",
            "text": "Portfolio managers shall comply with capital adequacy requirements.",
            "metadata": {"document": "portfolio_managers_2020", "organization": "SEBI", "section": "Capital requirements"},
        },
        {
            "chunk_id": "rbi-1",
            "text": "Prudential norms require banks to maintain capital adequacy through CRAR.",
            "metadata": {"document": "rbi_prudential_norms", "organization": "Reserve Bank of India", "section": "Capital Adequacy"},
        },
    ]
    index = BM25Index()
    index.build(chunks)

    results = index.search("RBI capital adequacy requirements", intent=analyze_query("RBI capital adequacy requirements"))

    assert results[0]["chunk_id"] == "rbi-1"
