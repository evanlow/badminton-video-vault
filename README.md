# Badminton Video Vault

A Flask web app for uploading, storing, sharing, and playing badminton session videos using AWS S3.

## Features

- **Secure authentication** via Flask-Login (email + password)
- **Video upload** — files streamed directly to a private AWS S3 bucket; only metadata stored in SQLite
- **Presigned URLs** for secure playback and optional download (no public S3 objects)
- **Visibility controls** — private / shared (link) / public per video
- **Share links** — time-limited share tokens for sharing with non-authenticated users
- **Tag & filter** your video library
- **Admin panel** — create and manage users

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Web framework | Flask 3 |
| Auth | Flask-Login |
| Forms | Flask-WTF / WTForms |
| ORM | SQLAlchemy + SQLite |
| Object storage | AWS S3 via boto3 |
| UI | Bootstrap 5 + Bootstrap Icons |

## Quick Start

### 1. Clone and install dependencies

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
.\venv\Scripts\Activate.ps1    # Windows (PowerShell)
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your AWS credentials and Flask secret key
```

### 3. Initialise the database

```bash
flask init-db
```

### 4. Create an admin user

```bash
flask create-admin
```

### 5. Run the development server

```bash
flask run
```

The app will be available at `http://localhost:5000`.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `FLASK_SECRET_KEY` | Flask session secret (change in production!) |
| `FLASK_ENV` | `development` or `production` |
| `DATABASE_URL` | SQLAlchemy DB URI (default: SQLite) |
| `AWS_ACCESS_KEY_ID` | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials |
| `AWS_REGION` | AWS region (e.g. `us-east-1`) |
| `S3_BUCKET_NAME` | Name of your **private** S3 bucket |
| `PRESIGNED_URL_EXPIRY` | Presigned URL TTL in seconds (default: 3600) |

## AWS S3 Setup

1. Create a **private** S3 bucket (block all public access).
2. Create an IAM user/role with the following permissions on the bucket:
   - `s3:PutObject`
   - `s3:GetObject`
   - `s3:DeleteObject`
3. Add the IAM credentials to your `.env`.

## Routes

| Route | Description |
|-------|-------------|
| `GET/POST /login` | Login page |
| `GET /logout` | Log out |
| `GET /dashboard` | Dashboard (login required) |
| `GET/POST /upload` | Upload a video (login required) |
| `GET /videos` | Video list (login required) |
| `GET/POST /videos/<id>` | Video detail, playback & edit (login required) |
| `POST /videos/<id>/delete` | Delete a video (login required) |
| `GET /share/<token>` | Public share link (no login required) |
| `GET /admin/users` | User management (admin only) |
| `GET/POST /admin/users/create` | Create user (admin only) |
| `POST /admin/users/<id>/toggle` | Activate/deactivate user (admin only) |

## Project Structure

```
.
├── app.py              # Application factory, routes, CLI commands
├── config.py           # Configuration from environment variables
├── extensions.py       # SQLAlchemy & LoginManager instances
├── models.py           # User and Video SQLAlchemy models
├── forms.py            # WTForms form classes
├── requirements.txt
├── .env.example
├── .gitignore
├── static/
│   └── style.css
└── templates/
    ├── base.html
    ├── login.html
    ├── dashboard.html
    ├── upload.html
    ├── videos.html
    ├── video_detail.html
    ├── admin_users.html
    ├── admin_create_user.html
    └── error.html
```

