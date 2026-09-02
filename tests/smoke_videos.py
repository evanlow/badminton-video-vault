"""Smoke tests: video list, video detail, direct S3 multipart upload, delete."""
import importlib
import os
import re
import sys
import time
import unittest
from datetime import timedelta
from unittest.mock import patch
from wtforms.validators import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._test_helpers import BaseTestCase  # noqa: E402
from config import Config  # noqa: E402
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

    def _initiate(self, s3, headers=None, **overrides):
        payload = self._initiate_payload(**overrides)
        s3.head_object.return_value = {"ContentLength": payload["file_size"]}
        response = self.client.post(
            "/api/uploads/multipart/initiate",
            json=payload,
            headers=headers,
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
        self.assertIn("upload_token_expires_in", payload)
        s3.create_multipart_upload.assert_called_once()
        s3.generate_presigned_url.assert_called_once()

    def test_s3_client_forces_sigv4_signing(self):
        from app import get_s3_client

        with patch("app.boto3.client") as boto_client:
            get_s3_client()

        kwargs = boto_client.call_args.kwargs
        self.assertIn("config", kwargs)
        self.assertEqual(kwargs["config"].signature_version, "s3v4")

    def test_initiate_presigns_exact_content_length_for_each_part(self):
        self.login_as_owner()
        oversized = (16 * 1024 * 1024) + 123
        with self.mock_s3() as get_client:
            s3 = get_client.return_value
            response = self.client.post(
                "/api/uploads/multipart/initiate",
                json=self._initiate_payload(file_size=oversized),
            )

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(s3.generate_presigned_url.call_count, 2)
        first_call = s3.generate_presigned_url.call_args_list[0]
        second_call = s3.generate_presigned_url.call_args_list[1]
        self.assertEqual(first_call.kwargs["Params"]["PartNumber"], 1)
        self.assertEqual(first_call.kwargs["Params"]["ContentLength"], 16 * 1024 * 1024)
        self.assertEqual(second_call.kwargs["Params"]["PartNumber"], 2)
        self.assertEqual(second_call.kwargs["Params"]["ContentLength"], 123)

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
        with self.mock_s3() as get_client:
            response = self.client.post(
                "/api/uploads/multipart/initiate",
                json=self._initiate_payload(
                    file_size=Config.MAX_VIDEO_FILE_SIZE + 1
                ),
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("exceeds", response.get_json()["error"])
        get_client.return_value.create_multipart_upload.assert_not_called()

    def test_production_config_default_max_video_file_size_is_3gib(self):
        import config as config_module

        with patch.dict(os.environ, {"FLASK_ENV": "development"}, clear=False):
            os.environ.pop("MAX_VIDEO_FILE_SIZE", None)
            with patch("dotenv.load_dotenv", return_value=False):
                reloaded = importlib.reload(config_module)
                self.assertEqual(reloaded.Config.MAX_VIDEO_FILE_SIZE, 3221225472)
        importlib.reload(config_module)

    def test_test_fixture_limit_matches_production_default(self):
        from app import app as flask_app

        expected = int(
            os.environ.get("MAX_VIDEO_FILE_SIZE", 3 * 1024 * 1024 * 1024)
        )
        self.assertEqual(
            flask_app.config["MAX_VIDEO_FILE_SIZE"], expected
        )

    def test_upload_page_exposes_configured_max_file_size(self):
        self.login_as_owner()
        response = self.client.get("/upload")
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            f'data-max-file-size="{Config.MAX_VIDEO_FILE_SIZE}"'.encode(),
            response.data,
        )

    def test_csrf_lifetime_integer_is_exposed_in_upload_and_api(self):
        self.login_as_owner()
        from app import app as flask_app

        original_value = flask_app.config.get("WTF_CSRF_TIME_LIMIT")
        flask_app.config["WTF_CSRF_TIME_LIMIT"] = 1234
        try:
            upload_page = self.client.get("/upload")
            self.assertEqual(upload_page.status_code, 200)
            self.assertIn(
                b'data-csrf-token-lifetime-seconds="1234"',
                upload_page.data,
            )

            csrf_response = self.client.get("/api/csrf-token")
            self.assertEqual(csrf_response.status_code, 200)
            payload = csrf_response.get_json()
            self.assertEqual(payload["expires_in"], 1234)
        finally:
            flask_app.config["WTF_CSRF_TIME_LIMIT"] = original_value

    def test_csrf_lifetime_timedelta_normalises_to_seconds(self):
        self.login_as_owner()
        from app import app as flask_app

        original_value = flask_app.config.get("WTF_CSRF_TIME_LIMIT")
        flask_app.config["WTF_CSRF_TIME_LIMIT"] = timedelta(hours=1)
        try:
            upload_page = self.client.get("/upload")
            self.assertEqual(upload_page.status_code, 200)
            self.assertIn(
                b'data-csrf-token-lifetime-seconds="3600"',
                upload_page.data,
            )

            csrf_response = self.client.get("/api/csrf-token")
            self.assertEqual(csrf_response.status_code, 200)
            payload = csrf_response.get_json()
            self.assertEqual(payload["expires_in"], 3600)
        finally:
            flask_app.config["WTF_CSRF_TIME_LIMIT"] = original_value

    def test_csrf_lifetime_none_remains_disabled_and_json_encodes(self):
        self.login_as_owner()
        from app import app as flask_app

        original_value = flask_app.config.get("WTF_CSRF_TIME_LIMIT")
        flask_app.config["WTF_CSRF_TIME_LIMIT"] = None
        try:
            upload_page = self.client.get("/upload")
            self.assertEqual(upload_page.status_code, 200)
            self.assertIn(
                b'data-csrf-token-lifetime-seconds=""',
                upload_page.data,
            )

            csrf_response = self.client.get("/api/csrf-token")
            self.assertEqual(csrf_response.status_code, 200)
            payload = csrf_response.get_json()
            self.assertIsNone(payload["expires_in"])
        finally:
            flask_app.config["WTF_CSRF_TIME_LIMIT"] = original_value

    def test_csrf_lifetime_invalid_config_fails_clearly_in_api(self):
        self.login_as_owner()
        from app import app as flask_app

        original_value = flask_app.config.get("WTF_CSRF_TIME_LIMIT")
        flask_app.config["WTF_CSRF_TIME_LIMIT"] = "1:00:00"
        try:
            csrf_response = self.client.get("/api/csrf-token")
        finally:
            flask_app.config["WTF_CSRF_TIME_LIMIT"] = original_value

        self.assertEqual(csrf_response.status_code, 500)
        payload = csrf_response.get_json()
        self.assertEqual(payload["code"], "csrf_config_invalid")
        self.assertIn("WTF_CSRF_TIME_LIMIT", payload["error"])

    def test_initiate_accepts_exactly_the_configured_limit_as_192_ordered_parts(self):
        self.login_as_owner()
        with self.mock_s3() as get_client:
            response = self.client.post(
                "/api/uploads/multipart/initiate",
                json=self._initiate_payload(file_size=Config.MAX_VIDEO_FILE_SIZE),
            )
            s3 = get_client.return_value

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertEqual(payload["total_parts"], 192)
        self.assertEqual(len(payload["parts"]), 192)
        self.assertEqual(
            [part["part_number"] for part in payload["parts"]],
            list(range(1, 193)),
        )
        s3.create_multipart_upload.assert_called_once()
        self.assertEqual(s3.generate_presigned_url.call_count, 192)

    def test_complete_rejects_mismatched_s3_part_size_before_assembly(self):
        self.login_as_owner()
        with self.mock_s3() as get_client:
            s3 = get_client.return_value
            initiation = self._initiate(s3)
            s3.list_parts.return_value = {
                "IsTruncated": False,
                "Parts": [{"PartNumber": 1, "ETag": '"etag-1"', "Size": 14}],
            }
            response = self.client.post(
                "/api/uploads/multipart/complete",
                json={
                    "upload_token": initiation["upload_token"],
                    "parts": [{"part_number": 1, "etag": '"etag-1"'}],
                },
            )

        self.assertEqual(response.status_code, 409)
        self.assertIn("does not match", response.get_json()["error"])
        s3.complete_multipart_upload.assert_not_called()
        s3.abort_multipart_upload.assert_called_once()

    def test_complete_rejects_mismatched_s3_part_etag_before_assembly(self):
        self.login_as_owner()
        with self.mock_s3() as get_client:
            s3 = get_client.return_value
            initiation = self._initiate(s3)
            s3.list_parts.return_value = {
                "IsTruncated": False,
                "Parts": [{"PartNumber": 1, "ETag": '"different"', "Size": 15}],
            }
            response = self.client.post(
                "/api/uploads/multipart/complete",
                json={
                    "upload_token": initiation["upload_token"],
                    "parts": [{"part_number": 1, "etag": '"etag-1"'}],
                },
            )

        self.assertEqual(response.status_code, 409)
        self.assertIn("does not match", response.get_json()["error"])
        s3.complete_multipart_upload.assert_not_called()
        s3.abort_multipart_upload.assert_called_once()

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
        s3.list_parts.assert_called_once()
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

    def test_refresh_part_returns_a_new_presigned_url_for_an_expired_part(self):
        # Simulates a slow upload where a late part's originally-issued
        # presigned URL has expired: the client asks the server for a fresh
        # URL for that part number and the upload can still complete.
        self.login_as_owner()
        with self.mock_s3() as get_client:
            s3 = get_client.return_value
            initiation = self._initiate(s3)
            response = self.client.post(
                "/api/uploads/multipart/refresh-part",
                json={
                    "upload_token": initiation["upload_token"],
                    "part_number": 1,
                },
            )

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertEqual(payload["part_number"], 1)
        self.assertIn("upload_part", payload["url"])
        self.assertIn("expires_in", payload)
        self.assertIn("upload_token", payload)
        self.assertIn("upload_token_expires_in", payload)
        self.assertNotEqual(payload["upload_token"], initiation["upload_token"])
        # generate_presigned_url is called once during initiation and once
        # more for the refresh.
        self.assertEqual(s3.generate_presigned_url.call_count, 2)

    def test_refresh_part_rejects_out_of_range_part_number(self):
        self.login_as_owner()
        with self.mock_s3() as get_client:
            s3 = get_client.return_value
            initiation = self._initiate(s3)
            response = self.client.post(
                "/api/uploads/multipart/refresh-part",
                json={
                    "upload_token": initiation["upload_token"],
                    "part_number": 99,
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Part number is invalid", response.get_json()["error"])

    def test_refresh_part_presigns_exact_content_length_for_final_part(self):
        self.login_as_owner()
        oversized = (16 * 1024 * 1024) + 123
        with self.mock_s3() as get_client:
            s3 = get_client.return_value
            initiation = self._initiate(s3, file_size=oversized)
            response = self.client.post(
                "/api/uploads/multipart/refresh-part",
                json={
                    "upload_token": initiation["upload_token"],
                    "part_number": 2,
                },
            )

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        refresh_call = s3.generate_presigned_url.call_args_list[-1]
        self.assertEqual(refresh_call.kwargs["Params"]["PartNumber"], 2)
        self.assertEqual(refresh_call.kwargs["Params"]["ContentLength"], 123)

    def test_refresh_part_rejects_another_users_upload_token(self):
        self.login_as_owner()
        with self.mock_s3() as get_client:
            s3 = get_client.return_value
            initiation = self._initiate(s3)
            self.client.get("/logout")
            self.login_as_other()
            response = self.client.post(
                "/api/uploads/multipart/refresh-part",
                json={
                    "upload_token": initiation["upload_token"],
                    "part_number": 1,
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("does not belong", response.get_json()["error"])

    def test_refresh_part_renews_upload_token_before_original_expiry(self):
        self.login_as_owner()
        from app import app as flask_app

        original_max_age = flask_app.config["S3_MULTIPART_TOKEN_MAX_AGE"]
        flask_app.config["S3_MULTIPART_TOKEN_MAX_AGE"] = 3
        try:
            with self.mock_s3() as get_client:
                s3 = get_client.return_value
                initiation = self._initiate(s3)
                time.sleep(2.2)
                refresh = self.client.post(
                    "/api/uploads/multipart/refresh-part",
                    json={
                        "upload_token": initiation["upload_token"],
                        "part_number": 1,
                    },
                )
                self.assertEqual(refresh.status_code, 200)
                refreshed_token = refresh.get_json()["upload_token"]
                time.sleep(1.2)
                response = self.client.post(
                    "/api/uploads/multipart/complete",
                    json={
                        "upload_token": refreshed_token,
                        "parts": [{"part_number": 1, "etag": '"etag-1"'}],
                    },
                )
        finally:
            flask_app.config["S3_MULTIPART_TOKEN_MAX_AGE"] = original_max_age

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

    def test_two_successive_csrf_tokens_remain_valid_for_multipart_requests(self):
        self.login_as_owner()
        from app import app as flask_app

        original_csrf_enabled = flask_app.config.get("WTF_CSRF_ENABLED")
        original_csrf_time_limit = flask_app.config.get("WTF_CSRF_TIME_LIMIT")
        flask_app.config["WTF_CSRF_ENABLED"] = True
        flask_app.config["WTF_CSRF_TIME_LIMIT"] = 3600
        try:
            first_token_response = self.client.get("/api/csrf-token")
            self.assertEqual(first_token_response.status_code, 200)
            first_token = first_token_response.get_json()["csrf_token"]

            second_token_response = self.client.get("/api/csrf-token")
            self.assertEqual(second_token_response.status_code, 200)
            second_token = second_token_response.get_json()["csrf_token"]

            with self.mock_s3() as get_client:
                s3 = get_client.return_value
                first_initiation = self._initiate(
                    s3,
                    headers={"X-CSRFToken": first_token},
                )
                second_initiation = self._initiate(
                    s3,
                    headers={"X-CSRFToken": second_token},
                )
        finally:
            flask_app.config["WTF_CSRF_ENABLED"] = original_csrf_enabled
            flask_app.config["WTF_CSRF_TIME_LIMIT"] = original_csrf_time_limit

        self.assertTrue(first_initiation["upload_token"])
        self.assertTrue(second_initiation["upload_token"])

    def test_expired_csrf_can_be_refreshed_for_multipart_upload(self):
        self.login_as_owner()
        from app import app as flask_app

        original_csrf_enabled = flask_app.config.get("WTF_CSRF_ENABLED")
        original_csrf_time_limit = flask_app.config.get("WTF_CSRF_TIME_LIMIT")
        flask_app.config["WTF_CSRF_ENABLED"] = True
        flask_app.config["WTF_CSRF_TIME_LIMIT"] = 10
        try:
            upload_page = self.client.get("/upload")
            html = upload_page.get_data(as_text=True)
            match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
            self.assertIsNotNone(match)
            expired_token = match.group(1)

            with self.mock_s3() as get_client:
                s3 = get_client.return_value
                with patch(
                    "flask_wtf.csrf.validate_csrf",
                    side_effect=ValidationError("The CSRF token has expired."),
                ):
                    expired_attempt = self.client.post(
                        "/api/uploads/multipart/initiate",
                        json=self._initiate_payload(),
                        headers={"X-CSRFToken": expired_token},
                    )
                self.assertEqual(expired_attempt.status_code, 400)
                self.assertEqual(expired_attempt.get_json()["code"], "csrf_failed")

                refresh = self.client.get("/api/csrf-token")
                self.assertEqual(refresh.status_code, 200)
                refreshed_payload = refresh.get_json()
                refreshed_token = refreshed_payload["csrf_token"]
                self.assertEqual(refreshed_payload["expires_in"], 10)
                self.assertIn("no-store", refresh.headers["Cache-Control"])

                with patch("flask_wtf.csrf.validate_csrf", return_value=True):
                    initiation = self._initiate(
                        s3,
                        headers={"X-CSRFToken": refreshed_token},
                    )
                    completion = self.client.post(
                        "/api/uploads/multipart/complete",
                        json={
                            "upload_token": initiation["upload_token"],
                            "parts": [{"part_number": 1, "etag": '"etag-1"'}],
                        },
                        headers={"X-CSRFToken": refreshed_token},
                    )
        finally:
            flask_app.config["WTF_CSRF_ENABLED"] = original_csrf_enabled
            flask_app.config["WTF_CSRF_TIME_LIMIT"] = original_csrf_time_limit

        self.assertEqual(completion.status_code, 200, completion.get_data(as_text=True))

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
