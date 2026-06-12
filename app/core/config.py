from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Regulatory Compliance RAG Assistant"
    environment: str = "dev"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    streamlit_port: int = 8501

    api_key: str = "change-me"
    rate_limit_per_minute: int = 100

    data_dir: str = str(BASE_DIR / "data" / "raw")
    processed_dir: str = str(BASE_DIR / "data" / "processed")
    vector_db_path: str = str(BASE_DIR / "storage" / "chroma")
    query_log_db_path: str = str(BASE_DIR / "storage" / "logs" / "query_logs.db")
    evaluation_db_path: str = str(BASE_DIR / "storage" / "logs" / "evaluation.db")

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    chunk_strategy: str = "hierarchical"
    chunk_size: int = 512
    chunk_overlap: int = 64

    llm_provider: str = "extractive"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    watcher_poll_seconds: int = 30

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    email_from: str | None = None
    email_to: str = ""

    ui_username: str = "compliance"
    ui_password: str = "compliance123"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
