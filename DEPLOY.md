# Deploying Badminton Video Vault to AWS

This guide is the single, end-to-end walkthrough for taking Badminton Video Vault from nothing to a fully running production deployment on AWS — provisioning the AWS resources (S3, IAM), launching and configuring an EC2 instance, and setting up continuous deployment from GitHub. Follow the parts in order; each part builds on the previous one.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Part 1 — Create an AWS Account](#part-1--create-an-aws-account)
4. [Part 2 — Create and Configure an S3 Bucket](#part-2--create-and-configure-an-s3-bucket)
5. [Part 3 — Set Up IAM User and Permissions](#part-3--set-up-iam-user-and-permissions)
6. [Part 4 — Generate Access Keys](#part-4--generate-access-keys)
7. [Part 5 — Configure CORS (Optional)](#part-5--configure-cors-optional)
8. [Part 6 — Launch an EC2 Instance](#part-6--launch-an-ec2-instance)
9. [Part 7 — Connect and Prepare the Server](#part-7--connect-and-prepare-the-server)
10. [Part 8 — Deploy the Application](#part-8--deploy-the-application)
11. [Part 9 — Configure Gunicorn as a Systemd Service](#part-9--configure-gunicorn-as-a-systemd-service)
12. [Part 10 — Configure Nginx as a Reverse Proxy](#part-10--configure-nginx-as-a-reverse-proxy)
13. [Part 11 — Custom Domain Setup and HTTPS with Let's Encrypt (Recommended)](#part-11--custom-domain-setup-and-https-with-lets-encrypt-recommended)
14. [Part 12 — Continuous Deployment from GitHub](#part-12--continuous-deployment-from-github)
15. [Database Options for Production](#database-options-for-production)
16. [Verify the Setup](#verify-the-setup)
17. [Maintenance](#maintenance)
18. [Security Best Practices](#security-best-practices)
19. [Cost Considerations](#cost-considerations)
20. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, ensure you have the following:

- A valid email address for AWS account registration
- A credit/debit card for AWS billing (free tier is available for new accounts)
- Python 3.8+ and the application dependencies installed locally (see [README.md](README.md))
- Basic familiarity with the AWS Management Console
- A GitHub repository fork/clone of Badminton Video Vault that you can deploy from

---

## Architecture Overview

```
GitHub (push to main)
        │
        ▼
GitHub Actions
  ├─ Run the full regression suite (all discovered smoke_*.py tests)   ← deploy is blocked if any test fails
  └─ SSH into EC2 → git pull → pip install → systemctl restart → verify HTTP response
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

The application never exposes S3 objects publicly — uploads and downloads are performed server-side, and video playback/download uses time-limited presigned URLs.

The first five parts of this guide set up the AWS resources (account, S3 bucket, IAM user, access keys). The remaining parts provision the EC2 server and deploy the application, using the credentials created earlier.

---

## Part 1 — Create an AWS Account

If you do not already have an AWS account:

1. Go to [https://aws.amazon.com/](https://aws.amazon.com/) and click **Create an AWS Account**.
2. Follow the prompts to provide your email, set a password, and enter payment details.
3. Choose the **Basic (Free)** support plan unless you require premium support.
4. Complete the identity verification process.
5. Sign in to the [AWS Management Console](https://console.aws.amazon.com/).

> **Note:** New AWS accounts have historically been eligible for the [AWS Free Tier](https://aws.amazon.com/free/), which has included a monthly allowance of S3 storage and requests plus a number of free EC2 hours for the first 12 months. **Free Tier offers, quotas, and eligibility change over time and vary by account and region** — check the [AWS Free Tier page](https://aws.amazon.com/free/) for current details rather than relying on any specific numbers.

---

## Part 2 — Create and Configure an S3 Bucket

Amazon S3 (Simple Storage Service) is used to store all uploaded video files.

### 2.1 — Create the Bucket

1. Navigate to the **S3** service in the AWS Management Console:
   - Search for "S3" in the top search bar, or find it under **Services → Storage → S3**.

2. Click **Create bucket**.

3. Configure the bucket:

   | Setting | Recommended Value |
   |---------|-------------------|
   | **Bucket name** | Choose a globally unique name (e.g., `badminton-video-vault-yourname`) |
   | **AWS Region** | Select the region closest to your users (e.g., `us-east-1`, `ap-southeast-1`) |
   | **Object Ownership** | ACLs disabled (recommended) |

4. **Block Public Access settings** — this is critical for security:
   - ✅ Check **Block *all* public access**
   - This ensures no video file is ever accidentally exposed to the internet

5. **Bucket Versioning** — leave as **Disabled** unless you want to retain previous versions of overwritten files (adds storage cost).

6. **Default encryption** — leave as **Server-side encryption with Amazon S3 managed keys (SSE-S3)** (the default).

7. Click **Create bucket**.

> **Record your bucket name** — you will use it as the `S3_BUCKET_NAME` environment variable later.

### 2.2 — Verify Public Access Is Blocked

1. Open your bucket in the S3 console.
2. Go to the **Permissions** tab.
3. Under **Block public access (bucket settings)**, confirm all four options are set to **On**:
   - Block public access to buckets and objects granted through *new* access control lists (ACLs)
   - Block public access to buckets and objects granted through *any* access control lists (ACLs)
   - Block public access to buckets and objects granted through *new* public bucket or access point policies
   - Restrict access to buckets and objects granted through *any* public bucket or access point policies

### 2.3 — Lifecycle Rules (Optional)

If you want to automatically manage storage costs, you can add lifecycle rules:

1. Go to the **Management** tab in your bucket.
2. Click **Create lifecycle rule**.
3. Example rules:
   - Move objects to **S3 Glacier** after 90 days (for archival)
   - Permanently delete incomplete multipart uploads after 7 days

---

## Part 3 — Set Up IAM User and Permissions

IAM (Identity and Access Management) controls who can access your AWS resources. You will create a dedicated IAM user for the application with the minimum permissions needed.

### Step 1: Create an IAM Policy

1. Navigate to **IAM** in the AWS Management Console (search for "IAM" in the top bar).
2. In the left sidebar, click **Policies**, then **Create policy**.
3. Click the **JSON** tab and paste the following policy:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "BadmintonVideoVaultS3Access",
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

4. Replace `YOUR-BUCKET-NAME` with the actual name of the bucket you created.
5. Click **Next**.
6. Name the policy (e.g., `BadmintonVideoVaultS3Policy`) and add an optional description.
7. Click **Create policy**.

> **Important:** This policy follows the principle of least privilege — the application can only put, get, and delete objects within the specific bucket. It cannot list buckets, modify bucket settings, or access other AWS services. There is no `s3:CreateMultipartUpload`, `s3:UploadPart`, or `s3:CompleteMultipartUpload` action in the IAM action namespace — those steps of a multipart upload are all authorized by `s3:PutObject`. `s3:AbortMultipartUpload` and `s3:ListMultipartUploadParts` are included so `boto3`'s `upload_fileobj()` (which transparently uses multipart uploads for larger files) can clean up and inspect any incomplete uploads.

### Step 2: Create an IAM User

1. In the IAM console, go to **Users** in the left sidebar.
2. Click **Create user**.
3. Enter a user name (e.g., `badminton-video-vault-app`).
4. **Do NOT** check "Provide user access to the AWS Management Console" — this user only needs programmatic access.
5. Click **Next**.

### Step 3: Attach the Policy

1. On the **Set permissions** page, select **Attach policies directly**.
2. Search for the policy you created (`BadmintonVideoVaultS3Policy`).
3. Check the box next to it.
4. Click **Next**, then **Create user**.

---

## Part 4 — Generate Access Keys

Since this application is deployed to an EC2 instance, the **recommended** way to authenticate to AWS is to attach an **EC2 instance IAM role** carrying the policy created in Part 3, rather than storing long-lived access keys in `.env`. An instance role provides temporary, automatically rotated credentials that `boto3` picks up without any configuration, and it removes the risk of an access key ever leaking from the server. See [Part 6.1a — Attach an IAM Role Instead of Access Keys](#61a--attach-an-iam-role-instead-of-access-keys-recommended) for how to create and attach the role when you launch the instance.

If you cannot use an instance role (e.g., you are testing the app somewhere other than EC2), you can fall back to a static access key pair:

1. In the IAM console, go to **Users** and click on the user you just created.
2. Go to the **Security credentials** tab.
3. Under **Access keys**, click **Create access key**.
4. Select **Application running outside AWS** as the use case.
5. Click **Next**, then **Create access key**.
6. **Important:** Copy both the **Access Key ID** and **Secret Access Key** immediately. The Secret Access Key will not be shown again.

> ⚠️ **Security Warning:** Never commit access keys to source control. Store them securely and treat them like passwords. Prefer the IAM role approach above whenever possible.

> **Checkpoint:** By this point you should have your **S3 bucket name** and **AWS region** recorded. If you are using the IAM role approach, that is all you need for AWS authentication — skip straight to Part 5. If you are using static access keys, also record the **Access Key ID** and **Secret Access Key** somewhere safe; you will need all four values in Part 8 when configuring the production `.env` file.

---

## Part 5 — Configure CORS (Optional)

CORS (Cross-Origin Resource Sharing) configuration is needed if your application serves content from a different domain than where S3 presigned URLs point. The browser fetches video playback URLs directly from S3 using presigned URLs, so CORS may be required depending on your frontend domain/origin setup. If you encounter CORS errors during video playback:

1. Open your bucket in the S3 console.
2. Go to the **Permissions** tab.
3. Scroll down to **Cross-origin resource sharing (CORS)** and click **Edit**.
4. Add the following configuration:

```json
[
    {
        "AllowedHeaders": ["*"],
        "AllowedMethods": ["GET", "PUT"],
        "AllowedOrigins": ["https://yourdomain.com"],
        "ExposeHeaders": ["ETag"],
        "MaxAgeSeconds": 3600
    }
]
```

5. Replace `https://yourdomain.com` with your application's actual domain. For local development, use `http://localhost:5000`.
6. Click **Save changes**.

---

## Part 6 — Launch an EC2 Instance

### 6.1 — Choose an AMI and Instance Type

1. In the AWS Management Console, navigate to **EC2 → Instances → Launch instances**.
2. Set **Name**: `badminton-video-vault`.
3. Under **Application and OS Images**, choose:
   - **Ubuntu Server 22.04 LTS (HVM), SSD Volume Type** — search for it in the Quick Start list.
   - Architecture: **64-bit (x86)**.
4. Under **Instance type**, choose:
   - **t2.micro** or **t3.micro** — check the [AWS Free Tier page](https://aws.amazon.com/free/) for current eligibility; otherwise pick the lowest-cost burstable instance type available in your region.

### 6.1a — Attach an IAM Role Instead of Access Keys (Recommended)

If you decided in [Part 4](#part-4--generate-access-keys) to use an EC2 instance role instead of static access keys:

1. In the IAM console, go to **Roles → Create role**.
2. Select **AWS service** as the trusted entity type, and **EC2** as the use case.
3. On the **Add permissions** page, search for and attach the policy you created in Part 3 (`BadmintonVideoVaultS3Policy`).
4. Name the role (e.g., `BadmintonVideoVaultEC2Role`) and click **Create role**.
5. Back on the **Launch an instance** page, under **Advanced details → IAM instance profile**, select the role you just created.

With an instance role attached, `boto3` automatically discovers temporary credentials from the EC2 instance metadata service — do **not** set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in `.env` in this case (see Part 8.4).

### 6.2 — Create a Key Pair

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

### 6.3 — Configure the Security Group

Under **Network settings**, click **Edit** and configure inbound rules:

| Type | Protocol | Port | Source | Purpose |
|------|----------|------|--------|---------|
| SSH | TCP | 22 | 0.0.0.0/0 | Remote access (key-based only; see note below) |
| HTTP | TCP | 80 | 0.0.0.0/0 | Web traffic |
| HTTPS | TCP | 443 | 0.0.0.0/0 | Secure web traffic |

> **Security note on SSH port 22:** Allowing SSH from `0.0.0.0/0` is acceptable as long as password authentication is disabled (Ubuntu's default) and you keep your `.pem` key secure. If you prefer stricter access, restrict port 22 to your home IP address — but note that GitHub Actions deployment will then require a different approach (e.g., AWS SSM Session Manager).

> **Note:** Port 5000 is intentionally **not** opened here. Gunicorn is only tested locally on the instance (see [Part 8.6](#86--smoke-test-the-application-manually)) and is reverse-proxied by Nginx on ports 80/443 in production.

### 6.4 — Configure Storage

Under **Configure storage**, set:
- **20 GiB gp3** root volume. Although uploaded videos are stored in S3, the application writes uploads to temporary disk space on the instance before transferring them to S3, so the root volume needs headroom beyond the OS and application footprint for large video files. Size this according to the largest single upload you expect; increase it further if you routinely upload very large videos. Check the current [AWS Free Tier](https://aws.amazon.com/free/) allowance for EBS storage, since it may not cover the full 20 GiB.
- Consider enabling **EBS encryption** (a checkbox on this screen) so the volume — including the SQLite database file — is encrypted at rest.

> **Longer-term design note:** For very large videos, uploading through the Flask app (browser → EC2 → S3) is not the most scalable approach. A direct browser-to-S3 multipart upload (using presigned POST/PUT URLs) avoids routing large file bodies through the application server entirely and is the preferred design if you expect frequent very-large uploads.

### 6.5 — Launch

Click **Launch instance** and wait for the **Instance state** to show **Running**.

> **Note:** Terminating (not just stopping) an EC2 instance may permanently delete its root EBS volume — and the SQLite database on it — depending on the volume's **Delete on Termination** setting (visible under **Storage** when launching, and under the volume's details afterward). If you want to preserve the database after terminating an instance, set **Delete on Termination** to `No`, or take an EBS snapshot before terminating (see [Security Best Practices](#security-best-practices)).

### 6.6 — Assign an Elastic IP

Without an Elastic IP, your instance's public IP changes every time it stops and starts.

1. In the EC2 console, navigate to **Network & Security → Elastic IPs**.
2. Click **Allocate Elastic IP address → Allocate**.
3. Select the newly allocated IP, then **Actions → Associate Elastic IP address**.
4. Select your instance and click **Associate**.
5. **Record this IP address** — you will need it throughout the rest of this guide.

> **Note:** AWS's pricing for public IPv4 addresses (including Elastic IPs) has changed over time and varies by account and region. Check the current [Amazon EC2 pricing page](https://aws.amazon.com/ec2/pricing/on-demand/) for the applicable rate before relying on any specific free allowance.

---

## Part 7 — Connect and Prepare the Server

### 7.1 — SSH Into the Instance

```bash
ssh -i ~/.ssh/badminton-vault-key.pem ubuntu@YOUR_ELASTIC_IP
```

Replace `YOUR_ELASTIC_IP` with the Elastic IP you just assigned.

### 7.2 — Update Packages

```bash
sudo apt update && sudo apt upgrade -y
```

### 7.3 — Install System Dependencies

```bash
sudo apt install -y python3 python3-pip python3-venv git nginx
```

Verify Python is 3.10 or later:

```bash
python3 --version
```

### 7.4 — Create the Application Directory

```bash
sudo mkdir -p /srv/badminton-video-vault
sudo chown ubuntu:ubuntu /srv/badminton-video-vault
```

> **Do not** create any subdirectories (such as `data/`) here — `git clone` requires the destination directory to be empty. The `data/` directory for the SQLite database is created in [Part 8.1](#81--clone-the-repository) immediately after cloning.

---

## Part 8 — Deploy the Application

### 8.1 — Clone the Repository

Badminton Video Vault is typically kept in a **private** GitHub repository, so cloning from EC2 needs non-interactive authentication — there is no terminal for you to type a password/token into during the initial clone if you're scripting this, and a stored Personal Access Token on the server is a broader credential than this task needs. The recommended approach is a **read-only GitHub deploy key**:

1. On the EC2 instance, generate a dedicated SSH key pair for this purpose:
   ```bash
   ssh-keygen -t ed25519 -C "badminton-video-vault-deploy-key" -f ~/.ssh/deploy_key -N ""
   cat ~/.ssh/deploy_key.pub
   ```
2. Copy the printed public key.
3. In your GitHub repository, go to **Settings → Deploy keys → Add deploy key**.
4. Paste the public key, give it a title (e.g., `ec2-deploy-key`), and **do not** check "Allow write access" — this key only needs to read the repository.
5. Back on the EC2 instance, tell SSH to use this key for GitHub and clone over SSH:
   ```bash
   cat >> ~/.ssh/config <<'EOF'
   Host github.com
     IdentityFile ~/.ssh/deploy_key
     IdentitiesOnly yes
   EOF
   chmod 600 ~/.ssh/config

   cd /srv
   git clone git@github.com:YOUR_GITHUB_USERNAME/badminton-video-vault.git
   cd badminton-video-vault
   ```

Replace `YOUR_GITHUB_USERNAME` with your GitHub username. A deploy key is scoped to a single repository and read-only, so it is safer to leave on the server long-term than a personal access token or your own SSH key.

Now that the repository is cloned, create the dedicated directory for the SQLite database:

```bash
mkdir -p /srv/badminton-video-vault/data
```

> If you prefer HTTPS instead of a deploy key, you can use a fine-grained [GitHub Personal Access Token](https://github.com/settings/tokens) as the password when prompted, but this requires either an interactive prompt or storing the token in a credential helper on the server — a deploy key avoids both.

### 8.2 — Create and Activate the Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 8.3 — Install Python Dependencies

```bash
pip install -r requirements.txt
```

This includes `gunicorn`, which is required to serve the app in production.

### 8.4 — Create the Production `.env` File

The `.env` file is **not** in the repository (it is gitignored). Create it directly on the server:

```bash
nano /srv/badminton-video-vault/.env
```

Paste and fill in all values, using the S3 bucket, region, and Mailgun credentials you recorded in Parts 2–4 (and Mailgun setup):

```ini
# Flask
FLASK_SECRET_KEY=generate-a-long-random-string-here
FLASK_ENV=production

# Database — absolute path to keep it outside the app directory
DATABASE_URL=sqlite:////srv/badminton-video-vault/data/badminton_vault.db

# AWS S3 (from Parts 2-4)
# If the EC2 instance has an IAM role attached (Part 6.1a, recommended), omit
# AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY entirely — boto3 will use the
# instance role's temporary credentials automatically.
AWS_ACCESS_KEY_ID=AKIA...your-access-key-id...
AWS_SECRET_ACCESS_KEY=your-secret-access-key
AWS_REGION=us-east-1
S3_BUCKET_NAME=your-bucket-name
PRESIGNED_URL_EXPIRY=3600

# Mailgun (required for password reset and magic login emails)
# Use a Mailgun Domain Sending Key where possible (more limited scope than a
# full private API key), as recommended in .env.example.
MAILGUN_API_KEY=your-mailgun-domain-sending-key
MAILGUN_DOMAIN=mg.yourdomain.com
MAILGUN_API_BASE_URL=https://api.mailgun.net
MAIL_FROM="Badminton Video Vault <noreply@mg.yourdomain.com>"
MAIL_SUPPRESS_SEND=false
MAILGUN_TEST_MODE=false
MAILGUN_TIMEOUT_SECONDS=10

# Public base URL used to build password reset / magic login links in emails
APP_BASE_URL=https://yourdomain.com
```

To generate a secure secret key, run:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

> **Important:** The `DATABASE_URL` uses four slashes (`sqlite:////`) to denote an absolute path on the filesystem. This ensures the database lives at `/srv/badminton-video-vault/data/badminton_vault.db` regardless of the working directory.

> **Important:** The `.env` file contains secrets (Flask secret key, AWS credentials if used, Mailgun API key). Restrict its permissions so only the owning user can read it:
> ```bash
> chmod 600 /srv/badminton-video-vault/.env
> ```

#### Environment Variable Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `AWS_ACCESS_KEY_ID` | The Access Key ID from the IAM user created in Part 3 (omit if using an EC2 instance role) | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | The Secret Access Key from the IAM user created in Part 3 (omit if using an EC2 instance role) | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_REGION` | The AWS region where your bucket is located | `us-east-1`, `ap-southeast-1`, `eu-west-1` |
| `S3_BUCKET_NAME` | The exact name of your S3 bucket | `badminton-video-vault-yourname` |
| `PRESIGNED_URL_EXPIRY` | How long presigned URLs remain valid (in seconds) | `3600` (1 hour) |
| `MAILGUN_API_KEY` | Your Mailgun Domain Sending Key (preferred; scoped to sending mail from one domain) or private API key | `key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `MAILGUN_DOMAIN` | The sending domain configured in Mailgun | `mg.yourdomain.com` |
| `MAILGUN_API_BASE_URL` | Mailgun API base URL (use the EU endpoint if your Mailgun account is in the EU region) | `https://api.mailgun.net` or `https://api.eu.mailgun.net` |
| `MAIL_FROM` | The "From" address used for password reset / magic login emails (quote it since it contains a space) | `"Badminton Video Vault <noreply@mg.yourdomain.com>"` |
| `MAIL_SUPPRESS_SEND` | Must be `false` in production, or no email is actually sent | `false` |
| `MAILGUN_TEST_MODE` | Must be `false` in production; `true` only for local/manual testing against Mailgun's sandbox | `false` |
| `MAILGUN_TIMEOUT_SECONDS` | HTTP timeout (seconds) for calls to the Mailgun API | `10` |
| `APP_BASE_URL` | The public base URL used to build links in emails; must match your production domain/IP | `https://yourdomain.com` |

**Notes on Presigned URL Expiry:**
- **Shorter expiry** (e.g., 900 seconds / 15 minutes) is more secure — URLs become invalid faster if shared.
- **Longer expiry** (e.g., 7200 seconds / 2 hours) is more convenient for long viewing sessions.
- The default of 3600 seconds (1 hour) provides a good balance.
- Share links have their own 30-day expiry managed at the application level, but the presigned URLs within them still respect this setting.

### 8.5 — Initialise the Database

**Run these commands only once on first deploy.** `flask init-db` calls `db.create_all()`, which creates tables that do not already exist — it is safe to run again on an existing installation (existing tables and data are left untouched), but there is no need to do so after the first deploy.

```bash
cd /srv/badminton-video-vault
source venv/bin/activate
flask init-db
flask create-admin
```

Follow the prompts for `create-admin` to set up the admin account.

### 8.6 — Smoke-Test the Application Manually

Before configuring the service, verify the app starts. Bind to `127.0.0.1` rather than `0.0.0.0` since port 5000 is intentionally not opened in the security group (see [Part 6.3](#63--configure-the-security-group)):

```bash
cd /srv/badminton-video-vault
source venv/bin/activate
gunicorn --bind 127.0.0.1:5000 --workers 1 app:app
```

In a **second** SSH session to the same instance, confirm the app responds:

```bash
curl -i http://127.0.0.1:5000/login
```

You should see an `HTTP/1.1 200 OK` response containing the login page HTML. Do **not** try to browse to `http://YOUR_ELASTIC_IP:5000` — that port is not open to the internet, and opening it is unnecessary since Nginx will proxy to Gunicorn over a Unix socket in production.

Press `Ctrl+C` in the first session to stop Gunicorn when done.

---

## Part 9 — Configure Gunicorn as a Systemd Service

A systemd service keeps Gunicorn running, starts it automatically on boot, and restarts it if it crashes.

### 9.1 — Create the Service File

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
    --timeout 300 \
    --bind unix:/run/badminton-vault.sock \
    --access-logfile /var/log/badminton-vault/access.log \
    --error-logfile /var/log/badminton-vault/error.log \
    app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

> **Why `--timeout 300`:** Gunicorn's default worker timeout is 30 seconds, which is too short for large video uploads that the app streams to S3 with `boto3.upload_fileobj()` — Gunicorn would kill and restart the worker mid-upload. 300 seconds gives large uploads room to complete; tune it further if you expect uploads that consistently take longer.

### 9.2 — Create the Log Directory

```bash
sudo mkdir -p /var/log/badminton-vault
sudo chown ubuntu:ubuntu /var/log/badminton-vault
```

Set up log rotation so the access/error logs do not grow unbounded:

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

`copytruncate` is used because Gunicorn keeps its log file descriptors open for the lifetime of the service, so the log file is truncated in place rather than moved.

### 9.3 — Enable and Start the Service

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

## Part 10 — Configure Nginx as a Reverse Proxy

Nginx accepts incoming HTTP/HTTPS traffic and forwards it to Gunicorn via a Unix socket.

### 10.1 — Create the Nginx Server Block

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
    client_body_timeout 300s;
    proxy_read_timeout 300s;
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/badminton-vault.sock;

        # Stream the request body straight to Gunicorn instead of buffering
        # the whole upload to disk in Nginx first — reduces latency and
        # temporary disk usage for large video uploads.
        proxy_request_buffering off;
    }
}
```

> **Note on large uploads:** These settings raise the ceiling for how long a single request may take and avoid double-buffering large request bodies, but the upload still passes through the EC2 instance (browser → Nginx → Gunicorn → S3). For very large videos, a direct browser-to-S3 multipart upload (presigned POST/PUT URLs) is a better long-term design — see the note in [Part 6.4](#64--configure-storage).

### 10.2 — Enable the Site

```bash
sudo ln -s /etc/nginx/sites-available/badminton-vault /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

If `nginx -t` reports errors, review the config file for typos.

### 10.3 — Verify

Navigate to `http://YOUR_ELASTIC_IP` in a browser. You should see the login page served through Nginx.

---

## Part 11 — Custom Domain Setup and HTTPS with Let's Encrypt (Recommended)

HTTPS is strongly recommended before using the app with real data. Using a domain name (instead of a bare IP address) also makes the app easier to remember and share. This part covers pointing a domain you already own at your EC2 instance and then enabling HTTPS with a free Let's Encrypt certificate.

If you do not have a domain yet, you can register one through a domain registrar (e.g. [Namecheap](https://www.namecheap.com/), [Squarespace Domains](https://www.squarespace.com/domains), [GoDaddy](https://www.godaddy.com/), or [Amazon Route 53](https://aws.amazon.com/route53/)). Alternatively, you can skip this part for now and revisit it later — the app will still work over `http://YOUR_ELASTIC_IP`.

### 11.1 — Point Your Domain at the Elastic IP

Domain registrars provide a **DNS management** page (sometimes called "DNS settings", "Manage DNS", or "Advanced DNS") where you add records. The exact steps vary by registrar, but you are always creating the same kind of record:

```
Type: A
Host/Name: @ (root/apex domain, e.g. yourdomain.com)
Value/Points to: YOUR_ELASTIC_IP
TTL: 300 (or "Automatic")
```

If you also want the app reachable at `www.yourdomain.com`, add a second record:

```
Type: A
Host/Name: www
Value/Points to: YOUR_ELASTIC_IP
TTL: 300 (or "Automatic")
```

If you'd rather use a subdomain only (e.g. `vault.yourdomain.com`) instead of the root domain, use that subdomain as the `Host/Name` value instead of `@`.

> If your domain is hosted on **Amazon Route 53**, create the A records from the Route 53 console instead: **Hosted zones → your domain → Create record**, with **Record type** `A`, and **Value** set to your Elastic IP.

DNS changes usually propagate within a few minutes, but can take up to 24-48 hours in rare cases. You can check propagation from the EC2 instance (or your local machine) with:

```bash
dig +short yourdomain.com
# or
nslookup yourdomain.com
```

The command should return your Elastic IP once propagation is complete. Do not continue until it does — Certbot's domain validation (Part 11.4) will fail otherwise.

### 11.2 — Update the Nginx Server Block for Your Domain

Edit the server block created in [Part 10](#part-10--configure-nginx-as-a-reverse-proxy) and replace the IP-based `server_name` with your domain(s):

```bash
sudo nano /etc/nginx/sites-available/badminton-vault
```

```nginx
server_name yourdomain.com www.yourdomain.com;
```

Test and restart Nginx:

```bash
sudo nginx -t
sudo systemctl restart nginx
```

Confirm the app is reachable at `http://yourdomain.com` before moving on.

### 11.3 — Install Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 11.4 — Obtain the Certificate

```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

(Omit `-d www.yourdomain.com` if you did not set up the `www` DNS record.) Follow the prompts. Certbot automatically edits your Nginx config to enable HTTPS and redirect HTTP to HTTPS.

### 11.5 — Auto-Renewal

Certbot installs a systemd timer that renews the certificate automatically. Verify it:

```bash
sudo systemctl status certbot.timer
```

Your site is now available at `https://yourdomain.com` and, if configured, `https://www.yourdomain.com`.

---

## Part 12 — Continuous Deployment from GitHub

This GitHub Actions workflow automatically:
1. Runs the full regression suite — every `tests/smoke_*.py` file, discovered dynamically by `tests/run_all_smoke.py` — in an isolated environment, on every pull request and every push to `main`.
2. **Only on a push to `main`, and only if every discovered test passes**, SSHs into EC2 and deploys the new code.

A failed test blocks the deploy — satisfying the prime directive requirement that the regression suite must be 100% green before any release. Running the test job on pull requests also means reviewers see regression results before merging, rather than only after code lands on `main`.

### 12.1 — Create the GitHub Actions Workflow File

In your local repository, create the following file:

```bash
mkdir -p .github/workflows
```

Create `.github/workflows/deploy.yml`:

```yaml
name: Test and Deploy

on:
  pull_request:
    branches:
      - main
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

  # ── Job 2: Deploy to EC2 (only runs on push to main, after tests pass) ─────
  deploy:
    name: Deploy to EC2
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
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

            # Confirm the app responds over its Unix socket directly (bypasses
            # Nginx's server_name/Host routing so the check is deterministic
            # even before Certbot/HTTPS is configured), retrying briefly to
            # give Gunicorn time to bind.
            for attempt in {1..10}; do
              if curl --fail --silent --show-error --max-time 10 \
                  --unix-socket /run/badminton-vault.sock \
                  http://localhost/login > /dev/null; then
                echo "Application responded successfully (attempt $attempt)."
                exit 0
              fi
              echo "Attempt $attempt: application not ready yet, retrying..."
              sleep 2
            done

            echo "Application did not respond over its Unix socket!"
            sudo systemctl status badminton-vault --no-pager
            sudo journalctl -u badminton-vault -n 100 --no-pager
            exit 1
```

### 12.2 — Add GitHub Secrets

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

### 12.3 — Push the Workflow

```bash
git add .github/workflows/deploy.yml requirements.txt
git commit -m "Add CI/CD workflow; add gunicorn to requirements"
git push
```

Navigate to your GitHub repository → **Actions**. You should see the workflow run. It will:
- Spin up a fresh Ubuntu runner.
- Install dependencies.
- Run the full regression suite (all `tests/smoke_*.py` files, discovered dynamically).
- If they all pass, SSH into EC2 and deploy.

### 12.4 — How Each Subsequent Deploy Works

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
         │    All discovered tests pass?
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

> **First deploy only:** `flask init-db` and `flask create-admin` are one-time setup steps you ran manually in Part 8. The GitHub Actions deploy script intentionally does **not** run them — they are interactive setup commands that only need to run once and are not part of the routine deployment process.

---

## Database Options for Production

Locally the application uses SQLite (a single file: `badminton_vault.db`). The database is configured entirely through the `DATABASE_URL` environment variable, so the same application code works with any SQL database SQLAlchemy supports.

### Option A — SQLite on an EBS-backed EC2 Instance (simplest, used by this guide)

If you deploy to a **single EC2 instance** as described in Parts 6–12, SQLite works perfectly in production. The EC2 root volume is already EBS-backed, which means it persists across instance reboots — no separate volume is required for durability. A separate EBS volume is optional and only needed if you want to manage the database volume independently (e.g., snapshot it separately, resize it, or reattach it to a different instance).

- **When to use:** Personal or small-team vault; single server; no auto-scaling needed.
- **Cost:** No extra database cost beyond the EC2 instance itself.
- **How to configure:** Point `DATABASE_URL` at the file path used by the guide:

  ```ini
  DATABASE_URL=sqlite:////srv/badminton-video-vault/data/badminton_vault.db
  ```

  (Four slashes = absolute path on Unix.)

- **Limitation:** Only one running instance can safely write to a SQLite file at a time. Not suitable if you later add auto-scaling or load balancing.

- **Backups and durability:** The EBS root volume persists across reboots, but it is still a single point of failure. Protect the database with one or both of:
  - **EBS snapshots** — in the EC2 console, go to **Elastic Block Store → Snapshots → Create snapshot** of the root volume, or automate this with **AWS Backup** / **Data Lifecycle Manager** on a schedule (e.g., daily).
  - **Scheduled database file backups** — use SQLite's own backup command (safe to run against a live database, unlike a plain `cp`, which can copy a file mid-transaction and produce a corrupt backup) and upload the result off-instance, e.g. to a dedicated S3 backup prefix, so the backup survives loss of the instance or its EBS volume. A small script keeps the logic (and error handling) easier to read and maintain than a long inline cron command:

    ```bash
    sudo mkdir -p /srv/badminton-video-vault/scripts
    sudo nano /srv/badminton-video-vault/scripts/backup-db.sh
    ```

    ```bash
    #!/bin/bash
    # Backs up the SQLite database and uploads it to S3. Replace the bucket
    # name below with your own backup bucket before enabling the cron job.
    set -euo pipefail

    DATA_DIR=/srv/badminton-video-vault/data
    BACKUP_DIR="$DATA_DIR/backups"
    LOG_FILE="$DATA_DIR/backup-errors.log"
    S3_BUCKET=s3://your-backup-bucket/badminton-vault/
    BACKUP_FILE="$BACKUP_DIR/badminton_vault-$(date +%Y%m%d%H%M).db"

    mkdir -p "$BACKUP_DIR"

    if ! sqlite3 "$DATA_DIR/badminton_vault.db" ".backup '$BACKUP_FILE'"; then
      echo "$(date): sqlite3 backup failed" >> "$LOG_FILE"
      exit 1
    fi

    if ! aws s3 cp "$BACKUP_FILE" "$S3_BUCKET"; then
      echo "$(date): upload to $S3_BUCKET failed" >> "$LOG_FILE"
      exit 1
    fi
    ```

    ```bash
    sudo chmod +x /srv/badminton-video-vault/scripts/backup-db.sh
    ```

    Add it to the crontab of the user that owns `/srv/badminton-video-vault` (`crontab -e`) to run daily at 02:00:

    ```bash
    0 2 * * * /srv/badminton-video-vault/scripts/backup-db.sh
    ```

    Add a separate retention/cleanup step if you want to prune old local copies once they've been uploaded.
  - Enable **EBS encryption** on the root volume (see [Part 6.4](#64--configure-storage)) so the database is encrypted at rest.

### Option B — Amazon RDS (recommended for multi-instance or managed deployments)

If you deploy to **Elastic Beanstalk, ECS, Fargate**, or any setup where the filesystem is ephemeral, you **must** use an external database. Amazon RDS is the natural AWS-managed choice.

- **When to use:** Container-based deployments; Elastic Beanstalk; any auto-scaling topology.
- **Recommended engine:** PostgreSQL. Check the [AWS Free Tier page](https://aws.amazon.com/free/) for current RDS free-tier eligibility.
- **Cost:** Varies by instance class and region — check the [Amazon RDS pricing page](https://aws.amazon.com/rds/pricing/) for current rates.

#### Steps to create an RDS PostgreSQL instance

1. In the AWS console, navigate to **RDS → Create database**.
2. Choose **Standard create** → **PostgreSQL**.
3. Under **Templates**, select **Free tier** (if eligible).
4. Set a **DB instance identifier**, **Master username**, and a strong **Master password**. Avoid characters that require URL-encoding in a connection string (see note below) or be prepared to encode them.
5. Leave **DB instance class** as `db.t3.micro` (or the current free-tier-eligible class).
6. Under **Connectivity**, place the instance in the same VPC as your application server.
7. Set **Public access** to **No** (the Flask app connects from inside the VPC; never expose RDS to the internet — do **not** open PostgreSQL to `0.0.0.0/0` under any circumstance).
8. Under **VPC security group**, create or select a security group for the database, then after creation edit its inbound rules to allow:

   | Type | Protocol | Port | Source | Purpose |
   |------|----------|------|--------|---------|
   | PostgreSQL | TCP | 5432 | The EC2 instance's security group (select it by ID, not an IP/CIDR) | Only the application server may connect |

9. Note the **Endpoint** hostname shown after the instance is created.
10. Once the instance is available, create the application database (the initial `badminton_vault` database is **not** created automatically):

    ```bash
    psql "host=your-rds-endpoint.rds.amazonaws.com port=5432 user=your-master-username dbname=postgres sslmode=require" \
      -c "CREATE DATABASE badminton_vault;"
    ```

    (Run this from the EC2 instance, or any host that can reach the RDS security group; you may need to `sudo apt install -y postgresql-client` first.)

#### Configure the application to use RDS

1. Add `psycopg2-binary` to `requirements.txt` (PostgreSQL driver for Python).
2. Set `DATABASE_URL` in your production environment:

   ```ini
   DATABASE_URL=postgresql://your_master_username:url-encoded-password@your-rds-endpoint.rds.amazonaws.com:5432/badminton_vault
   ```

   > **URL-encoding credentials:** If your master username or password contains special characters (`@`, `:`, `/`, `%`, etc.), they must be percent-encoded in the connection string or SQLAlchemy will fail to parse it correctly. For example, a password of `p@ss:word` becomes `p%40ss%3Aword`. You can compute this with:
   > ```bash
   > python3 -c "import urllib.parse; print(urllib.parse.quote('your-password', safe=''))"
   > ```

3. Run the database initialisation command on first deploy:

   ```bash
   flask init-db
   ```

4. Create the admin account:

   ```bash
   flask create-admin
   ```

> **Security note:** Never put the RDS password in source control. Use environment variables or AWS Secrets Manager.

### Summary

| Scenario | Database choice |
|----------|-----------------|
| Single EC2 instance | SQLite on an EBS volume — no RDS needed |
| Elastic Beanstalk / ECS / Fargate | RDS PostgreSQL or MySQL required |
| Local development | SQLite (default) — no change needed |

---

## Verify the Setup

After configuring everything, verify the integration works end-to-end.

### 1. Test AWS Connectivity

Run the following Python snippet (from the EC2 instance or locally with the same `.env`) to confirm your credentials and bucket are working:

```bash
python3 -c "
import boto3
from dotenv import load_dotenv
import os

load_dotenv()

s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)

bucket = os.getenv('S3_BUCKET_NAME')
test_key = 'connectivity-test.txt'

s3.put_object(Bucket=bucket, Key=test_key, Body=b'connectivity test')
s3.delete_object(Bucket=bucket, Key=test_key)

print(f'✅ Successfully connected to bucket: {bucket}')
print(f'   Region: {os.getenv(\"AWS_REGION\")}')
"
```

If successful, you will see a confirmation message. If not, check the [Troubleshooting](#troubleshooting) section below.

> This snippet works whether you are using an EC2 instance IAM role or static access keys — if `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` are unset, `boto3` automatically falls back to the instance role's credentials.

### 2. Test the Running Service

Navigate to `http://YOUR_ELASTIC_IP` (or your domain, if HTTPS is configured). You should see the login page served through Nginx.

### 3. Test Upload, Playback, and Deletion

1. Log in with your admin account.
2. Navigate to the Upload page and upload a small test video.
3. Confirm the video plays back on the Video Detail page.
4. If downloads are enabled, confirm the download link works.
5. Delete the test video and confirm it disappears from the video list and is removed from the S3 bucket.

### 4. Test Password Reset

1. Log out, then go to the login page and use the "Forgot password" / password reset flow with your admin account's email address.
2. Confirm a password reset email arrives (check Mailgun's dashboard logs if it does not) and that the link in the email uses your production `APP_BASE_URL`.
3. Follow the link and set a new password, then log in with it.

### 5. Test Magic Login

1. Log out, then use the magic login / passwordless sign-in option with your admin account's email address.
2. Confirm a magic login email arrives and that clicking the link signs you in without a password.

If either email fails to arrive, verify `MAIL_SUPPRESS_SEND=false`, `MAILGUN_TEST_MODE=false`, and the `MAILGUN_API_KEY`/`MAILGUN_DOMAIN` values in `.env`, and check the Mailgun dashboard's logs for delivery errors.

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

## Security Best Practices

Follow these guidelines to keep your deployment secure:

### Credential Management

- **Never commit `.env` or credentials** to version control. The `.gitignore` file already excludes `.env`.
- **Prefer an EC2 instance IAM role** (see [Part 6.1a](#61a--attach-an-iam-role-instead-of-access-keys-recommended)) over static access keys — the credentials are temporary, automatically rotated, and never stored on disk. Use static access keys only as a fallback (e.g., for local testing away from AWS).
- If you do use static access keys, **rotate them** periodically (every 90 days is a common recommendation). To rotate:
  1. Create a new access key in IAM.
  2. Update your `.env` with the new key.
  3. Verify the app works with the new key.
  4. Delete the old access key in IAM.
- Restrict `.env` file permissions with `chmod 600 /srv/badminton-video-vault/.env` (see [Part 8.4](#84--create-the-production-env-file)) so only the owning user can read it.

### Bucket Security

- Keep **Block Public Access** enabled at all times.
- Enable **S3 access logging** to track who is accessing your bucket (go to bucket **Properties** → **Server access logging**).
- Consider enabling **AWS CloudTrail** for auditing API calls to your bucket.
- Enable **MFA Delete** on the bucket if you want additional protection against accidental or malicious object deletion.

### Data Durability and Backups

- Enable **EBS encryption** on the EC2 root volume so the SQLite database is encrypted at rest (see [Part 6.4](#64--configure-storage)).
- Take periodic **EBS snapshots**, or schedule file-level backups of the SQLite database, so the data survives instance loss (see [Database Options for Production](#database-options-for-production)).
- Be aware that **terminating** (not just stopping) an EC2 instance can permanently delete its root EBS volume if **Delete on Termination** is enabled for that volume — check this setting before terminating an instance you care about.
- Rotate application logs so `/var/log/badminton-vault/*.log` does not grow unbounded (configured with `logrotate` in [Part 9.2](#92--create-the-log-directory)).

### Application Security

- Use a strong, unique `FLASK_SECRET_KEY` in production.
- Set `FLASK_ENV=production` when deploying (never use `development` in production).
- Keep `PRESIGNED_URL_EXPIRY` as short as practical.
- The application enforces a 2 GB upload limit — adjust `MAX_CONTENT_LENGTH` in `config.py` if needed.
- Set `MAIL_SUPPRESS_SEND=false` and `MAILGUN_TEST_MODE=false` in production, or password reset and magic-login emails will not actually be sent.
- Set `APP_BASE_URL` to your real production domain/IP so links in password reset and magic-login emails point at the right place.

---

## Cost Considerations

Understanding AWS pricing helps you estimate and manage costs.

### S3 Storage and Transfer

| Component | Pricing (approximate, varies by region) |
|-----------|------------------------------------------|
| Storage (S3 Standard) | ~$0.023 per GB per month |
| PUT requests (uploads) | ~$0.005 per 1,000 requests |
| GET requests (playback/download) | ~$0.0004 per 1,000 requests |
| Data Transfer Out (to internet) | ~$0.09 per GB (first 10 TB/month) |

**Example estimate** for a small team with 50 videos averaging 500 MB each:
- **Storage:** 25 GB × $0.023 = ~$0.58/month
- **Uploads:** 50 PUTs = negligible
- **Playback:** 500 GETs/month = negligible
- **Data Transfer:** If 10 videos (5 GB) are streamed = ~$0.45/month
- **Total:** ~$1.03/month

### EC2

- **t2.micro / t3.micro:** Check the [AWS Free Tier page](https://aws.amazon.com/free/) for current EC2 free-tier hours; otherwise billed per the [EC2 on-demand pricing page](https://aws.amazon.com/ec2/pricing/on-demand/), which varies by instance type and region.
- **20 GiB gp3 EBS volume:** May be partly or fully covered by the current EBS free-tier allowance, or billed per GB-month — check the [Amazon EBS pricing page](https://aws.amazon.com/ebs/pricing/).
- **Elastic IP / public IPv4:** AWS's pricing for public IPv4 addresses (including Elastic IPs) has changed over time. Check the current [Amazon EC2 pricing page](https://aws.amazon.com/ec2/pricing/on-demand/) for whether an associated Elastic IP is free or billed hourly in your account/region.

### Cost Optimization Tips

- Use **S3 Intelligent-Tiering** if access patterns are unpredictable.
- Set lifecycle rules to move old videos to **S3 Glacier** for long-term archival at ~$0.004/GB/month.
- Monitor costs with [AWS Cost Explorer](https://console.aws.amazon.com/cost-management/home).
- Set up **billing alerts** in AWS Budgets to avoid unexpected charges.

---

## Troubleshooting

### AWS / S3 / IAM Issues

| Problem | Likely Cause | Solution |
|---------|--------------|----------|
| `NoCredentialsError` | Missing or incorrect AWS credentials | Verify `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` in `.env`, or that an IAM role is attached to the instance (see [Part 6.1a](#61a--attach-an-iam-role-instead-of-access-keys-recommended)) |
| `AccessDenied` on upload | IAM policy does not include `s3:PutObject` | Review and update the IAM policy (see [Part 3](#part-3--set-up-iam-user-and-permissions)) |
| `AccessDenied` on playback | IAM policy does not include `s3:GetObject` | Review and update the IAM policy |
| `NoSuchBucket` | Bucket name in `.env` does not match the actual bucket | Double-check the `S3_BUCKET_NAME` value |
| `InvalidBucketName` | Bucket name contains invalid characters | Bucket names must be 3–63 characters, lowercase, numbers, hyphens only |
| Video playback fails (CORS error) | Missing CORS configuration on bucket | Add CORS rules (see [Part 5](#part-5--configure-cors-optional)) |
| `SignatureDoesNotMatch` | Clock skew or incorrect secret key | Ensure your system clock is accurate; re-check the secret key |
| Upload fails for large files | Gunicorn worker timeout, Nginx timeout, or insufficient disk space on the root volume | Confirm Gunicorn's `--timeout 300` (Part 9.1) and Nginx's timeout settings (Part 10.1) are in place; ensure the root volume has enough free space for temporary upload data (Part 6.4) |
| `403 Forbidden` on presigned URL | URL has expired or region mismatch | Check `PRESIGNED_URL_EXPIRY` and ensure `AWS_REGION` matches the bucket's actual region |

**Checking bucket region:** Your `AWS_REGION` environment variable **must** match the region where the bucket was created. Open your bucket in the S3 console → **Properties** tab → look for **AWS Region** under **Bucket overview**.

**Viewing S3 access logs:** If you have access logging enabled, check the target bucket for detailed access records. Each log entry shows the requester, operation, and response status.

### EC2 / Deployment Issues

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `502 Bad Gateway` from Nginx | Gunicorn is not running or the socket doesn't exist | `sudo systemctl restart badminton-vault` and check `journalctl -u badminton-vault -n 50` |
| `500 Internal Server Error` | Application exception | Check `/var/log/badminton-vault/error.log` |
| App starts but `.env` values missing | EnvironmentFile path wrong in service file | Verify `/etc/systemd/system/badminton-vault.service` has the correct `EnvironmentFile` path |
| `flask init-db` says `no such table` | Database path issue | Verify `DATABASE_URL` in `.env` uses four slashes for absolute path; confirm the `data/` directory exists |
| GitHub Actions deploy fails: "Permission denied (publickey)" | `EC2_SSH_KEY` secret is incorrect | Recopy the full `.pem` content (including header/footer lines) into the GitHub secret |
| GitHub Actions deploy step is skipped | Smoke tests failed in the `test` job | Fix the failing tests first; check the Actions log for which test failed |
| GitHub Actions deploy fails at the HTTP health check step | The app restarted but isn't responding (crash, wrong `.env`, Nginx misconfigured) | SSH in and check `journalctl -u badminton-vault -n 50`, `sudo systemctl status badminton-vault`, and `sudo nginx -t` |
| `git clone` fails with "destination path already exists and is not an empty directory" | A subdirectory (e.g. `data/`) was created inside `/srv/badminton-video-vault` before cloning | Clone first (Part 8.1), then create `data/` — do not create it in Part 7.4 |
| `git clone` hangs or prompts for a password non-interactively | Using an HTTPS URL for a private repo without a credential helper | Use a GitHub deploy key over SSH instead (see [Part 8.1](#81--clone-the-repository)) |
| Password reset / magic login email never arrives | `MAIL_SUPPRESS_SEND=true` or `MAILGUN_TEST_MODE=true` in production, or wrong Mailgun credentials | Set `MAIL_SUPPRESS_SEND=false` and `MAILGUN_TEST_MODE=false`; verify `MAILGUN_API_KEY`/`MAILGUN_DOMAIN` and check the Mailgun dashboard's delivery logs |
| Password reset / magic login link points at the wrong host | `APP_BASE_URL` not set to the production domain/IP | Set `APP_BASE_URL` in `.env` to your real production URL (see [Part 8.4](#84--create-the-production-env-file)) |
| Large video uploads time out | Nginx `proxy_read_timeout` or Gunicorn `--timeout` too short | Already set to `300s`/`300` respectively in the config in [Part 9](#part-9--configure-gunicorn-as-a-systemd-service) and [Part 10](#part-10--configure-nginx-as-a-reverse-proxy); increase further if needed |
| Video playback fails after deploy | Presigned URL expiry or S3 region mismatch | Verify `AWS_REGION` in `.env` matches the bucket's actual region |
| Domain doesn't load the app | DNS not propagated yet, or A record missing/incorrect | Run `dig +short yourdomain.com` and confirm it returns your Elastic IP; wait for propagation before retrying |
| Certbot fails with "DNS problem: NXDOMAIN" or similar | Domain's A record isn't pointing at the instance yet | Re-check the A record in your registrar's DNS settings (see [Part 11.1](#111--point-your-domain-at-the-elastic-ip)) and wait for propagation before re-running `certbot` |

### Getting Help

- [AWS S3 Documentation](https://docs.aws.amazon.com/s3/)
- [AWS IAM Documentation](https://docs.aws.amazon.com/iam/)
- [AWS EC2 Documentation](https://docs.aws.amazon.com/ec2/)
- [boto3 S3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html)
- [AWS Free Tier FAQ](https://aws.amazon.com/free/free-tier-faqs/)
