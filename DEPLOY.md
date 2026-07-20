# Deploying Badminton Video Vault to AWS

This guide deploys the application to one Ubuntu EC2 instance with Nginx, Gunicorn, SQLite, a private S3 bucket, an EC2 IAM role, and direct browser-to-S3 multipart uploads.

> **Important:** Video bytes do not pass through EC2. Flask authorises and completes the upload, while the browser sends the parts directly to S3. This avoids consuming EC2 RAM, `/tmp`, root-volume space, and video-path network bandwidth.

## Architecture

```text
Browser
   |-- small JSON requests --> Nginx --> Gunicorn --> Flask --> SQLite
   |
   `-- presigned multipart PUT requests ---------------------> Private S3
```

Default upload settings:

- Maximum video size: 2 GiB
- Part size: 16 MiB
- Concurrent part uploads: 3
- Automatic attempts per failed part: 3
- Presigned part URL lifetime: 2 hours
- Signed upload-token lifetime: 6 hours

The S3 bucket remains private. Upload, playback, and download use temporary presigned URLs.

---

## 1. Create the S3 Bucket

In **Amazon S3 → Create bucket**, configure:

| Setting | Value |
|---|---|
| Bucket name | A globally unique name |
| Region | The region closest to users |
| Object Ownership | ACLs disabled |
| Block Public Access | Block all public access |
| Default encryption | **SSE-S3**, recommended for this guide |

Record the exact bucket name and region.

> Using SSE-KMS is possible, but it requires additional KMS key-policy and IAM permissions such as `kms:GenerateDataKey` and `kms:Decrypt`. Do not select SSE-KMS unless those grants are configured for the EC2 role.

---

## 2. Create the S3 IAM Policy

Open **IAM → Policies → Create policy → JSON**:

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

Replace `YOUR-BUCKET-NAME` and save it as:

```text
BadmintonVideoVaultS3Policy
```

S3 authorises multipart creation, part upload, and completion through `s3:PutObject`. `s3:GetObject` also permits the post-completion `HeadObject` verification used by the application.

---

## 3. Create and Attach the EC2 IAM Role

1. Open **IAM → Roles → Create role**.
2. Trusted entity: **AWS service**.
3. Use case: **EC2**.
4. Attach `BadmintonVideoVaultS3Policy`.
5. Name it `BadmintonVideoVaultEC2Role`.

Attach it during EC2 launch under **Advanced details → IAM instance profile**.

For an existing instance:

1. Open **EC2 → Instances**.
2. Select the instance.
3. Choose **Actions → Security → Modify IAM role**.
4. Select `BadmintonVideoVaultEC2Role`.

When using the role, do not put these in production `.env`:

```text
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
```

---

## 4. Configure Required S3 CORS

Direct browser uploads require an exact-origin CORS rule and exposed `ETag` headers.

Open **S3 → bucket → Permissions → Cross-origin resource sharing (CORS)**.

For initial HTTP testing:

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

After HTTPS is working:

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

During migration, list both exact origins. Do not include trailing slashes. Add every actual frontend origin separately, for example apex and `www` when both are used. Do not use `"*"` for `AllowedOrigins` on a private production vault.

### Delete abandoned multipart uploads

Open **S3 → bucket → Management → Create lifecycle rule** and configure:

```text
Delete incomplete multipart uploads after 7 days
```

The UI attempts to abort cancelled and failed uploads, while the lifecycle rule handles closed tabs, dead batteries, and network loss.

---

## 5. Launch or Prepare EC2

Recommended AMI:

```text
Ubuntu Server 22.04 LTS or 24.04 LTS, 64-bit x86
```

Suggested starting points:

| Workload | Instance |
|---|---|
| Personal or small team | `t2.micro` or `t3.micro`, one Gunicorn worker |
| More concurrent page/API requests | At least 2 GiB RAM, such as `t3.small` |
| Multiple app instances | Larger instance plus an external database |

Direct S3 upload means a 2 GiB video does not require 2 GiB of EC2 RAM or temporary disk.

Use a 20 GiB encrypted gp3 root volume as a comfortable baseline.

Security-group inbound rules:

| Type | Port | Source |
|---|---:|---|
| SSH | 22 | Your public IP `/32` |
| HTTP | 80 | `0.0.0.0/0`, optionally `::/0` |
| HTTPS | 443 | `0.0.0.0/0`, optionally `::/0` |

Do not open port 5000. Avoid leaving SSH open to `0.0.0.0/0`.

Allocate and associate an Elastic IP so the public address remains stable. Public IPv4 may be billed.

---

## 6. Prepare Ubuntu

Connect:

```bash
ssh -i ~/.ssh/badminton-vault-key.pem ubuntu@YOUR_ELASTIC_IP
```

Windows PowerShell example:

```powershell
ssh -i "$HOME\.ssh\badminton-vault-key.pem" ubuntu@YOUR_ELASTIC_IP
```

Refresh package metadata before installing:

```bash
sudo apt update
sudo apt upgrade -y

