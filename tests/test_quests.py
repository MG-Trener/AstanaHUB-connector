import unittest
from unittest.mock import MagicMock, patch

from astanahub_connector.quests import (
    APPROVAL_COMMENTS,
    _localized_text,
    approval_comment,
    _comment_blog,
    quest_kind,
)


class QuestTests(unittest.TestCase):
    def test_classifies_supported_daily_quests(self) -> None:
        self.assertEqual(
            quest_kind({"title": {"ru": "Прочитайте 3 поста"}, "module": ["blog"]}),
            "read",
        )
        self.assertEqual(
            quest_kind({"title": {"ru": "Поставьте 3 лайка постам"}, "module": ["blog"]}),
            "like",
        )
        self.assertEqual(
            quest_kind({"title": {"ru": "Прокомментируйте 3 поста"}, "module": ["blog"]}),
            "comment",
        )

    def test_extracts_localized_and_plain_text(self) -> None:
        self.assertEqual(_localized_text({"ru": "Заголовок", "en": "Title"}), "Заголовок")
        self.assertEqual(_localized_text("Заголовок"), "Заголовок")

    def test_ignores_unrelated_quests(self) -> None:
        self.assertIsNone(
            quest_kind({"title": {"ru": "Подайтесь на вакансию"}, "module": ["vacancy"]})
        )
        self.assertIsNone(
            quest_kind(
                {"title": {"ru": "Получите 3 лайка на комментарии"}, "module": ["blog"]}
            )
        )

    def test_has_many_unique_short_approval_comments(self) -> None:
        self.assertGreaterEqual(len(APPROVAL_COMMENTS), 50)
        self.assertLessEqual(len(APPROVAL_COMMENTS), 100)
        self.assertEqual(len(APPROVAL_COMMENTS), len(set(APPROVAL_COMMENTS)))
        self.assertTrue(all(len(comment) <= 80 for comment in APPROVAL_COMMENTS))

    def test_approval_comment_is_stable_and_varies_between_posts(self) -> None:
        self.assertEqual(
            approval_comment(151901, "Маркетинг"),
            approval_comment(151901, "Маркетинг"),
        )
        selected = {approval_comment(blog_id, f"Пост {blog_id}") for blog_id in range(50)}
        self.assertGreaterEqual(len(selected), 30)

    def test_comment_quest_likes_post_before_posting_short_message(self) -> None:
        page = MagicMock()
        blog = {
            "id": 151901,
            "absolute_url": "https://astanahub.com/ru/community/example/",
            "title": {"ru": "Полезный пост"},
            "reacted_up": False,
        }
        with patch(
            "astanahub_connector.quests._already_commented", return_value=False
        ):
            with patch("astanahub_connector.quests._api_get") as api_get:
                with patch("astanahub_connector.quests._api_post") as api_post:
                    self.assertTrue(_comment_blog(page, blog, current_user_id=42))

        api_get.assert_called_once_with(page, "/api/blog/151901/reaction_up/")
        self.assertTrue(blog["reacted_up"])
        payload = api_post.call_args.args[2]
        self.assertIn(payload["message"], APPROVAL_COMMENTS)
        self.assertEqual(payload["primary_key"], "151901")


if __name__ == "__main__":
    unittest.main()
