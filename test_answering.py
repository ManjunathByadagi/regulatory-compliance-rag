from app.core.answering import build_extract_answer


def test_unknown_when_no_context() -> None:
    res = build_extract_answer("What is CRAR?", [])
    assert "I don't know" in res.answer
    assert res.status == "no_answer"


def test_extract_answer_with_context() -> None:
    contexts = [
        {
            "text": "Urban cooperative banks shall maintain a minimum CRAR of 9% on an ongoing basis.",
            "metadata": {"document": "RBI Circular 1452", "page_start": 8, "page_end": 10},
        }
    ]
    res = build_extract_answer("What CRAR percentage must urban cooperative banks maintain?", contexts)
    assert "CRAR" in res.answer
    assert res.sources


def test_extract_answer_synthesizes_across_sources() -> None:
    contexts = [
        {
            "text": "Capital Adequacy\nBanks shall maintain CRAR under RBI prudential norms.",
            "metadata": {"document": "rbi_prudential_norms", "page_start": 3, "page_end": 3, "organization": "Reserve Bank of India"},
            "rerank_score": 5.0,
        },
        {
            "text": "Basel III sets out capital adequacy buffers and risk weighted asset requirements.",
            "metadata": {"document": "basel_iii", "page_start": 12, "page_end": 12, "organization": "BIS"},
            "rerank_score": 3.0,
        },
    ]
    res = build_extract_answer("What are RBI capital adequacy requirements?", contexts)

    assert "retrieved regulatory sources" in res.answer
    assert "Reserve Bank of India" in res.answer
    assert len(res.sources) == 2
    assert res.confidence >= 0.6
