import unittest
from unittest.mock import MagicMock, patch

from astanahub_connector.github_login import (
    AuthenticationError,
    OtpRequiredError,
    _api_request,
)


class AuthPayloadTests(unittest.TestCase):
    def test_token_uses_epoch_milliseconds_and_md5_decimal_string(self):
        page = MagicMock()
        page.evaluate.return_value = {"ok": True, "status": 200, "body": {"user_exists": True}}
        with patch("astanahub_connector.github_login.time.time_ns", return_value=1_000_999_999):
            result = _api_request(page, "/auth/check/", {"value": "test@example.invalid"})
        script, args = page.evaluate.call_args.args
        self.assertEqual(args["payloadToken"], "1000a9b7ba70783b617e9998dc4dd82eb3c5W")
        self.assertEqual(args["data"], {"value": "test@example.invalid"})
        self.assertEqual(result, {"user_exists": True})
        self.assertNotIn("md5(", script)
        self.assertIn("'hub-payload-token': payloadToken", script)
        self.assertIn("credentials: 'include'", script)

    def test_token_is_recomputed_for_each_request(self):
        page = MagicMock()
        page.evaluate.return_value = {"ok": True, "status": 200, "body": {}}
        with patch("astanahub_connector.github_login.time.time_ns", side_effect=[1_000_000_000, 1_001_000_000]):
            _api_request(page, "/auth/check/", {})
            _api_request(page, "/auth/email/", {})
        first, second = [call.args[1] for call in page.evaluate.call_args_list]
        self.assertNotEqual(first["payloadToken"], second["payloadToken"])
        self.assertTrue(second["payloadToken"].startswith("1001"))

    def test_otp_response_is_preserved(self):
        page = MagicMock()
        page.evaluate.return_value = {"ok": False, "status": 403, "body": {"code": "otp_required"}}
        with self.assertRaises(OtpRequiredError):
            _api_request(page, "/auth/email/", {})

    def test_authentication_rejection_is_preserved(self):
        for status in (401, 403):
            with self.subTest(status=status):
                page = MagicMock()
                page.evaluate.return_value = {"ok": False, "status": status, "body": {}}
                with self.assertRaises(AuthenticationError):
                    _api_request(page, "/auth/email/", {})

    def test_rate_limit_response_is_preserved(self):
        for status in (423, 429):
            with self.subTest(status=status):
                page = MagicMock()
                page.evaluate.return_value = {"ok": False, "status": status, "body": {}}
                with self.assertRaisesRegex(AuthenticationError, "ограничил"):
                    _api_request(page, "/auth/email/", {})

    def test_other_failure_is_preserved(self):
        page = MagicMock()
        page.evaluate.return_value = {"ok": False, "status": 500, "body": {}}
        with self.assertRaisesRegex(AuthenticationError, "HTTP 500"):
            _api_request(page, "/auth/check/", {})
