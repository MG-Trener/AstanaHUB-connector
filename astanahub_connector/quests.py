from __future__ import annotations

import hashlib
import logging
from typing import Any

from playwright.sync_api import Page

COMMUNITY_URL = "https://astanahub.com/ru/community/"
LOGGER = logging.getLogger(__name__)
APPROVAL_COMMENTS = (
    "Отличный материал!",
    "Спасибо, было полезно!",
    "Интересный и полезный пост!",
    "Хорошая подача материала!",
    "Полезная публикация, спасибо!",
    "Отлично раскрытая тема!",
    "Спасибо за интересный пост!",
    "Ценный материал!",
    "Очень познавательно!",
    "Хороший и содержательный пост!",
    "Полезно, спасибо автору!",
    "Интересная публикация!",
    "Отличная работа!",
    "Спасибо за полезный материал!",
    "Тема раскрыта отлично!",
    "Было интересно прочитать!",
    "Содержательно и понятно!",
    "Хороший обзор темы!",
    "Отличный пост, спасибо!",
    "Полезные мысли!",
    "Действительно интересно!",
    "Спасибо за хорошую публикацию!",
    "Материал заслуживает внимания!",
    "Информативно и доступно!",
    "Очень полезный пост!",
    "Прекрасная подача!",
    "Спасибо за ценные мысли!",
    "Интересный взгляд на тему!",
    "Хорошо структурированный материал!",
    "Познавательная публикация!",
    "Отличное изложение!",
    "Спасибо, прочитал с интересом!",
    "Полезный и понятный материал!",
    "Заслуживает внимания, спасибо!",
    "Хорошая публикация!",
    "Интересно и содержательно!",
    "Спасибо за качественный пост!",
    "Отличный разбор!",
    "Полезная информация!",
    "Материал получился отличным!",
    "Спасибо за понятную подачу!",
    "Интересные наблюдения!",
    "Хорошо написано!",
    "Отличная публикация!",
    "Полезно и актуально!",
    "Спасибо за содержательный материал!",
    "Интересная тема!",
    "Очень хорошая подача!",
    "Материал действительно полезный!",
    "Спасибо, было интересно!",
    "Отличные мысли!",
    "Хороший материал для размышления!",
    "Полезный обзор!",
    "Написано понятно и интересно!",
    "Спасибо автору за публикацию!",
    "Сильный материал!",
    "Интересный разбор темы!",
    "Отлично и по делу!",
    "Полезная и ясная публикация!",
    "Спасибо за актуальный материал!",
    "Хорошая работа, спасибо!",
    "Содержательный пост!",
    "Отлично изложено!",
    "Интересно было ознакомиться!",
)


def _localized_text(value: Any) -> str:
    if isinstance(value, dict):
        for language in ("ru", "kk", "en"):
            text = str(value.get(language) or "").strip()
            if text:
                return text
        return ""
    return str(value or "").strip()


def quest_kind(quest: dict[str, Any]) -> str | None:
    title = quest.get("title") or {}
    text = " ".join(
        str(title.get(language, "")).lower() for language in ("ru", "en", "kk")
    )
    modules = {str(value).lower() for value in quest.get("module") or []}
    if "blog" not in modules:
        return None
    if ("прочит" in text and "пост" in text) or ("read" in text and "post" in text):
        return "read"
    if (
        ("лайк" in text and ("постав" in text or "лайкн" in text))
        or ("like" in text and "post" in text and "get likes" not in text)
    ):
        return "like"
    if (
        "прокоммент" in text
        or ("остав" in text and "коммент" in text)
        or "comment on" in text
        or ("leave" in text and "comment" in text)
    ):
        return "comment"
    return None


def approval_comment(blog_id: int, title: str = "") -> str:
    digest = hashlib.blake2b(
        f"{blog_id}:{title}".encode("utf-8"), digest_size=8
    ).digest()
    selector = int.from_bytes(digest, byteorder="big")
    return APPROVAL_COMMENTS[selector % len(APPROVAL_COMMENTS)]


def _api_get(page: Page, url: str) -> Any:
    return page.evaluate(
        """async (url) => {
            const response = await window.api.get(url);
            return response.data;
        }""",
        url,
    )


def _api_post(page: Page, url: str, data: dict[str, Any] | None = None) -> Any:
    return page.evaluate(
        """async ({url, data}) => {
            const response = await window.api.post(url, data || undefined);
            return response.data;
        }""",
        {"url": url, "data": data},
    )


def _active_quests(page: Page) -> list[dict[str, Any]]:
    data = _api_get(page, "/s/games/api/quests/")
    return list(data.get("active_quests") or [])


def _quest_progress(page: Page, quest_id: int) -> dict[str, Any] | None:
    return next((item for item in _active_quests(page) if item.get("id") == quest_id), None)


def _latest_blogs(page: Page) -> list[dict[str, Any]]:
    data = _api_get(
        page,
        "/community/api/blog/?page=1&page_size=20&feed=true&order_by=-publish_date",
    )
    return list(data.get("results") or [])


def _remaining(quest: dict[str, Any]) -> int:
    tasks = quest.get("tasks") or {}
    return max(0, int(tasks.get("total") or 0) - int(tasks.get("task_finished") or 0))


