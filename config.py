import os
from dotenv import load_dotenv


load_dotenv()


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name, default, minimum=None, maximum=None):
    raw_value = os.environ.get(name)
    try:
        value = int(raw_value) if raw_value is not None else int(default)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc

    if minimum is not None and value < minimum:
        raise RuntimeError(f"{name} must be at least {minimum}.")
    if maximum is not None and value > maximum:
        raise RuntimeError(f"{name} must be at most {maximum}.")
    return value


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
    AUTO_CREATE_DB = _env_bool("AUTO_CREATE_DB", default=True)

    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
    S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")

    PRESIGNED_URL_EXPIRY = _env_int(
        "PRESIGNED_URL_EXPIRY", 3600, minimum=60, maximum=604800
    )

    # Direct browser-to-S3 multipart uploads. Flask receives only small JSON
    # coordination requests; the video bytes never pass through EC2.
    MAX_VIDEO_FILE_SIZE = _env_int(
        "MAX_VIDEO_FILE_SIZE",
        3 * 1024 * 1024 * 1024,
        minimum=1,
        maximum=5 * 1024 * 1024 * 1024,
    )
    S3_MULTIPART_PART_SIZE = _env_int(
        "S3_MULTIPART_PART_SIZE",
        16 * 1024 * 1024,
        minimum=5 * 1024 * 1024,
        maximum=5 * 1024 * 1024 * 1024,
    )
    S3_MULTIPART_URL_EXPIRY = _env_int(
        "S3_MULTIPART_URL_EXPIRY",
        7200,
        minimum=300,
        maximum=604800,
    )
    S3_MULTIPART_TOKEN_MAX_AGE = _env_int(
        "S3_MULTIPART_TOKEN_MAX_AGE",
        21600,
        minimum=300,
        maximum=604800,
    )
    S3_MULTIPART_CONCURRENCY = _env_int(
        "S3_MULTIPART_CONCURRENCY",
        3,
        minimum=1,
        maximum=8,
    )

    # The server no longer accepts video bodies. Keep Flask request bodies small
    # to prevent accidental or malicious multi-gigabyte uploads to EC2.
    MAX_CONTENT_LENGTH = _env_int(
        "MAX_REQUEST_BODY_SIZE",
        4 * 1024 * 1024,
        minimum=64 * 1024,
        maximum=64 * 1024 * 1024,
    )

    # Mailgun HTTP API (not SMTP)
    MAILGUN_API_KEY = os.environ.get("MAILGUN_API_KEY")
    MAILGUN_DOMAIN = os.environ.get("MAILGUN_DOMAIN")
    MAILGUN_API_BASE_URL = os.environ.get(
        "MAILGUN_API_BASE_URL", "https://api.mailgun.net"
    )
    MAIL_FROM = os.environ.get(
        "MAIL_FROM",
        "Badminton Video Vault <noreply@notifications.tek10x.com>",
    )
    MAIL_SUPPRESS_SEND = _env_bool(
        "MAIL_SUPPRESS_SEND",
        default=os.environ.get("FLASK_ENV") == "development",
    )
    MAILGUN_TEST_MODE = _env_bool("MAILGUN_TEST_MODE", default=False)
    MAILGUN_TIMEOUT_SECONDS = _env_int(
        "MAILGUN_TIMEOUT_SECONDS", 10, minimum=1, maximum=120
    )

    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5000").rstrip("/")
    PASSWORD_RESET_TOKEN_TTL_MINUTES = _env_int(
        "PASSWORD_RESET_TOKEN_TTL_MINUTES", 30, minimum=1, maximum=1440
    )
    MAGIC_LOGIN_TOKEN_TTL_MINUTES = _env_int(
        "MAGIC_LOGIN_TOKEN_TTL_MINUTES", 15, minimum=1, maximum=1440
    )
    AUTH_EMAIL_COOLDOWN_SECONDS = _env_int(
        "AUTH_EMAIL_COOLDOWN_SECONDS", 60, minimum=0, maximum=86400
    )
