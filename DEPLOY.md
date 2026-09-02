# Deploying Badminton Video Vault to AWS

This guide deploys Badminton Video Vault to a single Ubuntu EC2 instance using:

- **Nginx** as the public web server
- **Gunicorn** to run the Flask application
- **SQLite** for application data
- a **private Amazon S3 bucket** for videos
- an **EC2 IAM role** instead of permanent AWS access keys
- **direct browser-to-S3 multipart uploads**
- an optional custom domain with **HTTPS from Let's Encrypt**

> **Important:** Video bytes do not pass through EC2. Flask authorises and completes each upload, while the browser sends video parts directly to S3. This avoids consuming EC2 RAM, temporary disk space, root-volume space, and EC2 video-path bandwidth.

---

## Read This First

This is a long guide because it includes the AWS console steps, Linux commands, domain setup, verification checkpoints, and troubleshooting.

Work through it in order. At every **Checkpoint**, stop and confirm the expected result before continuing.

### Deployment progress checklist

- [ ] S3 bucket created
- [ ] S3 IAM policy created
- [ ] EC2 IAM role created and attached
- [ ] EC2 instance running
- [ ] Elastic IP allocated and associated
- [ ] Application opens through the Elastic IP over HTTP
- [ ] DNS A record points the chosen hostname to the Elastic IP
- [ ] Nginx recognises the hostname
- [ ] HTTPS certificate installed
- [ ] `APP_BASE_URL` updated to the HTTPS domain
- [ ] S3 CORS updated to the HTTPS origin
- [ ] Small MP4 upload tested successfully
- [ ] Certificate renewal test passed

### Values worksheet

Record your own values here before starting. Use the same values consistently throughout the guide.

| Item | Your value | Example |
|---|---|---|
| AWS Region |  | `ap-southeast-1` |
| S3 bucket name |  | `my-badminton-video-vault` |
| EC2 instance name |  | `badminton-video-vault-evan` |
| EC2 key pair file |  | `badminton-vault-key.pem` |
| IAM policy name |  | `BadmintonVideoVaultS3Policy` |
| IAM role name |  | `BadmintonVideoVaultEC2Role` |
| Elastic IP |  | `203.0.113.10` |
| Root domain |  | `badmintonvideo.com` |
| Subdomain/host |  | `evan` |
| Full hostname |  | `evan.badmintonvideo.com` |
| Final application URL |  | `https://evan.badmintonvideo.com` |

`203.0.113.10` is a documentation-only example address. Replace it with the Elastic IP allocated in your AWS account.

---

## Architecture

```text
Browser
   |-- small JSON requests --> Nginx --> Gunicorn --> Flask --> SQLite
   |
   `-- presigned multipart PUT requests ---------------------> Private S3
