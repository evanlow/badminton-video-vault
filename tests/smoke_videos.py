"""Smoke tests: video list, video detail, upload, delete."""
import os
import sys
import unittest
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._test_helpers import BaseTestCase  # noqa: E402
from extensions import db  # noqa: E402
from models import Video  # noqa: E402


class TestVideosList(BaseTestCase):
    def test_videos_list_loads(self):
        self.login_as_owner()
        r = self.client.get("/videos")
        self.assertEqual(r.status_code, 200)

    def test_videos_list_shows_own_private_video(self):
        self.login_as_owner()
        r = self.client.get("/videos")
        self.assertIn(b"private.mp4", r.data)

    def test_videos_list_shows_own_public_video(self):
        self.login_as_owner()
        r = self.client.get("/videos")
        self.assertIn(b"public.mp4", r.data)

    def test_videos_list_shows_own_shared_video(self):
        self.login_as_owner()
        r = self.client.get("/videos")
        self.assertIn(b"shared.mp4", r.data)

    def test_videos_list_shows_other_users_public_video(self):
        self.login_as_other()
        r = self.client.get("/videos")
        self.assertIn(b"public.mp4", r.data)

    def test_videos_list_hides_other_users_private_video(self):
        self.login_as_other()
        r = self.client.get("/videos")
        self.assertNotIn(b"private.mp4", r.data)

    def test_videos_list_hides_other_users_shared_video(self):
        self.login_as_other()
        r = self.client.get("/videos")
        self.assertNotIn(b"shared.mp4", r.data)

    def test_videos_list_tag_filter(self):
        self.login_as_owner()
        r = self.client.get("/videos?tag=nonexistenttag")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(b"private.mp4", r.data)


class TestVideoDetail(BaseTestCase):
    def test_owner_can_view_own_private_video(self):
        self.login_as_owner()
        with self.mock_s3():
            r = self.client.get(f"/videos/{self.private_video_id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"private.mp4", r.data)

    def test_owner_sees_edit_form_on_own_video(self):
        self.login_as_owner()
        with self.mock_s3():
            r = self.client.get(f"/videos/{self.private_video_id}")
        self.assertIn(b"Save Changes", r.data)
        self.assertIn(b"Delete Video", r.data)

    def test_other_user_can_view_public_video(self):
        self.login_as_other()
        with self.mock_s3():
            r = self.client.get(f"/videos/{self.public_video_id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"public.mp4", r.data)

    def test_other_user_sees_no_edit_form_on_public_video(self):
        self.login_as_other()
        with self.mock_s3():
            r = self.client.get(f"/videos/{self.public_video_id}")
        self.assertNotIn(b"Save Changes", r.data)
        self.assertNotIn(b"Delete Video", r.data)

    def test_other_user_forbidden_on_private_video(self):
        self.login_as_other()
        r = self.client.get(f"/videos/{self.private_video_id}")
        self.assertEqual(r.status_code, 403)

    def test_other_user_forbidden_on_shared_video(self):
        self.login_as_other()
        r = self.client.get(f"/videos/{self.shared_video_id}")
        self.assertEqual(r.status_code, 403)

    def test_nonexistent_video_returns_404(self):
        self.login_as_owner()
        r = self.client.get("/videos/99999")
        self.assertEqual(r.status_code, 404)

    def test_admin_can_view_any_video(self):
        self.login_as_admin()
        with self.mock_s3():
            r = self.client.get(f"/videos/{self.private_video_id}")
        self.assertEqual(r.status_code, 200)

    def test_admin_sees_edit_form_on_any_video(self):
        self.login_as_admin()
        with self.mock_s3():
            r = self.client.get(f"/videos/{self.private_video_id}")
        self.assertIn(b"Save Changes", r.data)
        self.assertIn(b"Delete Video", r.data)

    def test_owner_can_edit_video_details(self):
        self.login_as_owner()
        with self.mock_s3():
            r = self.client.post(
                f"/videos/{self.private_video_id}",
                data={
                    "notes": "Updated notes",
                    "tags": "singles",
                    "visibility": "private",
                    "allow_download": False,
                },
                follow_redirects=True,
            )
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"updated", r.data)

    def test_shared_video_shows_copy_share_link_button_to_owner(self):
        self.login_as_owner()
        with self.mock_s3():
            r = self.client.get(f"/videos/{self.shared_video_id}")
        self.assertIn(b"Copy Share Link", r.data)


class TestUpload(BaseTestCase):
    def test_upload_page_loads(self):
        self.login_as_owner()
        r = self.client.get("/upload")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Upload", r.data)

    def test_upload_valid_mp4_creates_video_record(self):
        self.login_as_owner()
        before = Video.query.count()
        with self.mock_s3():
            r = self.client.post(
                "/upload",
                data={
                    "video_file": (BytesIO(b"fake video data"), "match.mp4", "video/mp4"),
                    "visibility": "private",
                },
                content_type="multipart/form-data",
                follow_redirects=True,
            )
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"uploaded successfully", r.data)
        db.session.expire_all()
        self.assertEqual(Video.query.count(), before + 1)

    def test_upload_invalid_extension_rejected(self):
        self.login_as_owner()
        before = Video.query.count()
        with self.mock_s3():
            r = self.client.post(
                "/upload",
                data={
                    "video_file": (BytesIO(b"not a video"), "malware.exe", "application/octet-stream"),
                    "visibility": "private",
                },
                content_type="multipart/form-data",
            )
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(b"uploaded successfully", r.data)
        db.session.expire_all()
        self.assertEqual(Video.query.count(), before)

    def test_upload_requires_login(self):
        r = self.client.post("/upload", follow_redirects=True)
        self.assertIn(b"Log In", r.data)


class TestDeleteVideo(BaseTestCase):
    def test_owner_can_delete_own_video(self):
        self.login_as_owner()
        with self.mock_s3():
            r = self.client.post(
                f"/videos/{self.private_video_id}/delete",
                follow_redirects=True,
            )
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"deleted", r.data)
        self.assertIsNone(self.fresh(Video, self.private_video_id))

    def test_other_user_cannot_delete_video(self):
        self.login_as_other()
        r = self.client.post(f"/videos/{self.private_video_id}/delete")
        self.assertEqual(r.status_code, 403)
        self.assertIsNotNone(self.fresh(Video, self.private_video_id))

    def test_delete_nonexistent_video_returns_404(self):
        self.login_as_owner()
        r = self.client.post("/videos/99999/delete")
        self.assertEqual(r.status_code, 404)

    def test_admin_can_delete_any_video(self):
        self.login_as_admin()
        with self.mock_s3():
            r = self.client.post(
                f"/videos/{self.private_video_id}/delete",
                follow_redirects=True,
            )
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(self.fresh(Video, self.private_video_id))


if __name__ == "__main__":
    unittest.main()
