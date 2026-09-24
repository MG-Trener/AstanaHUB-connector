import unittest

from astanahub_connector.quests import build_comment, quest_kind


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
            quest_kind({"title": {"ru": "Прокомментируйте пост"}, "module": ["blog"]}),
            "comment",
        )

    def test_ignores_unrelated_quests(self) -> None:
        self.assertIsNone(
            quest_kind({"title": {"ru": "Подайтесь на вакансию"}, "module": ["vacancy"]})
        )
        self.assertIsNone(
            quest_kind(
                {"title": {"ru": "Получите 3 лайка на комментарии"}, "module": ["blog"]}
            )
        )

    def test_builds_two_sentence_comment_from_post(self) -> None:
        comment = build_comment(
            "Автоматизация бизнес-процессов",
            [
                "Автор показывает, как автоматизация сокращает ручную работу и помогает команде быстрее обрабатывать документы."
            ],
        )
        self.assertIsNotNone(comment)
        self.assertIn("Автоматизация бизнес-процессов", comment)
        self.assertLessEqual(comment.count(".") + comment.count("!"), 2)

    def test_skips_comment_when_post_has_no_substantive_text(self) -> None:
        self.assertIsNone(build_comment("Короткий пост", ["Фото", "Спасибо"]))


if __name__ == "__main__":
    unittest.main()
