"""
Shared test infrastructure for all smoke tests.

IMPORTANT: This module sets DATABASE_URL in os.environ BEFORE importing
app.py, ensuring the test database is used instead of the real one.
load_dotenv() in config.py will not override an already-set env var.
"""
import os
import sys
import secrets
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# ── Must be set before app/config import ──────────────────────────────────────
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_TESTS_DIR)
_TEST_DB_PATH = os.path.join(_TESTS_DIR, "_smoke_test.db").replace("\\", "/")

os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-key")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-secret")
os.environ.setdefault("S3_BUCKET_NAME", "test-bucket")
os.environ.setdefault("AWS_REGION", "us-east-1")

sys.path.insert(0, _ROOT_DIR)
# ─────────────────────────────────────────────────────────────────────────────

from app import app  # noqa: E402  (must come after env var setup)
from extensions import db  # noqa: E402
from models import User, Video  # noqa: E402

# Apply test-only config flags (engine already bound to test DB via env var above)
app.config.update(
    {
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-secret-key",
    }
)


# ---------------------------------------------------------------------------
# S3 mock factory
# ---------------------------------------------------------------------------

def make_mock_s3_client():
    """Return a MagicMock S3 client that satisfies all app S3 call patterns."""
    mock = MagicMock()
    mock.generate_presigned_url.return_value = "https://s3.example.com/fake-presigned"
    mock.upload_fileobj.return_value = None
    mock.delete_object.return_value = {}
    return mock


# ---------------------------------------------------------------------------
# Base test case
# ---------------------------------------------------------------------------

class BaseTestCase(unittest.TestCase):
    """
    Resets the database to a clean, known state before every test.

    Lifecycle per test:
      setUp   → push app context → drop_all → create_all → create fixtures
      test    → HTTP requests via self.client
      tearDown → remove session → drop_all → pop app context
    """

    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        self._create_fixtures()
        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    # ------------------------------------------------------------------
    # Fixture creation
    # ------------------------------------------------------------------

    def _create_fixtures(self):
        """
        Creates four users and four videos owned by `owner`.

        Users
        -----
        admin@test.com    — role=admin,  is_active=True
        owner@test.com    — role=user,   is_active=True  (owns all test videos)
        other@test.com    — role=user,   is_active=True  (no videos)
        inactive@test.com — role=user,   is_active=False

        Videos (owned by owner)
        -----------------------
        private.mp4      — visibility=private
        public.mp4       — visibility=public
        shared.mp4       — visibility=shared, valid share_token, no expiry
        expired_shared.mp4 — visibility=shared, share_token, expired 1 day ago
        """
        admin = User(name="Admin User", email="admin@test.com", role="admin")
        admin.set_password("AdminPass123!")

        owner = User(name="Video Owner", email="owner@test.com", role="user")
        owner.set_password("OwnerPass123!")

        other = User(name="Other User", email="other@test.com", role="user")
        other.set_password("OtherPass123!")

        inactive = User(
            name="Inactive User", email="inactive@test.com", role="user", is_active=False
        )
        inactive.set_password("InactivePass123!")

        db.session.add_all([admin, owner, other, inactive])
        db.session.flush()  # populate .id without committing

        self.admin_id = admin.id
        self.owner_id = owner.id
        self.other_id = other.id
        self.inactive_id = inactive.id

        private_vid = Video(
            filename="private.mp4",
            s3_key=f"videos/{owner.id}/private.mp4",
            uploaded_by_user_id=owner.id,
            visibility="private",
        )
        public_vid = Video(
            filename="public.mp4",
            s3_key=f"videos/{owner.id}/public.mp4",
            uploaded_by_user_id=owner.id,
            visibility="public",
        )
        self.share_token = secrets.token_urlsafe(32)
        shared_vid = Video(
            filename="shared.mp4",
            s3_key=f"videos/{owner.id}/shared.mp4",
            uploaded_by_user_id=owner.id,
            visibility="shared",
            share_token=self.share_token,
        )
        self.expired_token = secrets.token_urlsafe(32)
        expired_vid = Video(
            filename="expired_shared.mp4",
            s3_key=f"videos/{owner.id}/expired_shared.mp4",
            uploaded_by_user_id=owner.id,
            visibility="shared",
            share_token=self.expired_token,
            share_expires_at=datetime.utcnow() - timedelta(days=1),
        )

        db.session.add_all([private_vid, public_vid, shared_vid, expired_vid])
        db.session.commit()

        self.private_video_id = private_vid.id
        self.public_video_id = public_vid.id
        self.shared_video_id = shared_vid.id
        self.expired_video_id = expired_vid.id

    # ------------------------------------------------------------------
    # Login helpers
    # ------------------------------------------------------------------

    def login(self, email, password):
        return self.client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=True,
        )

    def login_as_admin(self):
        return self.login("admin@test.com", "AdminPass123!")

    def login_as_owner(self):
        return self.login("owner@test.com", "OwnerPass123!")

    def login_as_other(self):
        return self.login("other@test.com", "OtherPass123!")

    # ------------------------------------------------------------------
    # S3 mock context manager
    # ------------------------------------------------------------------

    def mock_s3(self):
        """Patch app.get_s3_client for the duration of a with-block."""
        return patch("app.get_s3_client", return_value=make_mock_s3_client())

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def fresh(self, model, pk):
        """Return a freshly-loaded DB record, bypassing the session cache."""
        db.session.expire_all()
        return db.session.get(model, pk)
