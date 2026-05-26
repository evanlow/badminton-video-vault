"""Smoke tests: authentication — login, logout, protected route redirects."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._test_helpers import BaseTestCase  # noqa: E402 (env vars set inside)


class TestLoginPage(BaseTestCase):
    def test_login_page_loads(self):
        r = self.client.get("/login")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Log In", r.data)

    def test_login_already_authenticated_redirects_to_dashboard(self):
        self.login_as_owner()
        r = self.client.get("/login", follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Dashboard", r.data)


class TestLoginPost(BaseTestCase):
    def test_valid_credentials_redirect_to_dashboard(self):
        r = self.login("owner@test.com", "OwnerPass123!")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Dashboard", r.data)

    def test_wrong_password_stays_on_login_with_error(self):
        r = self.login("owner@test.com", "wrongpassword")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Invalid email or password", r.data)

    def test_unknown_email_stays_on_login_with_error(self):
        r = self.login("nobody@test.com", "anypassword")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Invalid email or password", r.data)

    def test_inactive_user_rejected(self):
        r = self.login("inactive@test.com", "InactivePass123!")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Invalid email or password", r.data)

    def test_admin_can_login(self):
        r = self.login_as_admin()
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Dashboard", r.data)


class TestLogout(BaseTestCase):
    def test_logout_redirects_to_login(self):
        self.login_as_owner()
        r = self.client.get("/logout", follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Log In", r.data)

    def test_logout_unauthenticated_redirects_to_login(self):
        r = self.client.get("/logout", follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Log In", r.data)


class TestProtectedRoutes(BaseTestCase):
    """All protected routes must redirect unauthenticated users to login."""

    def _assert_redirects_to_login(self, path):
        r = self.client.get(path, follow_redirects=True)
        self.assertEqual(r.status_code, 200, msg=f"GET {path} did not return 200")
        self.assertIn(b"Log In", r.data, msg=f"GET {path} did not redirect to login")

    def test_root_requires_login(self):
        self._assert_redirects_to_login("/")

    def test_dashboard_requires_login(self):
        self._assert_redirects_to_login("/dashboard")

    def test_videos_requires_login(self):
        self._assert_redirects_to_login("/videos")

    def test_upload_requires_login(self):
        self._assert_redirects_to_login("/upload")

    def test_video_detail_requires_login(self):
        self._assert_redirects_to_login(f"/videos/{self.private_video_id}")

    def test_admin_users_requires_login(self):
        self._assert_redirects_to_login("/admin/users")

    def test_root_redirects_to_dashboard_when_authenticated(self):
        self.login_as_owner()
        r = self.client.get("/", follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Dashboard", r.data)


if __name__ == "__main__":
    unittest.main()
