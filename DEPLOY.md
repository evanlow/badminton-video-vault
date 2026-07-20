# Deploying Badminton Video Vault to AWS

This guide deploys Badminton Video Vault to one Ubuntu EC2 instance with:

- Nginx on ports 80 and 443
- Gunicorn behind a systemd-managed Unix socket
- Flask and SQLite under `/srv/badminton-video-vault`
- Amazon S3 for private video storage
- An EC2 IAM role for temporary AWS credentials
- Optional GitHub Actions deployment after tests pass

Follow the parts in order. Commands assume Ubuntu and the default `ubuntu` user.

> **Capacity warning:** The current application receives each upload through Nginx and Gunicorn before sending it to S3. A 1 GiB `t2.micro` or `t3.micro` can run the vault for light use, but large uploads can exhaust memory unless Gunicorn is limited to one worker and swap is configured. For frequent uploads of several hundred megabytes or more, use an instance with at least 2 GiB RAM or redesign uploads to go directly from the browser to S3.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Part 1 — Create an AWS Account](#part-1--create-an-aws-account)
4. [Part 2 — Create and Configure an S3 Bucket](#part-2--create-and-configure-an-s3-bucket)
5. [Part 3 — Create the S3 IAM Policy](#part-3--create-the-s3-iam-policy)
6. [Part 4 — Create the EC2 IAM Role](#part-4--create-the-ec2-iam-role)
7. [Part 5 — Configure CORS Only If Needed](#part-5--configure-cors-only-if-needed)
8. [Part 6 — Launch or Prepare an EC2 Instance](#part-6--launch-or-prepare-an-ec2-instance)
9. [Part 7 — Connect and Prepare Ubuntu](#part-7--connect-and-prepare-ubuntu)
10. [Part 8 — Deploy the Application](#part-8--deploy-the-application)
11. [Part 9 — Configure Gunicorn with systemd](#part-9--configure-gunicorn-with-systemd)
12. [Part 10 — Configure Nginx](#part-10--configure-nginx)
13. [Part 11 — Configure a Domain and HTTPS](#part-11--configure-a-domain-and-https)
14. [Part 12 — Continuous Deployment from GitHub](#part-12--continuous-deployment-from-github)
15. [Database and Backup Options](#database-and-backup-options)
16. [Verify the Complete Setup](#verify-the-complete-setup)
17. [Maintenance](#maintenance)
18. [Security Best Practices](#security-best-practices)
19. [Capacity and Cost Notes](#capacity-and-cost-notes)
20. [Troubleshooting](#troubleshooting)

---

## Prerequisites

You need:

- An AWS account
- A GitHub repository containing this application
- An S3 bucket name that is globally unique
- Basic access to the AWS Management Console
- A domain name only if you want HTTPS and a friendly URL
- Mailgun HTTP API credentials only if password-reset and magic-login emails will be enabled

The production server should run Python 3.10 or later.

---

## Architecture Overview

```text
Browser
   |
   | HTTP/HTTPS
   v
Nginx :80/:443
   |
   | Unix socket
   v
Gunicorn
   |
   v
Flask application
   |                      |
   | SQLite metadata      | boto3 using EC2 IAM role
   v                      v
EBS root volume          Private S3 bucket
```

On a 1 GiB micro instance, this guide deliberately uses **one Gunicorn worker**. More worker processes consume more memory because each worker loads a separate Python application process.

Video objects remain private in S3. Playback and downloads use time-limited presigned URLs.

---

## Part 1 — Create an AWS Account

Create an AWS account from the AWS website and sign in to the AWS Management Console.

Use an IAM administrator identity for setup instead of routinely using the root account. Enable MFA on the root account and on privileged IAM identities.

AWS Free Tier eligibility, public IPv4 pricing, and instance eligibility change over time. Check the current AWS pricing and Free Tier pages before relying on a specific allowance.

---

## Part 2 — Create and Configure an S3 Bucket

### 2.1 — Create the bucket

In **Amazon S3 → General purpose buckets → Create bucket**, configure:

| Setting | Recommended value |
|---|---|
| Bucket name | A globally unique name, such as `badminton-video-vault-yourname` |
| AWS Region | The region closest to your users |
| Object Ownership | ACLs disabled |
| Block Public Access | Block all public access |
| Versioning | Optional |
| Default encryption | SSE-S3, or SSE-KMS if you require KMS controls |

Record:

```text
S3_BUCKET_NAME
AWS_REGION
```

The exact bucket region must later match `AWS_REGION` in `.env`.

### 2.2 — Optional lifecycle rule

A useful lifecycle rule is to delete incomplete multipart uploads after seven days. This prevents abandoned multipart parts from accumulating storage charges.

---

## Part 3 — Create the S3 IAM Policy

Create one customer-managed IAM policy. The same policy can be attached to an EC2 role and, only when necessary, to a non-EC2 IAM user.

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

This policy intentionally grants object access only within the selected bucket. It does not permit changing bucket settings or accessing other buckets.

---

## Part 4 — Create the EC2 IAM Role

An EC2 IAM role is the recommended authentication method. It gives boto3 temporary, automatically rotated credentials and avoids storing AWS access keys on the server.

### 4.1 — Create the role

1. Go to **IAM → Roles → Create role**.
2. Trusted entity type: **AWS service**.
3. Use case: **EC2**.
4. Attach `BadmintonVideoVaultS3Policy`.
5. Name the role:

   ```text
   BadmintonVideoVaultEC2Role
   ```

### 4.2 — Attach it during launch

During EC2 launch, open **Advanced details → IAM instance profile** and select `BadmintonVideoVaultEC2Role`.

### 4.3 — Attach it after the instance already exists

You do not need to recreate an instance merely because the role was omitted at launch:

1. Go to **EC2 → Instances**.
2. Select the instance.
3. Choose **Actions → Security → Modify IAM role**.
4. Select `BadmintonVideoVaultEC2Role`.
5. Choose **Update IAM role**.

An EC2 instance can have one instance role at a time, while that role can contain multiple policies.

### 4.4 — Static access keys are fallback-only

Create an IAM user and access key only when running the application outside EC2 and no workload role is available. Never commit access keys to GitHub.

When the EC2 role is attached, do **not** put these variables in `.env`:

```text
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
```

---

## Part 5 — Configure CORS Only If Needed

The current application uploads to S3 from the server, not directly from browser JavaScript. Start without an S3 CORS rule.

Add CORS only when the browser developer console shows a genuine S3 cross-origin error during playback or when a future direct browser-to-S3 upload feature is introduced.

Example:

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

Replace the origin with the exact production origin. Do not use `"*"` for a private production vault unless the design explicitly requires it.

---

## Part 6 — Launch or Prepare an EC2 Instance

### 6.1 — AMI and instance type

Recommended AMI:

```text
Ubuntu Server 22.04 LTS or Ubuntu Server 24.04 LTS
64-bit x86
```

Instance guidance:

| Workload | Suggested starting point |
|---|---|
| Light personal use and small uploads | `t2.micro` or `t3.micro`, one Gunicorn worker, 2 GiB swap |
| Uploads of several hundred MB, or several users | At least 2 GiB RAM, such as `t3.small` |
| Frequent large uploads | More RAM and direct browser-to-S3 multipart upload design |

A micro instance has roughly 1 GiB RAM. Three Gunicorn workers are not appropriate for this application on that memory size.

### 6.2 — Key pair

Create an RSA `.pem` key pair and store it securely. It cannot be downloaded again.

On Linux or macOS:

```bash
chmod 400 ~/.ssh/badminton-vault-key.pem
```

On Windows, use the built-in OpenSSH client from PowerShell and keep the key under your user profile, for example:

```powershell
ssh -i "$HOME\.ssh\badminton-vault-key.pem" ubuntu@YOUR_ELASTIC_IP
```

### 6.3 — Security group

Use these inbound rules:

| Type | Port | Source | Purpose |
|---|---:|---|---|
| SSH | 22 | Your public IP `/32` | SSH from your computer |
| HTTP | 80 | `0.0.0.0/0` and optionally `::/0` | Initial web access and certificate validation |
| HTTPS | 443 | `0.0.0.0/0` and optionally `::/0` | Production web access |

Do not open port 5000.

Avoid leaving SSH open to `0.0.0.0/0`. If you use browser-based **EC2 Instance Connect with a public IP**, allow port 22 from the AWS-managed prefix list named:

```text
com.amazonaws.YOUR-REGION.ec2-instance-connect
```

For Singapore, the name is:

```text
com.amazonaws.ap-southeast-1.ec2-instance-connect
```

GitHub-hosted Actions runners do not have one fixed source IP. Part 12 describes the security tradeoff before enabling SSH-based continuous deployment.

### 6.4 — Storage

Configure a **20 GiB gp3** root volume as a practical starting point and enable EBS encryption.

The root volume stores:

- Ubuntu and installed packages
- The application and Python virtual environment
- SQLite metadata
- Temporary request data
- Logs
- The optional 2 GiB swap file

Videos themselves are stored in S3.

### 6.5 — Elastic IP

Allocate and associate an Elastic IP so the server address remains stable after stops and starts. Record it as:

```text
YOUR_ELASTIC_IP
```

Public IPv4 addresses may be billed. Check current AWS pricing.

---

## Part 7 — Connect and Prepare Ubuntu

### 7.1 — Connect

From Linux, macOS, or Windows OpenSSH:

```bash
ssh -i ~/.ssh/badminton-vault-key.pem ubuntu@YOUR_ELASTIC_IP
```

The Ubuntu AMI username is `ubuntu`.

You may instead use **EC2 → Instances → Connect → EC2 Instance Connect** after configuring the correct prefix-list rule described in Part 6.3.

### 7.2 — Refresh package metadata first

Run:

```bash
sudo apt update
sudo apt upgrade -y
```

`apt update` is essential. Running only `apt upgrade` does not refresh the package index.

### 7.3 — Install operating-system packages

```bash
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

Verify:

```bash
python3 --version
git --version
nginx -v
```

If Ubuntu says `python3-pip` or `python3-venv` cannot be found:

```bash
sudo apt install -y software-properties-common
sudo add-apt-repository -y universe
sudo apt update
sudo apt install -y python3-pip python3-venv
```

### 7.4 — Install AWS CLI version 2

Do not depend on the Ubuntu `awscli` package being available or current. Install the official bundled AWS CLI v2:

```bash
ARCH="$(uname -m)"

case "$ARCH" in
  x86_64)
    AWSCLI_ARCH="x86_64"
    ;;
  aarch64|arm64)
    AWSCLI_ARCH="aarch64"
    ;;
  *)
    echo "Unsupported architecture: $ARCH"
    exit 1
    ;;
esac

curl "https://awscli.amazonaws.com/awscli-exe-linux-${AWSCLI_ARCH}.zip" \
  -o /tmp/awscliv2.zip

rm -rf /tmp/aws
unzip -q /tmp/awscliv2.zip -d /tmp
sudo /tmp/aws/install
rm -rf /tmp/aws /tmp/awscliv2.zip

aws --version
```

Do not run `aws configure` when using the EC2 IAM role.

Verify the attached role:

```bash
aws sts get-caller-identity
```

The ARN should contain:

```text
assumed-role/BadmintonVideoVaultEC2Role/
```

### 7.5 — Add swap on a 1 GiB micro instance

Check memory:

```bash
free -h
```

If the instance has about 1 GiB RAM and no swap, add a 2 GiB swap file:

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

Swap protects against temporary memory spikes but is much slower than RAM. If the application regularly uses substantial swap, resize the EC2 instance.

### 7.6 — Create the empty application directory

```bash
sudo mkdir -p /srv/badminton-video-vault
sudo chown ubuntu:ubuntu /srv/badminton-video-vault
```

Do not create `data/` yet. The destination must be empty before `git clone`.

Confirm:

```bash
ls -la /srv/badminton-video-vault
```

---

## Part 8 — Deploy the Application

### 8.1 — Clone the repository

For a **public** repository:

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/badminton-video-vault.git \
  /srv/badminton-video-vault

cd /srv/badminton-video-vault
mkdir -p data
```

The repository must be cloned first; only then create `data/`.

For a **private** repository, use a read-only deploy key:

```bash
ssh-keygen -t ed25519 \
  -C "badminton-video-vault-deploy-key" \
  -f ~/.ssh/deploy_key \
  -N ""

cat ~/.ssh/deploy_key.pub
```

Add the displayed public key under **GitHub repository → Settings → Deploy keys**, without write access. Then:

```bash
cat > ~/.ssh/config <<'EOF'
Host github.com
  IdentityFile ~/.ssh/deploy_key
  IdentitiesOnly yes
EOF

chmod 600 ~/.ssh/config

git clone git@github.com:YOUR_GITHUB_USERNAME/badminton-video-vault.git \
  /srv/badminton-video-vault

cd /srv/badminton-video-vault
mkdir -p data
```

### 8.2 — Create the virtual environment

```bash
cd /srv/badminton-video-vault
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 8.3 — Create `.env`

Generate a Flask secret:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Create the file:

```bash
nano /srv/badminton-video-vault/.env
```

Initial configuration when using the EC2 role:

```ini
FLASK_SECRET_KEY=PASTE_A_LONG_RANDOM_VALUE
FLASK_ENV=production
AUTO_CREATE_DB=false

DATABASE_URL=sqlite:////srv/badminton-video-vault/data/badminton_vault.db

AWS_REGION=ap-southeast-1
S3_BUCKET_NAME=your-exact-bucket-name
PRESIGNED_URL_EXPIRY=3600

# Initial HTTP testing. Change this after HTTPS is working.
APP_BASE_URL=http://YOUR_ELASTIC_IP

# Keep true until Mailgun is fully configured and tested.
MAIL_SUPPRESS_SEND=true
MAILGUN_TEST_MODE=false
MAILGUN_TIMEOUT_SECONDS=10
```

When enabling Mailgun HTTP API delivery, also add:

```ini
MAILGUN_API_KEY=your-mailgun-domain-sending-key
MAILGUN_DOMAIN=notifications.example.com
MAILGUN_API_BASE_URL=https://api.mailgun.net
MAIL_FROM="Badminton Video Vault <noreply@notifications.example.com>"
MAIL_SUPPRESS_SEND=false
```

Do not add AWS access-key variables when the instance role is attached.

Protect the file:

```bash
chmod 600 /srv/badminton-video-vault/.env
```

Important details:

- `sqlite:////` has four slashes because the database path is absolute.
- `APP_BASE_URL` is used in password-reset and magic-login email links.
- After HTTPS is configured, change `APP_BASE_URL` to the final `https://` URL and restart the service.

### 8.4 — Initialise the database and administrator

```bash
cd /srv/badminton-video-vault
source venv/bin/activate

flask init-db
flask create-admin
```

### 8.5 — Manual smoke test

Run Gunicorn temporarily:

```bash
cd /srv/badminton-video-vault
source venv/bin/activate
gunicorn --bind 127.0.0.1:5000 --workers 1 app:app
```

In a second session:

```bash
curl -i http://127.0.0.1:5000/login
```

Expect `HTTP/1.1 200 OK`. Stop the temporary Gunicorn process with `Ctrl+C`.

---

## Part 9 — Configure Gunicorn with systemd

The service below fixes two important deployment hazards:

1. `RuntimeDirectory=` creates a writable directory under `/run` for the unprivileged `ubuntu` process.
2. One worker avoids exhausting a 1 GiB micro instance during a large upload.

### 9.1 — Create the service

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
    --timeout 1200 \
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

Why these values:

- `--workers 1`: appropriate for the documented 1 GiB micro instance.
- `--timeout 1200`: allows up to 20 minutes for a slow large upload before a silent synchronous worker is killed.
- `RuntimeDirectory=badminton-vault`: avoids `Permission denied` when binding directly under `/run`.
- `UMask=0007`: allows Nginx, running in the `www-data` group, to use the socket.

If you resize to substantially more RAM, increase worker count only after monitoring memory under realistic uploads.

### 9.2 — Start and verify

```bash
sudo systemctl daemon-reload
sudo systemctl enable badminton-vault
sudo systemctl restart badminton-vault

sleep 5
sudo systemctl status badminton-vault --no-pager -l
```

Confirm:

```bash
ls -l /run/badminton-vault/
ps aux | grep '[g]unicorn'
```

You should see:

```text
/run/badminton-vault/badminton-vault.sock
```

and one Gunicorn master plus one worker.

### 9.3 — Configure log rotation

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

## Part 10 — Configure Nginx

### 10.1 — Create the site

```bash
sudo nano /etc/nginx/sites-available/badminton-vault
```

For initial access by Elastic IP or EC2 public DNS name:

```nginx
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    server_name _;

    client_max_body_size 2G;

    client_body_timeout 1200s;
    proxy_read_timeout 1200s;
    proxy_send_timeout 1200s;
    proxy_connect_timeout 60s;

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/badminton-vault/badminton-vault.sock;

        # Avoid Nginx buffering the entire large request body before proxying.
        proxy_request_buffering off;
    }
}
```

The request still passes through Flask and Gunicorn. Disabling Nginx request buffering does not remove the application server's RAM and temporary-storage requirements.

### 10.2 — Disable the Ubuntu default site

Without this step, browsing by public DNS name can show **Welcome to nginx!** instead of the application.

```bash
sudo rm -f /etc/nginx/sites-enabled/default

sudo ln -sf \
  /etc/nginx/sites-available/badminton-vault \
  /etc/nginx/sites-enabled/badminton-vault
```

### 10.3 — Test and reload

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Test inside EC2:

```bash
curl -i http://127.0.0.1/login
```

Then browse to:

```text
http://YOUR_ELASTIC_IP
```

You should see the login page.

---

## Part 11 — Configure a Domain and HTTPS

### 11.1 — Point DNS to the Elastic IP

Create an `A` record:

```text
Type: A
Name: vault
Value: YOUR_ELASTIC_IP
TTL: 300
```

This example produces:

```text
vault.example.com
```

Check propagation:

```bash
dig +short vault.example.com
```

Continue only after it returns the Elastic IP.

### 11.2 — Set the Nginx server name

Edit:

```bash
sudo nano /etc/nginx/sites-available/badminton-vault
```

Replace:

```nginx
server_name _;
```

with:

```nginx
server_name vault.example.com;
```

Then:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Confirm `http://vault.example.com` works.

### 11.3 — Install Certbot and obtain a certificate

```bash
sudo apt update
sudo apt install -y certbot python3-certbot-nginx

sudo certbot --nginx -d vault.example.com
```

Verify renewal:

```bash
sudo systemctl status certbot.timer --no-pager
sudo certbot renew --dry-run
```

### 11.4 — Update `APP_BASE_URL`

After HTTPS works:

```bash
nano /srv/badminton-video-vault/.env
```

Change:

```ini
APP_BASE_URL=http://YOUR_ELASTIC_IP
```

to:

```ini
APP_BASE_URL=https://vault.example.com
```

Restart:

```bash
sudo systemctl restart badminton-vault
```

No database recreation or reinstall is required.

---

## Part 12 — Continuous Deployment from GitHub

The repository includes `.github/workflows/deploy.yml`. It:

1. Runs all smoke tests for pull requests and pushes to `main`.
2. Deploys only after a successful push to `main`.
3. Pulls code on EC2, updates dependencies, restarts Gunicorn, and checks the Unix socket.

The health check must use:

```text
/run/badminton-vault/badminton-vault.sock
```

### 12.1 — Required GitHub secrets

Under **Repository → Settings → Secrets and variables → Actions**, add:

| Secret | Value |
|---|---|
| `EC2_HOST` | Elastic IP or production hostname |
| `EC2_SSH_KEY` | Complete private `.pem` key contents |

### 12.2 — SSH security tradeoff

A GitHub-hosted runner must reach port 22. GitHub publishes changing runner IP ranges, so permanently allowing a small static source list is not straightforward.

Preferred production approaches are:

- AWS Systems Manager deployment
- A self-hosted runner inside the VPC
- A controlled deployment host with a fixed source IP

Opening port 22 to `0.0.0.0/0` merely to support GitHub Actions increases attack exposure and is not the default recommendation in this guide. For a small initial deployment, manual pull-and-restart is safer while SSH remains restricted to your IP.

### 12.3 — Manual deployment

```bash
cd /srv/badminton-video-vault
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart badminton-vault
```

Verify:

```bash
curl --fail --silent --show-error \
  --unix-socket /run/badminton-vault/badminton-vault.sock \
  http://localhost/login > /dev/null \
  && echo "Application is healthy"
```

---

## Database and Backup Options

### SQLite on the EC2 root volume

SQLite is suitable for this guide's single-instance, light-concurrency deployment.

```ini
DATABASE_URL=sqlite:////srv/badminton-video-vault/data/badminton_vault.db
```

Limitations:

- Only one EC2 application instance should write to the file.
- SQLite is not a substitute for a managed database in an auto-scaled design.
- The root EBS volume is a single point of failure unless backed up.

### Safe SQLite backup to S3

Create:

```bash
mkdir -p /srv/badminton-video-vault/scripts
nano /srv/badminton-video-vault/scripts/backup-db.sh
```

Use:

```bash
#!/bin/bash
set -euo pipefail

DATA_DIR=/srv/badminton-video-vault/data
BACKUP_DIR="$DATA_DIR/backups"
BUCKET_NAME=your-exact-bucket-name
TIMESTAMP="$(date +%Y%m%d%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/badminton_vault-$TIMESTAMP.db"

mkdir -p "$BACKUP_DIR"

sqlite3 "$DATA_DIR/badminton_vault.db" \
  ".backup '$BACKUP_FILE'"

aws s3 cp "$BACKUP_FILE" \
  "s3://$BUCKET_NAME/backups/$(basename "$BACKUP_FILE")"
```

Then:

```bash
chmod +x /srv/badminton-video-vault/scripts/backup-db.sh
```

Run it manually once before scheduling it. The EC2 role supplies AWS CLI credentials automatically.

Example daily cron entry:

```cron
0 2 * * * /srv/badminton-video-vault/scripts/backup-db.sh
```

Also take periodic EBS snapshots or use AWS Backup.

### RDS

Use Amazon RDS PostgreSQL when you need multiple application instances, managed backups, stronger concurrency, or an architecture where the local filesystem is ephemeral.

Never expose PostgreSQL directly to `0.0.0.0/0`. Allow port 5432 only from the EC2 application's security group.

---

## Verify the Complete Setup

### 1 — Verify the EC2 role

```bash
aws sts get-caller-identity
```

### 2 — Verify S3 object operations

From `/srv/badminton-video-vault` with the virtual environment active:

```bash
python - <<'PY'
import os
import boto3
from dotenv import load_dotenv

load_dotenv("/srv/badminton-video-vault/.env")

region = os.environ["AWS_REGION"]
bucket = os.environ["S3_BUCKET_NAME"]
key = "deployment-tests/connectivity-test.txt"

s3 = boto3.client("s3", region_name=region)
s3.put_object(Bucket=bucket, Key=key, Body=b"connectivity test")
s3.get_object(Bucket=bucket, Key=key)["Body"].read()
s3.delete_object(Bucket=bucket, Key=key)

print(f"S3 put/get/delete succeeded for {bucket} in {region}")
PY
```

### 3 — Verify services and socket

```bash
sudo systemctl is-active badminton-vault
sudo systemctl is-active nginx
ls -l /run/badminton-vault/badminton-vault.sock
curl -i http://127.0.0.1/login
```

### 4 — Verify uploads progressively

1. Upload a small MP4, such as 10–30 MB.
2. Confirm the object appears under `videos/<user-id>/` in S3.
3. Confirm playback and deletion.
4. Only then test a larger file.

For a large-file test, monitor:

```bash
watch -n 1 'free -h; echo; swapon --show'
```

and in another session:

```bash
sudo tail -f \
  /var/log/badminton-vault/error.log \
  /var/log/nginx/error.log
```

---

## Maintenance

### Logs

```bash
sudo tail -f /var/log/badminton-vault/error.log
sudo tail -f /var/log/badminton-vault/access.log
sudo journalctl -u badminton-vault -f
sudo tail -f /var/log/nginx/error.log
```

### Service status

```bash
sudo systemctl status badminton-vault --no-pager -l
sudo systemctl status nginx --no-pager -l
```

### Restart

```bash
sudo systemctl restart badminton-vault
sudo systemctl reload nginx
```

### Check disk, RAM, and swap

```bash
df -h / /tmp
free -h
swapon --show
```

### Apply Ubuntu security updates

```bash
sudo apt update
sudo apt upgrade -y
```

Reboot when required:

```bash
sudo reboot
```

After reconnecting:

```bash
sudo systemctl is-active badminton-vault
sudo systemctl is-active nginx
```

---

## Security Best Practices

- Keep S3 Block Public Access enabled.
- Use the EC2 role instead of static access keys.
- Restrict SSH to your IP, an EC2 Instance Connect prefix list, SSM, or a controlled deployment source.
- Keep `.env` at mode `600`.
- Use a strong `FLASK_SECRET_KEY`.
- Use HTTPS before storing real user credentials or sensitive session metadata.
- Keep `PRESIGNED_URL_EXPIRY` as short as practical.
- Enable EBS encryption and scheduled backups.
- Do not commit SQLite databases, `.env`, private keys, Mailgun keys, or uploaded media.
- Keep Mailgun integration on the HTTP API settings documented here; do not add SMTP credentials unless the application is intentionally redesigned.
- Review logs after repeated failed logins, upload failures, worker restarts, or OOM events.

---

## Capacity and Cost Notes

### Memory

A 1 GiB instance can run this application for light use with:

- One Gunicorn worker
- A 2 GiB swap file
- Limited simultaneous requests
- Progressive testing of upload sizes

Swap is an emergency buffer, not equivalent to RAM. Resize the instance if large uploads regularly consume swap or if more concurrent users are required.

### Disk

A 20 GiB root volume is normally sufficient for the application, SQLite, logs, swap, and temporary data when videos are stored in S3. Check:

```bash
df -h / /tmp
```

The free space should comfortably exceed the largest upload plus operating-system headroom.

### Public IPv4 and AWS service pricing

EC2, EBS, S3, data transfer, public IPv4, snapshots, and RDS pricing varies by region and changes over time. Use AWS Pricing Calculator, Cost Explorer, Budgets, and the current service pricing pages rather than relying on fixed values in this guide.

---

## Troubleshooting

### Package installation

| Symptom | Cause | Fix |
|---|---|---|
| `Unable to locate package python3-pip` | Package index was not refreshed or Universe is disabled | Run `sudo apt update`; enable Universe as shown in Part 7.3 |
| `Package awscli has no installation candidate` | Ubuntu repository package unavailable or unsupported | Install official AWS CLI v2 as shown in Part 7.4 |
| `System restart required` | Kernel or core packages were upgraded | Reboot, reconnect, and verify both services |

### IAM and S3

| Symptom | Cause | Fix |
|---|---|---|
| `NoCredentialsError` | No instance role and no fallback credentials | Attach `BadmintonVideoVaultEC2Role`; verify with `aws sts get-caller-identity` |
| `AccessDenied` on upload | Missing `s3:PutObject` or wrong bucket ARN | Correct the policy resource and action |
| `AccessDenied` on playback | Missing `s3:GetObject` | Correct the policy |
| `NoSuchBucket` | Wrong `S3_BUCKET_NAME` | Copy the exact bucket name |
| `301`, redirect, or signature mismatch | Wrong bucket region | Set `AWS_REGION` to the bucket's actual region |
| Small upload works but large upload fails | Resource exhaustion or timeout | Use one worker, 1200-second timeouts, swap, and more RAM when needed |

### Gunicorn and systemd

| Symptom | Cause | Fix |
|---|---|---|
| `/run/badminton-vault.sock: Permission denied` | Unprivileged process tried to create a socket directly under `/run` | Use `RuntimeDirectory=badminton-vault` and the nested socket path from Part 9 |
| Socket does not exist | Service failed, restarted, or used a different path | Check `systemctl status`, journal, and `/var/log/badminton-vault/error.log` |
| Status briefly says active but restart count rises | Gunicorn is crashing in a loop | Stop the service and inspect the full status and logs |
| `Worker was sent SIGKILL! Perhaps out of memory?` | Linux OOM killer terminated a worker | Reduce to one worker, enable swap, and use an instance with more RAM |
| Generic 500 during a large upload with no Python traceback | Worker was killed before Flask could log an exception | Check the kernel OOM log below |

Check OOM activity:

```bash
sudo journalctl -k -b | \
  grep -Ei 'out of memory|oom-kill|killed process' | \
  tail -n 50
```

### Nginx

| Symptom | Cause | Fix |
|---|---|---|
| **Welcome to nginx!** | Ubuntu default site is still enabled or host did not match | Remove `/etc/nginx/sites-enabled/default`; use the catch-all initial configuration |
| `502 Bad Gateway` | Gunicorn is down or Nginx points to the wrong socket | Verify `/run/badminton-vault/badminton-vault.sock` and the `proxy_pass` path |
| `413 Request Entity Too Large` | `client_max_body_size` is too small | Use `client_max_body_size 2G` |
| Upload stops after several minutes | Nginx or Gunicorn timeout | Use the 1200-second values in Parts 9 and 10 |
| Nginx configuration test fails | Syntax or duplicate default server | Run `sudo nginx -t`; ensure the Ubuntu default site is disabled |

### Git and deployment

| Symptom | Cause | Fix |
|---|---|---|
| Clone destination is not empty | `data/` or another file was created before cloning | Remove only the unintended empty content, clone first, then create `data/` |
| Public repository prompts for credentials | Wrong clone URL or repository is not actually public | Use the HTTPS URL shown in Part 8.1 |
| Private repository cannot clone | No deploy key or wrong SSH config | Configure the read-only deploy key |
| GitHub Actions health check fails after this update | Workflow still uses old socket path | Use `/run/badminton-vault/badminton-vault.sock` |
| Password-reset link uses HTTP after HTTPS setup | `APP_BASE_URL` was not updated | Change it to the final HTTPS URL and restart Gunicorn |

### Useful diagnostic bundle

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

## Official References

- [Amazon EC2 documentation](https://docs.aws.amazon.com/ec2/)
- [Attach an IAM role to an EC2 instance](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/attach-iam-role.html)
- [EC2 Instance Connect prerequisites](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-connect-prerequisites.html)
- [AWS CLI version 2 installation](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [Amazon S3 documentation](https://docs.aws.amazon.com/s3/)
- [Gunicorn settings](https://docs.gunicorn.org/en/stable/settings.html)
- [systemd execution directories](https://man7.org/linux/man-pages/man5/systemd.exec.5.html)
