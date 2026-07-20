"""Smoke tests: video list, video detail, direct S3 multipart upload, delete."""
import os
import sys
import unittest

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


class TestMultipartUpload(BaseTestCase):
    def _initiate_payload(self, **overrides):
        payload = {
            "filename": "match.mp4",
            "file_size": 15,
            "session_date": "2026-07-20",
            "notes": "Training match",
            "tags": "training,singles",
            "visibility": "private",
            "allow_download": False,
        }
        payload.update(overrides)
        return payload

    def _initiate(self, s3, **overrides):
        payload = self._initiate_payload(**overrides)
        s3.head_object.return_value = {"ContentLength": payload["file_size"]}
        response = self.client.post(
            "/api/uploads/multipart/initiate",
            json=payload,
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    def test_upload_page_loads_with_direct_s3_script(self):
        self.login_as_owner()
        response = self.client.get("/upload")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Direct-to-S3 upload", response.data)
        self.assertIn(b"upload.js", response.data)

    def test_legacy_form_post_does_not_accept_video_body(self):
        self.login_as_owner()
        before = Video.query.count()
        response = self.client.post("/upload")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"requires JavaScript", response.data)
        self.assertEqual(Video.query.count(), before)

    def test_initiate_creates_multipart_upload_and_presigned_parts(self):
        self.login_as_owner()
        with self.mock_s3() as get_client:
            response = self.client.post(
                "/api/uploads/multipart/initiate",
                json=self._initiate_payload(),
            )
            s3 = get_client.return_value

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["upload_token"])
        self.assertEqual(payload["total_parts"], 1)
        self.assertEqual(payload["parts"][0]["part_number"], 1)
        self.assertIn("upload_part", payload["parts"][0]["url"])
        s3.create_multipart_upload.assert_called_once()
        s3.generate_presigned_url.assert_called_once()

    def test_initiate_rejects_invalid_extension(self):
        self.login_as_owner()
        with self.mock_s3() as get_client:
            response = self.client.post(
                "/api/uploads/multipart/initiate",
                json=self._initiate_payload(filename="malware.exe"),
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported video format", response.get_json()["error"])
        get_client.return_value.create_multipart_upload.assert_not_called()

    def test_initiate_rejects_file_larger_than_limit(self):
        self.login_as_owner()
        with self.mock_s3():
            response = self.client.post(
                "/api/uploads/multipart/initiate",
                json=self._initiate_payload(
                    file_size=2 * 1024 * 1024 * 1024 + 1
                ),
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("exceeds", response.get_json()["error"])

    def test_complete_creates_video_record_after_s3_completion(self):
        self.login_as_owner()
        before = Video.query.count()
        with self.mock_s3() as get_client:
            s3 = get_client.return_value
            initiation = self._initiate(s3)
            response = self.client.post(
                "/api/uploads/multipart/complete",
                json={
                    "upload_token": initiation["upload_token"],
                    "parts": [{"part_number": 1, "etag": '"etag-1"'}],
                },
            )

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        db.session.expire_all()
        self.assertEqual(Video.query.count(), before + 1)
        video = Video.query.order_by(Video.id.desc()).first()
        self.assertEqual(video.filename, "match.mp4")
        self.assertEqual(video.file_size, 15)
        self.assertEqual(video.notes, "Training match")
        self.assertEqual(video.tags, "training,singles")
        s3.complete_multipart_upload.assert_called_once()
        s3.head_object.assert_called_once()

    def test_complete_rejects_missing_part(self):
        self.login_as_owner()
        with self.mock_s3() as get_client:
            s3 = get_client.return_value
            initiation = self._initiate(s3)
            response = self.client.post(
                "/api/uploads/multipart/complete",
                json={"upload_token": initiation["upload_token"], "parts": []},
            )

        self.assertEqual(response.status_code, 400)
        s3.complete_multipart_upload.assert_not_called()

    def test_complete_deletes_object_when_size_does_not_match(self):
        self.login_as_owner()
        before = Video.query.count()
        with self.mock_s3() as get_client:
            s3 = get_client.return_value
            initiation = self._initiate(s3)
            s3.head_object.return_value = {"ContentLength": 14}
            response = self.client.post(
                "/api/uploads/multipart/complete",
                json={
                    "upload_token": initiation["upload_token"],
                    "parts": [{"part_number": 1, "etag": '"etag-1"'}],
                },
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(Video.query.count(), before)
        s3.delete_object.assert_called_once()

    def test_abort_cancels_incomplete_upload(self):
        self.login_as_owner()
        with self.mock_s3() as get_client:
            s3 = get_client.return_value
            initiation = self._initiate(s3)
            response = self.client.post(
                "/api/uploads/multipart/abort",
                json={"upload_token": initiation["upload_token"]},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["aborted"])
        s3.abort_multipart_upload.assert_called_once()

    def test_direct_upload_api_requires_login(self):
        response = self.client.post(
            "/api/uploads/multipart/initiate",
            json=self._initiate_payload(),
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("login session", response.get_json()["error"])


class TestDeleteVideo(BaseTestCase):
    def test_owner_can_delete_own_video(self):
        self.login_as_owner()
        with self.mock_s3():
            response = self.client.post(
                f"/videos/{self.private_video_id}/delete",
                follow_redirects=True,
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"deleted", response.data)
        self.assertIsNone(self.fresh(Video, self.private_video_id))

    def test_other_user_cannot_delete_video(self):
        self.login_as_other()
        response = self.client.post(f"/videos/{self.private_video_id}/delete")
        self.assertEqual(response.status_code, 403)
        self.assertIsNotNone(self.fresh(Video, self.private_video_id))

    def test_delete_nonexistent_video_returns_404(self):
        self.login_as_owner()
        response = self.client.post("/videos/99999/delete")
        self.assertEqual(response.status_code, 404)

    def test_admin_can_delete_any_video(self):
        self.login_as_admin()
        with self.mock_s3():
            response = self.client.post(
                f"/videos/{self.private_video_id}/delete",
                follow_redirects=True,
            )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.fresh(Video, self.private_video_id))


if __name__ == "__main__":
    unittest.main()
