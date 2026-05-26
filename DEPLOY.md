# Deploying to AWS EC2 from GitHub

This guide walks through deploying Badminton Video Vault to a single AWS EC2 instance, with a GitHub Actions pipeline that automatically tests and deploys every push to `main`.

**Before you begin:** complete [AWS_setup.md](AWS_setup.md) first — you will need your S3 bucket, IAM credentials, and `FLASK_SECRET_KEY` ready before starting Part 3.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Part 1 — Launch an EC2 Instance](#part-1--launch-an-ec2-instance)
3. [Part 2 — Connect and Prepare the Server](#part-2--connect-and-prepare-the-server)
4. [Part 3 — Deploy the Application](#part-3--deploy-the-application)
5. [Part 4 — Configure Gunicorn as a Systemd Service](#part-4--configure-gunicorn-as-a-systemd-service)
6. [Part 5 — Configure Nginx as a Reverse Proxy](#part-5--configure-nginx-as-a-reverse-proxy)
7. [Part 6 — HTTPS with Let's Encrypt (Recommended)](#part-6--https-with-lets-encrypt-recommended)
8. [Part 7 — Continuous Deployment from GitHub](#part-7--continuous-deployment-from-github)
9. [Maintenance](#maintenance)
10. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
GitHub (push to main)
        │
        ▼
GitHub Actions
  ├─ Run smoke test suite (67 tests)   ← deploy is blocked if any test fails
  └─ SSH into EC2 → git pull → pip install → systemctl restart
        │
        ▼
EC2 Instance (Ubuntu 22.04)
  ├─ Nginx  (port 80/443, reverse proxy)
  ├─ Gunicorn  (WSGI, unix socket, 3 workers)
  ├─ Flask app  (/srv/badminton-video-vault)
  ├─ SQLite DB  (/srv/badminton-video-vault/data/badminton_vault.db)
  └─ .env file  (production secrets, never in git)
        │
        ▼
AWS S3  (video file storage, presigned URLs for playback)
```

---

## Part 1 — Launch an EC2 Instance

### 1.1 — Choose an AMI and Instance Type

1. In the AWS Management Console, navigate to **EC2 → Instances → Launch instances**.
2. Set **Name**: `badminton-video-vault`.
3. Under **Application and OS Images**, choose:
   - **Ubuntu Server 22.04 LTS (HVM), SSD Volume Type** — search for it in the Quick Start list.
   - Architecture: **64-bit (x86)**.
4. Under **Instance type**, choose:
   - **t2.micro** — free tier eligible (750 hours/month for 12 months).
   - If your free tier has expired, **t3.micro** (~$0.01/hour) is the next cheapest option.

### 1.2 — Create a Key Pair

1. Under **Key pair (login)**, click **Create new key pair**.
2. Name it `badminton-vault-key`.
3. Key pair type: **RSA**, format: **.pem**.
4. Click **Create key pair** — the `.pem` file downloads automatically.
5. Move it somewhere safe:
   ```bash
   mv ~/Downloads/badminton-vault-key.pem ~/.ssh/
   chmod 400 ~/.ssh/badminton-vault-key.pem
   ```

> ⚠️ **You cannot re-download this file.** If you lose it, you will need to create a new key pair and replace the instance.

### 1.3 — Configure the Security Group

Under **Network settings**, click **Edit** and configure inbound rules:

| Type | Protocol | Port | Source | Purpose |
|------|----------|------|--------|---------|
| SSH | TCP | 22 | 0.0.0.0/0 | Remote access (key-based only; see note below) |
| HTTP | TCP | 80 | 0.0.0.0/0 | Web traffic |
| HTTPS | TCP | 443 | 0.0.0.0/0 | Secure web traffic |

> **Security note on SSH port 22:** Allowing SSH from `0.0.0.0/0` is acceptable as long as password authentication is disabled (Ubuntu's default) and you keep your `.pem` key secure. If you prefer stricter access, restrict port 22 to your home IP address — but note that GitHub Actions deployment will then require a different approach (e.g., AWS SSM Session Manager).

### 1.4 — Configure Storage

Under **Configure storage**, set:
- **8 GiB gp3** root volume (free tier provides 30 GB; 8 GB is sufficient since videos live in S3).

### 1.5 — Launch

Click **Launch instance** and wait for the **Instance state** to show **Running**.

### 1.6 — Assign an Elastic IP

Without an Elastic IP, your instance's public IP changes every time it stops and starts.

1. In the EC2 console, navigate to **Network & Security → Elastic IPs**.
2. Click **Allocate Elastic IP address → Allocate**.
3. Select the newly allocated IP, then **Actions → Associate Elastic IP address**.
4. Select your instance and click **Associate**.
5. **Record this IP address** — you will need it throughout this guide.

---

## Part 2 — Connect and Prepare the Server

### 2.1 — SSH Into the Instance

```bash
ssh -i ~/.ssh/badminton-vault-key.pem ubuntu@YOUR_ELASTIC_IP
```

Replace `YOUR_ELASTIC_IP` with the Elastic IP you just assigned.

### 2.2 — Update Packages

```bash
sudo apt update && sudo apt upgrade -y
```

### 2.3 — Install System Dependencies

```bash
sudo apt install -y python3 python3-pip python3-venv git nginx
```

Verify Python is 3.10 or later:

```bash
python3 --version
```

### 2.4 — Create the Application Directory

```bash
sudo mkdir -p /srv/badminton-video-vault
sudo chown ubuntu:ubuntu /srv/badminton-video-vault
```

Also create a dedicated directory for the SQLite database:

```bash
mkdir -p /srv/badminton-video-vault/data
```

---

## Part 3 — Deploy the Application

### 3.1 — Clone the Repository

```bash
cd /srv
git clone https://github.com/YOUR_GITHUB_USERNAME/badminton-video-vault.git
cd badminton-video-vault
```

Replace `YOUR_GITHUB_USERNAME` with your GitHub username. If the repository is private, you will need to authenticate — the easiest approach is to use a [GitHub Personal Access Token](https://github.com/settings/tokens) as the password when prompted, or set up an SSH deploy key.

### 3.2 — Create and Activate the Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3.3 — Install Python Dependencies

```bash
pip install -r requirements.txt
```

This includes `gunicorn`, which is required to serve the app in production.

### 3.4 — Create the Production `.env` File

The `.env` file is **not** in the repository (it is gitignored). Create it directly on the server:

```bash
nano /srv/badminton-video-vault/.env
```

Paste and fill in all values:

```ini
# Flask
FLASK_SECRET_KEY=generate-a-long-random-string-here
FLASK_ENV=production

# Database — absolute path to keep it outside the app directory
DATABASE_URL=sqlite:////srv/badminton-video-vault/data/badminton_vault.db

# AWS S3 (from AWS_setup.md)
AWS_ACCESS_KEY_ID=AKIA...your-access-key-id...
AWS_SECRET_ACCESS_KEY=your-secret-access-key
AWS_REGION=us-east-1
S3_BUCKET_NAME=your-bucket-name
PRESIGNED_URL_EXPIRY=3600
```

To generate a secure secret key, run:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

> **Important:** The `DATABASE_URL` uses four slashes (`sqlite:////`) to denote an absolute path on the filesystem. This ensures the database lives at `/srv/badminton-video-vault/data/badminton_vault.db` regardless of the working directory.

### 3.5 — Initialise the Database

**Run these commands only once on first deploy.** Running `init-db` again on an existing installation will drop and recreate all tables, erasing all data.

```bash
cd /srv/badminton-video-vault
source venv/bin/activate
flask init-db
flask create-admin
```

Follow the prompts for `create-admin` to set up the admin account.

### 3.6 — Smoke-Test the Application Manually

Before configuring the service, verify the app starts:

```bash
cd /srv/badminton-video-vault
source venv/bin/activate
gunicorn --bind 0.0.0.0:5000 --workers 1 app:app
```

In a browser, navigate to `http://YOUR_ELASTIC_IP:5000`. You should see the login page.

Press `Ctrl+C` to stop Gunicorn when done.

---

## Part 4 — Configure Gunicorn as a Systemd Service

A systemd service keeps Gunicorn running, starts it automatically on boot, and restarts it if it crashes.

### 4.1 — Create the Service File

```bash
sudo nano /etc/systemd/system/badminton-vault.service
```

Paste the following:

```ini
[Unit]
Description=Gunicorn instance for Badminton Video Vault
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/srv/badminton-video-vault
EnvironmentFile=/srv/badminton-video-vault/.env
ExecStart=/srv/badminton-video-vault/venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/run/badminton-vault.sock \
    --access-logfile /var/log/badminton-vault/access.log \
    --error-logfile /var/log/badminton-vault/error.log \
    app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

### 4.2 — Create the Log Directory

```bash
sudo mkdir -p /var/log/badminton-vault
sudo chown ubuntu:ubuntu /var/log/badminton-vault
```

### 4.3 — Enable and Start the Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable badminton-vault
sudo systemctl start badminton-vault
sudo systemctl status badminton-vault
```

You should see `Active: active (running)`. If not, check the logs:

```bash
journalctl -u badminton-vault -n 50
```

---

## Part 5 — Configure Nginx as a Reverse Proxy

Nginx accepts incoming HTTP/HTTPS traffic and forwards it to Gunicorn via a Unix socket.

### 5.1 — Create the Nginx Server Block

```bash
sudo nano /etc/nginx/sites-available/badminton-vault
```

Paste the following (replace `YOUR_ELASTIC_IP` with your actual IP or domain name):

```nginx
server {
    listen 80;
    server_name YOUR_ELASTIC_IP;

    # Increase upload size limit to match app's 2 GB setting
    client_max_body_size 2G;

    # Increase timeouts for large video uploads
    proxy_read_timeout 300s;
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/badminton-vault.sock;
    }
}
```

### 5.2 — Enable the Site

```bash
sudo ln -s /etc/nginx/sites-available/badminton-vault /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

If `nginx -t` reports errors, review the config file for typos.

### 5.3 — Verify

Navigate to `http://YOUR_ELASTIC_IP` in a browser. You should see the login page served through Nginx.

---

## Part 6 — HTTPS with Let's Encrypt (Recommended)

HTTPS is strongly recommended before using the app with real data. This requires a **domain name** pointing to your Elastic IP (not just a bare IP address).

If you do not have a domain yet, skip this part and revisit it when you add one.

### 6.1 — Point a Domain at Your Elastic IP

In your DNS provider, create an A record:

```
Type: A
Name: @ (or subdomain, e.g. vault)
Value: YOUR_ELASTIC_IP
TTL: 300
```

Wait for DNS to propagate (usually a few minutes).

### 6.2 — Install Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 6.3 — Obtain the Certificate

```bash
sudo certbot --nginx -d yourdomain.com
```

Follow the prompts. Certbot will automatically edit your Nginx config to enable HTTPS and redirect HTTP to HTTPS.

### 6.4 — Auto-Renewal

Certbot installs a systemd timer that renews the certificate automatically. Verify it:

```bash
sudo systemctl status certbot.timer
```

### 6.5 — Update the Nginx Config

After certbot runs, update the `server_name` in `/etc/nginx/sites-available/badminton-vault` from the IP address to your domain name, then restart Nginx.

---

## Part 7 — Continuous Deployment from GitHub

This GitHub Actions workflow automatically:
1. Runs the full smoke test suite (67 tests) in an isolated environment.
2. **Only if all 67 tests pass**, SSHs into EC2 and deploys the new code.

A failed test blocks the deploy — satisfying the prime directive requirement that the regression suite must be 100% green before any release.

### 7.1 — Create the GitHub Actions Workflow File

In your local repository, create the following file:

```bash
mkdir -p .github/workflows
```

Create `.github/workflows/deploy.yml`:

```yaml
name: Test and Deploy

on:
  push:
    branches:
      - main

jobs:
  # ── Job 1: Run smoke tests ─────────────────────────────────────────────────
  test:
    name: Smoke Tests
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run regression suite
        run: python tests/run_all_smoke.py

  # ── Job 2: Deploy to EC2 (only runs if test job passed) ────────────────────
  deploy:
    name: Deploy to EC2
    runs-on: ubuntu-latest
    needs: test          # blocked until all smoke tests pass

    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ubuntu
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            set -e

            cd /srv/badminton-video-vault

            # Pull latest code
            git pull origin main

            # Activate venv and update dependencies
            source venv/bin/activate
            pip install -r requirements.txt

            # Restart the application service
            sudo systemctl restart badminton-vault

            # Confirm the service came back up
            sleep 3
            sudo systemctl is-active --quiet badminton-vault && echo "Service is running." || (echo "Service failed to start!" && exit 1)
```

### 7.2 — Add GitHub Secrets

The workflow needs two secrets stored in your GitHub repository:

1. Navigate to your GitHub repository → **Settings → Secrets and variables → Actions → New repository secret**.

2. Add the following secrets:

   | Secret name | Value |
   |-------------|-------|
   | `EC2_HOST` | Your Elastic IP address (e.g. `54.123.45.67`) |
   | `EC2_SSH_KEY` | The full contents of your `.pem` file — including the `-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----` lines |

   To copy the private key content:
   ```bash
   cat ~/.ssh/badminton-vault-key.pem
   ```
   Select and copy everything, then paste it into the secret value.

### 7.3 — Push the Workflow

```bash
git add .github/workflows/deploy.yml requirements.txt
git commit -m "Add CI/CD workflow; add gunicorn to requirements"
git push
```

Navigate to your GitHub repository → **Actions**. You should see the workflow run. It will:
- Spin up a fresh Ubuntu runner.
- Install dependencies.
- Run all 67 smoke tests.
- If they all pass, SSH into EC2 and deploy.

### 7.4 — How Each Subsequent Deploy Works

Every time you push to `main`:

```
You push code to GitHub
         │
         ▼
GitHub Actions spins up a fresh runner
         │
         ├─ Installs Python + requirements
         ├─ Runs tests/run_all_smoke.py
         │         │
         │    All 67 pass?
         │         │
         │    No ──► Workflow fails. Deploy is blocked. EC2 is untouched.
         │         │
         │    Yes ─►│
         │          ▼
         │    SSH into EC2
         │    git pull origin main
         │    pip install -r requirements.txt
         │    systemctl restart badminton-vault
         │    Verify service is active
         │          │
         ▼          ▼
     Workflow passes. New version is live.
```

> **First deploy only:** `flask init-db` and `flask create-admin` are one-time setup steps you ran manually in Part 3. The GitHub Actions deploy script intentionally does **not** run them — doing so would drop and recreate all tables on every deploy, erasing your data.

---

## Maintenance

### Viewing Logs

```bash
# Application errors (gunicorn stderr)
tail -f /var/log/badminton-vault/error.log

# HTTP access log (gunicorn)
tail -f /var/log/badminton-vault/access.log

# Systemd service journal (startup errors, crashes)
journalctl -u badminton-vault -f

# Nginx error log
sudo tail -f /var/log/nginx/error.log
```

### Manually Deploying Without GitHub Actions

If you need to deploy directly from the server:

```bash
ssh -i ~/.ssh/badminton-vault-key.pem ubuntu@YOUR_ELASTIC_IP
cd /srv/badminton-video-vault
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart badminton-vault
```

### Restarting the Application

```bash
sudo systemctl restart badminton-vault   # restart gunicorn
sudo systemctl restart nginx             # restart nginx (rarely needed)
```

### Checking Service Status

```bash
sudo systemctl status badminton-vault
sudo systemctl status nginx
```

### Stopping and Starting the Instance

When you stop an EC2 instance, the Elastic IP remains assigned. Your data (SQLite DB) is on the EBS root volume and is preserved. When you restart the instance:
- Nginx and the Gunicorn service start automatically (because they are `systemctl enable`d).
- No manual steps are needed.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `502 Bad Gateway` from Nginx | Gunicorn is not running or the socket doesn't exist | `sudo systemctl restart badminton-vault` and check `journalctl -u badminton-vault -n 50` |
| `500 Internal Server Error` | Application exception | Check `/var/log/badminton-vault/error.log` |
| App starts but `.env` values missing | EnvironmentFile path wrong in service file | Verify `/etc/systemd/system/badminton-vault.service` has the correct `EnvironmentFile` path |
| `flask init-db` says `no such table` | Database path issue | Verify `DATABASE_URL` in `.env` uses four slashes for absolute path; confirm the `data/` directory exists |
| GitHub Actions deploy fails: "Permission denied (publickey)" | `EC2_SSH_KEY` secret is incorrect | Recopy the full `.pem` content (including header/footer lines) into the GitHub secret |
| GitHub Actions deploy step is skipped | Smoke tests failed in the `test` job | Fix the failing tests first; check the Actions log for which test failed |
| Large video uploads time out | Nginx `proxy_read_timeout` too short | Already set to `300s` in the Nginx config above; increase further if needed |
| Video playback fails after deploy | Presigned URL expiry or S3 region mismatch | Verify `AWS_REGION` in `.env` matches the bucket's actual region |
