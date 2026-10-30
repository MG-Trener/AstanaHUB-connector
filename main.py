from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOGS_DIR = Path("logs")
LOCAL_TIMEZONE = timezone(timedelta(hours=5), name="UTC+5")
REWARD_INTERVAL = timedelta(hours=24)
DEFAULT_VISIT_ATTEMPTS = 6
DEFAULT_RETRY_DELAY_SECONDS = 300


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


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def _retry_stays_in_day(now: datetime, delay_seconds: int) -> bool:
    retry_time = now + timedelta(seconds=delay_seconds)
    return retry_time.date() == now.date()


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

    max_attempts = _positive_int_env("VISIT_MAX_ATTEMPTS", DEFAULT_VISIT_ATTEMPTS)
    retry_delay = _positive_int_env(
        "VISIT_RETRY_DELAY_SECONDS", DEFAULT_RETRY_DELAY_SECONDS
    )
    final_error: Exception | None = None
    last_reward_result = "награда уже получена или недоступна"
    last_quest_result: str | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            last_reward_result, last_quest_result = run_daily_visit(
                email,
                password,
                claim_reward=True,
                run_quests=True,
            )
            final_error = None
            if last_reward_result == "ежедневная награда получена":
                write_monthly_log(
                    "успешно",
                    reward_log_status(last_reward_result),
                    last_quest_result,
                )
                logging.info(
                    "Готово: %s; квесты: %s",
                    last_reward_result,
                    last_quest_result or "не запускались",
                )
                return 0
        except Exception as exc:
            final_error = exc
            logging.warning(
                "Попытка авторизации и получения награды %s/%s не удалась: %s",
                attempt,
                max_attempts,
                exc,
            )
            if getattr(exc, "retryable", True) is False:
                logging.error("Ошибка не исправится повтором в этом запуске")
                break

        now = datetime.now(LOCAL_TIMEZONE)
        if attempt >= max_attempts or not _retry_stays_in_day(now, retry_delay):
            break
        logging.info(
            "Повторная полная попытка через %s секунд; текущий день UTC+5 ещё не завершён",
            retry_delay,
        )
        time.sleep(retry_delay)

    if final_error is not None:
        write_monthly_log("ошибка", "не проверена", last_quest_result)
        logging.error("Все попытки ежедневного входа исчерпаны: %s", final_error)
        return 1

    write_monthly_log(
        "успешно",
        reward_log_status(last_reward_result),
        last_quest_result,
    )
    logging.warning(
        "Награда не стала доступна после %s попыток в пределах текущего дня",
        max_attempts,
    )
    return 0


if __name__ == "__main__":
    if "--check-due" in sys.argv:
        print("due" if reward_due() else "not-due")
        raise SystemExit(0)
    raise SystemExit(main())
