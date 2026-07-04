from datetime import datetime
from flask import current_app
from flask_login import UserMixin
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

# Token lifetimes, in seconds.
RESET_PASSWORD_TOKEN_MAX_AGE = 30 * 60  # 30 minutes
MAGIC_LOGIN_TOKEN_MAX_AGE = 15 * 60  # 15 minutes


def _get_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # "admin" or "user"
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # Timestamp of the last successful magic-link login, used to prevent a
    # single magic-link token from being replayed more than once.
    last_magic_login_at = db.Column(db.DateTime, nullable=True)

    videos = db.relationship("Video", back_populates="uploader", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"

    # ------------------------------------------------------------------
    # Password reset tokens
    # ------------------------------------------------------------------

    def get_reset_password_token(self):
        """Return a signed, time-limited token for resetting this user's password.

        The token embeds a fragment of the current password hash so that it
        is automatically invalidated once the password has been changed.
        """
        serializer = _get_serializer()
        return serializer.dumps(
            {"user_id": self.id, "hash": self.password_hash[:32]},
            salt="password-reset",
        )

    @staticmethod
    def verify_reset_password_token(token):
        serializer = _get_serializer()
        try:
            data = serializer.loads(
                token, salt="password-reset", max_age=RESET_PASSWORD_TOKEN_MAX_AGE
            )
        except (BadSignature, SignatureExpired):
            return None
        user = db.session.get(User, data.get("user_id"))
        if not user or data.get("hash") != user.password_hash[:32]:
            return None
        return user

    # ------------------------------------------------------------------
    # Magic-link login tokens
    # ------------------------------------------------------------------

    def get_magic_login_token(self):
        serializer = _get_serializer()
        return serializer.dumps({"user_id": self.id}, salt="magic-login")

    @staticmethod
    def verify_magic_login_token(token):
        serializer = _get_serializer()
        try:
            data, issued_at = serializer.loads(
                token,
                salt="magic-login",
                max_age=MAGIC_LOGIN_TOKEN_MAX_AGE,
                return_timestamp=True,
            )
        except (BadSignature, SignatureExpired):
            return None
        user = db.session.get(User, data.get("user_id"))
        if not user or not user.is_active:
            return None
        issued_at = issued_at.replace(tzinfo=None)
        if user.last_magic_login_at and issued_at <= user.last_magic_login_at:
            # This token has already been used to log in once.
            return None
        user.last_magic_login_at = datetime.utcnow()
        db.session.commit()
        return user

    def __repr__(self):
        return f"<User {self.email}>"


class Video(db.Model):
    __tablename__ = "videos"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    s3_key = db.Column(db.String(1024), nullable=False, unique=True)
    uploaded_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    session_date = db.Column(db.Date, nullable=True)
    file_size = db.Column(db.BigInteger, nullable=True)  # bytes
    notes = db.Column(db.Text, nullable=True)
    tags = db.Column(db.String(500), nullable=True)  # comma-separated tags
    visibility = db.Column(db.String(20), nullable=False, default="private")  # private/shared/public
    share_token = db.Column(db.String(64), nullable=True, unique=True, index=True)
    share_expires_at = db.Column(db.DateTime, nullable=True)
    allow_download = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    uploader = db.relationship("User", back_populates="videos")

    @property
    def tag_list(self):
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    def formatted_size(self):
        if self.file_size is None:
            return "Unknown"
        size = self.file_size
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def __repr__(self):
        return f"<Video {self.filename}>"
