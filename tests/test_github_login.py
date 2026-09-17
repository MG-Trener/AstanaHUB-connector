import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import main


class MainTests(unittest.TestCase):
    def test_missing_secrets_fails_without_browser_when_due(self) -> None:
        with patch("main.reward_due", return_value=True):
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(main.main(), 2)

    def test_runner_receives_secrets_when_due(self) -> None:
        with patch("main.reward_due", return_value=True):
            with patch.dict(os.environ, {"ASTANAHUB_EMAIL": "user@example.com", "ASTANAHUB_PASSWORD": "secret"}, clear=True):
                with patch("main.run_daily_visit", return_value="ok") as run:
                    with patch("main.write_monthly_log") as write_log:
                        self.assertEqual(main.main(), 0)
                        run.assert_called_once_with("user@example.com", "secret")
                        write_log.assert_called_once_with("успешно", "не доступна")

    def test_runner_is_skipped_before_24_hours(self) -> None:
        with patch("main.reward_due", return_value=False):
            with patch("main.last_reward_time", return_value=datetime(2026, 9, 16, 11, 43, tzinfo=main.LOCAL_TIMEZONE)):
                with patch("main.run_daily_visit") as run:
                    self.assertEqual(main.main(), 0)
                    run.assert_not_called()

    def test_reward_due_exactly_24_hours_after_last_claim(self) -> None:
        zone = timezone(timedelta(hours=5))
        claim_time = datetime(2026, 9, 16, 11, 43, 31, tzinfo=zone)
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "2026-09.log"
            log_path.write_text(
                "2026-09-16 11:43:31 +0500 | Авторизация: успешно | Награда: получена\n",
                encoding="utf-8",
            )
            self.assertFalse(main.reward_due(claim_time + timedelta(hours=23, minutes=59), Path(directory)))
            self.assertTrue(main.reward_due(claim_time + timedelta(hours=24), Path(directory)))

    def test_unavailable_reward_does_not_reset_24_hour_clock(self) -> None:
        zone = timezone(timedelta(hours=5))
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "2026-09.log"
            log_path.write_text(
                "2026-09-16 11:43:31 +0500 | Авторизация: успешно | Награда: получена\n"
                "2026-09-17 11:44:10 +0500 | Авторизация: успешно | Награда: не доступна\n",
                encoding="utf-8",
            )
            self.assertTrue(
                main.reward_due(
                    datetime(2026, 9, 17, 11, 49, tzinfo=zone),
                    Path(directory),
                )
            )

    def test_no_successful_claim_means_due(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(main.reward_due(logs_dir=Path(directory)))

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
