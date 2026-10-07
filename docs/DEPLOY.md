# VPS Deployment Guide & Setup Checklist

This document details the one-time VPS setup required for automated deployments via GitHub Actions.

---

## 1. Prerequisites on the VPS

### 1.1 Install Docker and Docker Compose
Install Docker Engine and Docker Compose v2 following official instructions for your distribution (e.g. Ubuntu/Debian):
```bash
sudo apt update && sudo apt install -y ca-certificates curl gnupg
# Install Docker Engine and compose plugin
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

### 1.2 Create Deployment Directory
Create a dedicated folder for the notes service (e.g. `/opt/notes-mcp` or `~/notes-mcp`):
```bash
sudo mkdir -p /opt/notes-mcp
sudo chown $USER:$USER /opt/notes-mcp
cd /opt/notes-mcp
```

### 1.3 Configure `docker-compose.yml` and `.env`
Copy `docker-compose.yml` from this repository to `/opt/notes-mcp/docker-compose.yml`.

Create the `.env` file manually on the VPS:
```bash
cat << 'EOF' > /opt/notes-mcp/.env
# Generate a secure token: openssl rand -hex 32
MCP_AUTH_TOKEN=your-random-token-here
DB_PATH=/app/data/notes.db
HOST=0.0.0.0
PORT=3000
LOG_LEVEL=INFO
ALLOWED_HOSTS=*
EOF
chmod 600 /opt/notes-mcp/.env
```

### 1.4 GHCR Image Access (if Package is Private)
If your repository or GitHub Container Registry package is private, authenticate Docker on the VPS:
```bash
echo "<GITHUB_PAT_WITH_READ_PACKAGES>" | docker login ghcr.io -u <GITHUB_USERNAME> --password-stdin
```

---

## 2. Dedicated SSH Deploy Key Setup

Generate a dedicated SSH key pair on your local machine or VPS:
```bash
ssh-keygen -t ed25519 -C "deploy-notes-mcp" -f ./deploy_key -N ""
```

1. Append the **public key** (`deploy_key.pub`) to `~/.ssh/authorized_keys` on your VPS.
2. The **private key** (`deploy_key`) will be added to GitHub Repository Secrets.

---

## 3. Reverse Proxy & SSL Setup (Nginx + Certbot)

Install Nginx and Certbot:
```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

1. Copy [deploy/nginx.conf.example](deploy/nginx.conf.example) to `/etc/nginx/sites-available/notes-mcp.conf`.
2. Replace `mcp.example.com` with your domain.
3. Obtain a TLS certificate with Let's Encrypt:
   ```bash
   sudo certbot --nginx -d mcp.example.com
   ```
4. Enable the configuration and reload Nginx:
   ```bash
   sudo ln -s /etc/nginx/sites-available/notes-mcp.conf /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   ```

---

## 4. GitHub Actions Repository Secrets

In your GitHub repository, navigate to **Settings ➔ Secrets and variables ➔ Actions** and add the following repository secrets:

| Secret Name | Description | Example Value |
|---|---|---|
| `VPS_HOST` | VPS IP address or hostname | `203.0.113.10` or `vps.example.com` |
| `VPS_USER` | SSH username | `ubuntu` or `deploy` |
| `VPS_SSH_KEY` | Private SSH key (content of `deploy_key`) | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `VPS_PORT` | SSH port *(optional, defaults to 22)* | `22` |
| `VPS_DEPLOY_PATH` | Path to deployment directory on VPS | `/opt/notes-mcp` |

---

## 5. Deployment Verification

Once secrets are set, any commit pushed to `main` triggers `.github/workflows/release.yml`:
1. Runs tests and linters.
2. Builds and pushes the Docker image to GHCR.
3. SSH connects to the VPS, pulls the new image, updates containers with zero data loss, and prunes old images.
