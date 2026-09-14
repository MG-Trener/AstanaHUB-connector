from __future__ import annotations

import logging
from typing import Any

from playwright.sync_api import Page, sync_playwright

LOGIN_URL = "https://astanahub.com/ru/s/auth/login/"
ACCOUNT_URL = "https://astanahub.com/account/v2/main/"
API_BASE = "/s/auth/api/v1"
LOGGER = logging.getLogger(__name__)


class AuthenticationError(RuntimeError):
    pass


class OtpRequiredError(AuthenticationError):
    pass


def _api_request(page: Page, path: str, data: dict[str, Any]) -> dict[str, Any]:
    result = page.evaluate(
        """async ({path, data}) => {
            const timestamp = Date.now();
            const response = await fetch('/s/auth/api/v1' + path, {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                    'hub-payload-token': `${timestamp}${md5(timestamp)}W`
                },
                body: JSON.stringify(data)
            });
            let body = {};
            try { body = await response.json(); } catch (_) {}
            return {ok: response.ok, status: response.status, body};
        }""",
        {"path": path, "data": data},
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
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=120_000)
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


def _claim_reward(page: Page) -> str:
    welcome_close = page.locator("button[x-show='isBanner']:visible")
    if welcome_close.count():
        welcome_close.first.click()

    reward = page.locator("button:visible", has_text="Получить награду").first
    if not reward.count():
        return "награда уже получена или недоступна"

    reward.click()
    page.wait_for_timeout(3000)
    if page.locator("button:visible", has_text="Получить награду").count():
        raise RuntimeError("Astana Hub оставил кнопку награды после нажатия")
    return "ежедневная награда получена"


def run_daily_visit(email: str, password: str) -> str:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(locale="ru-RU", timezone_id="Asia/Qyzylorda")
        try:
            page = context.new_page()
            _login(page, email, password)
            return _claim_reward(page)
        finally:
            context.close()
            browser.close()

