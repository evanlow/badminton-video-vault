import os
from dotenv import load_dotenv

load_dotenv()


def _get_secret_key():
    key = os.environ.get("FLASK_SECRET_KEY")
    if not key:
        if os.environ.get("FLASK_ENV") == "development":
            return "dev-secret-key"
        raise RuntimeError(
            "FLASK_SECRET_KEY environment variable must be set in non-development environments."
        )
    return key


class Config:
    SECRET_KEY = _get_secret_key()
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///badminton_vault.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
    S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")

    PRESIGNED_URL_EXPIRY = int(os.environ.get("PRESIGNED_URL_EXPIRY", 3600))

    MAX_CONTENT_LENGTH = 2 * 1024 * 1024 * 1024  # 2 GB upload limit
