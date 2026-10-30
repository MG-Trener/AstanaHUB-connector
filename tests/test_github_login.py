import hashlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import main
from astanahub_connector import github_login


class MainTests(unittest.TestCase):
    def test_missing_secrets_fails_without_browser_when_due(self) -> None:
        with patch("main.reward_due", return_value=True):
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(main.main(), 2)

    def test_runner_receives_secrets_when_due(self) -> None:
        with patch("main.reward_due", return_value=True):
            with patch.dict(os.environ, {"ASTANAHUB_EMAIL": "user@example.com", "ASTANAHUB_PASSWORD": "secret"}, clear=True):
                with patch(
                    "main.run_daily_visit",
                    return_value=("ежедневная награда получена", "Прочитайте 3 поста: 3/3"),
                ) as run:
                    with patch("main.write_monthly_log") as write_log:
                        self.assertEqual(main.main(), 0)
                        run.assert_called_once_with(
                            "user@example.com",
                            "secret",
                            claim_reward=True,
                            run_quests=True,
                        )
                        write_log.assert_called_once_with(
                            "успешно",
                            "получена",
                            "Прочитайте 3 поста: 3/3",
                        )

    def test_runner_is_skipped_before_24_hours(self) -> None:
        with patch("main.reward_due", return_value=False):
            with patch("main.last_reward_time", return_value=datetime(2026, 9, 16, 11, 43, tzinfo=main.LOCAL_TIMEZONE)):
                with patch("main.run_daily_visit") as run:
                    self.assertEqual(main.main(), 0)
                    run.assert_not_called()

    def test_transient_browser_failure_retries_full_visit(self) -> None:
        environment = {
            "ASTANAHUB_EMAIL": "user@example.com",
            "ASTANAHUB_PASSWORD": "secret",
            "VISIT_MAX_ATTEMPTS": "2",
            "VISIT_RETRY_DELAY_SECONDS": "1",
        }
        with patch("main.reward_due", return_value=True):
            with patch.dict(os.environ, environment, clear=True):
                with patch(
                    "main.run_daily_visit",
                    side_effect=[
                        RuntimeError("modal blocked click"),
                        ("ежедневная награда получена", "квестов нет"),
                    ],
                ) as run:
                    with patch("main.time.sleep") as sleep:
                        with patch("main.write_monthly_log") as write_log:
                            self.assertEqual(main.main(), 0)

        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once_with(1)
        write_log.assert_called_once_with("успешно", "получена", "квестов нет")

    def test_non_retryable_access_block_stops_immediately(self) -> None:
        environment = {
            "ASTANAHUB_EMAIL": "user@example.com",
            "ASTANAHUB_PASSWORD": "secret",
            "VISIT_MAX_ATTEMPTS": "6",
            "VISIT_RETRY_DELAY_SECONDS": "300",
        }
        error = github_login.AccessBlockedError("Cloudflare blocked runner")
        with patch("main.reward_due", return_value=True):
            with patch.dict(os.environ, environment, clear=True):
                with patch("main.run_daily_visit", side_effect=error) as run:
                    with patch("main.time.sleep") as sleep:
                        with patch("main.write_monthly_log") as write_log:
                            self.assertEqual(main.main(), 1)

        run.assert_called_once()
        sleep.assert_not_called()
        write_log.assert_called_once_with("ошибка", "не проверена", None)

    def test_unavailable_reward_is_retried_inside_same_run(self) -> None:
        environment = {
            "ASTANAHUB_EMAIL": "user@example.com",
            "ASTANAHUB_PASSWORD": "secret",
            "VISIT_MAX_ATTEMPTS": "2",
            "VISIT_RETRY_DELAY_SECONDS": "1",
        }
        with patch("main.reward_due", return_value=True):
            with patch.dict(os.environ, environment, clear=True):
                with patch(
                    "main.run_daily_visit",
                    return_value=("награда уже получена или недоступна", None),
                ) as run:
                    with patch("main.time.sleep") as sleep:
                        with patch("main.write_monthly_log") as write_log:
                            self.assertEqual(main.main(), 0)

        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once_with(1)
        write_log.assert_called_once_with("успешно", "не доступна", None)

    def test_retry_does_not_cross_local_midnight(self) -> None:
        zone = timezone(timedelta(hours=5))
        self.assertTrue(
            main._retry_stays_in_day(
                datetime(2026, 10, 4, 23, 50, tzinfo=zone),
                300,
            )
        )
        self.assertFalse(
            main._retry_stays_in_day(
                datetime(2026, 10, 4, 23, 58, tzinfo=zone),
                300,
            )
        )

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


class LoginProtocolTests(unittest.TestCase):
    def test_payload_token_does_not_depend_on_page_md5(self) -> None:
        timestamp = 1_700_000_000_123
        expected_digest = hashlib.md5(
            str(timestamp).encode("ascii"), usedforsecurity=False
        ).hexdigest()
        self.assertEqual(
            github_login._payload_token(timestamp),
            f"{timestamp}{expected_digest}W",
        )

    def test_api_request_passes_precomputed_payload_token(self) -> None:
        page = MagicMock()
        page.evaluate.return_value = {"ok": True, "status": 200, "body": {"ok": True}}
        with patch(
            "astanahub_connector.github_login._payload_token",
            return_value="precomputed-token",
        ):
            result = github_login._api_request(page, "/auth/check/", {"value": "x"})

        script, arguments = page.evaluate.call_args.args
        self.assertNotIn("md5(", script)
        self.assertEqual(arguments["payloadToken"], "precomputed-token")
        self.assertEqual(result, {"ok": True})

    def test_cloudflare_block_page_is_detected(self) -> None:
        page = MagicMock()
        page.title.return_value = "Attention Required! | Cloudflare"
        page.locator.return_value.inner_text.return_value = (
            "Sorry, you have been blocked. Cloudflare Ray ID: test"
        )

        with self.assertRaisesRegex(
            github_login.AccessBlockedError,
            "Ray ID test",
        ):
            github_login._raise_if_access_blocked(page, 403)

    def test_monthly_log_uses_a_new_file_for_each_month(self) -> None:
        zone = timezone(timedelta(hours=5))
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(main, "LOGS_DIR", Path(directory)):
                september = main.write_monthly_log(
                    "успешно",
                    "получена",
                    "Прочитайте 3 поста: 3/3",
                    now=datetime(2026, 9, 30, 18, 40, tzinfo=zone),
                )
                october = main.write_monthly_log(
                    "успешно",
                    "не доступна",
                    now=datetime(2026, 10, 1, 6, 40, tzinfo=zone),
                )

            self.assertEqual(september.name, "2026-09.log")
            self.assertEqual(october.name, "2026-10.log")
            self.assertIn("Награда: получена", september.read_text(encoding="utf-8"))
            self.assertIn("Квесты: Прочитайте 3 поста: 3/3", september.read_text(encoding="utf-8"))
            self.assertIn("Награда: не доступна", october.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
