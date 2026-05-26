"""Smoke tests: public share links — /share/<token>."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._test_helpers import BaseTestCase  # noqa: E402


class TestShareLink(BaseTestCase):
    def test_valid_share_link_accessible_without_login(self):
        """Unauthenticated users can view a valid share link."""
        with self.mock_s3():
            r = self.client.get(f"/share/{self.share_token}")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"shared.mp4", r.data)

    def test_valid_share_link_accessible_when_logged_in(self):
        """Logged-in users can also access share links."""
        self.login_as_owner()
        with self.mock_s3():
            r = self.client.get(f"/share/{self.share_token}")
        self.assertEqual(r.status_code, 200)

    def test_valid_share_link_accessible_to_unrelated_user(self):
        """Another authenticated user can view a share link."""
        self.login_as_other()
        with self.mock_s3():
            r = self.client.get(f"/share/{self.share_token}")
        self.assertEqual(r.status_code, 200)

    def test_expired_share_link_returns_410(self):
        r = self.client.get(f"/share/{self.expired_token}")
        self.assertEqual(r.status_code, 410)

    def test_invalid_token_returns_404(self):
        r = self.client.get("/share/completely-invalid-token-xyz-000")
        self.assertEqual(r.status_code, 404)

    def test_share_page_does_not_show_edit_controls(self):
        """Edit form and delete button must be hidden on share view."""
        with self.mock_s3():
            r = self.client.get(f"/share/{self.share_token}")
        self.assertNotIn(b"Save Changes", r.data)
        self.assertNotIn(b"Delete Video", r.data)

    def test_share_page_does_not_show_navbar(self):
        """The main navbar is hidden on share view (shared_view=True)."""
        with self.mock_s3():
            r = self.client.get(f"/share/{self.share_token}")
        # Navbar is wrapped in {% if not shared_view %} in base.html
        self.assertNotIn(b"navbar-brand", r.data)


if __name__ == "__main__":
    unittest.main()