```

Default upload settings:

- Maximum video size: 3 GiB
- Part size: 16 MiB
- Concurrent part uploads: 3
- Automatic attempts per failed part: 3
- Presigned part URL lifetime: 2 hours
- Signed upload-token lifetime per token: 6 hours (renewed while the authenticated upload page remains open)

The S3 bucket remains private. Upload, playback, and download use temporary presigned URLs.

---

# Part A — AWS Storage and Permissions

## 1. Create the S3 Bucket

1. Sign in to the AWS Console.
2. Confirm the selected region in the top-right corner.
3. Open **Amazon S3**.
4. Choose **Create bucket**.
5. Configure:

| Setting | Value |
|---|---|
| Bucket name | A globally unique name |
| AWS Region | The same region used by EC2 |
| Object Ownership | ACLs disabled |
| Block Public Access | Block all public access |
| Bucket Versioning | Optional |
| Default encryption | **SSE-S3**, recommended for this guide |

6. Choose **Create bucket**.
7. Record the exact bucket name and region in the worksheet.

> Using SSE-KMS is possible, but it requires additional KMS key-policy and IAM permissions such as `kms:GenerateDataKey` and `kms:Decrypt`. Do not select SSE-KMS unless those grants are configured for the EC2 role.

### Checkpoint 1

Open the bucket and confirm:

- **Block all public access** is enabled.
- The bucket is in the intended region.
- You know its exact name, including hyphens and spelling.

---

## 2. Create the S3 IAM Policy

This policy allows the application to upload, play, download, and delete objects without making the bucket public.

1. Open **IAM → Policies**.
2. Choose **Create policy**.
3. Select the **JSON** editor.
4. Replace the editor contents with:

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

5. Replace `YOUR-BUCKET-NAME` with the exact bucket name.
6. Choose **Next** or **Review and create**.
7. Enter a policy name such as:

```text
BadmintonVideoVaultS3Policy
```

A user or role may have more than one policy. Creating this policy does not prevent other policies from being attached.

### Checkpoint 2

Open the new policy and confirm that the resource ends in:

```text
arn:aws:s3:::YOUR-ACTUAL-BUCKET-NAME/*
```

The final `/*` is required because the application works with objects inside the bucket.

---

## 3. Create and Attach the EC2 IAM Role

The IAM role lets EC2 obtain temporary credentials automatically. Do not place permanent AWS access keys in the production `.env` file.

### Create the role

1. Open **IAM → Roles**.
2. Choose **Create role**.
3. Trusted entity type: **AWS service**.
4. Service or use case: **EC2**.
5. Choose **Next**.
6. Search for and select `BadmintonVideoVaultS3Policy`.
7. Choose **Next**.
8. Name the role:

```text
BadmintonVideoVaultEC2Role
```

9. Choose **Create role**.

### Attach the role to an existing EC2 instance

1. Open **EC2 → Instances**.
2. Select the badminton vault instance.
3. Choose **Actions → Security → Modify IAM role**.
4. Select `BadmintonVideoVaultEC2Role`.
5. Choose **Update IAM role**.

For a new EC2 instance, select the role under **Advanced details → IAM instance profile** during launch.

Do not put these variables in the production `.env` when the EC2 role is attached:

```text
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
```

---

# Part B — EC2 and a Stable Public Address

## 4. Launch or Prepare the EC2 Instance

Recommended AMI:

```text
Ubuntu Server 22.04 LTS or 24.04 LTS, 64-bit x86
```

Suggested starting points:

| Workload | Instance |
|---|---|
| Personal or small team | `t3.micro`, one Gunicorn worker |
| More concurrent page/API requests | At least 2 GiB RAM, such as `t3.small` |
| Multiple application instances | Larger instance plus an external database |

Use a 20 GiB encrypted gp3 root volume as a comfortable baseline.

### Security group inbound rules

| Type | Port | Source |
|---|---:|---|
| SSH | 22 | Your public IP `/32` |
| HTTP | 80 | `0.0.0.0/0`, optionally `::/0` |
| HTTPS | 443 | `0.0.0.0/0`, optionally `::/0` |

Do not open port 5000. Avoid leaving SSH open to `0.0.0.0/0`.

---

## 5. Allocate and Associate an Elastic IP

A normal EC2 public IPv4 address can change after the instance is stopped and started. DNS must point to a stable address, so allocate an Elastic IP before configuring the domain.

Public IPv4 addresses may be billed. Check current AWS pricing.

### 5.1 Allocate the Elastic IP

1. Open **EC2**.
2. In the left menu, open **Network & Security → Elastic IPs**.
3. Choose **Allocate Elastic IP address**.
4. Leave the Amazon IPv4 pool and network border group at their defaults unless you have a specific requirement.
5. Choose **Allocate**.
6. Optionally add a descriptive **Name** tag, for example:

```text
badminton-video-vault-evan
```

At this point the address exists in your AWS account, but it is not yet connected to the instance.

### 5.2 Associate the Elastic IP with EC2

1. Select the newly allocated Elastic IP.
2. Choose **Actions → Associate Elastic IP address**.
3. Resource type: **Instance**.
4. Select the correct badminton vault EC2 instance.
5. Select its primary private IPv4 address.
6. Choose **Associate**.

The instance's ordinary public IP will be replaced by the Elastic IP. This is expected.

### 5.3 Confirm the association

Open **EC2 → Instances** and select the instance. Confirm that:

- **Public IPv4 address** equals the Elastic IP.
- **Elastic IP address** shows the same value.
- The instance is **Running**.
- Status checks have passed.

### Checkpoint 3

If you are configuring an already-running instance, confirm it still opens over the Elastic IP:

```text
http://YOUR_ELASTIC_IP/login
```

For a fresh deployment, continue to Part C first, then complete this check at Checkpoint 4.

---

## 6. Configure Initial S3 CORS for HTTP Testing

The browser sends video parts directly to S3. S3 therefore needs an exact-origin CORS rule and must expose the upload `ETag` response header.

1. Open **S3 → your bucket → Permissions**.
2. Scroll to **Cross-origin resource sharing (CORS)**.
3. Choose **Edit**.
4. Use this during initial HTTP testing:

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

Do not add a trailing slash to the origin.

> **Temporary setting:** `http://YOUR_ELASTIC_IP` is only for the initial HTTP test. As soon as users open the application through an HTTPS hostname, update this CORS rule to include that exact HTTPS origin. An IP address and a hostname are different origins, and different subdomains are also different origins. For example, `https://evan.badmintonvideo.com` does not permit uploads from `https://yk.badmintonvideo.com`.

### Delete abandoned multipart uploads

1. Open **S3 → your bucket → Management**.
2. Choose **Create lifecycle rule**.
3. Configure it to delete incomplete multipart uploads after 7 days.

The application attempts to abort cancelled or failed uploads. The lifecycle rule handles closed tabs, dead batteries, and network loss.

---

# Part C — Install and Run the Application

## 7. Connect to Ubuntu

### Option A — EC2 Instance Connect in the browser

1. Open **EC2 → Instances**.
2. Select the instance.
3. Choose **Connect**.
4. Choose **EC2 Instance Connect**.
5. Confirm the username is `ubuntu`.
6. Choose **Connect**.

### Option B — SSH

macOS or Linux:

```bash
ssh -i ~/.ssh/badminton-vault-key.pem ubuntu@YOUR_ELASTIC_IP
```

Windows PowerShell:

```powershell
ssh -i "$HOME\.ssh\badminton-vault-key.pem" ubuntu@YOUR_ELASTIC_IP
```

If SSH times out, check that:

- the instance is running;
- the Elastic IP is associated with the correct instance;
- port 22 is allowed from your current public IP;
- you are using the correct key pair and username.

---

## 8. Prepare Ubuntu

Refresh package metadata and install dependencies:

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

Do not run `aws configure` when using the EC2 role. The returned ARN should contain:

```text
assumed-role/BadmintonVideoVaultEC2Role/
```

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

Regular swap use under normal traffic means the instance should be resized.

Create the application destination:

```bash
sudo mkdir -p /srv/badminton-video-vault
sudo chown ubuntu:ubuntu /srv/badminton-video-vault
ls -la /srv/badminton-video-vault
```

Do not create `data/` before cloning into this destination.

---

## 9. Clone and Configure the Application

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

Append a GitHub host block without overwriting unrelated SSH configuration:

```bash
touch ~/.ssh/config
chmod 600 ~/.ssh/config

grep -q '^Host github.com$' ~/.ssh/config || cat >> ~/.ssh/config <<'KEYEOF'
Host github.com
  IdentityFile ~/.ssh/deploy_key
  IdentitiesOnly yes
KEYEOF

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

### Create the production `.env`

Generate a secret:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Open the environment file:

```bash
nano /srv/badminton-video-vault/.env
```

Use the following as a starting point:

```ini
FLASK_SECRET_KEY=PASTE_A_LONG_RANDOM_VALUE
FLASK_ENV=production
AUTO_CREATE_DB=false

DATABASE_URL=sqlite:////srv/badminton-video-vault/data/badminton_vault.db

AWS_REGION=YOUR_BUCKET_REGION
S3_BUCKET_NAME=YOUR_EXACT_BUCKET_NAME
PRESIGNED_URL_EXPIRY=3600

MAX_VIDEO_FILE_SIZE=3221225472
MAX_REQUEST_BODY_SIZE=4194304
S3_MULTIPART_PART_SIZE=16777216
S3_MULTIPART_URL_EXPIRY=7200
S3_MULTIPART_TOKEN_MAX_AGE=21600
S3_MULTIPART_CONCURRENCY=3

# Temporary value until the custom domain and HTTPS are ready.
APP_BASE_URL=http://YOUR_ELASTIC_IP

# Keep email suppressed until Mailgun is configured and tested.
MAIL_SUPPRESS_SEND=true
MAILGUN_TEST_MODE=false
MAILGUN_TIMEOUT_SECONDS=10

PASSWORD_RESET_TOKEN_TTL_MINUTES=30
MAGIC_LOGIN_TOKEN_TTL_MINUTES=15
AUTH_EMAIL_COOLDOWN_SECONDS=60
```

Do not add AWS access-key variables when the EC2 IAM role is attached.

Protect the file:

```bash
chmod 600 /srv/badminton-video-vault/.env
```

Initialise the database and create the first administrator:

```bash
cd /srv/badminton-video-vault
source venv/bin/activate
flask init-db
flask create-admin
```

### Manual application test

```bash
gunicorn --bind 127.0.0.1:5000 --workers 1 app:app
```

In another session:

```bash
curl -i http://127.0.0.1:5000/login
```

Expect `HTTP/1.1 200 OK`, then stop the manual Gunicorn process with `Ctrl+C`.

---

## 10. Configure Gunicorn and systemd

Create the service file:

```bash
sudo nano /etc/systemd/system/badminton-vault.service
```

Paste:

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

Start and verify:

```bash
sudo systemctl daemon-reload
sudo systemctl enable badminton-vault
sudo systemctl restart badminton-vault
sleep 5
sudo systemctl status badminton-vault --no-pager -l
ls -l /run/badminton-vault/
```

The status should show:

```text
active (running)
```

Configure log rotation:

```bash
sudo tee /etc/logrotate.d/badminton-vault > /dev/null <<'LOGEOF'
/var/log/badminton-vault/*.log {
    weekly
    rotate 8
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
LOGEOF
```

---

## 11. Configure Nginx for Initial HTTP Access

Create the site configuration:

```bash
sudo nano /etc/nginx/sites-available/badminton-vault
```

Paste:

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

Enable the site and remove Ubuntu's default site:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf \
  /etc/nginx/sites-available/badminton-vault \
  /etc/nginx/sites-enabled/badminton-vault

sudo nginx -t
sudo systemctl reload nginx
```

Test locally:

```bash
curl -i http://127.0.0.1/login
```

Then open:

```text
http://YOUR_ELASTIC_IP/login
```

### Checkpoint 4

Do not begin domain or HTTPS setup until the application opens through the Elastic IP.

---

# Part D — Custom Domain and HTTPS

## 12. Beginner-Friendly Domain and HTTPS Walkthrough

This section connects a hostname such as `evan.badmintonvideo.com` to the EC2 application and then enables HTTPS.

```text
evan.badmintonvideo.com
          |  DNS A record
          v
EC2 Elastic IP
          |  ports 80 and 443
          v
Nginx -> Gunicorn -> Flask

Browser video PUT requests --------------------------> Private S3 bucket
```

The setup spans four places:

1. **AWS EC2** provides the stable Elastic IP and permits ports 80/443.
2. **Your DNS provider** points the hostname to the Elastic IP.
3. **The EC2 server** configures Nginx and obtains a TLS certificate.
4. **The S3 bucket** permits direct uploads from the final HTTPS origin.

Follow the checkpoints in order. Do not jump directly to Certbot.

---

### 12.1 Choose the Exact Hostname

A dedicated subdomain is normally easiest and is less likely to interfere with an existing website or email configuration.

Example:

```text
Root domain: badmintonvideo.com
Host/name:   evan
Full name:   evan.badmintonvideo.com
Final URL:   https://evan.badmintonvideo.com
```

Use only the hostname in DNS and Nginx:

```text
YOUR_HOSTNAME
```

Do not enter any of these as a hostname:

```text
https://YOUR_HOSTNAME
YOUR_HOSTNAME/login
YOUR_HOSTNAME/
YOUR_HOSTNAME:5000
```

---

### 12.2 Confirm the AWS Prerequisites

Before changing DNS, confirm all of the following:

- The application opens at `http://YOUR_ELASTIC_IP/login`.
- The Elastic IP is associated with the correct EC2 instance.
- The EC2 security group permits inbound HTTP on port 80.
- The EC2 security group permits inbound HTTPS on port 443.
- SSH on port 22 is restricted to your trusted source.
- Port 5000 is not publicly exposed.
- Nginx and the application service are running.

From EC2:

```bash
curl -i http://127.0.0.1/login
sudo systemctl status nginx --no-pager -l
sudo systemctl status badminton-vault --no-pager -l
```

Fix any failure before continuing.

---

### 12.3 Create the DNS A Record

#### Is Amazon Route 53 required?

**No. Route 53 is optional.** Use the DNS provider whose nameservers are currently authoritative for your domain.

- If your domain's DNS is already managed by WHOIS/MyOrderBox, Cloudflare, GoDaddy, Namecheap, Squarespace Domains, or another provider, create the `A` record there and skip the Route 53 steps.
- Creating a Route 53 hosted zone by itself does not make Route 53 active. The domain continues using its current DNS provider until its nameservers are changed at the registrar.
- Moving DNS to Route 53 is a separate migration. Before changing nameservers, recreate every required record in Route 53, including existing `A`, `CNAME`, `MX`, `TXT`, SPF, DKIM, and DMARC records. Missing records can interrupt websites or email.
- Do not create matching records at multiple DNS providers and expect both sets to control the domain. Only the provider named by the domain's authoritative nameservers is live.

For a working WHOIS/MyOrderBox setup, the path is simply:

```text
WHOIS/MyOrderBox DNS
        -> A record for the chosen subdomain
        -> EC2 Elastic IP
        -> Nginx on the badminton vault EC2 instance
```

Sign in to the company that currently manages DNS for the root domain. This may be WHOIS/MyOrderBox, Route 53, Cloudflare, GoDaddy, Namecheap, Squarespace Domains, or another provider.

Look for **DNS Management**, **Manage DNS**, **Zone Editor**, or **DNS Records**.

Create an IPv4 `A` record:

| DNS field | Enter |
|---|---|
| Type | `A` |
| Name, Host, or Record name | Only the subdomain portion, for example `evan` |
| Destination, Value, Address, or Points to | Your Elastic IP |
| TTL | `300`, five minutes, or the provider default |

Example:

```text
Type:        A
Name/Host:   evan
Destination: 203.0.113.10
TTL:         Auto
```

This means:

```text
YOUR_HOSTNAME -> 203.0.113.10
```

#### WHOIS/MyOrderBox-style DNS screen

1. Open the domain's **DNS Management** page.
2. Choose **Manage DNS**.
3. Open the **A Records** tab.
4. Choose **Add A Record** or **Add Address A Record**.
5. Enter only the subdomain label, such as `evan`, in the name field.
6. Enter the Elastic IP in the destination IP field.
7. Save.
8. Confirm the resulting row shows the full hostname, the Elastic IP, and an **Active** status.

#### Amazon Route 53

1. Open **Route 53 → Hosted zones**.
2. Select the hosted zone for the root domain.
3. Choose **Create record**.
4. Set **Record name** to the subdomain label, such as `evan`.
5. Set **Record type** to `A`.
6. Enter the Elastic IP under **Value**.
7. Use **Simple routing**.
8. Choose **Create records**.

#### Important DNS rules

- Do not use **Domain Forwarding** for this setup. Use a DNS `A` record.
- Do not enter `https://` in an A record.
- Do not include `/login`, a slash, or a port.
- Do not create a CNAME whose target is an IP address.
- Do not point DNS to the EC2 private IP address.
- Do not point DNS to an old temporary public IP.
- Do not add an `AAAA` record unless IPv6 is deliberately configured end to end.
- If the DNS provider offers proxy/CDN mode, use **DNS only** until HTTPS works directly.
- Do not change unrelated MX, TXT, SPF, DKIM, DMARC, or other email records.

---

### 12.4 Verify DNS Resolution

Do not continue to Certbot until the hostname resolves publicly to the exact Elastic IP.

From Windows PowerShell:

```powershell
nslookup YOUR_HOSTNAME
Resolve-DnsName YOUR_HOSTNAME -Type A
```

From macOS, Linux, or EC2:

```bash
dig +short A YOUR_HOSTNAME
```

If `dig` is unavailable on Ubuntu:

```bash
sudo apt update
sudo apt install -y dnsutils
dig +short A YOUR_HOSTNAME
```

The result must be your Elastic IP.

If the result is blank or incorrect:

1. Recheck the A record name and value.
2. Confirm the root domain uses the nameservers of the DNS provider you edited.
3. Remove conflicting A or AAAA records for the same hostname.
4. Wait for DNS caches to expire according to the previous TTL.
5. Repeat the lookup.

### Checkpoint 5

Confirm both of these before continuing:

- `nslookup` or `dig` returns the Elastic IP.
- `http://YOUR_HOSTNAME/login` opens the correct application.

The browser will still show **Not secure** at this point. That is expected because HTTPS has not been installed yet.

---

### 12.5 Configure Nginx for the Hostname

Connect to EC2 using EC2 Instance Connect or SSH.

Back up the working Nginx configuration:

```bash
sudo cp \
  /etc/nginx/sites-available/badminton-vault \
  /etc/nginx/sites-available/badminton-vault.before-domain
```

Open the configuration:

```bash
sudo nano /etc/nginx/sites-available/badminton-vault
```

Find:

```nginx
server_name _;
```

Replace it with the exact hostname:

```nginx
server_name YOUR_HOSTNAME;
```

Do not include `https://`, a path, or a trailing slash.

#### Saving in Nano

Press:

```text
Ctrl+O
Enter
Ctrl+X
```

Test before reloading:

```bash
sudo nginx -t
```

The expected result includes:

```text
syntax is ok
test is successful
```

Do not reload Nginx if the test reports an error.

After a successful test:

```bash
sudo systemctl reload nginx
sudo systemctl status nginx --no-pager -l
```

To restore the backup if needed:

```bash
sudo cp \
  /etc/nginx/sites-available/badminton-vault.before-domain \
  /etc/nginx/sites-available/badminton-vault
sudo nginx -t
sudo systemctl reload nginx
```

---

### 12.6 Test the Hostname over HTTP

From EC2:

```bash
curl -I http://YOUR_HOSTNAME/login
```

Also open this in a browser:

```text
http://YOUR_HOSTNAME/login
```

The login page should match the application previously reached through the Elastic IP.

If the Elastic IP works but the hostname does not, recheck DNS, the security group, and the Nginx `server_name` before continuing.

---

### 12.7 Install Certbot and Enable HTTPS

Install Certbot and its Nginx integration:

```bash
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
```

Request a certificate for the exact hostname:

```bash
sudo certbot --nginx -d YOUR_HOSTNAME
```

During the prompts:

1. Enter an email address for renewal and security notices.
2. Accept the terms of service.
3. Choose HTTP-to-HTTPS redirection if Certbot offers the option.

A successful result should state that the certificate was received and deployed.

Verify:

```bash
sudo nginx -t
sudo systemctl status nginx --no-pager -l
sudo certbot certificates
curl -I https://YOUR_HOSTNAME/login
```

A normal result may be `200 OK` or an application redirect.

If Certbot reports an authorisation or connection failure, do not repeatedly retry. First verify:

- DNS resolves to the correct Elastic IP.
- Port 80 is publicly reachable.
- The Elastic IP is associated with the correct instance.
- Nginx is running.
- DNS proxy/CDN mode is disabled during initial setup.

---

### 12.8 Update `APP_BASE_URL`

The application uses `APP_BASE_URL` in password-reset and magic-login links. Replace the temporary IP-based URL with the final HTTPS origin.

Open the production environment file:

```bash
nano /srv/badminton-video-vault/.env
```

Find:

```ini
APP_BASE_URL=http://YOUR_ELASTIC_IP
```

Replace it with:

```ini
APP_BASE_URL=https://YOUR_HOSTNAME
```

Do not add a trailing slash.

Restart the application:

```bash
sudo systemctl restart badminton-vault
sleep 3
sudo systemctl status badminton-vault --no-pager -l
```

Confirm only the intended value without printing unrelated secrets:

```bash
grep '^APP_BASE_URL=' /srv/badminton-video-vault/.env
```

Expected:

```text
APP_BASE_URL=https://YOUR_HOSTNAME
```

---

### 12.9 Test Automatic Certificate Renewal

Run a safe simulated renewal:

```bash
sudo certbot renew --dry-run
```

The expected result is similar to:

```text
Congratulations, all simulated renewals succeeded
```

Certbot normally installs a timer or scheduled task for automatic renewal.

---

### 12.10 Update S3 CORS to the HTTPS Origin

This step is essential. The website can load correctly while direct video uploads still fail if S3 does not allow the new HTTPS origin.

Open **S3 → your bucket → Permissions → Cross-origin resource sharing (CORS)**.

During migration, allow both the temporary HTTP origin and the final HTTPS origin:

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "PUT"],
    "AllowedOrigins": [
      "http://YOUR_ELASTIC_IP",
      "https://YOUR_HOSTNAME"
    ],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

After HTTPS uploads work, remove the temporary HTTP origin:

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "PUT"],
    "AllowedOrigins": ["https://YOUR_HOSTNAME"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

The origin must match the browser address exactly and must not have a trailing slash.

Examples of separate origins that must each be listed when they are used:

```text
http://YOUR_ELASTIC_IP
https://evan.badmintonvideo.com
https://yk.badmintonvideo.com
```

Changing DNS, Nginx, Certbot, or `APP_BASE_URL` does **not** update S3 CORS automatically. If the website opens normally but upload displays `The browser could not upload a part to S3. Check the bucket CORS rule and your network connection.`, check this CORS rule first, add the exact HTTPS hostname origin, and remove the old IP origin only after HTTPS uploads work.

Do not use `"*"` for `AllowedOrigins` on the private production vault. Updating CORS does not make the bucket public.

---

### 12.11 Perform the Final Domain Test

Verify the HTTP-to-HTTPS redirect:

```bash
curl -I http://YOUR_HOSTNAME/login
```

Verify HTTPS directly:

```bash
curl -I https://YOUR_HOSTNAME/login
```

Then test in a browser:

1. Open `https://YOUR_HOSTNAME`.
2. Confirm the browser reports a valid secure connection.
3. Sign in.
4. Upload a small MP4 before testing a large file.
5. Open browser developer tools → **Network**.
6. Confirm application JSON requests use the HTTPS hostname.
7. Confirm multipart `PUT` requests go directly to an S3 hostname.
8. Confirm the video record is created.
9. Confirm playback and download work.
10. Test **Cancel Upload** and confirm no video record is created.

### Checkpoint 6 — Domain Setup Complete

The domain setup is complete when all of these are true:

- [ ] DNS resolves to the Elastic IP.
- [ ] HTTP redirects to HTTPS.
- [ ] The browser shows a valid secure connection.
- [ ] Nginx and `badminton-vault` are active.
- [ ] `APP_BASE_URL` contains the HTTPS hostname.
- [ ] S3 CORS contains the exact HTTPS origin.
- [ ] A small MP4 uploads and plays successfully.
- [ ] `sudo certbot renew --dry-run` succeeds.

Use the hostname instead of the Elastic IP for normal access from now on.

---

### 12.12 Domain and HTTPS Troubleshooting

| Symptom | Checks and fixes |
|---|---|
| DNS lookup is blank | Check the record name, active nameservers, and DNS-zone selection; then wait for caches to expire |
| DNS lookup returns the wrong IP | Replace the record value with the associated Elastic IP and remove conflicting A/AAAA records |
| Domain times out | Confirm the Elastic IP association, inbound ports 80/443, Nginx status, and any active host firewall |
| Domain opens the wrong server | Check for an old A/AAAA record and confirm the Elastic IP is associated with the intended instance |
| Certbot reports `unauthorized` | Confirm DNS points to this EC2 instance, port 80 is reachable, Nginx is running, and proxy mode is disabled |
| `sudo nginx -t` fails | Correct the reported syntax error or restore `badminton-vault.before-domain` before reloading |
| HTTPS returns `502 Bad Gateway` | Check the `badminton-vault` service and the Unix socket under `/run/badminton-vault/` |
| Browser shows the wrong certificate | Check old DNS records, `sudo certbot certificates`, and whether a proxy is serving another certificate |
| Website works but uploads fail with CORS | Add the exact HTTPS origin to S3 CORS, preserve `ETag`, and remove any trailing slash |
| Password-reset email contains the IP | Update `APP_BASE_URL` and restart `badminton-vault` |
| IPv4 works but some clients fail | Remove an unintended AAAA record or fully configure IPv6 end to end |

Useful diagnostics:

```bash
dig +short A YOUR_HOSTNAME
sudo nginx -t
sudo systemctl status nginx --no-pager -l
sudo systemctl status badminton-vault --no-pager -l
sudo certbot certificates
sudo tail -n 100 /var/log/nginx/error.log
sudo tail -n 100 /var/log/badminton-vault/error.log
sudo ufw status
```

If UFW is active and does not permit web traffic:

```bash
sudo ufw allow 'Nginx Full'
sudo ufw status
```

---

# Part E — Operations

## 13. Configure Mailgun Later, If Needed

Keep this setting while outbound email is not ready:

```ini
MAIL_SUPPRESS_SEND=true
```

When configuring Mailgun, use values based on `.env.example`, including:

```ini
MAILGUN_API_KEY=your-mailgun-domain-sending-key
MAILGUN_DOMAIN=your-verified-mailgun-domain
MAILGUN_API_BASE_URL=https://api.mailgun.net
MAIL_FROM="Badminton Video Vault <noreply@your-domain>"
MAIL_SUPPRESS_SEND=false
MAILGUN_TEST_MODE=false
MAILGUN_TIMEOUT_SECONDS=10
```

Restart the application after changing `.env`:

```bash
sudo systemctl restart badminton-vault
```

Do not expose API keys in screenshots, logs, commits, or support messages.

---

## 14. Deploy Application Updates

Manual deployment:

```bash
cd /srv/badminton-video-vault
git pull --ff-only origin main

# Upgrade the historical MAX_VIDEO_FILE_SIZE default (2 GiB) to the new
# 3 GiB default. Only rewrite the value if it still matches the old
# default exactly, preserving any deliberate custom override.
if [ -f .env ] && grep -qx 'MAX_VIDEO_FILE_SIZE=2147483648' .env; then
  sed -i 's/^MAX_VIDEO_FILE_SIZE=2147483648$/MAX_VIDEO_FILE_SIZE=3221225472/' .env
  echo "Upgraded MAX_VIDEO_FILE_SIZE from the old 2 GiB default to 3 GiB."
fi

source venv/bin/activate
python -m pip install -r requirements.txt
sudo systemctl restart badminton-vault
```

Verify the effective limit took effect after the restart:

```bash
grep '^MAX_VIDEO_FILE_SIZE=' /srv/badminton-video-vault/.env || echo "Using the code default (3 GiB)."
```

Verify through the Unix socket:

```bash
curl --fail --silent --show-error \
  --unix-socket /run/badminton-vault/badminton-vault.sock \
  http://localhost/login > /dev/null \
  && echo "Application is healthy"
```

Then verify the public HTTPS URL.

The included GitHub Actions workflow runs smoke tests before deployment and uses the nested socket path. It requires `EC2_HOST` and `EC2_SSH_KEY` repository secrets. Prefer SSM, a self-hosted runner, or a controlled source IP rather than opening SSH globally for CI/CD.

---

## 15. Backups and Maintenance

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

## 16. General Troubleshooting

### S3 and direct upload

| Symptom | Fix |
|---|---|
| Browser CORS/network error | Add the exact browser origin to S3 CORS; no trailing slash |
| Missing ETag error | Add `"ExposeHeaders": ["ETag"]` |
| `AccessDenied` | Verify the EC2 role, bucket ARN, and required S3 actions |
| URLs expire before completion | Increase `S3_MULTIPART_URL_EXPIRY`, then restart Gunicorn |
| File rejected immediately | Check the extension and `MAX_VIDEO_FILE_SIZE` |
| Upload reaches 100% then fails | Inspect the Gunicorn log for completion, size, or database failure |
| Abandoned parts accumulate | Enable the seven-day incomplete-multipart lifecycle rule |
| `413 Request Entity Too Large` | Ensure the latest direct-upload JavaScript is loaded and the video is not being posted to Flask |

### Gunicorn and Nginx

| Symptom | Fix |
|---|---|
| Socket permission error | Use `RuntimeDirectory=badminton-vault` and the nested socket path |
| `502 Bad Gateway` | Check the service status and socket path |
| **Welcome to nginx!** | Remove `/etc/nginx/sites-enabled/default` |
| Generic 500 error | Check `/var/log/badminton-vault/error.log` |
| Worker restart loop | Check systemd, Gunicorn, and kernel out-of-memory logs |

Out-of-memory diagnostics:

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
- Use an EC2 IAM role instead of static access keys.
- Restrict SSH to trusted sources.
- Keep `.env` mode `600`.
- Use HTTPS and a strong `FLASK_SECRET_KEY`.
- Keep the operating system and Python dependencies patched.
- Do not expose Mailgun keys, Flask secrets, SSH keys, or AWS credentials.
- Incomplete multipart parts consume S3 storage until aborted or removed by lifecycle policy.
- Public IPv4 addresses, EC2, EBS, S3 requests, data transfer, snapshots, and backups may incur charges. Check current AWS pricing.

---

## References

- [S3 multipart upload](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html)
- [S3 CORS](https://docs.aws.amazon.com/AmazonS3/latest/userguide/cors.html)
- [Abort incomplete multipart uploads with lifecycle](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpu-abort-incomplete-mpu-lifecycle-config.html)
- [Attach an IAM role to EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/attach-iam-role.html)
- [Elastic IP addresses](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/elastic-ip-addresses-eip.html)
- [Create records in Route 53](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resource-record-sets-creating.html)
- [Nginx server names](https://nginx.org/en/docs/http/server_names.html)
- [Certbot instructions](https://certbot.eff.org/instructions)
- [Let's Encrypt challenge types](https://letsencrypt.org/docs/challenge-types/)
- [AWS CLI v2 installation](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
