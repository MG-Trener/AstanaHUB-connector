from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from astanahub_connector.github_login import run_daily_visit

LOGS_DIR = Path("logs")
LOCAL_TIMEZONE = timezone(timedelta(hours=5), name="UTC+5")


def write_monthly_log(authentication: str, reward: str, now: datetime | None = None) -> Path:
    timestamp = now or datetime.now(LOCAL_TIMEZONE)
    log_path = LOGS_DIR / f"{timestamp:%Y-%m}.log"
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(
            f"{timestamp:%Y-%m-%d %H:%M:%S %z} | "
            f"Авторизация: {authentication} | Награда: {reward}\n"
        )
    return log_path


def reward_log_status(result: str) -> str:
    if result == "ежедневная награда получена":
        return "получена"
    return "не доступна"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    email = os.environ.get("ASTANAHUB_EMAIL", "").strip()
    password = os.environ.get("ASTANAHUB_PASSWORD", "")
    if not email or not password:
        logging.error("Добавьте GitHub Secrets ASTANAHUB_EMAIL и ASTANAHUB_PASSWORD")
        return 2
    try:
        result = run_daily_visit(email, password)
        write_monthly_log("успешно", reward_log_status(result))
        logging.info("Готово: %s", result)
        return 0
    except Exception as exc:
        write_monthly_log("ошибка", "не проверена")
        logging.error("Ежедневный вход не выполнен: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
