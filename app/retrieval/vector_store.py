from __future__ import annotations

from collections.abc import Iterable

import chromadb
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.ingestion.chunking import Chunk
from app.retrieval.query_understanding import QueryIntent, metadata_boost


class VectorStore:
    def __init__(self) -> None:
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Loading VectorStore")
        self.client = chromadb.PersistentClient(path=settings.vector_db_path)
        self.collection = self.client.get_or_create_collection(name="regulatory_chunks")
        self._embedder = None

    @property
    def embedder(self) -> SentenceTransformer:
        if self._embedder is None:
            import logging
            logger = logging.getLogger(__name__)
            logger.info("Loading Embedding Model")
            self._embedder = SentenceTransformer(settings.embedding_model)
        return self._embedder

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

    def dense_search(
        self,
        query: str,
        k: int = 50,
        intent: QueryIntent | None = None,
        filters: dict | None = None,
    ) -> list[dict]:
        search_text = intent.expanded_query if intent is not None else query
        q_emb = self.embedder.encode([search_text], normalize_embeddings=True).tolist()[0]
        query_args = {"query_embeddings": [q_emb], "n_results": k}
        if filters:
            query_args["where"] = filters

        res = self.collection.query(**query_args)
        items: list[dict] = []

        ids = res.get("ids", [[]])[0]
        docs = res.get("documents", [[]])[0]
        mets = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]

        for i in range(len(ids)):
            dense_score = 1.0 - float(dists[i]) if i < len(dists) else 0.0
            item = {
                "chunk_id": ids[i],
                "text": docs[i],
                "metadata": mets[i],
                "score": dense_score,
                "dense_score": dense_score,
            }
            if intent is not None:
                item["score"] += 0.05 * metadata_boost(intent, item)
            items.append(item)
        items.sort(key=lambda x: x["score"], reverse=True)
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
