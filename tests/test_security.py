import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.main import app, get_rag_service
from app.api.security import RateLimiter
from app.core.config import settings
from app.core.schemas import QueryResponse


def test_rate_limiter_blocks_after_limit() -> None:
    limiter = RateLimiter(2)
    key = "k"
    limiter.check(key)
    limiter.check(key)
    with pytest.raises(HTTPException):
        limiter.check(key)


def test_openapi_uses_bearer_security_scheme() -> None:
    schema = app.openapi()

    assert schema["components"]["securitySchemes"]["BearerAuth"] == {
        "type": "http",
        "description": "Use the configured API key as a bearer token.",
        "scheme": "bearer",
        "bearerFormat": "API key",
    }
    assert schema["paths"]["/ingest"]["post"]["security"] == [{"BearerAuth": []}]
    assert schema["paths"]["/query"]["post"]["security"] == [{"BearerAuth": []}]


def test_protected_endpoints_receive_authorization_header() -> None:
    seen: dict[str, str] = {}

    class StubRAGService:
        def batch_ingest(self, root_dir: str) -> dict:
            seen["root_dir"] = root_dir
            return {"documents": 0}

        def query(self, request, user_id: str) -> QueryResponse:
            seen["user_id"] = user_id
            return QueryResponse(answer="ok", sources=[], confidence=1.0, latency_ms=1)

    app.dependency_overrides[get_rag_service] = lambda: StubRAGService()
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {settings.api_key}"}

    try:
        ingest_response = client.post("/ingest", params={"root_dir": "data/raw"}, headers=headers)
        query_response = client.post("/query", json={"question": "What is Basel III?"}, headers=headers)
        missing_token_response = client.post("/ingest", params={"root_dir": "data/raw"})
    finally:
        app.dependency_overrides.clear()

    assert ingest_response.status_code == 200
    assert ingest_response.json() == {"status": "ok", "summary": {"documents": 0}}
    assert seen["root_dir"] == "data/raw"

    assert query_response.status_code == 200
    assert query_response.json()["answer"] == "ok"
    assert seen["user_id"] == settings.api_key[:8]

    assert missing_token_response.status_code == 401
    assert missing_token_response.json() == {"detail": "Missing bearer token"}