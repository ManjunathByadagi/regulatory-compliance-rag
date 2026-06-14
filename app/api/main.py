from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.security import validate_api_key
from app.core.config import settings
from app.core.rag_service import RAGService
from app.core.schemas import QueryRequest, QueryResponse
from app.utils.logging_utils import configure_logging


configure_logging()
app = FastAPI(title="Regulatory Compliance RAG API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag_service = RAGService()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name}


@app.post("/ingest")
def ingest_documents(root_dir: str, _: str = Depends(validate_api_key)) -> dict:
    summary = rag_service.batch_ingest(root_dir)
    return {"status": "ok", "summary": summary}


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest, token: str = Depends(validate_api_key)) -> QueryResponse:
    try:
        return rag_service.query(request=request, user_id=token[:8])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}") from exc
