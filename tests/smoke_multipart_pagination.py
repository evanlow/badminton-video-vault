"""Regression tests for paginated S3 multipart-part listings."""
from unittest.mock import MagicMock

from tests._test_helpers import BaseTestCase
from app import _list_multipart_upload_parts


class TestMultipartPartListingPagination(BaseTestCase):
    def test_list_parts_follows_next_marker_and_combines_pages(self):
        s3 = MagicMock()
        s3.list_parts.side_effect = [
            {
                "IsTruncated": True,
                "NextPartNumberMarker": 1000,
                "Parts": [
                    {"PartNumber": 1000, "ETag": '"etag-1000"', "Size": 5}
                ],
            },
            {
                "IsTruncated": False,
                "Parts": [
                    {"PartNumber": 1001, "ETag": '"etag-1001"', "Size": 5}
                ],
            },
        ]

        parts = _list_multipart_upload_parts(
            s3,
            "videos/2/example.mp4",
            "upload-id",
        )

        self.assertEqual(
            [part["PartNumber"] for part in parts],
            [1000, 1001],
        )
        self.assertEqual(s3.list_parts.call_count, 2)
        self.assertEqual(
            s3.list_parts.call_args_list[0].kwargs["PartNumberMarker"],
            0,
        )
        self.assertEqual(
            s3.list_parts.call_args_list[1].kwargs["PartNumberMarker"],
            1000,
        )

    def test_list_parts_uses_last_part_as_safe_marker_fallback(self):
        s3 = MagicMock()
        s3.list_parts.side_effect = [
            {
                "IsTruncated": True,
                "Parts": [
                    {"PartNumber": 7, "ETag": '"etag-7"', "Size": 5}
                ],
            },
            {
                "IsTruncated": False,
                "Parts": [
                    {"PartNumber": 8, "ETag": '"etag-8"', "Size": 5}
                ],
            },
        ]

        parts = _list_multipart_upload_parts(
            s3,
            "videos/2/example.mp4",
            "upload-id",
        )

        self.assertEqual(
            [part["PartNumber"] for part in parts],
            [7, 8],
        )
        self.assertEqual(
            s3.list_parts.call_args_list[1].kwargs["PartNumberMarker"],
            7,
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
