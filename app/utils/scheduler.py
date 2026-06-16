from __future__ import annotations

import time

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.evaluation.metrics import run_daily_evaluation


def start_scheduler() -> None:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_daily_evaluation,
        trigger="cron",
        hour=21,
        minute=0,
        kwargs={"benchmark_path": f"{settings.processed_dir}/benchmark_test_questions.json"},
        id="daily_ragas",
        replace_existing=True,
    )
    scheduler.start()

    try:
        while True:
            time.sleep(10)
    finally:
        scheduler.shutdown()
