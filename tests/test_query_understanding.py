from app.retrieval.query_understanding import analyze_query, metadata_boost


def test_analyze_query_detects_rbi_capital_adequacy() -> None:
    intent = analyze_query("What are RBI capital adequacy requirements?")

    assert intent.primary_organization == "Reserve Bank of India"
    assert "capital adequacy" in intent.topics
    assert "crar" in intent.expanded_query.lower()


def test_metadata_boost_prefers_requested_organization() -> None:
    intent = analyze_query("RBI capital adequacy requirements")
    rbi = {"text": "Prudential norms on capital adequacy and CRAR.", "metadata": {"organization": "Reserve Bank of India"}}
    sebi = {"text": "Capital requirements for portfolio managers.", "metadata": {"organization": "SEBI"}}

    assert metadata_boost(intent, rbi) > metadata_boost(intent, sebi)
