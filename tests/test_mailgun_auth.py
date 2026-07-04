"""Tests for password reset and magic login through Mailgun HTTP."""
import re
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from tests._test_helpers import BaseTestCase, app
from extensions import db
from models import AuthToken, User
from email_service import send_mailgun_email


def extract_token(mock_send, path_prefix):
    body = mock_send.call_args.args[2]
    match = re.search(rf"{re.escape(path_prefix)}/([A-Za-z0-9_-]+)", body)
    assert match, body
    return match.group(1)


class TestMailgunService(BaseTestCase):
    def test_send_uses_mailgun_http_endpoint(self):
        app.config.update({
            "MAIL_SUPPRESS_SEND": False,
            "MAILGUN_API_KEY": "mg-test",
            "MAILGUN_DOMAIN": "mg.example.com",
            "MAILGUN_API_BASE_URL": "https://api.mailgun.net",
            "MAIL_FROM": "Badminton Video Vault <noreply@example.com>",
            "MAILGUN_TIMEOUT_SECONDS": 7,
            "MAILGUN_TEST_MODE": True,
        })
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"message": "Queued. Thank you."}
        response.raise_for_status.return_value = None

        with patch("email_service.requests.post", return_value=response) as post:
            send_mailgun_email("owner@test.com", "Subject", "Plain text body", "<p>HTML body</p>", "password-reset")

        self.assertEqual(post.call_args.args[0], "https://api.mailgun.net/v3/mg.example.com/messages")
        self.assertEqual(post.call_args.kwargs["auth"], ("api", "mg-test"))
        self.assertEqual(post.call_args.kwargs["data"]["to"], "owner@test.com")
        self.assertEqual(post.call_args.kwargs["data"]["o:testmode"], "yes")

    def test_suppress_send_skips_http_call(self):
        app.config.update({"MAIL_SUPPRESS_SEND": True})
        with patch("email_service.requests.post") as post:
            result = send_mailgun_email("owner@test.com", "Subject", "Body")
        post.assert_not_called()
        self.assertTrue(result["suppressed"])


class TestForgotPasswordFlow(BaseTestCase):
    def test_login_page_has_recovery_links(self):
        r = self.client.get("/login")
        self.assertIn(b"Forgot your password?", r.data)
        self.assertIn(b"magic sign-in link", r.data)

    def test_known_active_user_gets_reset_token(self):
        with patch("app.send_mailgun_email") as send:
            r = self.client.post("/forgot-password", data={"email": "owner@test.com"}, follow_redirects=True)
        self.assertIn(b"If an active account exists", r.data)
        send.assert_called_once()
        self.assertEqual(AuthToken.query.filter_by(purpose=AuthToken.PURPOSE_RESET_PASSWORD).count(), 1)

    def test_unknown_and_inactive_users_do_not_send_reset_email(self):
        for email in ("nobody@test.com", "inactive@test.com"):
            db.session.query(AuthToken).delete()
            db.session.commit()
            with patch("app.send_mailgun_email") as send:
                r = self.client.post("/forgot-password", data={"email": email}, follow_redirects=True)
            self.assertIn(b"If an active account exists", r.data)
            send.assert_not_called()
            self.assertEqual(AuthToken.query.count(), 0)

    def test_reset_token_changes_password_once(self):
        with patch("app.send_mailgun_email") as send:
            self.client.post("/forgot-password", data={"email": "owner@test.com"}, follow_redirects=True)
        raw_token = extract_token(send, "/reset-password")

        r = self.client.post(
            f"/reset-password/{raw_token}",
            data={"password": "NewOwnerPass123!", "confirm_password": "NewOwnerPass123!"},
            follow_redirects=True,
        )
        self.assertIn(b"Your password has been reset", r.data)
        self.assertIn(b"Invalid email or password", self.login("owner@test.com", "OwnerPass123!").data)
        self.assertIn(b"Dashboard", self.login("owner@test.com", "NewOwnerPass123!").data)

    def test_reset_rejects_invalid_or_expired_token(self):
        r = self.client.get("/reset-password/not-real", follow_redirects=True)
        self.assertIn(b"invalid, expired, or has already been used", r.data)

        user = db.session.get(User, self.owner_id)
        raw_token, token = AuthToken.create_for_user(user, AuthToken.PURPOSE_RESET_PASSWORD, 30)
        token.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()
        r = self.client.get(f"/reset-password/{raw_token}", follow_redirects=True)
        self.assertIn(b"invalid, expired, or has already been used", r.data)


class TestMagicLoginFlow(BaseTestCase):
    def test_known_active_user_gets_magic_token(self):
        with patch("app.send_mailgun_email") as send:
            r = self.client.post("/magic-login", data={"email": "owner@test.com"}, follow_redirects=True)
        self.assertIn(b"If an active account exists", r.data)
        send.assert_called_once()
        self.assertEqual(AuthToken.query.filter_by(purpose=AuthToken.PURPOSE_MAGIC_LOGIN).count(), 1)

    def test_unknown_and_inactive_users_do_not_send_magic_email(self):
        for email in ("nobody@test.com", "inactive@test.com"):
            db.session.query(AuthToken).delete()
            db.session.commit()
            with patch("app.send_mailgun_email") as send:
                r = self.client.post("/magic-login", data={"email": email}, follow_redirects=True)
            self.assertIn(b"If an active account exists", r.data)
            send.assert_not_called()
            self.assertEqual(AuthToken.query.count(), 0)

    def test_magic_token_logs_in_once(self):
        with patch("app.send_mailgun_email") as send:
            self.client.post("/magic-login", data={"email": "owner@test.com"}, follow_redirects=True)
        raw_token = extract_token(send, "/magic-login")

        r = self.client.get(f"/magic-login/{raw_token}", follow_redirects=True)
        self.assertIn(b"Dashboard", r.data)

        self.client.get("/logout", follow_redirects=True)
        reused = self.client.get(f"/magic-login/{raw_token}", follow_redirects=True)
        self.assertIn(b"invalid, expired, or has already been used", reused.data)

    def test_magic_rejects_expired_token(self):
        user = db.session.get(User, self.owner_id)
        raw_token, token = AuthToken.create_for_user(user, AuthToken.PURPOSE_MAGIC_LOGIN, 15)
        token.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()
        r = self.client.get(f"/magic-login/{raw_token}", follow_redirects=True)
        self.assertIn(b"invalid, expired, or has already been used", r.data)


if __name__ == "__main__":
    unittest.main()
