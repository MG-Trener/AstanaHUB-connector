import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import main


class MainTests(unittest.TestCase):
    def test_missing_secrets_fails_without_browser(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(main.main(), 2)

    def test_runner_receives_secrets(self) -> None:
        with patch.dict(os.environ, {"ASTANAHUB_EMAIL": "user@example.com", "ASTANAHUB_PASSWORD": "secret"}, clear=True):
            with patch("main.run_daily_visit", return_value="ok") as run:
                with patch("main.write_monthly_log") as write_log:
                    self.assertEqual(main.main(), 0)
                    run.assert_called_once_with("user@example.com", "secret")
                    write_log.assert_called_once_with("успешно", "не доступна")

    def test_monthly_log_uses_a_new_file_for_each_month(self) -> None:
        zone = timezone(timedelta(hours=5))
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(main, "LOGS_DIR", Path(directory)):
                september = main.write_monthly_log("успешно", "получена", datetime(2026, 9, 30, 18, 40, tzinfo=zone))
                october = main.write_monthly_log("успешно", "не доступна", datetime(2026, 10, 1, 6, 40, tzinfo=zone))

            self.assertEqual(september.name, "2026-09.log")
            self.assertEqual(october.name, "2026-10.log")
            self.assertIn("Награда: получена", september.read_text(encoding="utf-8"))
            self.assertIn("Награда: не доступна", october.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
