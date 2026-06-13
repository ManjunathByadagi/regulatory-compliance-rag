from app.ingestion.chunking import build_chunks


def test_hierarchical_chunking_adds_section() -> None:
    page_texts = [
        (1, "Section 2.2 Cooperative Banks\n\nUrban cooperative banks shall maintain CRAR of 9%."),
    ]
    chunks = build_chunks("doc", page_texts, strategy="hierarchical")
    assert len(chunks) >= 1
    assert any("CRAR" in c.text for c in chunks)
