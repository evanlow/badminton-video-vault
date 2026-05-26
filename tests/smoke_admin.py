"""Smoke tests: admin panel — user management, create user, toggle active."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._test_helpers import BaseTestCase  # noqa: E402
from extensions import db  # noqa: E402
from models import User  # noqa: E402


class TestAdminUsersPage(BaseTestCase):
    def test_admin_users_page_requires_login(self):
        r = self.client.get("/admin/users", follow_redirects=True)
        self.assertIn(b"Log In", r.data)

    def test_regular_user_gets_403(self):
        self.login_as_other()
        r = self.client.get("/admin/users")
        self.assertEqual(r.status_code, 403)

    def test_owner_user_gets_403(self):
        self.login_as_owner()
        r = self.client.get("/admin/users")
        self.assertEqual(r.status_code, 403)

    def test_admin_can_access_users_page(self):
        self.login_as_admin()
        r = self.client.get("/admin/users")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Manage Users", r.data)

    def test_admin_users_page_lists_all_users(self):
        self.login_as_admin()
        r = self.client.get("/admin/users")
        self.assertIn(b"owner@test.com", r.data)
        self.assertIn(b"other@test.com", r.data)
        self.assertIn(b"inactive@test.com", r.data)


class TestAdminCreateUser(BaseTestCase):
    def test_create_user_page_requires_admin(self):
        self.login_as_other()
        r = self.client.get("/admin/users/create")
        self.assertEqual(r.status_code, 403)

    def test_create_user_page_loads_for_admin(self):
        self.login_as_admin()
        r = self.client.get("/admin/users/create")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Create User", r.data)

    def test_create_user_success(self):
        self.login_as_admin()
        r = self.client.post(
            "/admin/users/create",
            data={
                "name": "New Player",
                "email": "newplayer@test.com",
                "password": "NewPass123!",
                "confirm_password": "NewPass123!",
                "role": "user",
            },
            follow_redirects=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"created successfully", r.data)
        db.session.expire_all()
        user = User.query.filter_by(email="newplayer@test.com").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.name, "New Player")
        self.assertEqual(user.role, "user")
        self.assertTrue(user.is_active)

    def test_create_admin_user_success(self):
        self.login_as_admin()
        r = self.client.post(
            "/admin/users/create",
            data={
                "name": "Second Admin",
                "email": "admin2@test.com",
                "password": "AdminPass123!",
                "confirm_password": "AdminPass123!",
                "role": "admin",
            },
            follow_redirects=True,
        )
        self.assertEqual(r.status_code, 200)
        db.session.expire_all()
        user = User.query.filter_by(email="admin2@test.com").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.role, "admin")

    def test_create_user_duplicate_email_rejected(self):
        self.login_as_admin()
        before_count = User.query.count()
        r = self.client.post(
            "/admin/users/create",
            data={
                "name": "Duplicate",
                "email": "owner@test.com",  # already exists
                "password": "NewPass123!",
                "confirm_password": "NewPass123!",
                "role": "user",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"already exists", r.data)
        db.session.expire_all()
        self.assertEqual(User.query.count(), before_count)

    def test_create_user_password_mismatch_rejected(self):
        self.login_as_admin()
        r = self.client.post(
            "/admin/users/create",
            data={
                "name": "Mismatch",
                "email": "mismatch@test.com",
                "password": "Pass123!",
                "confirm_password": "Different123!",
                "role": "user",
            },
        )
        self.assertEqual(r.status_code, 200)
        db.session.expire_all()
        self.assertIsNone(User.query.filter_by(email="mismatch@test.com").first())

    def test_create_user_short_password_rejected(self):
        self.login_as_admin()
        r = self.client.post(
            "/admin/users/create",
            data={
                "name": "Short Pass",
                "email": "shortpass@test.com",
                "password": "abc",
                "confirm_password": "abc",
                "role": "user",
            },
        )
        self.assertEqual(r.status_code, 200)
        db.session.expire_all()
        self.assertIsNone(User.query.filter_by(email="shortpass@test.com").first())


class TestAdminToggleUser(BaseTestCase):
    def test_toggle_active_user_deactivates_them(self):
        self.login_as_admin()
        r = self.client.post(
            f"/admin/users/{self.other_id}/toggle",
            follow_redirects=True,
        )
        self.assertEqual(r.status_code, 200)
        user = self.fresh(User, self.other_id)
        self.assertFalse(user.is_active)

    def test_toggle_inactive_user_activates_them(self):
        self.login_as_admin()
        r = self.client.post(
            f"/admin/users/{self.inactive_id}/toggle",
            follow_redirects=True,
        )
        self.assertEqual(r.status_code, 200)
        user = self.fresh(User, self.inactive_id)
        self.assertTrue(user.is_active)

    def test_admin_cannot_deactivate_own_account(self):
        self.login_as_admin()
        r = self.client.post(
            f"/admin/users/{self.admin_id}/toggle",
            follow_redirects=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"cannot deactivate your own account", r.data)
        admin = self.fresh(User, self.admin_id)
        self.assertTrue(admin.is_active)

    def test_toggle_requires_admin(self):
        self.login_as_other()
        r = self.client.post(f"/admin/users/{self.inactive_id}/toggle")
        self.assertEqual(r.status_code, 403)

    def test_toggle_nonexistent_user_returns_404(self):
        self.login_as_admin()
        r = self.client.post("/admin/users/99999/toggle")
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
