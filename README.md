# Regulatory Compliance RAG Assistant

Production-oriented RAG system for compliance teams handling RBI circulars, Basel III guidance, and SEBI regulations.

## Implemented Features

1. Smart question answering with confidence score and explicit "I don't know" behavior.
2. Hybrid retrieval: dense embeddings + BM25 + Reciprocal Rank Fusion + cross-encoder reranking.
3. Full citation support with document, page range, section, excerpt, and highlight hints.
4. Semantic and hierarchical chunking with metadata.
5. Multi-document comparison formatting for compare/difference questions.
6. Real-time document updates via folder watcher and incremental ingestion.
7. Daily evaluation pipeline with RAGAS-style metrics persisted for dashboarding.
8. Streamlit web UI with authentication, filters, recent queries, confidence color coding.
9. FastAPI endpoint with API-key authentication, rate limiting, and Swagger docs.
10. Docker + docker-compose deployment assets with health checks.

## Architecture

- Ingestion: PDF parse -> chunk -> metadata enrich -> embed -> ChromaDB upsert.
- Retrieval: Dense top-100 + BM25 top-100 -> RRF fuse -> cross-encoder rerank top-5.
- Generation: Extractive answer synthesis from reranked chunks with strict citation grounding.
- Audit: SQLite query logs with 7-year retention function.
- Evaluation: Daily scheduled benchmark scoring + trend dashboard.

## Quick Start

1. Copy env file:

```bash
cp .env.example .env
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Ingest documents:

```bash
python -m app.main api
# In another shell:
curl -X POST "http://localhost:8000/ingest?root_dir=./data/raw" -H "Authorization: Bearer change-me"
```

4. Query API:

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Authorization: Bearer change-me" \
  -H "Content-Type: application/json" \
  -d '{"question":"What CRAR percentage must urban cooperative banks maintain?","max_sources":5,"include_excerpts":true}'
```

5. Launch Streamlit UI:

```bash
streamlit run app/ui/streamlit_app.py
```

6. Launch Evaluation Dashboard:

```bash
streamlit run app/ui/dashboard.py --server.port 8502
```

## Daily Evaluation

Run one-off:

```bash
python -m app.main evaluate --path ./data/processed/benchmark_test_questions.json
```

Run scheduler:

```bash
python -m app.main schedule
```

## Auto-Ingestion Watcher

```bash
python -m app.main watch --path ./data/raw
```

## Docker Deployment

```bash
docker-compose up --build
```

- API: http://localhost:8000/docs
- Assistant UI: http://localhost:8501
- RAGAS Dashboard: http://localhost:8502

## API Contract

### POST /query

Request:

```json
{
  "question": "What CRAR percentage for urban cooperative banks?",
  "max_sources": 5,
  "include_excerpts": true
}
```

Response:

```json
{
  "answer": "Urban cooperative banks shall maintain ...",
  "sources": [
    {
      "document": "RBI Circular 1452",
      "page": "8-10",
      "excerpt": "Urban cooperative banks shall maintain a minimum CRAR of 9%...",
      "highlight": ["CRAR", "9%"],
      "section": "Section 2.2 Cooperative Banks",
      "organization": "Reserve Bank of India",
      "date": null,
      "doc_type": "Regulatory Circular",
      "download_link": "./data/raw/rbi_circulars/...pdf"
    }
  ],
  "confidence": 0.92,
  "latency_ms": 1200,
  "status": "ok",
  "review_flag": false
}
```

## Testing

```bash
pytest -q
```

## Notes

- Place benchmark file at `data/processed/benchmark_test_questions.json`.
- Place PDFs under `data/raw/rbi_circulars`, `data/raw/basel_iii`, `data/raw/sebi_regulations`.
- For production, replace extractive answer mode with enterprise LLM under guarded prompt + citation verifier.
