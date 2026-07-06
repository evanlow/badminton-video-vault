import os
import secrets
import logging
from datetime import datetime, timedelta
from functools import wraps

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    abort,
)
from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user,
)
from sqlalchemy import func, or_
from werkzeug.utils import secure_filename

from config import Config
from email_service import EmailDeliveryError, send_mailgun_email
from extensions import db, login_manager, csrf
from models import AuthToken, User, Video
from forms import (
    CreateUserForm,
    EditVideoForm,
    ForgotPasswordForm,
    LoginForm,
    MagicLoginForm,
    ResetPasswordForm,
    UploadVideoForm,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"mp4", "avi", "mov", "mkv", "webm"}
ALLOWED_MIME_TYPES = {
    "video/mp4",
    "video/avi",
    "video/x-msvideo",
    "video/quicktime",
    "video/x-matroska",
    "video/webm",
}


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
# Helpers
# ---------------------------------------------------------------------------

def get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=app.config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=app.config["AWS_SECRET_ACCESS_KEY"],
        region_name=app.config["AWS_REGION"],
    )


def generate_presigned_upload_url(s3_key, content_type, expiry=None):
    """Return a presigned PUT URL for direct browser-to-S3 upload."""
    s3 = get_s3_client()
    expiry = expiry or app.config["PRESIGNED_URL_EXPIRY"]
    try:
        url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": app.config["S3_BUCKET_NAME"],
                "Key": s3_key,
                "ContentType": content_type,
            },
            ExpiresIn=expiry,
        )
        return url
    except (ClientError, BotoCoreError) as exc:
        logger.error("Error generating presigned upload URL: %s", exc)
        return None


def generate_presigned_play_url(s3_key, expiry=None):
    """Return a presigned GET URL for streaming/playback."""
    s3 = get_s3_client()
    expiry = expiry or app.config["PRESIGNED_URL_EXPIRY"]
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": app.config["S3_BUCKET_NAME"], "Key": s3_key},
            ExpiresIn=expiry,
        )
        return url
    except (ClientError, BotoCoreError) as exc:
        logger.error("Error generating presigned play URL: %s", exc)
        return None


def generate_presigned_download_url(s3_key, filename, expiry=None):
    """Return a presigned GET URL that triggers a file download."""
    safe_filename = secure_filename(filename) or "download"
    s3 = get_s3_client()
    expiry = expiry or app.config["PRESIGNED_URL_EXPIRY"]
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": app.config["S3_BUCKET_NAME"],
                "Key": s3_key,
                "ResponseContentDisposition": f'attachment; filename="{safe_filename}"',
            },
            ExpiresIn=expiry,
        )
        return url
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
    return request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()


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
        flash("This password reset link is invalid, expired, or has already been used.", "danger")
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

        flash("Your password has been reset. Please log in with your new password.", "success")
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
        flash("This magic login link is invalid, expired, or has already been used.", "danger")
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
    return render_template("dashboard.html", total_videos=total_videos, recent_videos=recent_videos)


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    form = UploadVideoForm()

    if form.validate_on_submit():
        file = form.video_file.data
        original_filename = file.filename
        if not original_filename:
            flash("No file selected.", "danger")
            return render_template("upload.html", form=form)

        extension = os.path.splitext(original_filename)[1].lower().lstrip(".")
        if extension not in ALLOWED_EXTENSIONS:
            flash("Invalid file type. Please upload a video file (mp4, avi, mov, mkv, webm).", "danger")
            return render_template("upload.html", form=form)

        content_type = file.content_type or "video/mp4"
        if content_type not in ALLOWED_MIME_TYPES:
            flash("Invalid file type. Please upload a video file.", "danger")
            return render_template("upload.html", form=form)

        unique_name = f"{secrets.token_hex(16)}.{extension}"
        s3_key = f"videos/{current_user.id}/{unique_name}"

        # Read file size before streaming
        file.stream.seek(0, 2)
        file_size = file.stream.tell()
        file.stream.seek(0)

        # Upload directly via boto3 (server-side)
        s3 = get_s3_client()
        try:
            s3.upload_fileobj(
                file.stream,
                app.config["S3_BUCKET_NAME"],
                s3_key,
                ExtraArgs={"ContentType": content_type},
            )
        except (ClientError, BotoCoreError) as exc:
            logger.error("S3 upload failed: %s", exc)
            flash("Upload to S3 failed. Please try again.", "danger")
            return render_template("upload.html", form=form)

        video = Video(
            filename=original_filename,
            s3_key=s3_key,
            uploaded_by_user_id=current_user.id,
            session_date=form.session_date.data,
            file_size=file_size,
            notes=form.notes.data,
            tags=form.tags.data,
            visibility=form.visibility.data,
            allow_download=form.allow_download.data,
        )
        if video.visibility == "shared":
            video.share_token = secrets.token_urlsafe(32)
            video.share_expires_at = datetime.utcnow() + timedelta(days=30)

        db.session.add(video)
        db.session.commit()
        flash("Video uploaded successfully!", "success")
        return redirect(url_for("video_detail", video_id=video.id))

    return render_template("upload.html", form=form)


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

    pagination = query.order_by(Video.created_at.desc()).paginate(page=page, per_page=12, error_out=False)
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
    # Allow access if owner, admin, or video is public
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
            or (video.share_expires_at and video.share_expires_at < datetime.utcnow())
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
        flash("Could not delete the video file from storage. The video record has been kept.", "danger")
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
        abort(410)  # Gone

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
    return render_template("admin_users.html", users=users, video_counts=video_counts)


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

@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="You don't have permission to access this page."), 403


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="The page you're looking for doesn't exist."), 404


@app.errorhandler(410)
def gone(e):
    return render_template("error.html", code=410, message="This share link has expired."), 410


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500, message="An internal server error occurred."), 500


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
    password = click.prompt("Admin password", hide_input=True, confirmation_prompt=True)

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
