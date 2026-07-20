# Deploying Badminton Video Vault to AWS

This guide deploys Badminton Video Vault to a single Ubuntu EC2 instance with:

- Nginx on ports 80 and 443
- Gunicorn behind a systemd-managed Unix socket
- Flask and SQLite under `/srv/badminton-video-vault`
- A private Amazon S3 bucket for video objects
- Direct browser-to-S3 multipart uploads
- An EC2 IAM role for temporary AWS credentials
- Optional deployment from GitHub Actions after all smoke tests pass

Follow the parts in order. Commands assume the default Ubuntu user, `ubuntu`.

> **Upload architecture:** Video bytes no longer pass through Nginx, Gunicorn, Flask, `/tmp`, or the EC2 root disk. Flask creates a multipart upload and returns temporary presigned part URLs. The browser uploads the parts directly to private S3. Flask then completes the multipart upload, verifies the final object size, and stores only metadata in SQLite.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Part 1 — Create the S3 Bucket](#part-1--create-the-s3-bucket)
3. [Part 2 — Create the S3 IAM Policy](#part-2--create-the-s3-iam-policy)
4. [Part 3 — Create and Attach the EC2 IAM Role](#part-3--create-and-attach-the-ec2-iam-role)
5. [Part 4 — Configure Required S3 CORS and Lifecycle](#part-4--configure-required-s3-cors-and-lifecycle)
6. [Part 5 — Launch or Prepare EC2](#part-5--launch-or-prepare-ec2)
7. [Part 6 — Prepare Ubuntu](#part-6--prepare-ubuntu)
8. [Part 7 — Clone and Configure the Application](#part-7--clone-and-configure-the-application)
9. [Part 8 — Configure Gunicorn and systemd](#part-8--configure-gunicorn-and-systemd)
10. [Part 9 — Configure Nginx](#part-9--configure-nginx)
11. [Part 10 — Domain and HTTPS](#part-10--domain-and-https)
12. [Part 11 — Deploy Updates](#part-11--deploy-updates)
13. [Part 12 — Verify the Complete Setup](#part-12--verify-the-complete-setup)
14. [Backups and Maintenance](#backups-and-maintenance)
15. [Troubleshooting](#troubleshooting)

---

## Architecture

```text
Browser
   |-- small authenticated JSON requests --> Nginx --> Gunicorn --> Flask
   |
   `-- presigned multipart PUT requests --------------------------> Private S3

Flask -- completes upload and verifies size --> S3
Flask -- stores metadata --------------------> SQLite on EBS
```

The default upload settings are:

- Maximum video size: 2 GiB
- Multipart part size: 16 MiB
- Concurrent browser uploads: 3 parts
- Automatic retry: up to 3 attempts per failed part
- Part URL lifetime: 2 hours
- Signed coordination-token lifetime: 6 hours

For a 2 GiB video, the browser sends 128 parts directly to S3. EC2 handles only small JSON requests, so video size no longer determines EC2 RAM or temporary-disk requirements.

The S3 bucket remains private. Upload, playback, and download access use temporary presigned URLs.

---

## Part 1 — Create the S3 Bucket

In **Amazon S3 → General purpose buckets → Create bucket**, configure:

| Setting | Recommended value |
|---|---|
| Bucket name | A globally unique name, such as `badminton-video-vault-yourname` |
| AWS Region | The region closest to your users |
| Object Ownership | ACLs disabled |
| Block Public Access | Block all public access |
| Versioning | Optional |
| Default encryption | SSE-S3, or SSE-KMS when required |

Record the exact values:

```text
S3_BUCKET_NAME
AWS_REGION
```

`AWS_REGION` in `.env` must match the bucket region.

---

## Part 2 — Create the S3 IAM Policy

Go to **IAM → Policies → Create policy → JSON** and use:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BadmintonVideoVaultS3ObjectAccess",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:AbortMultipartUpload",
        "s3:ListMultipartUploadParts"
      ],
      "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/*"
    }
  ]
}
```

Replace `YOUR-BUCKET-NAME`, then name the policy:

```text
BadmintonVideoVaultS3Policy
```

S3 authorizes multipart creation, part upload, and completion through `s3:PutObject`. `AbortMultipartUpload` permits cancellation and cleanup. `GetObject` also permits the post-completion `HeadObject` size verification used by the application.

---

## Part 3 — Create and Attach the EC2 IAM Role

### 3.1 — Create the role

1. Open **IAM → Roles → Create role**.
2. Trusted entity: **AWS service**.
3. Use case: **EC2**.
4. Attach `BadmintonVideoVaultS3Policy`.
5. Name it:

   ```text
   BadmintonVideoVaultEC2Role
   ```

### 3.2 — Attach during launch

In the EC2 launch screen, choose **Advanced details → IAM instance profile → BadmintonVideoVaultEC2Role**.

### 3.3 — Attach to an existing instance

You do not need to recreate an instance:

1. Open **EC2 → Instances**.
2. Select the instance.
3. Choose **Actions → Security → Modify IAM role**.
4. Select `BadmintonVideoVaultEC2Role`.
5. Choose **Update IAM role**.

With the role attached, do not place these variables in production `.env`:

```text
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
```

Boto3 and AWS CLI automatically use the instance role's temporary credentials.

---

## Part 4 — Configure Required S3 CORS and Lifecycle

### 4.1 — CORS is required for direct uploads

Open **S3 → your bucket → Permissions → Cross-origin resource sharing (CORS) → Edit**.

For initial HTTP testing by Elastic IP:

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "PUT"],
    "AllowedOrigins": ["http://YOUR_ELASTIC_IP"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

After HTTPS is working, replace the origin with the final site origin:

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "PUT"],
    "AllowedOrigins": ["https://vault.example.com"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

During migration, both exact origins may be listed:

```json
"AllowedOrigins": [
  "http://YOUR_ELASTIC_IP",
  "https://vault.example.com"
]
```

Important details:

- The origin has no trailing slash.
- Include every real frontend origin separately, such as both apex and `www` when both are used.
- Keep S3 Block Public Access enabled.
- Do not use `"*"` for `AllowedOrigins` on a private production vault.
- `ExposeHeaders` must include `ETag`; the browser needs each part's ETag to complete the upload.

### 4.2 — Delete abandoned multipart uploads

The browser asks Flask to abort a failed or cancelled upload, but a closed tab, dead battery, or network outage may prevent that request.

Open **S3 → your bucket → Management → Create lifecycle rule** and add a rule that:

```text
Deletes incomplete multipart uploads after 7 days
```

This is the final cleanup layer for abandoned parts and avoids indefinite storage charges.

---

## Part 5 — Launch or Prepare EC2

### 5.1 — AMI and instance type

Use Ubuntu Server 22.04 LTS or 24.04 LTS, 64-bit x86.

| Workload | Suggested starting point |
|---|---|
| Personal or small team | `t2.micro` or `t3.micro`, one Gunicorn worker |
| More concurrent page/API traffic | At least 2 GiB RAM, such as `t3.small` |
| Multiple application instances | Larger instance plus an external database such as RDS |

Direct S3 upload means a 2 GiB video does not require 2 GiB of EC2 RAM or temporary disk. Instance size is driven by concurrent Flask requests and database work rather than video size.

### 5.2 — Root volume

Use a 20 GiB gp3 root volume as a comfortable starting point and enable EBS encryption.

The volume stores Ubuntu, the application, virtual environment, SQLite database, logs, and optional swap. It does not store uploaded video bodies.

### 5.3 — Security group

| Type | Port | Source | Purpose |
|---|---:|---|---|
| SSH | 22 | Your public IP `/32` | Administration |
| HTTP | 80 | `0.0.0.0/0`, optionally `::/0` | Initial site and certificate validation |
| HTTPS | 443 | `0.0.0.0/0`, optionally `::/0` | Production site |

Do not open port 5000.

Avoid leaving SSH open to `0.0.0.0/0`. For browser-based EC2 Instance Connect, use the AWS-managed EC2 Instance Connect prefix list for the instance region.

### 5.4 — Elastic IP

Allocate and associate an Elastic IP so the address remains stable after stops and starts. Record it as `YOUR_ELASTIC_IP`.

Public IPv4 addresses may be billed; check current AWS pricing.

---

## Part 6 — Prepare Ubuntu

### 6.1 — Connect

```bash
ssh -i ~/.ssh/badminton-vault-key.pem ubuntu@YOUR_ELASTIC_IP
```

On Windows PowerShell, a typical path is:

```powershell
ssh -i "$HOME\.ssh\badminton-vault-key.pem" ubuntu@YOUR_ELASTIC_IP
```

### 6.2 — Update first, then install packages

```bash
sudo apt update
sudo apt upgrade -y

sudo apt install -y \
  python3 \
  python3-pip \
  python3-venv \
  git \
  nginx \
  sqlite3 \
  curl \
  unzip
```

If `python3-pip` or `python3-venv` cannot be found:

```bash
sudo apt install -y software-properties-common
sudo add-apt-repository -y universe
sudo apt update
sudo apt install -y python3-pip python3-venv
```

Verify:

```bash
python3 --version
git --version
nginx -v
```

### 6.3 — Install AWS CLI v2

```bash
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64) AWSCLI_ARCH="x86_64" ;;
  aarch64|arm64) AWSCLI_ARCH="aarch64" ;;
  *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

curl "https://awscli.amazonaws.com/awscli-exe-linux-${AWSCLI_ARCH}.zip" \
  -o /tmp/awscliv2.zip
rm -rf /tmp/aws
unzip -q /tmp/awscliv2.zip -d /tmp
sudo /tmp/aws/install
rm -rf /tmp/aws /tmp/awscliv2.zip

aws --version
aws sts get-caller-identity
```

Do not run `aws configure` when the EC2 role is attached. The returned ARN should contain `assumed-role/BadmintonVideoVaultEC2Role/`.

### 6.4 — Optional swap on a 1 GiB instance

Direct uploads no longer require swap proportional to the video size. A small swap file can still provide emergency headroom:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

grep -q '^/swapfile ' /etc/fstab || \
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

free -h
swapon --show
```

Frequent swap use under ordinary traffic means the instance should be resized.

### 6.5 — Create an empty application directory

```bash
sudo mkdir -p /srv/badminton-video-vault
sudo chown ubuntu:ubuntu /srv/badminton-video-vault
ls -la /srv/badminton-video-vault
```

Do not create `data/` before cloning. `git clone` requires the destination to be empty.

---

## Part 7 — Clone and Configure the Application

### 7.1 — Clone

For a public repository:

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/badminton-video-vault.git \
  /srv/badminton-video-vault
```

For a private repository, create a read-only GitHub deploy key and clone over SSH.

After cloning:

```bash
cd /srv/badminton-video-vault
mkdir -p data
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 7.2 — Create `.env`

Generate a secret:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Create the file:

```bash
nano /srv/badminton-video-vault/.env
```

Example for an EC2 IAM role:

```ini
FLASK_SECRET_KEY=PASTE_A_LONG_RANDOM_VALUE
FLASK_ENV=production
AUTO_CREATE_DB=false

DATABASE_URL=sqlite:////srv/badminton-video-vault/data/badminton_vault.db

AWS_REGION=ap-southeast-1
S3_BUCKET_NAME=your-exact-bucket-name

# Playback/download links
PRESIGNED_URL_EXPIRY=3600

# Direct browser-to-S3 multipart uploads
MAX_VIDEO_FILE_SIZE=2147483648
MAX_REQUEST_BODY_SIZE=4194304
S3_MULTIPART_PART_SIZE=16777216
S3_MULTIPART_URL_EXPIRY=7200
S3_MULTIPART_TOKEN_MAX_AGE=21600
S3_MULTIPART_CONCURRENCY=3

# Initial HTTP testing; change after HTTPS is working
APP_BASE_URL=http://YOUR_ELASTIC_IP

# Keep suppressed until Mailgun is configured
MAIL_SUPPRESS_SEND=true
MAILGUN_TEST_MODE=false
MAILGUN_TIMEOUT_SECONDS=10
```

Configuration notes:

- `MAX_VIDEO_FILE_SIZE` controls the selectable video size, not Flask's request-body limit.
- `MAX_REQUEST_BODY_SIZE` stays small because Flask receives JSON only.
- S3 multipart parts must be at least 5 MiB except the final part; 16 MiB is a practical default.
- Increase `S3_MULTIPART_URL_EXPIRY` when users have very slow upstream connections.
- A signed upload token is bound to the authenticated user and expires after `S3_MULTIPART_TOKEN_MAX_AGE`.
- Do not add AWS access-key variables when using the instance role.

Protect the file:

```bash
chmod 600 /srv/badminton-video-vault/.env
```

### 7.3 — Initialise the database and admin

```bash
cd /srv/badminton-video-vault
source venv/bin/activate
flask init-db
flask create-admin
```

No database migration is required when upgrading from the older server-upload implementation; the existing `videos` schema is reused.

### 7.4 — Manual smoke test

```bash
cd /srv/badminton-video-vault
source venv/bin/activate
gunicorn --bind 127.0.0.1:5000 --workers 1 app:app
```

In another session:

```bash
curl -i http://127.0.0.1:5000/login
```

Expect `HTTP/1.1 200 OK`, then stop the temporary Gunicorn with `Ctrl+C`.

---

## Part 8 — Configure Gunicorn and systemd

Create:

```bash
sudo nano /etc/systemd/system/badminton-vault.service
```

Use:

```ini
[Unit]
Description=Gunicorn instance for Badminton Video Vault
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/srv/badminton-video-vault
EnvironmentFile=/srv/badminton-video-vault/.env

RuntimeDirectory=badminton-vault
RuntimeDirectoryMode=0750
LogsDirectory=badminton-vault
LogsDirectoryMode=0750
UMask=0007

ExecStart=/srv/badminton-video-vault/venv/bin/gunicorn \
    --workers 1 \
    --timeout 120 \
    --bind unix:/run/badminton-vault/badminton-vault.sock \
    --access-logfile /var/log/badminton-vault/access.log \
    --error-logfile /var/log/badminton-vault/error.log \
    --capture-output \
    app:app

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Why:

- One worker is the safe baseline for a roughly 1 GiB micro instance.
- The 20-minute upload timeout is no longer needed because video bytes bypass Gunicorn.
- `RuntimeDirectory=` avoids permission errors from binding directly under `/run`.
- `UMask=0007` allows Nginx, in group `www-data`, to access the socket.

Start and verify:

```bash
sudo systemctl daemon-reload
sudo systemctl enable badminton-vault
sudo systemctl restart badminton-vault
sleep 5
sudo systemctl status badminton-vault --no-pager -l
ls -l /run/badminton-vault/
```

Configure log rotation:

```bash
sudo tee /etc/logrotate.d/badminton-vault > /dev/null <<'EOF'
/var/log/badminton-vault/*.log {
    weekly
    rotate 8
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
EOF
```

---

## Part 9 — Configure Nginx

Create:

```bash
sudo nano /etc/nginx/sites-available/badminton-vault
```

Use this initial catch-all configuration:

```nginx
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    server_name _;

    # Flask receives forms and JSON only. Video parts go directly to S3.
    client_max_body_size 4M;

    client_body_timeout 60s;
    proxy_read_timeout 120s;
    proxy_send_timeout 120s;
    proxy_connect_timeout 30s;

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/badminton-vault/badminton-vault.sock;
    }
}
```

Disable Ubuntu's default site and enable the application:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf \
  /etc/nginx/sites-available/badminton-vault \
  /etc/nginx/sites-enabled/badminton-vault

sudo nginx -t
sudo systemctl reload nginx
```

Test:

```bash
curl -i http://127.0.0.1/login
```

Then browse to `http://YOUR_ELASTIC_IP`.

If the browser still shows **Welcome to nginx!**, the default site remains enabled or the application site was not linked correctly.

---

## Part 10 — Domain and HTTPS

### 10.1 — DNS

Create an `A` record pointing the chosen hostname to the Elastic IP, for example:

```text
Type: A
Name: vault
Value: YOUR_ELASTIC_IP
TTL: 300
```

Verify:

```bash
dig +short vault.example.com
```

### 10.2 — Update Nginx and obtain a certificate

Replace `server_name _;` with:

```nginx
server_name vault.example.com;
```

Then:

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d vault.example.com
sudo certbot renew --dry-run
```

### 10.3 — Update both application and S3 origin settings

Change `.env`:

```ini
APP_BASE_URL=https://vault.example.com
```

Restart Gunicorn:

```bash
sudo systemctl restart badminton-vault
```

Then update the S3 CORS rule so `AllowedOrigins` contains the exact HTTPS origin. Keep the old HTTP/IP origin only during migration, then remove it.

---

## Part 11 — Deploy Updates

### 11.1 — Manual deployment

```bash
cd /srv/badminton-video-vault
git pull --ff-only origin main
source venv/bin/activate
python -m pip install -r requirements.txt
sudo systemctl restart badminton-vault
```

Verify over the socket:

```bash
curl --fail --silent --show-error \
  --unix-socket /run/badminton-vault/badminton-vault.sock \
  http://localhost/login > /dev/null \
  && echo "Application is healthy"
```

### 11.2 — GitHub Actions

The included `.github/workflows/deploy.yml`:

1. Runs every discovered `tests/smoke_*.py` test.
2. Deploys only on a successful push to `main`.
3. Pulls with `--ff-only`, installs dependencies, restarts the service, and checks the correct nested socket.

Required repository secrets:

| Secret | Value |
|---|---|
| `EC2_HOST` | Elastic IP or production hostname |
| `EC2_SSH_KEY` | Complete private `.pem` key contents |

A GitHub-hosted runner must reach port 22. Prefer SSM, a self-hosted runner inside the VPC, or a controlled source IP rather than opening SSH globally solely for CI/CD.

---

## Part 12 — Verify the Complete Setup

### 12.1 — Role and S3 access

```bash
aws sts get-caller-identity
```

Then, from the application directory with the virtual environment active:

```bash
python - <<'PY'
import os
import boto3
from dotenv import load_dotenv

load_dotenv('/srv/badminton-video-vault/.env')
region = os.environ['AWS_REGION']
bucket = os.environ['S3_BUCKET_NAME']
key = 'deployment-tests/connectivity-test.txt'

s3 = boto3.client('s3', region_name=region)
s3.put_object(Bucket=bucket, Key=key, Body=b'connectivity test')
s3.head_object(Bucket=bucket, Key=key)
s3.delete_object(Bucket=bucket, Key=key)
print(f'S3 put/head/delete succeeded for {bucket} in {region}')
PY
```

### 12.2 — Services

```bash
sudo systemctl is-active badminton-vault
sudo systemctl is-active nginx
ls -l /run/badminton-vault/badminton-vault.sock
curl -i http://127.0.0.1/login
```

### 12.3 — Direct multipart upload

1. Open browser developer tools → **Network**.
2. Upload a small MP4 first.
3. Confirm small JSON calls to `/api/uploads/multipart/initiate` and `/complete`.
4. Confirm multiple `PUT` requests go directly to an S3 hostname, not to the EC2 hostname.
5. Confirm the final object appears under `videos/<user-id>/` in S3.
6. Confirm a `Video` record appears in the UI and playback works.
7. Test **Cancel Upload** and verify no video record is created.
8. Test the intended large-file range only after the small test succeeds.

During a direct upload, EC2 RAM and disk should remain comparatively steady. The user's browser and network carry the video bytes.

---

## Backups and Maintenance

### SQLite backup

Use SQLite's backup command rather than copying a live database file:

```bash
mkdir -p /srv/badminton-video-vault/data/backups
sqlite3 /srv/badminton-video-vault/data/badminton_vault.db \
  ".backup '/srv/badminton-video-vault/data/backups/badminton_vault-$(date +%Y%m%d%H%M%S).db'"
```

Upload backups to an S3 `backups/` prefix or use EBS snapshots/AWS Backup. Test restoration periodically.

### Logs and status

```bash
sudo tail -f /var/log/badminton-vault/error.log
sudo tail -f /var/log/badminton-vault/access.log
sudo tail -f /var/log/nginx/error.log
sudo journalctl -u badminton-vault -f

sudo systemctl status badminton-vault --no-pager -l
sudo systemctl status nginx --no-pager -l
```

### Resource checks

```bash
free -h
swapon --show
df -h / /tmp
```

### Updates

```bash
sudo apt update
sudo apt upgrade -y
```

After a required reboot, verify both services again.

---

## Troubleshooting

### Direct upload and S3

| Symptom | Likely cause | Fix |
|---|---|---|
| Browser reports a CORS/network failure | Exact application origin missing from S3 CORS | Apply Part 4; no trailing slash |
| Browser reports missing ETag | S3 CORS does not expose `ETag` | Add `"ExposeHeaders": ["ETag"]` |
| `AccessDenied` on initiation/completion | Wrong role policy or bucket ARN | Verify `s3:PutObject` and the exact bucket object ARN |
| `NoCredentialsError` | Instance role missing | Attach the EC2 role and run `aws sts get-caller-identity` |
| Upload URLs expire before completion | Upload slower than URL lifetime | Increase `S3_MULTIPART_URL_EXPIRY` and restart Gunicorn |
| File rejected immediately | Unsupported extension or over configured size | Check `MAX_VIDEO_FILE_SIZE` and selected extension |
| Upload reaches 100% then fails | S3 completion, object-size verification, or DB commit failed | Inspect Gunicorn error log |
| Incomplete multipart storage accumulates | Browser closed before abort completed | Enable the seven-day lifecycle rule |
| App returns 413 during video upload | Old upload form/JS is still deployed or video was posted to Flask | Pull latest code and verify `static/upload.js` loads |

### Gunicorn and Nginx

| Symptom | Likely cause | Fix |
|---|---|---|
| `/run/badminton-vault.sock: Permission denied` | Socket placed directly under `/run` | Use `RuntimeDirectory=badminton-vault` and the nested path |
| `502 Bad Gateway` | Gunicorn down or socket path mismatch | Check service status and `/run/badminton-vault/badminton-vault.sock` |
| **Welcome to nginx!** | Ubuntu default site still enabled | Remove `/etc/nginx/sites-enabled/default` |
| Generic 500 | Application exception | Check `/var/log/badminton-vault/error.log` |
| Worker repeatedly restarts | Startup error or OOM | Check systemd, Gunicorn log, and kernel log |

Check OOM events:

```bash
sudo journalctl -k -b | \
  grep -Ei 'out of memory|oom-kill|killed process' | \
  tail -n 50
```

### Package and Git issues

| Symptom | Fix |
|---|---|
| `Unable to locate package python3-pip` | Run `sudo apt update`, enable Universe, retry |
| `Package awscli has no installation candidate` | Install official AWS CLI v2 as shown above |
| Clone destination is not empty | Clone before creating `data/` |
| Public repository asks for credentials | Use the repository's HTTPS clone URL and confirm it is public |
| Private repository cannot clone | Configure a read-only deploy key |
| GitHub Actions health check uses old socket | Use `/run/badminton-vault/badminton-vault.sock` |

### Diagnostic bundle

```bash
sudo systemctl status badminton-vault --no-pager -l
sudo journalctl -u badminton-vault -n 100 --no-pager
sudo tail -n 100 /var/log/badminton-vault/error.log
sudo tail -n 100 /var/log/nginx/error.log
sudo nginx -t
ls -l /run/badminton-vault/
free -h
swapon --show
df -h / /tmp
aws sts get-caller-identity
```

---

## Security and Cost Notes

- Keep S3 Block Public Access enabled.
- Restrict S3 CORS to exact application origins.
- Use the EC2 IAM role instead of static access keys.
- Restrict SSH to trusted sources.
- Keep `.env` mode `600`.
- Use HTTPS before real use.
- Use a strong `FLASK_SECRET_KEY`; it signs sessions and upload coordination tokens.
- Keep playback URLs short-lived and multipart URLs only as long-lived as necessary.
- The final S3 object consumes the same storage as any other upload method. The savings are on EC2 disk, RAM, and inbound/outbound processing. Incomplete multipart parts also consume S3 storage until aborted or removed by lifecycle policy.
- S3 requests and transfer, EC2, EBS, snapshots, and public IPv4 pricing vary by region and over time; use current AWS pricing tools.

---

## Official References

- [Amazon S3 multipart upload](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html)
- [Amazon S3 CORS](https://docs.aws.amazon.com/AmazonS3/latest/userguide/cors.html)
- [S3 lifecycle for incomplete multipart uploads](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpu-abort-incomplete-mpu-lifecycle-config.html)
- [Attach an IAM role to EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/attach-iam-role.html)
- [AWS CLI version 2 installation](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [Gunicorn settings](https://docs.gunicorn.org/en/stable/settings.html)
- [systemd execution directories](https://man7.org/linux/man-pages/man5/systemd.exec.5.html)
