import os
import secrets
import logging
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError
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
from functools import wraps

from config import Config
from extensions import db, login_manager
from models import User, Video
from forms import LoginForm, UploadVideoForm, EditVideoForm, CreateUserForm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    with app.app_context():
        db.create_all()

    return app


app = create_app()


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
    except ClientError as exc:
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
    except ClientError as exc:
        logger.error("Error generating presigned play URL: %s", exc)
        return None


def generate_presigned_download_url(s3_key, filename, expiry=None):
    """Return a presigned GET URL that triggers a file download."""
    s3 = get_s3_client()
    expiry = expiry or app.config["PRESIGNED_URL_EXPIRY"]
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": app.config["S3_BUCKET_NAME"],
                "Key": s3_key,
                "ResponseContentDisposition": f'attachment; filename="{filename}"',
            },
            ExpiresIn=expiry,
        )
        return url
    except ClientError as exc:
        logger.error("Error generating presigned download URL: %s", exc)
        return None


def delete_s3_object(s3_key):
    s3 = get_s3_client()
    try:
        s3.delete_object(Bucket=app.config["S3_BUCKET_NAME"], Key=s3_key)
        return True
    except ClientError as exc:
        logger.error("Error deleting S3 object %s: %s", s3_key, exc)
        return False





def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


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
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
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
    presigned_url = None
    s3_key = None

    if form.validate_on_submit():
        file = form.video_file.data
        original_filename = file.filename
        extension = os.path.splitext(original_filename)[1].lower()
        unique_name = f"{secrets.token_hex(16)}{extension}"
        s3_key = f"videos/{current_user.id}/{unique_name}"

        content_type = file.content_type or "video/mp4"
        presigned_url = generate_presigned_upload_url(s3_key, content_type)

        if not presigned_url:
            flash("Could not generate upload URL. Check your AWS configuration.", "danger")
            return render_template("upload.html", form=form)

        # Read file size before streaming
        file.stream.seek(0, 2)
        file_size = file.stream.tell()
        file.stream.seek(0)

        # Upload directly via boto3 (server-side) for simplicity in MVP
        s3 = get_s3_client()
        try:
            s3.upload_fileobj(
                file.stream,
                app.config["S3_BUCKET_NAME"],
                s3_key,
                ExtraArgs={"ContentType": content_type},
            )
        except ClientError as exc:
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

    query = Video.query.filter_by(uploaded_by_user_id=current_user.id)

    if tag_filter:
        query = query.filter(Video.tags.ilike(f"%{tag_filter}%"))
    if visibility_filter:
        query = query.filter_by(visibility=visibility_filter)

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
    # Only the uploader or an admin can view
    if video.uploaded_by_user_id != current_user.id and not current_user.is_admin:
        abort(403)

    form = EditVideoForm(obj=video)
    if form.validate_on_submit():
        video.session_date = form.session_date.data
        video.notes = form.notes.data
        video.tags = form.tags.data
        video.visibility = form.visibility.data
        video.allow_download = form.allow_download.data

        if video.visibility == "shared" and not video.share_token:
            video.share_token = secrets.token_urlsafe(32)
            video.share_expires_at = datetime.utcnow() + timedelta(days=30)

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

    delete_s3_object(video.s3_key)
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
    return render_template("admin_users.html", users=users)


@app.route("/admin/users/create", methods=["GET", "POST"])
@login_required
@admin_required
def admin_create_user():
    form = CreateUserForm()
    if form.validate_on_submit():
        existing = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if existing:
            flash("A user with that email already exists.", "danger")
            return render_template("admin_create_user.html", form=form)

        user = User(
            name=form.name.data,
            email=form.email.data.lower().strip(),
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

@app.cli.command("create-admin")
def create_admin():
    """Create an initial admin user interactively."""
    import click
    email = click.prompt("Admin email")
    name = click.prompt("Admin name")
    password = click.prompt("Admin password", hide_input=True, confirmation_prompt=True)

    existing = User.query.filter_by(email=email.lower().strip()).first()
    if existing:
        click.echo(f"User {email} already exists.")
        return

    user = User(name=name, email=email.lower().strip(), role="admin")
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
