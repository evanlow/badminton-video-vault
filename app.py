import logging
import math
import os
import secrets
from datetime import date, datetime, timedelta
from functools import wraps

import boto3
from botocore.config import Config as BotocoreConfig
from botocore.exceptions import BotoCoreError, ClientError
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_wtf.csrf import CSRFError, generate_csrf
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename

from config import Config
from email_service import EmailDeliveryError, send_mailgun_email
from extensions import csrf, db, login_manager
from forms import (
    CreateUserForm,
    EditVideoForm,
    ForgotPasswordForm,
    LoginForm,
    MagicLoginForm,
    ResetPasswordForm,
    UploadVideoForm,
)
from models import AuthToken, User, Video


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"mp4", "avi", "mov", "mkv", "webm"}
CONTENT_TYPE_BY_EXTENSION = {
    "mp4": "video/mp4",
    "avi": "video/x-msvideo",
    "mov": "video/quicktime",
    "mkv": "video/x-matroska",
    "webm": "video/webm",
}
S3_MAX_MULTIPART_PARTS = 10_000
UPLOAD_TOKEN_SALT = "badminton-video-vault-multipart-upload-v1"


class UploadValidationError(ValueError):
    """Raised when a direct-upload coordination request is invalid."""


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    return app


app = create_app()

if app.config.get("AUTO_CREATE_DB", False):
    with app.app_context():
        db.create_all()


# ---------------------------------------------------------------------------
# S3 and upload helpers
# ---------------------------------------------------------------------------


def get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=app.config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=app.config["AWS_SECRET_ACCESS_KEY"],
        region_name=app.config["AWS_REGION"],
        config=BotocoreConfig(signature_version="s3v4"),
    )


def generate_presigned_part_url(
    s3_key, upload_id, part_number, content_length, expiry=None, s3=None
):
    """Return a presigned URL for one S3 multipart-upload part."""
    s3 = s3 or get_s3_client()
    expiry = expiry or app.config["S3_MULTIPART_URL_EXPIRY"]
    return s3.generate_presigned_url(
        "upload_part",
        Params={
            "Bucket": app.config["S3_BUCKET_NAME"],
            "Key": s3_key,
            "UploadId": upload_id,
            "PartNumber": part_number,
            "ContentLength": int(content_length),
        },
        ExpiresIn=expiry,
        HttpMethod="PUT",
    )


def generate_presigned_play_url(s3_key, expiry=None):
    """Return a presigned GET URL for streaming/playback."""
    s3 = get_s3_client()
    expiry = expiry or app.config["PRESIGNED_URL_EXPIRY"]
    try:
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": app.config["S3_BUCKET_NAME"], "Key": s3_key},
            ExpiresIn=expiry,
        )
    except (ClientError, BotoCoreError) as exc:
        logger.error("Error generating presigned play URL: %s", exc)
        return None


def generate_presigned_download_url(s3_key, filename, expiry=None):
    """Return a presigned GET URL that triggers a file download."""
    safe_filename = secure_filename(filename) or "download"
    s3 = get_s3_client()
    expiry = expiry or app.config["PRESIGNED_URL_EXPIRY"]
    try:
        return s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": app.config["S3_BUCKET_NAME"],
                "Key": s3_key,
                "ResponseContentDisposition": f'attachment; filename="{safe_filename}"',
            },
            ExpiresIn=expiry,
        )
    except (ClientError, BotoCoreError) as exc:
        logger.error("Error generating presigned download URL: %s", exc)
        return None


def delete_s3_object(s3_key):
    s3 = get_s3_client()
    try:
        s3.delete_object(Bucket=app.config["S3_BUCKET_NAME"], Key=s3_key)
        return True
    except (ClientError, BotoCoreError) as exc:
        logger.error("Error deleting S3 object %s: %s", s3_key, exc)
        return False


def _multipart_serializer():
    return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt=UPLOAD_TOKEN_SALT)


def _issue_upload_token(payload):
    token_payload = dict(payload)
    token_payload["token_nonce"] = secrets.token_hex(8)
    return _multipart_serializer().dumps(token_payload)


def _json_error(message, status=400, code=None):
    payload = {"error": message}
    if code:
        payload["code"] = code
    return jsonify(payload), status


def _client_error_code(exc):
    if not isinstance(exc, ClientError):
        return None
    return exc.response.get("Error", {}).get("Code")


def _required_json_object():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise UploadValidationError("A JSON request body is required.")
    return payload


def _normalise_csrf_time_limit_seconds(raw_value):
    if raw_value is None:
        return None
    if isinstance(raw_value, bool):
        raise RuntimeError("WTF_CSRF_TIME_LIMIT must be a non-negative number or None.")

    if hasattr(raw_value, "total_seconds"):
        raw_value = raw_value.total_seconds()

    try:
        seconds = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            "WTF_CSRF_TIME_LIMIT must be a non-negative number, timedelta, or None."
        ) from exc

    if seconds < 0:
        raise RuntimeError("WTF_CSRF_TIME_LIMIT must be non-negative.")
    return seconds