sudo apt install -y \
  python3 python3-pip python3-venv \
  git nginx sqlite3 curl unzip
```

If `python3-pip` or `python3-venv` cannot be found:

```bash
sudo apt install -y software-properties-common
sudo add-apt-repository -y universe
sudo apt update
sudo apt install -y python3-pip python3-venv
```

### Install AWS CLI v2

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

Do not run `aws configure` with an EC2 role. The ARN should contain `assumed-role/BadmintonVideoVaultEC2Role/`.

### Optional swap on a 1 GiB instance

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

grep -Eq '^/swapfile[[:space:]]' /etc/fstab || \
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

free -h
swapon --show
```

Swap is optional for direct uploads. Regular swap use under ordinary traffic means the instance should be resized.

Create an empty destination:

```bash
sudo mkdir -p /srv/badminton-video-vault
sudo chown ubuntu:ubuntu /srv/badminton-video-vault
ls -la /srv/badminton-video-vault
```

Do not create `data/` before cloning.

---

## 7. Clone and Configure the Application

### Public repository

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/badminton-video-vault.git \
  /srv/badminton-video-vault
```

### Private repository

Generate a read-only deploy key:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
ssh-keygen -t ed25519 \
  -C "badminton-video-vault-deploy-key" \
  -f ~/.ssh/deploy_key \
  -N ""
cat ~/.ssh/deploy_key.pub
```

Add the public key under **GitHub repository → Settings → Deploy keys**, without write access.

Append the host block only when it is not already present; do not overwrite unrelated SSH configuration:

```bash
touch ~/.ssh/config
chmod 600 ~/.ssh/config

grep -q '^Host github.com$' ~/.ssh/config || cat >> ~/.ssh/config <<'EOF'
Host github.com
  IdentityFile ~/.ssh/deploy_key
  IdentitiesOnly yes
EOF

git clone git@github.com:YOUR_GITHUB_USERNAME/badminton-video-vault.git \
  /srv/badminton-video-vault
```

After cloning:

```bash
cd /srv/badminton-video-vault
mkdir -p data
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Create `.env`

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
nano /srv/badminton-video-vault/.env
```

Use:

```ini
FLASK_SECRET_KEY=PASTE_A_LONG_RANDOM_VALUE
FLASK_ENV=production
AUTO_CREATE_DB=false

DATABASE_URL=sqlite:////srv/badminton-video-vault/data/badminton_vault.db

AWS_REGION=YOUR_BUCKET_REGION
S3_BUCKET_NAME=YOUR_EXACT_BUCKET_NAME

PRESIGNED_URL_EXPIRY=3600

MAX_VIDEO_FILE_SIZE=2147483648
MAX_REQUEST_BODY_SIZE=4194304
S3_MULTIPART_PART_SIZE=16777216
S3_MULTIPART_URL_EXPIRY=7200
S3_MULTIPART_TOKEN_MAX_AGE=21600
S3_MULTIPART_CONCURRENCY=3

APP_BASE_URL=http://YOUR_ELASTIC_IP

MAIL_SUPPRESS_SEND=true
MAILGUN_TEST_MODE=false
MAILGUN_TIMEOUT_SECONDS=10
```

Notes:

- `MAX_VIDEO_FILE_SIZE` controls selectable video size.
- `MAX_REQUEST_BODY_SIZE` remains small because Flask receives JSON only.
- S3 parts must be at least 5 MiB except the final part.
- Increase `S3_MULTIPART_URL_EXPIRY` for very slow upload connections.
- Do not add access-key variables when the instance role is attached.

Protect the file:

```bash
chmod 600 /srv/badminton-video-vault/.env
```

Initialise:

```bash
cd /srv/badminton-video-vault
source venv/bin/activate
flask init-db
flask create-admin
```

No database schema migration is required when upgrading from the earlier server-upload implementation.

Manual smoke test:

```bash
gunicorn --bind 127.0.0.1:5000 --workers 1 app:app
```

In another session:

```bash
curl -i http://127.0.0.1:5000/login
```

Expect `HTTP/1.1 200 OK`, then stop Gunicorn with `Ctrl+C`.

---

## 8. Configure Gunicorn and systemd

Create `/etc/systemd/system/badminton-vault.service`:

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

The old 20-minute upload timeout is unnecessary because video bytes bypass Gunicorn. `RuntimeDirectory=` prevents permission errors from trying to create a socket directly under `/run`.

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

## 9. Configure Nginx

Create `/etc/nginx/sites-available/badminton-vault`:

