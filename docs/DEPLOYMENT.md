# Production Deployment Guide 🚀

This guide describes how to deploy the SFA-Routing service to a production environment (Linux Server).

## 1. Prerequisites

- **Server**: 
  - Ubuntu 22.04 LTS (Recommended)
  - 2+ vCPUs, 4GB+ RAM (Minimum)
  - 50GB SSD
- **Software**:
  - Docker Engine v24+
  - Docker Compose v2.20+
  - Git
- **Network**:
  - Static IP
  - Domain name (e.g., `api.example.com`) pointing to the IP
  - Ports 80 and 443 open

## 2. Server Setup

### Install Docker
```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

## 3. Deployment Steps

### Step 1: Clone Repository
```bash
git clone https://github.com/your-org/sfa-routing.git /opt/sfa-routing
cd /opt/sfa-routing
```

### Step 2: Configure Environment
Create the `.env` file for production variables.

```bash
cp .env.example .env
nano .env
```

**Critical Variables to Set:**
- `SECRET_KEY`: Generate a strong random string (e.g., `openssl rand -hex 32`)
- `POSTGRES_PASSWORD`: Strong database password
- `LOG_LEVEL`: Set to `INFO` or `WARNING`
- `CORS_ORIGINS`: Set to your frontend domain (e.g., `["https://app.example.com"]`)

### Step 3: Nginx & SSL
The project uses Nginx as a reverse proxy. By default, it runs on port 80.
For SSL, we recommend running Certbot on the host or adding a sidecar container.

*Host-based Certbot (Recommended for simplicity):*
```bash
sudo apt install certbot python3-certbot-nginx
# After starting nginx container, proxy_pass localhost:80
```

### Step 4: Launch Services
Use the production override file (`docker-compose.prod.yml`) which:
- Removes development volume mounts
- Sets resource limits
- Tunes PostgreSQL

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### Step 5: Verify Deployment
Check service status:
```bash
docker compose ps
```

Monitor logs:
```bash
docker compose logs -f api
```

Verify Health Check:
```bash
curl http://localhost/api/v1/health/detailed
```

## 4. Maintenance

### Database Backups
Create a cron job to dump the database daily.
```bash
# /etc/cron.daily/backup-sfa
docker compose exec -t db pg_dumpall -c -U routeuser > /backups/dump_$(date +%F).sql
```

### Updates
To update the application:
```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose exec api alembic upgrade head
```

## 5. Troubleshooting

- **"502 Bad Gateway"**: Usually means the API container isn't running or healthy. Check `docker compose logs api`.
- **Database Connection Error**: Verify `POSTGRES_PASSWORD` matches in `.env` and `db` service.
- **High Memory Usage**: Adjust resource limits in `docker-compose.prod.yml`.
