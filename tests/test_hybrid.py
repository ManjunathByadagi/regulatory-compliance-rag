from app.retrieval.hybrid import reciprocal_rank_fusion


def test_rrf_combines_rankings() -> None:
    dense = [{"chunk_id": "a", "text": "x"}, {"chunk_id": "b", "text": "y"}]
    bm25 = [{"chunk_id": "b", "text": "y"}, {"chunk_id": "c", "text": "z"}]

    fused = reciprocal_rank_fusion([dense, bm25])
    ids = [i["chunk_id"] for i in fused]

    assert "b" in ids
    assert len(fused) == 3
