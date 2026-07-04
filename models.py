import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from flask import current_app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # "admin" or "user"
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    videos = db.relationship("Video", back_populates="uploader", lazy="dynamic")
    auth_tokens = db.relationship("AuthToken", back_populates="user", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"

    def __repr__(self):
        return f"<User {self.email}>"


class AuthToken(db.Model):
    __tablename__ = "auth_tokens"

    PURPOSE_RESET_PASSWORD = "reset_password"
    PURPOSE_MAGIC_LOGIN = "magic_login"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    purpose = db.Column(db.String(32), nullable=False, index=True)
    token_hash = db.Column(db.String(128), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_ip = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)

    user = db.relationship("User", back_populates="auth_tokens")

    @staticmethod
    def generate_raw_token():
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_raw_token(raw_token):
        secret = current_app.config["SECRET_KEY"].encode("utf-8")
        return hmac.new(secret, raw_token.encode("utf-8"), hashlib.sha256).hexdigest()

    @property
    def is_expired(self):
        return self.expires_at < datetime.utcnow()

    @property
    def is_usable(self):
        return self.used_at is None and not self.is_expired and self.user and self.user.is_active

    def mark_used(self):
        self.used_at = datetime.utcnow()

    @classmethod
    def invalidate_unused(cls, user_id, purpose, exclude_id=None):
        query = cls.query.filter_by(user_id=user_id, purpose=purpose, used_at=None)
        if exclude_id is not None:
            query = query.filter(cls.id != exclude_id)
        query.update({"used_at": datetime.utcnow()}, synchronize_session=False)

    @classmethod
    def create_for_user(cls, user, purpose, ttl_minutes, created_ip=None, user_agent=None):
        cls.invalidate_unused(user.id, purpose)

        raw_token = cls.generate_raw_token()
        token = cls(
            user_id=user.id,
            purpose=purpose,
            token_hash=cls.hash_raw_token(raw_token),
            expires_at=datetime.utcnow() + timedelta(minutes=int(ttl_minutes)),
            created_ip=created_ip,
            user_agent=(user_agent or "")[:255],
        )
        db.session.add(token)
        return raw_token, token

    @classmethod
    def find_usable(cls, raw_token, purpose):
        if not raw_token:
            return None

        token_hash = cls.hash_raw_token(raw_token)
        token = cls.query.filter_by(token_hash=token_hash, purpose=purpose).first()
        if not token or not token.is_usable:
            return None
        return token

    def __repr__(self):
        return f"<AuthToken user_id={self.user_id} purpose={self.purpose} used={self.used_at is not None}>"


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