def _normalise_text(value, field_name, max_length, required=False):
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise UploadValidationError(f"{field_name} must be text.")
    value = value.strip()
    if required and not value:
        raise UploadValidationError(f"{field_name} is required.")
    if len(value) > max_length:
        raise UploadValidationError(
            f"{field_name} must be {max_length} characters or fewer."
        )
    return value or None


def _normalise_original_filename(value):
    if not isinstance(value, str):
        raise UploadValidationError("Filename is required.")

    # Browsers normally send only the basename, but strip either path separator
    # defensively in case a non-browser client supplies a path.
    filename = value.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not filename or filename in {".", ".."}:
        raise UploadValidationError("Filename is required.")
    if "\x00" in filename:
        raise UploadValidationError("Filename contains an invalid character.")
    if len(filename) > 255:
        raise UploadValidationError("Filename must be 255 characters or fewer.")

    extension = os.path.splitext(filename)[1].lower().lstrip(".")
    if extension not in ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            "Unsupported video format. Use MP4, AVI, MOV, MKV, or WebM."
        )
    return filename, extension


def _normalise_file_size(value):
    if isinstance(value, bool):
        raise UploadValidationError("File size is invalid.")
    try:
        file_size = int(value)
    except (TypeError, ValueError) as exc:
        raise UploadValidationError("File size is invalid.") from exc

    if file_size <= 0:
        raise UploadValidationError("The selected file is empty.")

    maximum = int(app.config["MAX_VIDEO_FILE_SIZE"])
    if file_size > maximum:
        raise UploadValidationError(
            f"The selected file exceeds the {maximum} byte upload limit."
        )
    return file_size


def _normalise_session_date(value):
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise UploadValidationError("Session date is invalid.")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise UploadValidationError("Session date must use YYYY-MM-DD format.") from exc


def _normalise_allow_download(value):
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    raise UploadValidationError("Allow download must be true or false.")


def _normalise_upload_metadata(payload):
    filename, extension = _normalise_original_filename(payload.get("filename"))
    file_size = _normalise_file_size(payload.get("file_size"))

    visibility = payload.get("visibility", "private")
    if visibility not in {"private", "shared", "public"}:
        raise UploadValidationError("Visibility is invalid.")

    return {
        "filename": filename,
        "extension": extension,
        # Use a canonical type derived from the validated extension rather than
        # trusting the browser-supplied MIME type.
        "content_type": CONTENT_TYPE_BY_EXTENSION[extension],
        "file_size": file_size,
        "session_date": _normalise_session_date(payload.get("session_date")),
        "notes": _normalise_text(payload.get("notes"), "Notes", 2000),
        "tags": _normalise_text(payload.get("tags"), "Tags", 500),
        "visibility": visibility,
        "allow_download": _normalise_allow_download(payload.get("allow_download")),
    }


def _load_upload_token(token):
    if not isinstance(token, str) or not token:
        raise UploadValidationError("Upload token is required.")

    try:
        payload = _multipart_serializer().loads(
            token,
            max_age=int(app.config["S3_MULTIPART_TOKEN_MAX_AGE"]),
        )
    except SignatureExpired as exc:
        raise UploadValidationError(
            "This upload session has expired. Start the upload again."
        ) from exc
    except BadSignature as exc:
        raise UploadValidationError("Upload token is invalid.") from exc

    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise UploadValidationError("Upload token is invalid.")
    if payload.get("user_id") != current_user.id:
        raise UploadValidationError("Upload token does not belong to this user.")

    required_fields = {
        "s3_key",
        "upload_id",
        "filename",
        "file_size",
        "content_type",
        "total_parts",
        "metadata",
    }
    if not required_fields.issubset(payload):
        raise UploadValidationError("Upload token is incomplete.")
    if not str(payload["s3_key"]).startswith(f"videos/{current_user.id}/"):
        raise UploadValidationError("Upload key is invalid.")

    raw_part_size = payload.get("part_size", app.config["S3_MULTIPART_PART_SIZE"])
    if isinstance(raw_part_size, bool):
        raise UploadValidationError("Upload token is invalid.")
    try:
        payload["part_size"] = int(raw_part_size)
    except (TypeError, ValueError) as exc:
        raise UploadValidationError("Upload token is invalid.") from exc
    if payload["part_size"] <= 0:
        raise UploadValidationError("Upload token is invalid.")
    return payload


def _expected_part_size(file_size, part_size, part_number, total_parts):
    if part_number < 1 or part_number > total_parts:
        raise UploadValidationError("Part number is invalid.")
    if part_number < total_parts:
        return part_size
    bytes_before_last = part_size * (total_parts - 1)
    return file_size - bytes_before_last


