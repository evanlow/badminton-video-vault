import os
from dotenv import load_dotenv

load_dotenv()


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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

    # Mailgun HTTP API (not SMTP)
    MAILGUN_API_KEY = os.environ.get("MAILGUN_API_KEY")
    MAILGUN_DOMAIN = os.environ.get("MAILGUN_DOMAIN")
    MAILGUN_API_BASE_URL = os.environ.get("MAILGUN_API_BASE_URL", "https://api.mailgun.net")
    MAIL_FROM = os.environ.get(
        "MAIL_FROM",
        "Badminton Video Vault <noreply@notifications.tek10x.com>",
    )
    MAIL_SUPPRESS_SEND = _env_bool(
        "MAIL_SUPPRESS_SEND",
        default=os.environ.get("FLASK_ENV") == "development",
    )
    MAILGUN_TEST_MODE = _env_bool("MAILGUN_TEST_MODE", default=False)
    MAILGUN_TIMEOUT_SECONDS = int(os.environ.get("MAILGUN_TIMEOUT_SECONDS", 10))

    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5000").rstrip("/")
    PASSWORD_RESET_TOKEN_TTL_MINUTES = int(os.environ.get("PASSWORD_RESET_TOKEN_TTL_MINUTES", 30))
    MAGIC_LOGIN_TOKEN_TTL_MINUTES = int(os.environ.get("MAGIC_LOGIN_TOKEN_TTL_MINUTES", 15))

    MAX_CONTENT_LENGTH = 2 * 1024 * 1024 * 1024  # 2 GB upload limit
