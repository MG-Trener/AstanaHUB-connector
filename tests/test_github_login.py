import os
import unittest
from unittest.mock import patch

import main


class MainTests(unittest.TestCase):
    def test_missing_secrets_fails_without_browser(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(main.main(), 2)

    def test_runner_receives_secrets(self) -> None:
        with patch.dict(os.environ, {"ASTANAHUB_EMAIL": "user@example.com", "ASTANAHUB_PASSWORD": "secret"}, clear=True):
            with patch("main.run_daily_visit", return_value="ok") as run:
                self.assertEqual(main.main(), 0)
                run.assert_called_once_with("user@example.com", "secret")


if __name__ == "__main__":
    unittest.main()