def _read_blog(page: Page, blog: dict[str, Any]) -> None:
    page.goto(str(blog["absolute_url"]), wait_until="domcontentloaded", timeout=120_000)
    page.locator("body").wait_for(state="visible", timeout=30_000)
    page.evaluate(
        """() => {
            window.scrollTo({top: document.documentElement.scrollHeight, behavior: 'instant'});
            window.dispatchEvent(new Event('scroll'));
        }"""
    )
    page.wait_for_timeout(21_000)


def _like_blog(page: Page, blog: dict[str, Any]) -> None:
    page.goto(str(blog["absolute_url"]), wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_function("window.api && typeof window.api.get === 'function'")
    _api_get(page, f"/api/blog/{int(blog['id'])}/reaction_up/")


def _already_commented(page: Page, blog_id: int, current_user_id: int) -> bool:
    data = _api_get(
        page,
        f"/api/comment/?primary_key={blog_id}&page=1&page_size=100&source=Blog&ordering=-created_at",
    )
    return any(
        int((comment.get("user") or {}).get("id") or 0) == current_user_id
        for comment in data.get("results") or []
    )


def _comment_blog(page: Page, blog: dict[str, Any], current_user_id: int) -> bool:
    page.goto(str(blog["absolute_url"]), wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_function("window.api && typeof window.api.post === 'function'")
    blog_id = int(blog["id"])
    if _already_commented(page, blog_id, current_user_id):
        return False

    title = _localized_text(blog.get("title"))
    if not blog.get("reacted_up"):
        _api_get(page, f"/api/blog/{blog_id}/reaction_up/")
        blog["reacted_up"] = True
        LOGGER.info("Поставлен лайк посту %s перед комментированием", blog_id)

    comment = approval_comment(blog_id, title)
    _api_post(
        page,
        "/api/comment/",
        {"message": comment, "primary_key": str(blog_id), "source": "Blog"},
    )
    LOGGER.info("Оставлен короткий комментарий к посту %s: %s", blog_id, title)
    return True


def _claim_if_completed(page: Page, quest_id: int) -> str:
    quest = _quest_progress(page, quest_id)
    if not quest:
        return "квест больше не активен"
    tasks = quest.get("tasks") or {}
    progress = f"{int(tasks.get('task_finished') or 0)}/{int(tasks.get('total') or 0)}"
    if quest.get("completed") and not quest.get("claimed"):
        _api_get(page, f"/s/games/api/quests/{quest_id}/claim/")
        return f"{progress}, награда квеста получена"
    if quest.get("claimed"):
        return f"{progress}, награда квеста уже получена"
    return f"{progress}, квест не завершён"


def run_active_community_quests(page: Page) -> str:
    page.goto(COMMUNITY_URL, wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_function("window.api && typeof window.api.get === 'function'")
    current_user_id = int(page.evaluate("window.currentUserId || 0"))
    quests = [quest for quest in _active_quests(page) if quest_kind(quest)]
    if not quests:
        return "подходящих дневных квестов нет"

    blogs = [
        blog
        for blog in _latest_blogs(page)
        if int((blog.get("author") or {}).get("id") or 0) != current_user_id
    ]
    summaries: list[str] = []

    for quest in quests:
        quest_id = int(quest["id"])
        kind = quest_kind(quest)
        title = _localized_text(quest.get("title")) or str(quest_id)
        current_quest = _quest_progress(page, quest_id) or quest
        needed = _remaining(current_quest)
        LOGGER.info("Активный квест: %s; осталось действий: %s", title, needed)

        try:
            if kind == "read":
                start_index = int((quest.get("tasks") or {}).get("task_finished") or 0)
                for blog in blogs[start_index:]:
                    if needed <= 0:
                        break
                    before = _quest_progress(page, quest_id) or quest
                    before_done = int((before.get("tasks") or {}).get("task_finished") or 0)
                    _read_blog(page, blog)
                    after = _quest_progress(page, quest_id) or before
                    after_done = int((after.get("tasks") or {}).get("task_finished") or 0)
                    if after_done == before_done:
                        _api_post(page, f"/community/api/blog/{int(blog['id'])}/read/")
                        after = _quest_progress(page, quest_id) or before
                        after_done = int((after.get("tasks") or {}).get("task_finished") or 0)
                    if after_done > before_done:
                        needed -= after_done - before_done

            elif kind == "like":
                for blog in blogs:
                    if needed <= 0:
                        break
                    if blog.get("reacted_up"):
                        continue
                    _like_blog(page, blog)
                    blog["reacted_up"] = True
                    needed -= 1

            elif kind == "comment":
                if not current_user_id:
                    summaries.append(f"{title}: не удалось определить пользователя")
                    continue
                attempted_comment = False
                for blog in blogs:
                    if needed <= 0:
                        break
                    if attempted_comment:
                        page.wait_for_timeout(10_000)
                    try:
                        posted = _comment_blog(page, blog, current_user_id)
                    except Exception as exc:
                        LOGGER.warning(
                            "Комментарий к посту %s отклонён (%s); пробую следующий пост",
                            blog.get("id"),
                            type(exc).__name__,
                        )
                        attempted_comment = True
                        continue
                    attempted_comment = True
                    if posted:
                        needed -= 1

            summaries.append(f"{title}: {_claim_if_completed(page, quest_id)}")
        except Exception as exc:
            LOGGER.exception("Не удалось завершить квест %s", title)
            summaries.append(f"{title}: ошибка {type(exc).__name__}")

    return "; ".join(summaries)