def _list_multipart_upload_parts(s3, s3_key, upload_id):
    all_parts = []
    part_number_marker = 0
    while True:
        response = s3.list_parts(
            Bucket=app.config["S3_BUCKET_NAME"],
            Key=s3_key,
            UploadId=upload_id,
            MaxParts=1000,
            PartNumberMarker=part_number_marker,
        )
        page_parts = response.get("Parts", [])
        if not isinstance(page_parts, list):
            raise UploadValidationError("S3 returned an invalid multipart part listing.")
        all_parts.extend(page_parts)
        if not response.get("IsTruncated"):
            break
        raw_next_marker = response.get("NextPartNumberMarker")
        if raw_next_marker is None:
            raw_next_marker = page_parts[-1].get("PartNumber") if page_parts else None
        try:
            next_marker = int(raw_next_marker)
        except (TypeError, ValueError) as exc:
            raise UploadValidationError(
                "S3 returned an invalid multipart part listing."
            ) from exc
        if next_marker <= part_number_marker:
            raise UploadValidationError("S3 returned an invalid multipart part listing.")
        part_number_marker = next_marker
    return all_parts


def _normalise_etag(etag):
    if not isinstance(etag, str):
        return ""
    return etag.strip().strip('"')


def _validate_uploaded_parts_against_s3(upload_payload, completed_parts, s3_parts):
    expected_count = int(upload_payload["total_parts"])
    if len(s3_parts) != expected_count:
        raise UploadValidationError(
            "Uploaded part data in S3 does not match this upload session."
        )

    expected_numbers = list(range(1, expected_count + 1))
    try:
        actual_numbers = [int(part.get("PartNumber", -1)) for part in s3_parts]
    except (TypeError, ValueError) as exc:
        raise UploadValidationError(
            "Uploaded part data in S3 does not match this upload session."
        ) from exc
    if actual_numbers != expected_numbers:
        raise UploadValidationError(
            "Uploaded part data in S3 does not match this upload session."
        )

    file_size = int(upload_payload["file_size"])
    part_size = int(upload_payload["part_size"])
    total_size = 0

    for index, s3_part in enumerate(s3_parts):
        part_number = expected_numbers[index]
        expected_size = _expected_part_size(
            file_size, part_size, part_number, expected_count
        )
        try:
            actual_size = int(s3_part.get("Size", -1))
        except (TypeError, ValueError) as exc:
            raise UploadValidationError(
                "Uploaded part data in S3 does not match this upload session."
            ) from exc
        if actual_size != expected_size:
            raise UploadValidationError(
                "Uploaded part data in S3 does not match this upload session."
            )
        total_size += actual_size

        expected_etag = _normalise_etag(completed_parts[index]["ETag"])
        actual_etag = _normalise_etag(s3_part.get("ETag"))
        if expected_etag != actual_etag:
            raise UploadValidationError(
                "Uploaded part data in S3 does not match this upload session."
            )

    if total_size != file_size:
        raise UploadValidationError(
            "Uploaded part data in S3 does not match this upload session."
        )


def _validate_completed_parts(parts, expected_count):
    if not isinstance(parts, list):
        raise UploadValidationError("Completed parts must be a list.")
    if len(parts) != expected_count:
        raise UploadValidationError(
            f"Expected {expected_count} uploaded parts, received {len(parts)}."
        )

    normalised = []
    seen = set()
    for item in parts:
        if not isinstance(item, dict):
            raise UploadValidationError("A completed part is invalid.")

        part_number = item.get("part_number")
        if isinstance(part_number, bool):
            raise UploadValidationError("A completed part number is invalid.")
        try:
            part_number = int(part_number)
        except (TypeError, ValueError) as exc:
            raise UploadValidationError("A completed part number is invalid.") from exc

        etag = item.get("etag")
        if not isinstance(etag, str) or not etag.strip() or len(etag) > 200:
            raise UploadValidationError("A completed part ETag is invalid.")

        if part_number in seen:
            raise UploadValidationError("Completed part numbers must be unique.")
        seen.add(part_number)
        normalised.append({"PartNumber": part_number, "ETag": etag.strip()})

    normalised.sort(key=lambda item: item["PartNumber"])
    expected_numbers = list(range(1, expected_count + 1))
    actual_numbers = [item["PartNumber"] for item in normalised]
    if actual_numbers != expected_numbers:
        raise UploadValidationError("Completed parts must be numbered consecutively.")
    return normalised


def _abort_multipart_upload(s3, s3_key, upload_id):
    try:
        s3.abort_multipart_upload(
            Bucket=app.config["S3_BUCKET_NAME"],
            Key=s3_key,
            UploadId=upload_id,
        )
    except ClientError as exc:
        if _client_error_code(exc) != "NoSuchUpload":
            raise


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)

    return decorated


def _normalise_email(email):
    return (email or "").lower().strip()


def _request_ip():
    return request.headers.get(
        "X-Forwarded-For", request.remote_addr or ""
    ).split(",")[0].strip()


def _user_agent():
    return (request.headers.get("User-Agent") or "")[:255]


