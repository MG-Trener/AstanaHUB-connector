from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Any

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from astanahub_connector.quests import run_active_community_quests

LOGIN_URL = "https://astanahub.com/ru/s/auth/login/"
ACCOUNT_URL = "https://astanahub.com/account/v2/main/"
API_BASE = "/s/auth/api/v1"
LOGGER = logging.getLogger(__name__)
REWARD_CLICK_ATTEMPTS = 3


class AuthenticationError(RuntimeError):
    pass


class NonRetryableVisitError(RuntimeError):
    retryable = False


class AccessBlockedError(NonRetryableVisitError):
    pass


class OtpRequiredError(AuthenticationError, NonRetryableVisitError):
    pass


def _payload_token(timestamp_ms: int | None = None) -> str:
    timestamp = timestamp_ms if timestamp_ms is not None else time.time_ns() // 1_000_000
    digest = hashlib.md5(str(timestamp).encode("ascii"), usedforsecurity=False).hexdigest()
    return f"{timestamp}{digest}W"


def _raise_if_access_blocked(page: Page, status: int | None) -> None:
    title = page.title()
    body_text = page.locator("body").inner_text(timeout=5_000)
    block_markers = (
        "sorry, you have been blocked",
        "attention required",
        "cloudflare ray id",
        "unable to access astanahub.com",
    )
    page_text = f"{title}\n{body_text}".lower()
    if status in (403, 429) or any(marker in page_text for marker in block_markers):
        status_text = f"HTTP {status}" if status is not None else "без HTTP-статуса"
        ray_match = re.search(r"Cloudflare Ray ID:\s*([a-z0-9]+)", body_text, re.I)
        ray_text = f", Ray ID {ray_match.group(1)}" if ray_match else ""
        raise AccessBlockedError(
            "Cloudflare заблокировал адрес запуска при доступе к Astana Hub "
            f"({status_text}{ray_text}); требуется разрешённый адрес запуска"
        )


def _api_request(page: Page, path: str, data: dict[str, Any]) -> dict[str, Any]:
    result = page.evaluate(
        """async ({path, data, payloadToken}) => {
            const response = await fetch('/s/auth/api/v1' + path, {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                    'hub-payload-token': payloadToken
                },
                body: JSON.stringify(data)
            });
            let body = {};
            try { body = await response.json(); } catch (_) {}
            return {ok: response.ok, status: response.status, body};
        }""",
        {"path": path, "data": data, "payloadToken": _payload_token()},
    )
    if not result["ok"]:
        codes = result["body"].get("code", []) if isinstance(result["body"], dict) else []
        if isinstance(codes, str):
            codes = [codes]
        if "otp_required" in codes:
            raise OtpRequiredError("Astana Hub требует одноразовый код; автономный вход по паролю недоступен")
        if result["status"] in (401, 403):
            raise AuthenticationError("Astana Hub отклонил email или пароль")
        if result["status"] in (423, 429):
            raise AuthenticationError("Astana Hub временно ограничил попытки входа")
        raise AuthenticationError(f"Ошибка API Astana Hub: HTTP {result['status']}")
    return result["body"]


def _login(page: Page, email: str, password: str) -> None:
    response = page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=120_000)
    _raise_if_access_blocked(page, response.status if response else None)
    check = _api_request(page, "/auth/check/", {"value": email})
    if not check.get("user_exists"):
        raise AuthenticationError("Аккаунт с указанным email не найден")
    if check.get("method") != "email":
        raise AuthenticationError("Для этого аккаунта Astana Hub выбрал вход не по email")
    if check.get("login_method") == "otp":
        raise OtpRequiredError("Для этого email включён вход по одноразовому коду")

    _api_request(page, "/auth/email/", {"email": email, "password": password})
    page.goto(ACCOUNT_URL, wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(2000)
    if "/auth/login" in page.url:
        raise AuthenticationError("После ввода пароля Astana Hub вернул страницу входа")
    LOGGER.info("Вход по email выполнен")


def _dismiss_blocking_modals(page: Page) -> None:
    close_selectors = (
        "button[x-show='isBanner']:visible",
        "button[aria-label='Close']:visible",
        "button[aria-label='Закрыть']:visible",
        "button:visible:text-is('Закрыть')",
        "button:visible:text-is('Пропустить')",
        "button:visible:text-is('Не сейчас')",
        "button:visible:text-is('Позже')",
        "button:visible:text-is('×')",
    )
    for selector in close_selectors:
        locator = page.locator(selector)
        for index in range(min(locator.count(), 3)):
            try:
                locator.nth(index).click(timeout=3_000)
                page.wait_for_timeout(300)
            except PlaywrightTimeoutError:
                continue

    overlays = page.locator(
        "div.absolute.inset-0.bg-black.bg-opacity-50.backdrop-blur-sm:visible"
    )
    for _ in range(min(overlays.count(), 5)):
        overlay = overlays.first
        try:
            overlay.click(position={"x": 5, "y": 5}, timeout=3_000)
            page.wait_for_timeout(500)
        except PlaywrightTimeoutError:
            break

    if overlays.count():
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)


def _claim_reward(page: Page) -> str:
    last_error: Exception | None = None
    clicked_once = False
    for attempt in range(1, REWARD_CLICK_ATTEMPTS + 1):
        _dismiss_blocking_modals(page)

        reward = page.locator("button:visible", has_text="Получить награду").first
        if not reward.count():
            return (
                "ежедневная награда получена"
                if clicked_once
                else "награда уже получена или недоступна"
            )

        try:
            reward.click(timeout=10_000)
        except PlaywrightTimeoutError as exc:
            last_error = exc
            LOGGER.warning(
                "Кнопку награды перекрывает интерфейс сайта; попытка %s/%s",
                attempt,
                REWARD_CLICK_ATTEMPTS,
            )
        else:
            clicked_once = True
            page.wait_for_timeout(3_000)
            if not page.locator("button:visible", has_text="Получить награду").count():
                return "ежедневная награда получена"
            last_error = RuntimeError("Astana Hub оставил кнопку награды после нажатия")

        if attempt < REWARD_CLICK_ATTEMPTS:
            page.goto(ACCOUNT_URL, wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_timeout(2_000)

    raise RuntimeError(
        f"Не удалось нажать кнопку награды после {REWARD_CLICK_ATTEMPTS} попыток"
    ) from last_error


def run_daily_visit(
    email: str,
    password: str,
    *,
    claim_reward: bool = True,
    run_quests: bool = True,
) -> tuple[str, str | None]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(locale="ru-RU", timezone_id="Asia/Qyzylorda")
        try:
            page = context.new_page()
            _login(page, email, password)
            reward = (
                _claim_reward(page)
                if claim_reward
                else "ежедневная награда не проверялась"
            )
            quests = None
            if run_quests:
                try:
                    quests = run_active_community_quests(page)
                except Exception as exc:
                    LOGGER.exception("Проверка квестов завершилась ошибкой")
                    quests = f"ошибка {type(exc).__name__}"
            return reward, quests
        finally:
            context.close()
            browser.close()
