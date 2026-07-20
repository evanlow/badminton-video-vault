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

This section connects a human-readable domain to the application and then enables HTTPS:

```text
vault.example.com
        |  DNS A record
        v
EC2 Elastic IP
        |  ports 80 and 443
        v
Nginx -> Gunicorn -> Flask

Browser video PUT requests -------------------------> Private S3 bucket
```

`vault.example.com` is only a placeholder. Replace it everywhere below with the exact hostname you control, such as `vault.mybadmintonclub.com`. Do not literally configure `example.com`.

The domain setup spans three places:

1. **Your DNS provider** points the hostname to the EC2 Elastic IP.
2. **The EC2 server** configures Nginx and obtains a TLS certificate with Certbot.
3. **The S3 bucket** permits direct browser uploads from the new HTTPS origin.

### 10.1 Before you begin

Confirm all of the following before changing DNS:

- You own a domain and can edit its DNS records.
- The application currently opens at `http://YOUR_ELASTIC_IP`.
- The Elastic IP is associated with the correct EC2 instance.
- The EC2 security group permits inbound HTTP on port 80 and HTTPS on port 443.
- SSH on port 22 remains restricted to your public IP or another trusted source.
- Port 5000 is not exposed publicly.

From the EC2 server, verify the current HTTP deployment:

```bash
curl -i http://127.0.0.1/login
curl -I http://YOUR_ELASTIC_IP/login
```

Fix the EC2, Gunicorn, or Nginx deployment before continuing if these checks fail.

### 10.2 Choose the exact hostname

A subdomain is usually the simplest option:

```text
vault.example.com
```

For a domain such as `mybadmintonclub.com`, that would be:

```text
vault.mybadmintonclub.com
```

Use one exact hostname throughout the initial setup. The hostname must not contain:

- `http://` or `https://`
- a path such as `/login`
- a trailing slash
- a port such as `:5000`

For example, use this in DNS and Nginx:

```text
vault.mybadmintonclub.com
```

Do not use this as a hostname:

```text
https://vault.mybadmintonclub.com/login
```

Using the root or apex domain, such as `mybadmintonclub.com`, is possible. DNS providers normally represent it with `@` or an empty record name. A dedicated subdomain is less likely to interfere with an existing website or email configuration.

### 10.3 Confirm the Elastic IP and security group

In AWS:

1. Open **EC2 → Network & Security → Elastic IP addresses**.
2. Select the Elastic IP intended for this application.
3. Confirm its associated instance is the badminton vault EC2 instance.
4. Copy the IPv4 address. It will look similar to `203.0.113.10`.

If it is not associated:

1. Select the Elastic IP.
2. Choose **Actions → Associate Elastic IP address**.
3. Select the EC2 instance and its primary private IPv4 address.
4. Choose **Associate**.

Then open the instance's security group and confirm these inbound rules:

| Type | Port | Source |
|---|---:|---|
| SSH | 22 | Your public IP `/32` |
| HTTP | 80 | `0.0.0.0/0`, optionally `::/0` |
| HTTPS | 443 | `0.0.0.0/0`, optionally `::/0` |

Do not point DNS at the instance's private IPv4 address. Do not point DNS at a temporary public IPv4 address when an Elastic IP has been allocated.

### 10.4 Create the DNS A record

Sign in to the service that manages DNS for the domain. This may be Route 53, Cloudflare, Squarespace Domains, GoDaddy, Namecheap, or another provider.

Create an IPv4 `A` record:

| DNS field | Example value |
|---|---|
| Type | `A` |
| Name or Host | `vault` |
| Value, Address, or Points to | `YOUR_ELASTIC_IP` |
| TTL | `300`, five minutes, or `Auto` |

For example:

```text
Type:   A
Name:   vault
Value:  203.0.113.10
TTL:    Auto
```

That record means:

```text
vault.example.com -> 203.0.113.10
```

For Amazon Route 53:

1. Open **Route 53 → Hosted zones**.
2. Select the hosted zone for the domain.
3. Choose **Create record**.
4. Set **Record name** to `vault`.
5. Set **Record type** to `A`.
6. Enter the Elastic IP under **Value**.
7. Use **Simple routing**.
8. Choose **Create records**.