def _app_link(endpoint, **values):
    """Build absolute app links from APP_BASE_URL so production links are not localhost."""
    base_url = app.config["APP_BASE_URL"].rstrip("/")
    return f"{base_url}{url_for(endpoint, **values)}"


def _generic_email_confirmation(link_type):
    if link_type == "reset":
        return "If an active account exists for that email, a password reset link has been sent."
    return "If an active account exists for that email, a magic login link has been sent."


def _auth_email_log_label(purpose):
    if purpose == AuthToken.PURPOSE_RESET_PASSWORD:
        return "reset"
    if purpose == AuthToken.PURPOSE_MAGIC_LOGIN:
        return "magic-login"
    return "unknown"


def _is_auth_email_throttled(user_id, purpose):
    cooldown_seconds = int(app.config["AUTH_EMAIL_COOLDOWN_SECONDS"])
    if cooldown_seconds <= 0:
        return False

    cutoff = datetime.utcnow() - timedelta(seconds=cooldown_seconds)
    return db.session.query(AuthToken.id).filter(
        AuthToken.user_id == user_id,
        AuthToken.purpose == purpose,
        AuthToken.used_at.is_(None),
        AuthToken.created_at >= cutoff,
    ).first() is not None


def _send_password_reset_email(user, raw_token):
    reset_url = _app_link("reset_password", token=raw_token)
    ttl = int(app.config["PASSWORD_RESET_TOKEN_TTL_MINUTES"])

    subject = "Reset your Badminton Video Vault password"
    text_body = (
        f"Hello {user.name},\n\n"
        "We received a request to reset your Badminton Video Vault password.\n\n"
        f"Reset your password here: {reset_url}\n\n"
        f"This link expires in {ttl} minutes and can only be used once.\n\n"
        "If you did not request this, you can ignore this email."
    )
    html_body = render_template(
        "emails/password_reset.html",
        user=user,
        reset_url=reset_url,
        ttl_minutes=ttl,
    )
    return send_mailgun_email(
        user.email,
        subject,
        text_body,
        html_body=html_body,
        tag="password-reset",
    )


def _send_magic_login_email(user, raw_token):
    magic_url = _app_link("consume_magic_login", token=raw_token)
    ttl = int(app.config["MAGIC_LOGIN_TOKEN_TTL_MINUTES"])

    subject = "Your Badminton Video Vault magic login link"
    text_body = (
        f"Hello {user.name},\n\n"
        "Use this one-time link to log in to Badminton Video Vault:\n\n"
        f"{magic_url}\n\n"
        f"This link expires in {ttl} minutes and can only be used once.\n\n"
        "If you did not request this, you can ignore this email."
    )
    html_body = render_template(
        "emails/magic_login.html",
        user=user,
        magic_url=magic_url,
        ttl_minutes=ttl,
    )
    return send_mailgun_email(
        user.email,
        subject,
        text_body,
        html_body=html_body,
        tag="magic-login",
    )


def _issue_auth_token_email(user, purpose):
    if purpose == AuthToken.PURPOSE_RESET_PASSWORD:
        ttl = int(app.config["PASSWORD_RESET_TOKEN_TTL_MINUTES"])
    elif purpose == AuthToken.PURPOSE_MAGIC_LOGIN:
        ttl = int(app.config["MAGIC_LOGIN_TOKEN_TTL_MINUTES"])
    else:
        raise ValueError(f"Unknown auth token purpose: {purpose}")

    if _is_auth_email_throttled(user.id, purpose):
        logger.info(
            "Skipping auth email for user_id=%s type=%s during cooldown",
            user.id,
            _auth_email_log_label(purpose),
        )
        return

    raw_token, _ = AuthToken.create_for_user(
        user=user,
        purpose=purpose,
        ttl_minutes=ttl,
        created_ip=_request_ip(),
        user_agent=_user_agent(),
    )
    db.session.commit()

    try:
        if purpose == AuthToken.PURPOSE_RESET_PASSWORD:
            _send_password_reset_email(user, raw_token)
        else:
            _send_magic_login_email(user, raw_token)
    except EmailDeliveryError as exc:
        logger.error(
            "Auth email delivery failed for user_id=%s type=%s: %s",
            user.id,
            _auth_email_log_label(purpose),
            exc,
        )


def _find_active_user_by_email(email):
    user = User.query.filter_by(email=_normalise_email(email)).first()
    if not user or not user.is_active:
        return None
    return user


