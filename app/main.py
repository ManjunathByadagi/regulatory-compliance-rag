from __future__ import annotations

import argparse

import uvicorn

from app.api.main import app
from app.core.config import settings
from app.evaluation.metrics import run_daily_evaluation
from app.evaluation.scheduler import start_scheduler
from app.ingestion.watcher import start_watcher


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regulatory Compliance RAG")
    parser.add_argument("command", choices=["api", "watch", "evaluate", "schedule"], help="Service to run")
    parser.add_argument("--path", default=settings.data_dir, help="Path for watch/evaluate")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "api":
        uvicorn.run(app, host=settings.api_host, port=settings.api_port)
    elif args.command == "watch":
        start_watcher(args.path)
    elif args.command == "evaluate":
        result = run_daily_evaluation(args.path)
        print(result)
    elif args.command == "schedule":
        start_scheduler()


if __name__ == "__main__":
    main()
