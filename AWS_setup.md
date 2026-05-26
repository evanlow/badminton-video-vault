# AWS Setup Guide for Badminton Video Vault

This guide provides comprehensive, step-by-step instructions for configuring the AWS services required by the Badminton Video Vault application. It is intended to complement the [README.md](README.md) and help you set up everything from scratch.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Create an AWS Account](#create-an-aws-account)
3. [Create an S3 Bucket](#create-an-s3-bucket)
4. [Configure Bucket Settings](#configure-bucket-settings)
5. [Set Up IAM User and Permissions](#set-up-iam-user-and-permissions)
6. [Generate Access Keys](#generate-access-keys)
7. [Configure CORS (Optional)](#configure-cors-optional)
8. [Configure Your Application](#configure-your-application)
9. [Database Options for Production](#database-options-for-production)
10. [Verify the Setup](#verify-the-setup)
11. [Security Best Practices](#security-best-practices)
12. [Cost Considerations](#cost-considerations)
13. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, ensure you have the following:

- A valid email address for AWS account registration
- A credit/debit card for AWS billing (free tier is available for new accounts)
- Python 3.8+ and the application dependencies installed (see [README.md](README.md))
- Basic familiarity with the AWS Management Console

---

## Create an AWS Account

If you do not already have an AWS account:

1. Go to [https://aws.amazon.com/](https://aws.amazon.com/) and click **Create an AWS Account**.
2. Follow the prompts to provide your email, set a password, and enter payment details.
3. Choose the **Basic (Free)** support plan unless you require premium support.
4. Complete the identity verification process.
5. Sign in to the [AWS Management Console](https://console.aws.amazon.com/).

> **Note:** New AWS accounts are eligible for the [AWS Free Tier](https://aws.amazon.com/free/), which includes 5 GB of S3 Standard storage, 20,000 GET requests, and 2,000 PUT requests per month for 12 months.

---

## Create an S3 Bucket

Amazon S3 (Simple Storage Service) is used to store all uploaded video files. Uploads are performed server-side by the Flask app, and the application never exposes S3 objects publicly — it uses presigned URLs for playback and download access.

### Steps

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

### Record Your Bucket Name

Take note of the bucket name you chose — you will use it as the `S3_BUCKET_NAME` environment variable.

---

## Configure Bucket Settings

### Verify Public Access is Blocked

1. Open your bucket in the S3 console.
2. Go to the **Permissions** tab.
3. Under **Block public access (bucket settings)**, confirm all four options are set to **On**:
   - Block public access to buckets and objects granted through *new* access control lists (ACLs)
   - Block public access to buckets and objects granted through *any* access control lists (ACLs)
   - Block public access to buckets and objects granted through *new* public bucket or access point policies
   - Restrict access to buckets and objects granted through *any* public bucket or access point policies

### Lifecycle Rules (Optional)

If you want to automatically manage storage costs, you can add lifecycle rules:

1. Go to the **Management** tab in your bucket.
2. Click **Create lifecycle rule**.
3. Example rules:
   - Move objects to **S3 Glacier** after 90 days (for archival)
   - Permanently delete incomplete multipart uploads after 7 days

---

## Set Up IAM User and Permissions

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
                "s3:DeleteObject"
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

> **Important:** This policy follows the principle of least privilege — the application can only put, get, and delete objects within the specific bucket. It cannot list buckets, modify bucket settings, or access other AWS services.

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

## Generate Access Keys

The application authenticates to AWS using access keys (an Access Key ID and Secret Access Key pair).

1. In the IAM console, go to **Users** and click on the user you just created.
2. Go to the **Security credentials** tab.
3. Under **Access keys**, click **Create access key**.
4. Select **Application running outside AWS** as the use case.
5. Click **Next**, then **Create access key**.
6. **Important:** Copy both the **Access Key ID** and **Secret Access Key** immediately. The Secret Access Key will not be shown again.

> ⚠️ **Security Warning:** Never commit access keys to source control. Store them securely and treat them like passwords.

---

## Configure CORS (Optional)

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

## Configure Your Application

With the AWS resources set up, configure the application environment variables:

1. Copy the example environment file:

   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file with your AWS credentials:

   ```ini
   # AWS Configuration
   AWS_ACCESS_KEY_ID=AKIA...your-access-key-id...
   AWS_SECRET_ACCESS_KEY=your-secret-access-key
   AWS_REGION=us-east-1
   S3_BUCKET_NAME=badminton-video-vault-yourname

   # Presigned URL expiry (seconds) — default is 3600 (1 hour)
   PRESIGNED_URL_EXPIRY=3600
   ```

### Environment Variable Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `AWS_ACCESS_KEY_ID` | The Access Key ID from the IAM user you created | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | The Secret Access Key from the IAM user you created | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_REGION` | The AWS region where your bucket is located | `us-east-1`, `ap-southeast-1`, `eu-west-1` |
| `S3_BUCKET_NAME` | The exact name of your S3 bucket | `badminton-video-vault-yourname` |
| `PRESIGNED_URL_EXPIRY` | How long presigned URLs remain valid (in seconds) | `3600` (1 hour) |

### Notes on Presigned URL Expiry

- **Shorter expiry** (e.g., 900 seconds / 15 minutes) is more secure — URLs become invalid faster if shared.
- **Longer expiry** (e.g., 7200 seconds / 2 hours) is more convenient for long viewing sessions.
- The default of 3600 seconds (1 hour) provides a good balance.
- Share links have their own 30-day expiry managed at the application level, but the presigned URLs within them still respect this setting.

---

## Database Options for Production

Locally the application uses SQLite (a single file: `badminton_vault.db`). The database is configured entirely through the `DATABASE_URL` environment variable, so the same application code works with any SQL database SQLAlchemy supports.

### Option A — SQLite on an EBS-backed EC2 Instance (simplest)

If you deploy to a **single EC2 instance**, SQLite works perfectly in production as long as the database file lives on an **EBS (Elastic Block Store)** volume, which persists across instance reboots and is independent of the root volume.

- **When to use:** Personal or small-team vault; single server; no auto-scaling needed.
- **Cost:** No extra database cost beyond the EC2 instance itself.
- **How to configure:** Mount the EBS volume and point `DATABASE_URL` at the file path:

  ```ini
  DATABASE_URL=sqlite:////data/badminton_vault.db
  ```

  (Four slashes = absolute path on Unix.)

- **Limitation:** Only one running instance can safely write to a SQLite file at a time. Not suitable if you later add auto-scaling or load balancing.

### Option B — Amazon RDS (recommended for multi-instance or managed deployments)

If you deploy to **Elastic Beanstalk, ECS, Fargate**, or any setup where the filesystem is ephemeral, you **must** use an external database. Amazon RDS is the natural AWS-managed choice.

- **When to use:** Container-based deployments; Elastic Beanstalk; any auto-scaling topology.
- **Recommended engine:** PostgreSQL (free tier: `db.t3.micro` for 12 months).
- **Cost:** ~$15–25/month after free tier for a `db.t3.micro` instance.

#### Steps to create an RDS PostgreSQL instance

1. In the AWS console, navigate to **RDS → Create database**.
2. Choose **Standard create** → **PostgreSQL**.
3. Under **Templates**, select **Free tier** (if eligible).
4. Set a **DB instance identifier**, **Master username**, and a strong **Master password**.
5. Leave **DB instance class** as `db.t3.micro`.
6. Under **Connectivity**, place the instance in the same VPC as your application server.
7. Set **Public access** to **No** (the Flask app connects from inside the VPC; never expose RDS to the internet).
8. Note the **Endpoint** hostname shown after the instance is created.

#### Configure the application to use RDS

1. Add `psycopg2-binary` to `requirements.txt` (PostgreSQL driver for Python).
2. Set `DATABASE_URL` in your production environment:

   ```ini
   DATABASE_URL=postgresql://username:password@your-rds-endpoint.rds.amazonaws.com:5432/badminton_vault
   ```

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

After configuring everything, verify the integration works:

### 1. Test AWS Connectivity

Run the following Python snippet to confirm your credentials and bucket are working:

```bash
python -c "
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

### 2. Test Upload and Playback

1. Start the application: `flask run`
2. Log in with your admin account.
3. Navigate to the Upload page and upload a small test video.
4. Confirm the video plays back on the Video Detail page.
5. If downloads are enabled, confirm the download link works.

---

## Security Best Practices

Follow these guidelines to keep your deployment secure:

### Credential Management

- **Never commit `.env` or credentials** to version control. The `.gitignore` file already excludes `.env`.
- **Rotate access keys** periodically (every 90 days is a common recommendation). To rotate:
  1. Create a new access key in IAM.
  2. Update your `.env` with the new key.
  3. Verify the app works with the new key.
  4. Delete the old access key in IAM.
- **Use IAM roles** instead of access keys when deploying to AWS services (e.g., EC2, ECS, Lambda). This eliminates the need for long-lived credentials.

### Bucket Security

- Keep **Block Public Access** enabled at all times.
- Enable **S3 access logging** to track who is accessing your bucket (go to bucket **Properties** → **Server access logging**).
- Consider enabling **AWS CloudTrail** for auditing API calls to your bucket.
- Enable **MFA Delete** on the bucket if you want additional protection against accidental or malicious object deletion.

### Application Security

- Use a strong, unique `FLASK_SECRET_KEY` in production.
- Set `FLASK_ENV=production` when deploying (never use `development` in production).
- Keep `PRESIGNED_URL_EXPIRY` as short as practical.
- The application enforces a 2 GB upload limit — adjust `MAX_CONTENT_LENGTH` in `config.py` if needed.

---

## Cost Considerations

Understanding AWS S3 pricing helps you estimate and manage costs:

| Component | Pricing (approximate, varies by region) |
|-----------|------------------------------------------|
| Storage (S3 Standard) | ~$0.023 per GB per month |
| PUT requests (uploads) | ~$0.005 per 1,000 requests |
| GET requests (playback/download) | ~$0.0004 per 1,000 requests |
| Data Transfer Out (to internet) | ~$0.09 per GB (first 10 TB/month) |

### Example Cost Estimate

For a small team with 50 videos averaging 500 MB each:
- **Storage:** 25 GB × $0.023 = ~$0.58/month
- **Uploads:** 50 PUTs = negligible
- **Playback:** 500 GETs/month = negligible
- **Data Transfer:** If 10 videos (5 GB) are streamed = ~$0.45/month
- **Total:** ~$1.03/month

### Cost Optimization Tips

- Use **S3 Intelligent-Tiering** if access patterns are unpredictable.
- Set lifecycle rules to move old videos to **S3 Glacier** for long-term archival at ~$0.004/GB/month.
- Monitor costs with [AWS Cost Explorer](https://console.aws.amazon.com/cost-management/home).
- Set up **billing alerts** in AWS Budgets to avoid unexpected charges.

---

## Troubleshooting

### Common Issues

| Problem | Likely Cause | Solution |
|---------|--------------|----------|
| `NoCredentialsError` | Missing or incorrect AWS credentials | Verify `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `.env` |
| `AccessDenied` on upload | IAM policy does not include `s3:PutObject` | Review and update the IAM policy (see [Set Up IAM User](#set-up-iam-user-and-permissions)) |
| `AccessDenied` on playback | IAM policy does not include `s3:GetObject` | Review and update the IAM policy |
| `NoSuchBucket` | Bucket name in `.env` does not match the actual bucket | Double-check the `S3_BUCKET_NAME` value |
| `InvalidBucketName` | Bucket name contains invalid characters | Bucket names must be 3–63 characters, lowercase, numbers, hyphens only |
| Video playback fails (CORS error) | Missing CORS configuration on bucket | Add CORS rules (see [Configure CORS](#configure-cors-optional)) |
| `SignatureDoesNotMatch` | Clock skew or incorrect secret key | Ensure your system clock is accurate; re-check the secret key |
| Upload fails for large files | Server timeout or memory limits | Consider using multipart uploads or increasing server timeout settings |
| `403 Forbidden` on presigned URL | URL has expired or region mismatch | Check `PRESIGNED_URL_EXPIRY` and ensure `AWS_REGION` matches the bucket's actual region |

### Checking Bucket Region

Your `AWS_REGION` environment variable **must** match the region where the bucket was created. To verify:

1. Open your bucket in the S3 console.
2. Go to the **Properties** tab.
3. Look for **AWS Region** under **Bucket overview**.

### Viewing S3 Access Logs

If you have access logging enabled, check the target bucket for detailed access records. Each log entry shows the requester, operation, and response status.

### Getting Help

- [AWS S3 Documentation](https://docs.aws.amazon.com/s3/)
- [AWS IAM Documentation](https://docs.aws.amazon.com/iam/)
- [boto3 S3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html)
- [AWS Free Tier FAQ](https://aws.amazon.com/free/free-tier-faqs/)
