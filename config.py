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

    # Mail (used for "forgot password" and "magic link" login emails).
    # Works with Mailgun's SMTP relay: set MAIL_SERVER=smtp.mailgun.org and
    # MAIL_USERNAME/MAIL_PASSWORD to the SMTP credentials shown in your
    # Mailgun domain settings (not the HTTP API key).
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.mailgun.org")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get(
        "MAIL_DEFAULT_SENDER", "no-reply@badminton-video-vault.local"
    )
    # When true (or when no mail credentials are configured), emails are
    # logged instead of actually sent — useful for local development.
    MAIL_SUPPRESS_SEND = os.environ.get("MAIL_SUPPRESS_SEND", "false").lower() == "true"
