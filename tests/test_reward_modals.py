import unittest
from unittest.mock import MagicMock

from astanahub_connector.github_login import _claim_reward, _dismiss_blocking_modals


class RewardModalTests(unittest.TestCase):
    def test_clicks_blocking_backdrop_before_reward(self) -> None:
        page = MagicMock()
        empty = MagicMock()
        empty.count.return_value = 0
        overlay = MagicMock()
        overlay.count.side_effect = [1, 0]
        overlay.first = overlay

        def locator(selector: str, **_: object) -> MagicMock:
            if "backdrop-blur-sm" in selector:
                return overlay
            return empty

        page.locator.side_effect = locator

        _dismiss_blocking_modals(page)

        overlay.click.assert_called_once_with(
            position={"x": 5, "y": 5}, timeout=3_000
        )
        page.keyboard.press.assert_not_called()

    def test_disappearing_button_after_reload_counts_as_claimed(self) -> None:
        page = MagicMock()
        empty = MagicMock()
        empty.count.return_value = 0
        reward = MagicMock()
        reward.first = reward
        reward.count.side_effect = [1, 1, 0]

        def locator(selector: str, **kwargs: object) -> MagicMock:
            if kwargs.get("has_text") == "Получить награду":
                return reward
            return empty

        page.locator.side_effect = locator

        self.assertEqual(_claim_reward(page), "ежедневная награда получена")
        reward.click.assert_called_once_with(timeout=10_000)
        page.goto.assert_called_once()


if __name__ == "__main__":
    unittest.main()