Important DNS rules:

- Enter only the hostname portion requested by the provider. Some providers expect `vault`; others display or expect the full hostname.
- Do not enter `https://vault.example.com` in an A record.
- Do not include a path, slash, or port.
- Do not create a `CNAME` record whose target is an IP address.
- Do not add an `AAAA` record unless IPv6 has deliberately been configured for the instance, routing, security group, and Nginx.
- If a DNS provider offers an HTTP proxy or CDN mode, use **DNS only** during initial certificate setup. Re-enable the proxy later only after the direct origin works correctly.
- Avoid changing unrelated MX, TXT, DKIM, SPF, or other records used by email and existing services.

### 10.5 Verify DNS resolution

Do not continue to Certbot until the hostname resolves publicly to the exact Elastic IP.

From Windows PowerShell:

```powershell
nslookup vault.example.com
Resolve-DnsName vault.example.com -Type A
```

From macOS, Linux, or the EC2 instance:

```bash
dig +short A vault.example.com
```

If `dig` is unavailable on Ubuntu:

```bash
sudo apt update
sudo apt install -y dnsutils
dig +short A vault.example.com
```

The result must be the Elastic IP, for example:

```text
203.0.113.10
```

If the result is blank or shows another address:

1. Recheck the A record name and value.
2. Confirm the domain is using the nameservers of the DNS provider you edited.
3. Remove conflicting records for the same hostname.
4. Allow existing DNS caches to expire according to the previous TTL.
5. Repeat the lookup until it returns the Elastic IP.

Stop here while DNS is incorrect. Certbot cannot validate a hostname that does not reach this server.

### 10.6 Configure Nginx for the hostname

Connect to EC2 over SSH if not already connected:

```bash
ssh -i ~/.ssh/badminton-vault-key.pem ubuntu@YOUR_ELASTIC_IP
```

Windows PowerShell example:

```powershell
ssh -i "$HOME\.ssh\badminton-vault-key.pem" ubuntu@YOUR_ELASTIC_IP
```

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
server_name vault.example.com;
```

The `server_name` value contains only the hostname. Do not include `https://`, a path, or a trailing slash.

Save the file, test it, and reload Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl status nginx --no-pager -l
```

Do not reload Nginx if `sudo nginx -t` reports an error. Correct the indicated file and line first. To restore the backup if necessary:

```bash
sudo cp \
  /etc/nginx/sites-available/badminton-vault.before-domain \
  /etc/nginx/sites-available/badminton-vault