```nginx
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    server_name _;

    # Flask receives forms and JSON only; video parts go directly to S3.
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

Enable it and remove Ubuntu's default site:

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

Browse to `http://YOUR_ELASTIC_IP`.

---

## 10. Domain and HTTPS

Point an `A` record to the Elastic IP, for example `vault.example.com`.

Verify:

```bash
dig +short vault.example.com
```

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

Update `.env`:

```ini
APP_BASE_URL=https://vault.example.com
```

Restart:

```bash
sudo systemctl restart badminton-vault
```

Finally, replace or extend the S3 CORS origin with the exact HTTPS origin.

---

## 11. Deploy Updates

Manual deployment:

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

The included GitHub Actions workflow runs all smoke tests before deployment and uses the correct nested socket path. It requires `EC2_HOST` and `EC2_SSH_KEY` repository secrets. Prefer SSM, a self-hosted runner, or a controlled source IP rather than opening SSH globally only for CI/CD.

---

## 12. Verify Direct Multipart Upload

1. Open browser developer tools → **Network**.
2. Upload a small MP4 first.
3. Confirm small JSON calls to:
   - `/api/uploads/multipart/initiate`
   - `/api/uploads/multipart/complete`
4. Confirm multiple `PUT` requests go directly to an S3 hostname.
5. Confirm the object appears under `videos/<user-id>/` in S3.
6. Confirm the application creates a video record and playback works.
7. Test **Cancel Upload** and confirm no video record is created.
8. Test larger files only after the small test succeeds.

During upload, EC2 RAM and disk should remain comparatively steady.

---

## Backups and Maintenance

Safe SQLite backup:

```bash
mkdir -p /srv/badminton-video-vault/data/backups
sqlite3 /srv/badminton-video-vault/data/badminton_vault.db \
  ".backup '/srv/badminton-video-vault/data/backups/badminton_vault-$(date +%Y%m%d%H%M%S).db'"
```

Upload backups to an S3 `backups/` prefix or use EBS snapshots/AWS Backup.

Useful commands:

```bash
sudo tail -f /var/log/badminton-vault/error.log
sudo tail -f /var/log/nginx/error.log
sudo journalctl -u badminton-vault -f
sudo systemctl status badminton-vault --no-pager -l
sudo systemctl status nginx --no-pager -l
free -h
swapon --show
df -h / /tmp
```

---

## Troubleshooting

### S3 and direct upload

| Symptom | Fix |
|---|---|
| Browser CORS/network error | Add the exact origin to S3 CORS; no trailing slash |
| Missing ETag error | Add `"ExposeHeaders": ["ETag"]` |
| AccessDenied | Verify EC2 role, bucket ARN, and S3 actions |
| URLs expire before completion | Increase `S3_MULTIPART_URL_EXPIRY`, restart Gunicorn |
| File rejected immediately | Check extension and `MAX_VIDEO_FILE_SIZE` |
| Upload reaches 100% then fails | Inspect Gunicorn log for completion, size, or DB failure |
| Abandoned parts accumulate | Enable the seven-day incomplete-multipart lifecycle rule |
| 413 during video upload | Latest `static/upload.js` is not loaded, or video was posted to Flask |

### Gunicorn and Nginx

| Symptom | Fix |
|---|---|
| `/run/badminton-vault.sock: Permission denied` | Use `RuntimeDirectory=badminton-vault` and nested socket path |
| `502 Bad Gateway` | Check service status and socket path |
| **Welcome to nginx!** | Remove `/etc/nginx/sites-enabled/default` |
| Generic 500 | Check `/var/log/badminton-vault/error.log` |
| Worker restart loop | Check systemd, Gunicorn, and kernel OOM logs |

OOM diagnostics:

```bash
sudo journalctl -k -b | \
  grep -Ei 'out of memory|oom-kill|killed process' | \
  tail -n 50
```

Diagnostic bundle:

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
- Use an EC2 role instead of static access keys.
- Restrict SSH to trusted sources.
- Keep `.env` mode `600`.
- Use HTTPS and a strong `FLASK_SECRET_KEY`.
- The completed S3 object uses the same storage regardless of upload method. The savings are on EC2 RAM, disk, and video-path processing. Incomplete multipart parts consume S3 storage until aborted or removed by lifecycle policy.
- Check current AWS pricing for S3 requests/transfer, EC2, EBS, snapshots, and public IPv4.

## References

- [S3 multipart upload](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html)
- [S3 CORS](https://docs.aws.amazon.com/AmazonS3/latest/userguide/cors.html)
- [Abort incomplete multipart uploads with lifecycle](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpu-abort-incomplete-mpu-lifecycle-config.html)
- [Attach an IAM role to EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/attach-iam-role.html)
- [AWS CLI v2 installation](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
