# Badminton Video Vault

A Flask web app for uploading, storing, sharing, and playing badminton session videos using a private AWS S3 bucket.

## Features

- **Secure authentication** via Flask-Login (email + password)
- **Direct browser-to-S3 multipart upload** with progress, cancellation, CSRF renewal, token renewal, and per-part retry
- **No large video body through Flask/EC2** — the application coordinates S3 and stores metadata in SQLite
- **Presigned URLs** for private playback and optional download
- **Visibility controls** — private / shared link / public per video
- **Time-limited share links** for non-authenticated viewers
- **Tagging and filtering** for the video library
- **Admin panel** for creating and managing users

## Upload Architecture

```text
Browser
   |-- small authenticated JSON requests --> Flask
   |
   `-- presigned multipart PUT requests ---> private S3 bucket

Flask completes the S3 multipart upload, verifies the object size, and then
creates the SQLite Video record.
```

A failed or cancelled upload is aborted on a best-effort basis. Configure an S3 lifecycle rule to delete incomplete multipart uploads after a few days as the final cleanup layer.

## Tech Stack

| Layer | Technology |
|---|---|
| Web framework | Flask 3 |
| Authentication | Flask-Login |
| Forms / CSRF | Flask-WTF / WTForms |
| ORM / metadata | SQLAlchemy + SQLite |
| Object storage | Amazon S3 through boto3 and presigned URLs |
| UI | Bootstrap 5 + vanilla JavaScript |

## Quick Start

### 1. Clone and install dependencies

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
.\venv\Scripts\Activate.ps1    # Windows PowerShell
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env with the bucket, region, Flask secret, and optional Mailgun settings.
```

For EC2, prefer an attached IAM role and omit `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.

### 3. Configure S3 CORS

Direct browser uploads require an S3 CORS rule that permits `PUT` from the exact application origin and exposes `ETag`. See [`DEPLOY.md`](DEPLOY.md) for the production rule.

### 4. Initialise the database and administrator

```bash
flask init-db
flask create-admin
```

### 5. Run the development server

```bash
flask run
```

The app will be available at `http://localhost:5000`.

## Environment Variables

| Variable | Description |
|---|---|
| `FLASK_SECRET_KEY` | Flask session and signed upload-token secret |
| `FLASK_ENV` | `development` or `production` |
| `DATABASE_URL` | SQLAlchemy database URI |
| `AUTO_CREATE_DB` | Auto-create missing tables at startup |
| `AWS_ACCESS_KEY_ID` | Optional fallback credential outside EC2 |
| `AWS_SECRET_ACCESS_KEY` | Optional fallback credential outside EC2 |
| `AWS_REGION` | S3 bucket region |
| `S3_BUCKET_NAME` | Private S3 bucket name |
| `PRESIGNED_URL_EXPIRY` | Playback/download URL lifetime in seconds |
| `MAX_VIDEO_FILE_SIZE` | Largest selectable video in bytes; default 3 GiB |
| `MAX_REQUEST_BODY_SIZE` | Maximum Flask request body; default 4 MiB |
| `S3_MULTIPART_PART_SIZE` | S3 part size; default 16 MiB |
| `S3_MULTIPART_URL_EXPIRY` | Multipart part URL lifetime; default 7,200 seconds |
| `S3_MULTIPART_TOKEN_MAX_AGE` | Signed coordination-token lifetime per token; default 21,600 seconds (renewed while upload page remains open) |
| `S3_MULTIPART_CONCURRENCY` | Browser part-upload concurrency; default 3 |

See `.env.example` for Mailgun and authentication-token settings.

## AWS S3 Permissions

The application role needs object access within the selected bucket:

- `s3:PutObject`
- `s3:GetObject`
- `s3:DeleteObject`
- `s3:AbortMultipartUpload`
- `s3:ListMultipartUploadParts`

S3 authorizes multipart creation, part upload, and completion through `s3:PutObject`. Keep S3 Block Public Access enabled.

## Routes

| Route | Description |
|---|---|
| `GET/POST /login` | Login page |
| `GET /logout` | Log out |
| `GET /dashboard` | Dashboard |
| `GET /upload` | Direct-upload page |
| `GET /api/csrf-token` | Issue a fresh CSRF token for long-running authenticated uploads |
| `POST /api/uploads/multipart/initiate` | Create S3 multipart upload and sign parts |
| `POST /api/uploads/multipart/refresh-part` | Refresh a part URL and renew the signed upload token |
| `POST /api/uploads/multipart/complete` | Complete S3 upload and save metadata |
| `POST /api/uploads/multipart/abort` | Abort an incomplete upload |
| `GET /videos` | Video list |
| `GET/POST /videos/<id>` | Video detail, playback, and edit |
| `POST /videos/<id>/delete` | Delete S3 object and metadata |
| `GET /share/<token>` | Public share link |
| `GET /admin/users` | User management |
| `GET/POST /admin/users/create` | Create user |
| `POST /admin/users/<id>/toggle` | Activate/deactivate user |

## Tests

```bash
python tests/run_all_smoke.py
```

The suite includes the multipart initiation, completion, validation, abort, and authentication paths.

## Production Deployment

Follow [`DEPLOY.md`](DEPLOY.md). It covers S3 CORS, IAM roles, EC2, systemd, Nginx, HTTPS, diagnostics, backups, and optional GitHub Actions deployment.