# ---------------------------------------------------------------------------
# Flask-Login user loader
# ---------------------------------------------------------------------------


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith("/api/"):
        return _json_error("Your login session has expired. Sign in and try again.", 401)
    flash(login_manager.login_message, login_manager.login_message_category)
    return redirect(url_for("login", next=request.url))


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=_normalise_email(form.email.data)).first()
        if user and user.is_active and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = _find_active_user_by_email(form.email.data)
        if user:
            _issue_auth_token_email(user, AuthToken.PURPOSE_RESET_PASSWORD)

        flash(_generic_email_confirmation("reset"), "info")
        return redirect(url_for("login"))

    return render_template("forgot_password.html", form=form)


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    auth_token = AuthToken.find_usable(token, AuthToken.PURPOSE_RESET_PASSWORD)
    if not auth_token:
        flash(
            "This password reset link is invalid, expired, or has already been used.",
            "danger",
        )
        return redirect(url_for("forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = auth_token.user
        user.set_password(form.password.data)
        auth_token.mark_used()
        AuthToken.invalidate_unused(
            user_id=user.id,
            purpose=AuthToken.PURPOSE_RESET_PASSWORD,
            exclude_id=auth_token.id,
        )
        db.session.commit()

        flash(
            "Your password has been reset. Please log in with your new password.",
            "success",
        )
        return redirect(url_for("login"))

    return render_template("reset_password.html", form=form)


@app.route("/magic-login", methods=["GET", "POST"])
def magic_login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    form = MagicLoginForm()
    if form.validate_on_submit():
        user = _find_active_user_by_email(form.email.data)
        if user:
            _issue_auth_token_email(user, AuthToken.PURPOSE_MAGIC_LOGIN)

        flash(_generic_email_confirmation("magic"), "info")
        return redirect(url_for("login"))

    return render_template("magic_login.html", form=form)


@app.route("/magic-login/<token>")
def consume_magic_login(token):
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    auth_token = AuthToken.find_usable(token, AuthToken.PURPOSE_MAGIC_LOGIN)
    if not auth_token:
        flash(
            "This magic login link is invalid, expired, or has already been used.",
            "danger",
        )
        return redirect(url_for("magic_login"))

    user = auth_token.user
    auth_token.mark_used()
    AuthToken.invalidate_unused(
        user_id=user.id,
        purpose=AuthToken.PURPOSE_MAGIC_LOGIN,
        exclude_id=auth_token.id,
    )
    db.session.commit()

    login_user(user)
    flash("You have been logged in using your magic link.", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# Main routes
# ---------------------------------------------------------------------------


@app.route("/")
@login_required
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
@login_required
def dashboard():
    total_videos = Video.query.filter_by(uploaded_by_user_id=current_user.id).count()
    recent_videos = (
        Video.query.filter_by(uploaded_by_user_id=current_user.id)
        .order_by(Video.created_at.desc())
        .limit(5)
        .all()
    )
    return render_template(
        "dashboard.html", total_videos=total_videos, recent_videos=recent_videos
    )


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    form = UploadVideoForm()

    # static/upload.js coordinates the upload. With JavaScript disabled, never
    # accept a multipart video body through Flask.
    if request.method == "POST":
        flash(
            "Direct video upload requires JavaScript. Enable JavaScript and try again.",
            "warning",
        )

    csrf_token_lifetime_seconds = _normalise_csrf_time_limit_seconds(
        app.config.get("WTF_CSRF_TIME_LIMIT", 3600)
    )
    return render_template(
        "upload.html",
        form=form,
        max_video_file_size=int(app.config["MAX_VIDEO_FILE_SIZE"]),
        multipart_upload_concurrency=int(app.config["S3_MULTIPART_CONCURRENCY"]),
        csrf_token_lifetime_seconds=csrf_token_lifetime_seconds,
    )


@app.get("/api/csrf-token")
@login_required
def api_csrf_token():
    try:
        expires_in = _normalise_csrf_time_limit_seconds(
            app.config.get("WTF_CSRF_TIME_LIMIT", 3600)
        )
    except RuntimeError as exc:
        logger.error("Invalid WTF_CSRF_TIME_LIMIT: %s", exc)
        return _json_error(
            "CSRF configuration is invalid.",
            500,
            code="csrf_config_invalid",
        )

    response = jsonify(
        {
            "csrf_token": generate_csrf(),
            "expires_in": expires_in,
        }
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.post("/api/uploads/multipart/initiate")
@login_required
def multipart_upload_initiate():
    try:
        metadata = _normalise_upload_metadata(_required_json_object())
    except UploadValidationError as exc:
        return _json_error(str(exc))

    part_size = int(app.config["S3_MULTIPART_PART_SIZE"])
    total_parts = math.ceil(metadata["file_size"] / part_size)
    if total_parts > S3_MAX_MULTIPART_PARTS:
        return _json_error(
            "The selected file requires too many multipart-upload parts."
        )

    unique_name = f"{secrets.token_hex(16)}.{metadata['extension']}"
    s3_key = f"videos/{current_user.id}/{unique_name}"
    s3 = get_s3_client()
    upload_id = None

    try:
        response = s3.create_multipart_upload(
            Bucket=app.config["S3_BUCKET_NAME"],
            Key=s3_key,
            ContentType=metadata["content_type"],
        )
        upload_id = response["UploadId"]

        part_urls = [
            {
                "part_number": part_number,
                "url": generate_presigned_part_url(
                    s3_key,
                    upload_id,
                    part_number,
                    _expected_part_size(
                        metadata["file_size"], part_size, part_number, total_parts
                    ),
                    s3=s3,
                ),
            }
            for part_number in range(1, total_parts + 1)
        ]
    except (ClientError, BotoCoreError, KeyError) as exc:
        if upload_id:
            try:
                _abort_multipart_upload(s3, s3_key, upload_id)
            except (ClientError, BotoCoreError):
                logger.exception(
                    "Failed to clean up multipart upload after initiation error"
                )
        logger.exception("Could not initiate S3 multipart upload: %s", exc)
        return _json_error("Could not start the S3 upload. Please try again.", 502)

    upload_token = _issue_upload_token(
        {
            "version": 1,
            "user_id": current_user.id,
            "s3_key": s3_key,
            "upload_id": upload_id,
            "filename": metadata["filename"],
            "file_size": metadata["file_size"],
            "content_type": metadata["content_type"],
            "total_parts": total_parts,
            "part_size": part_size,
            "metadata": {
                "session_date": metadata["session_date"],
                "notes": metadata["notes"],
                "tags": metadata["tags"],
                "visibility": metadata["visibility"],
                "allow_download": metadata["allow_download"],
            },
        }
    )

    return jsonify(
        {
            "upload_token": upload_token,
            "part_size": part_size,
            "total_parts": total_parts,
            "parts": part_urls,
            "expires_in": int(app.config["S3_MULTIPART_URL_EXPIRY"]),
            "upload_token_expires_in": int(app.config["S3_MULTIPART_TOKEN_MAX_AGE"]),
        }
    )


@app.post("/api/uploads/multipart/complete")
@login_required
def multipart_upload_complete():
    try:
        request_payload = _required_json_object()
        upload_payload = _load_upload_token(request_payload.get("upload_token"))
        completed_parts = _validate_completed_parts(
            request_payload.get("parts"),
            int(upload_payload["total_parts"]),
        )
    except UploadValidationError as exc:
        return _json_error(str(exc))

    existing = Video.query.filter_by(s3_key=upload_payload["s3_key"]).first()
    if existing:
        if existing.uploaded_by_user_id != current_user.id:
            return _json_error("The upload record belongs to another user.", 403)
        return jsonify(
            {
                "video_id": existing.id,
                "redirect_url": url_for("video_detail", video_id=existing.id),
            }
        )

    s3 = get_s3_client()
    try:
        s3_parts = _list_multipart_upload_parts(
            s3, upload_payload["s3_key"], upload_payload["upload_id"]
        )
        _validate_uploaded_parts_against_s3(upload_payload, completed_parts, s3_parts)
        s3.complete_multipart_upload(
            Bucket=app.config["S3_BUCKET_NAME"],
            Key=upload_payload["s3_key"],
            UploadId=upload_payload["upload_id"],
            MultipartUpload={"Parts": completed_parts},
        )
        head = s3.head_object(
            Bucket=app.config["S3_BUCKET_NAME"],
            Key=upload_payload["s3_key"],
        )
    except ClientError as exc:
        code = _client_error_code(exc)
        logger.exception("Could not complete S3 multipart upload: %s", exc)
        if code == "NoSuchUpload":
            return _json_error(
                "This upload session no longer exists. Start the upload again.",
                409,
            )
        return _json_error("S3 could not complete the upload. Please try again.", 502)
    except BotoCoreError as exc:
        logger.exception("Could not complete S3 multipart upload: %s", exc)
        return _json_error("S3 could not complete the upload. Please try again.", 502)
    except UploadValidationError as exc:
        logger.warning(
            "Rejecting multipart completion for %s: %s",
            upload_payload["s3_key"],
            exc,
        )
        try:
            _abort_multipart_upload(
                s3,
                upload_payload["s3_key"],
                upload_payload["upload_id"],
            )
        except (ClientError, BotoCoreError):
            logger.exception("Could not abort invalid multipart upload")
        return _json_error(str(exc), 409)

    actual_size = int(head.get("ContentLength", -1))
    if actual_size != int(upload_payload["file_size"]):
        logger.error(
            "Completed upload size mismatch for %s: expected=%s actual=%s",
            upload_payload["s3_key"],
            upload_payload["file_size"],
            actual_size,
        )
        try:
            s3.delete_object(
                Bucket=app.config["S3_BUCKET_NAME"],
                Key=upload_payload["s3_key"],
            )
        except (ClientError, BotoCoreError):
            logger.exception("Could not delete S3 object after size mismatch")
        return _json_error(
            "The completed S3 object size did not match the selected file. Upload it again.",
            409,
        )

    metadata = upload_payload["metadata"]
    session_date = (
        date.fromisoformat(metadata["session_date"])
        if metadata.get("session_date")
        else None
    )
    video = Video(
        filename=upload_payload["filename"],
        s3_key=upload_payload["s3_key"],
        uploaded_by_user_id=current_user.id,
        session_date=session_date,
        file_size=upload_payload["file_size"],
        notes=metadata.get("notes"),
        tags=metadata.get("tags"),
        visibility=metadata["visibility"],
        allow_download=bool(metadata["allow_download"]),
    )
    if video.visibility == "shared":
        video.share_token = secrets.token_urlsafe(32)
        video.share_expires_at = datetime.utcnow() + timedelta(days=30)

    try:
        db.session.add(video)
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.exception("Could not save completed upload metadata: %s", exc)
        try:
            s3.delete_object(
                Bucket=app.config["S3_BUCKET_NAME"],
                Key=upload_payload["s3_key"],
            )
        except (ClientError, BotoCoreError):
            logger.exception(
                "Could not remove orphaned S3 object after database error"
            )
        return _json_error(
            "The video uploaded, but its metadata could not be saved.", 500
        )

    flash("Video uploaded successfully!", "success")
    return jsonify(
        {
            "video_id": video.id,
            "redirect_url": url_for("video_detail", video_id=video.id),
        }
    )


@app.post("/api/uploads/multipart/refresh-part")
@login_required
def multipart_upload_refresh_part():
    try:
        request_payload = _required_json_object()
        upload_payload = _load_upload_token(request_payload.get("upload_token"))
        part_number = request_payload.get("part_number")
        if isinstance(part_number, bool) or not isinstance(part_number, int):
            raise UploadValidationError("Part number is invalid.")
        total_parts = int(upload_payload["total_parts"])
        if part_number < 1 or part_number > total_parts:
            raise UploadValidationError("Part number is invalid.")
    except UploadValidationError as exc:
        return _json_error(str(exc))

    s3 = get_s3_client()
    try:
        url = generate_presigned_part_url(
            upload_payload["s3_key"],
            upload_payload["upload_id"],
            part_number,
            _expected_part_size(
                int(upload_payload["file_size"]),
                int(upload_payload["part_size"]),
                part_number,
                total_parts,
            ),
            s3=s3,
        )
    except (ClientError, BotoCoreError) as exc:
        logger.exception("Could not refresh presigned part URL: %s", exc)
        return _json_error("Could not refresh the upload URL. Please try again.", 502)

    refreshed_upload_token = _issue_upload_token(upload_payload)

    return jsonify(
        {
            "part_number": part_number,
            "url": url,
            "expires_in": int(app.config["S3_MULTIPART_URL_EXPIRY"]),
            "upload_token": refreshed_upload_token,
            "upload_token_expires_in": int(app.config["S3_MULTIPART_TOKEN_MAX_AGE"]),
        }
    )


@app.post("/api/uploads/multipart/abort")
@login_required
def multipart_upload_abort():
    try:
        request_payload = _required_json_object()
        upload_payload = _load_upload_token(request_payload.get("upload_token"))
    except UploadValidationError as exc:
        return _json_error(str(exc))

    s3 = get_s3_client()
    try:
        _abort_multipart_upload(
            s3,
            upload_payload["s3_key"],
            upload_payload["upload_id"],
        )
    except (ClientError, BotoCoreError) as exc:
        logger.exception("Could not abort S3 multipart upload: %s", exc)
        return _json_error("Could not cancel the S3 upload.", 502)

    return jsonify({"aborted": True})


@app.route("/videos")
@login_required
def videos():
    page = request.args.get("page", 1, type=int)
    tag_filter = request.args.get("tag", "").strip()
    visibility_filter = request.args.get("visibility", "").strip()

    query = Video.query.filter(
        or_(
            Video.uploaded_by_user_id == current_user.id,
            Video.visibility == "public",
        )
    )

    if tag_filter:
        query = query.filter(Video.tags.ilike(f"%{tag_filter}%"))
    if visibility_filter:
        query = query.filter(Video.visibility == visibility_filter)

    pagination = query.order_by(Video.created_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )
    return render_template(
        "videos.html",
        pagination=pagination,
        tag_filter=tag_filter,
        visibility_filter=visibility_filter,
    )


@app.route("/videos/<int:video_id>", methods=["GET", "POST"])
@login_required
def video_detail(video_id):
    video = db.session.get(Video, video_id)
    if video is None:
        abort(404)

    can_edit = video.uploaded_by_user_id == current_user.id or current_user.is_admin
    if not can_edit and video.visibility != "public":
        abort(403)

    form = EditVideoForm(obj=video) if can_edit else None
    if form and form.validate_on_submit():
        video.session_date = form.session_date.data
        video.notes = form.notes.data
        video.tags = form.tags.data
        video.visibility = form.visibility.data
        video.allow_download = form.allow_download.data

        if video.visibility == "shared" and (
            not video.share_token
            or (
                video.share_expires_at
                and video.share_expires_at < datetime.utcnow()
            )
        ):
            video.share_token = secrets.token_urlsafe(32)
            video.share_expires_at = datetime.utcnow() + timedelta(days=30)
        elif video.visibility != "shared":
            video.share_token = None
            video.share_expires_at = None

        db.session.commit()
        flash("Video details updated.", "success")
        return redirect(url_for("video_detail", video_id=video.id))

    play_url = generate_presigned_play_url(video.s3_key)
    download_url = None
    if video.allow_download:
        download_url = generate_presigned_download_url(video.s3_key, video.filename)

    return render_template(
        "video_detail.html",
        video=video,
        form=form,
        play_url=play_url,
        download_url=download_url,
    )


@app.route("/videos/<int:video_id>/delete", methods=["POST"])
@login_required
def delete_video(video_id):
    video = db.session.get(Video, video_id)
    if video is None:
        abort(404)
    if video.uploaded_by_user_id != current_user.id and not current_user.is_admin:
        abort(403)

    s3_deleted = delete_s3_object(video.s3_key)
    if not s3_deleted:
        flash(
            "Could not delete the video file from storage. The video record has been kept.",
            "danger",
        )
        return redirect(url_for("video_detail", video_id=video_id))

    db.session.delete(video)
    db.session.commit()
    flash("Video deleted.", "success")
    return redirect(url_for("videos"))


@app.route("/share/<token>")
def shared_video(token):
    """Public share link — no login required."""
    video = Video.query.filter_by(share_token=token).first_or_404()
    if video.visibility not in ("shared", "public"):
        abort(404)
    if video.share_expires_at and video.share_expires_at < datetime.utcnow():
        abort(410)

    play_url = generate_presigned_play_url(video.s3_key)
    download_url = None
    if video.allow_download:
        download_url = generate_presigned_download_url(video.s3_key, video.filename)

    return render_template(
        "video_detail.html",
        video=video,
        form=None,
        play_url=play_url,
        download_url=download_url,
        shared_view=True,
    )


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------


@app.route("/admin/users")
@login_required
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    video_counts = dict(
        db.session.query(Video.uploaded_by_user_id, func.count(Video.id))
        .group_by(Video.uploaded_by_user_id)
        .all()
    )
    return render_template(
        "admin_users.html", users=users, video_counts=video_counts
    )


@app.route("/admin/users/create", methods=["GET", "POST"])
@login_required
@admin_required
def admin_create_user():
    form = CreateUserForm()
    if form.validate_on_submit():
        existing = User.query.filter_by(email=_normalise_email(form.email.data)).first()
        if existing:
            flash("A user with that email already exists.", "danger")
            return render_template("admin_create_user.html", form=form)

        user = User(
            name=form.name.data,
            email=_normalise_email(form.email.data),
            role=form.role.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(f"User {user.email} created successfully.", "success")
        return redirect(url_for("admin_users"))

    return render_template("admin_create_user.html", form=form)


@app.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@admin_required
def admin_toggle_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    if user.id == current_user.id:
        flash("You cannot deactivate your own account.", "warning")
        return redirect(url_for("admin_users"))
    user.is_active = not user.is_active
    db.session.commit()
    status = "activated" if user.is_active else "deactivated"
    flash(f"User {user.email} has been {status}.", "success")
    return redirect(url_for("admin_users"))


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------


@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    if request.path.startswith("/api/"):
        return _json_error(
            e.description or "CSRF token is missing or invalid.",
            400,
            code="csrf_failed",
        )
    return render_template(
        "error.html",
        code=400,
        message="The form security token is invalid or expired. Refresh and try again.",
    ), 400


@app.errorhandler(403)
def forbidden(e):
    return render_template(
        "error.html",
        code=403,
        message="You don't have permission to access this page.",
    ), 403


@app.errorhandler(404)
def not_found(e):
    return render_template(
        "error.html", code=404, message="The page you're looking for doesn't exist."
    ), 404


@app.errorhandler(410)
def gone(e):
    return render_template(
        "error.html", code=410, message="This share link has expired."
    ), 410


@app.errorhandler(413)
def request_too_large(e):
    if request.path.startswith("/api/"):
        return _json_error("The request body is too large.", 413)
    return render_template(
        "error.html",
        code=413,
        message="This request is too large. Video files must be uploaded directly to S3.",
    ), 413


@app.errorhandler(500)
def server_error(e):
    return render_template(
        "error.html", code=500, message="An internal server error occurred."
    ), 500


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


@app.cli.command("init-db")
def init_db():
    """Create database tables (run once before first use)."""
    import click

    with app.app_context():
        db.create_all()
    click.echo("Database tables created.")


@app.cli.command("create-admin")
def create_admin():
    """Create an initial admin user interactively."""
    import click

    email = click.prompt("Admin email")
    name = click.prompt("Admin name")
    password = click.prompt(
        "Admin password", hide_input=True, confirmation_prompt=True
    )

    existing = User.query.filter_by(email=_normalise_email(email)).first()
    if existing:
        click.echo(f"User {email} already exists.")
        return

    user = User(name=name, email=_normalise_email(email), role="admin")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f"Admin user {email} created successfully.")


@app.context_processor
def inject_now():
    return {"now": datetime.utcnow()}


if __name__ == "__main__":
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(debug=debug)
