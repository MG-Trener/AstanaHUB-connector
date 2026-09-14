from __future__ import annotations

import logging
import os
import sys

from astanahub_connector.github_login import run_daily_visit


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    email = os.environ.get("ASTANAHUB_EMAIL", "").strip()
    password = os.environ.get("ASTANAHUB_PASSWORD", "")
    if not email or not password:
        logging.error("Добавьте GitHub Secrets ASTANAHUB_EMAIL и ASTANAHUB_PASSWORD")
        return 2
    try:
        result = run_daily_visit(email, password)
        logging.info("Готово: %s", result)
        return 0
    except Exception as exc:
        logging.error("Ежедневный вход не выполнен: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