sudo nginx -t
sudo systemctl reload nginx
```

### 10.7 Test the domain over HTTP

Test the public hostname before requesting a certificate:

```bash
curl -I http://vault.example.com/login
```

Also open this address in a browser:

```text
http://vault.example.com/login
```

The login page should be the same application previously reached through the Elastic IP. If the Elastic IP works but the domain does not, recheck DNS, the EC2 security group, and `server_name` before continuing.

### 10.8 Install Certbot and enable HTTPS

Install Certbot and its Nginx integration on the EC2 server:

```bash
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
```

Request a certificate for the exact hostname:

```bash
sudo certbot --nginx -d vault.example.com
```

During the prompts:

1. Enter an email address used for renewal and security notices.
2. Accept the terms of service.
3. Choose the option that redirects HTTP traffic to HTTPS when offered.

Certbot should obtain the certificate and update the Nginx configuration. Then verify Nginx and the certificate:

```bash
sudo nginx -t
sudo systemctl status nginx --no-pager -l
sudo certbot certificates
curl -I https://vault.example.com/login
```

Test automatic renewal without changing the live certificate:

```bash
sudo certbot renew --dry-run
```

The normal HTTP validation must reach this EC2 instance on port 80. If Certbot reports an authorisation or connection error, do not repeatedly retry without first checking the DNS result, Elastic IP association, port 80 security-group rule, Nginx status, and any DNS-provider proxy mode.

### 10.9 Update the application base URL

Open the production environment file:

```bash
nano /srv/badminton-video-vault/.env
```

Find the temporary HTTP value:

```ini
APP_BASE_URL=http://YOUR_ELASTIC_IP
```

Replace it with the exact HTTPS origin, with no trailing slash:

```ini
APP_BASE_URL=https://vault.example.com
```

Save the file and restart the application so Gunicorn loads the new environment value:

```bash
sudo systemctl restart badminton-vault
sleep 3
sudo systemctl status badminton-vault --no-pager -l
```

Confirm the configured value without printing unrelated secrets:

```bash
grep '^APP_BASE_URL=' /srv/badminton-video-vault/.env
```

### 10.10 Update the S3 CORS origin

The browser uploads video parts directly to S3, so the S3 bucket must allow the new HTTPS origin.

Open **S3 → bucket → Permissions → Cross-origin resource sharing (CORS)**.

During migration, both the temporary IP address and the new domain may be listed:

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "PUT"],
    "AllowedOrigins": [
      "http://YOUR_ELASTIC_IP",
      "https://vault.example.com"
    ],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

After HTTPS uploads have been tested successfully, remove the temporary HTTP origin:

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

The origin must match the browser address exactly:

```text
https://vault.example.com
```

Do not add a trailing slash. Do not use `"*"` for `AllowedOrigins` on the private production vault. Updating CORS does not make the bucket public; S3 objects remain protected by Block Public Access and temporary presigned URLs.

### 10.11 Perform the final domain test

Verify the HTTP-to-HTTPS redirect:

```bash
curl -I http://vault.example.com/login
```

The response should redirect to an `https://vault.example.com/...` location.

Verify HTTPS directly:

```bash
curl -I https://vault.example.com/login
```

Then use a browser to complete the application test:

1. Open `https://vault.example.com`.
2. Confirm the browser reports a valid secure connection.
3. Sign in.
4. Upload a small MP4 before testing a large file.
5. In browser developer tools, open **Network**.
6. Confirm application JSON requests use the HTTPS domain.
7. Confirm multipart `PUT` requests go directly to an S3 hostname.
8. Confirm the video record is created and playback works.

After the domain works, use the hostname instead of the Elastic IP for normal access.

### 10.12 Domain and HTTPS troubleshooting

| Symptom | Checks and fixes |
|---|---|
| DNS lookup is blank | Check the record name, active nameservers, and DNS-zone selection; then wait for the previous TTL to expire |
| DNS lookup returns the wrong IP | Replace the record value with the associated Elastic IP and remove conflicting A records |
| Domain times out | Confirm the Elastic IP association, inbound ports 80/443, Nginx status, and any active host firewall |
| Certbot reports `unauthorized` | Confirm the A record resolves to this EC2 instance, port 80 is reachable, Nginx is running, and proxy/CDN mode is disabled during setup |
| `sudo nginx -t` fails | Correct the reported syntax error or restore `badminton-vault.before-domain` before reloading |
| HTTPS returns `502 Bad Gateway` | Check `badminton-vault` service status and the Unix socket under `/run/badminton-vault/` |
| Browser shows the wrong certificate | Check DNS for old A/AAAA records, inspect `sudo certbot certificates`, and confirm the browser is reaching this server rather than a proxy |
| Website works but uploads fail with CORS | Add the exact `https://vault.example.com` origin to S3 CORS, preserve `ETag`, and remove any trailing slash |
| IPv4 works but some clients fail | Remove an unintended AAAA record or fully configure IPv6 through DNS, EC2 networking, the security group, and Nginx |

Useful diagnostics:

```bash
dig +short A vault.example.com
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
- [Elastic IP addresses](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/elastic-ip-addresses-eip.html)
- [Create records in Route 53](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resource-record-sets-creating.html)
- [Nginx server names](https://nginx.org/en/docs/http/server_names.html)
- [Certbot instructions](https://certbot.eff.org/instructions)
- [Let's Encrypt challenge types](https://letsencrypt.org/docs/challenge-types/)
- [AWS CLI v2 installation](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
