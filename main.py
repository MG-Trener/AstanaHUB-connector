from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOGS_DIR = Path("logs")
LOCAL_TIMEZONE = timezone(timedelta(hours=5), name="UTC+5")
REWARD_INTERVAL = timedelta(hours=24)


def write_monthly_log(
    authentication: str,
    reward: str,
    quests: str | None = None,
    now: datetime | None = None,
) -> Path:
    timestamp = now or datetime.now(LOCAL_TIMEZONE)
    log_path = LOGS_DIR / f"{timestamp:%Y-%m}.log"
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        line = (
            f"{timestamp:%Y-%m-%d %H:%M:%S %z} | "
            f"Авторизация: {authentication} | Награда: {reward}"
        )
        if quests:
            line += f" | Квесты: {quests}"
        log_file.write(line + "\n")
    return log_path


def reward_log_status(result: str) -> str:
    if result == "ежедневная награда получена":
        return "получена"
    if result == "ежедневная награда не проверялась":
        return "не проверялась"
    return "не доступна"


def last_reward_time(logs_dir: Path | None = None) -> datetime | None:
    directory = logs_dir or LOGS_DIR
    latest: datetime | None = None
    if not directory.exists():
        return None

    for log_path in directory.glob("*.log"):
        try:
            lines = log_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue

        for line in lines:
            if "| Награда: получена" not in line:
                continue
            timestamp_text = line.split(" | ", 1)[0].strip()
            try:
                timestamp = datetime.strptime(timestamp_text, "%Y-%m-%d %H:%M:%S %z")
            except ValueError:
                continue
            if latest is None or timestamp > latest:
                latest = timestamp

    return latest


def reward_due(now: datetime | None = None, logs_dir: Path | None = None) -> bool:
    current = now or datetime.now(LOCAL_TIMEZONE)
    last_claim = last_reward_time(logs_dir)
    if last_claim is None:
        return True
    return current >= last_claim + REWARD_INTERVAL


def run_daily_visit(
    email: str,
    password: str,
    *,
    claim_reward: bool,
    run_quests: bool,
) -> tuple[str, str | None]:
    from astanahub_connector.github_login import run_daily_visit as browser_run_daily_visit

    return browser_run_daily_visit(
        email,
        password,
        claim_reward=claim_reward,
        run_quests=run_quests,
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    force_run = os.environ.get("FORCE_RUN", "").lower() == "true"
    reward_is_due = force_run or reward_due()

    if not reward_is_due:
        last_claim = last_reward_time()
        next_attempt = last_claim + REWARD_INTERVAL if last_claim else None
        if next_attempt:
            logging.info("24 часа после награды ещё не прошли. Следующая попытка не раньше %s", next_attempt.isoformat())
        return 0

    last_claim = last_reward_time()
    if reward_is_due and last_claim:
        logging.info("24 часа после награды прошли; запускаю авторизацию. Последняя награда: %s", last_claim.isoformat())
    elif reward_is_due:
        logging.info("Успешная награда в журнале не найдена; запускаю авторизацию")
    email = os.environ.get("ASTANAHUB_EMAIL", "").strip()
    password = os.environ.get("ASTANAHUB_PASSWORD", "")
    if not email or not password:
        logging.error("Добавьте GitHub Secrets ASTANAHUB_EMAIL и ASTANAHUB_PASSWORD")
        return 2

    try:
        reward_result, quest_result = run_daily_visit(
            email,
            password,
            claim_reward=True,
            run_quests=True,
        )
        write_monthly_log("успешно", reward_log_status(reward_result), quest_result)
        logging.info("Готово: %s; квесты: %s", reward_result, quest_result or "не запускались")
        return 0
    except Exception as exc:
        write_monthly_log("ошибка", "не проверена")
        logging.error("Ежедневный вход не выполнен: %s", exc)
        return 1


if __name__ == "__main__":
    if "--check-due" in sys.argv:
        print("due" if reward_due() else "not-due")
        raise SystemExit(0)
    raise SystemExit(main())
