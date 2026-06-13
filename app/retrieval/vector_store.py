from __future__ import annotations

from collections.abc import Iterable

import chromadb
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.ingestion.chunking import Chunk


class VectorStore:
    def __init__(self) -> None:
        self.client = chromadb.PersistentClient(path=settings.vector_db_path)
        self.collection = self.client.get_or_create_collection(name="regulatory_chunks")
        self.embedder = SentenceTransformer(settings.embedding_model)

    def upsert_chunks(self, chunks: Iterable[Chunk], source_path: str, doc_type: str, organization: str) -> int:
        ids: list[str] = []
        docs: list[str] = []
        metadatas: list[dict] = []

        for c in chunks:
            ids.append(c.chunk_id)
            docs.append(c.text)
            metadatas.append(
                {
                    "document": c.document,
                    "section": c.section,
                    "page_start": c.page_start,
                    "page_end": c.page_end,
                    "source_path": source_path,
                    "doc_type": doc_type,
                    "organization": organization,
                }
            )

        if not ids:
            return 0

        embeddings = self.embedder.encode(docs, normalize_embeddings=True).tolist()
        self.collection.upsert(ids=ids, documents=docs, embeddings=embeddings, metadatas=metadatas)
        return len(ids)

    def dense_search(self, query: str, k: int = 50) -> list[dict]:
        q_emb = self.embedder.encode([query], normalize_embeddings=True).tolist()[0]
        res = self.collection.query(query_embeddings=[q_emb], n_results=k)
        items: list[dict] = []

        ids = res.get("ids", [[]])[0]
        docs = res.get("documents", [[]])[0]
        mets = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]

        for i in range(len(ids)):
            items.append(
                {
                    "chunk_id": ids[i],
                    "text": docs[i],
                    "metadata": mets[i],
                    "score": 1.0 - float(dists[i]) if i < len(dists) else 0.0,
                }
            )
        return items

    def all_docs(self) -> list[dict]:
        data = self.collection.get(include=["documents", "metadatas"])
        out: list[dict] = []
        for idx, chunk_id in enumerate(data.get("ids", [])):
            out.append(
                {
                    "chunk_id": chunk_id,
                    "text": data["documents"][idx],
                    "metadata": data["metadatas"][idx],
                }
            )
        return out
