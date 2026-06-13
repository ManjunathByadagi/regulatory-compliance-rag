from __future__ import annotations

import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.core.rag_service import RAGService
from app.ingestion.alerts import send_ingestion_email


class PDFIngestionHandler(FileSystemEventHandler):
    def __init__(self, rag: RAGService) -> None:
        self.rag = rag

    def on_created(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.is_directory or not event.src_path.lower().endswith(".pdf"):
            return

        added = self.rag.ingest_pdf(event.src_path)
        send_ingestion_email(
            subject="New Regulatory Circular Ingested",
            body=f"File: {event.src_path}\nChunks indexed: {added}",
        )


def start_watcher(root_dir: str) -> None:
    rag = RAGService()
    handler = PDFIngestionHandler(rag)
    observer = Observer()
    observer.schedule(handler, str(Path(root_dir)), recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    finally:
        observer.stop()
        observer.join()
