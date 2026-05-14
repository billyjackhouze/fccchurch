# FFC Church App — Server Setup Guide

This app runs on the same server as the National Smart Healthcare app.
It uses the same stack: **Python + FastAPI + PostgreSQL**, isolated on its own port and database.

---

## Step 1 — Connect to Your Server

Open a terminal on your Mac and SSH into the server:

```bash
ssh your_username@your.server.ip.address
```

---

## Step 2 — Install Required Software (if not already installed)

These should already be on the server from the healthcare app. Run each command to check:

```bash
python3 --version        # Need 3.10+
psql --version           # Need PostgreSQL 14+
git --version            # Need Git 2+
```

If anything is missing, install it:

```bash
# Update package list
sudo apt update

# Python (if missing)
sudo apt install -y python3 python3-pip python3-venv

# PostgreSQL (if missing)
sudo apt install -y postgresql postgresql-contrib

# Git (if missing)
sudo apt install -y git
```

---

## Step 3 — Set Up the PostgreSQL Database

Log into PostgreSQL as the admin user:

```bash
sudo -u postgres psql
```

Inside the PostgreSQL prompt, run these commands:

```sql
-- Create a dedicated database user for the church app
CREATE USER fcc_user WITH PASSWORD 'choose_a_strong_password_here';

-- Create the database
CREATE DATABASE fcc_church OWNER fcc_user;

-- Grant all privileges
GRANT ALL PRIVILEGES ON DATABASE fcc_church TO fcc_user;

-- Exit PostgreSQL
\q
```

> **Write down the password you chose** — you will need it in Step 5.

---

## Step 4 — Clone the GitHub Repository

Navigate to the directory where you want to host the app (same parent as the healthcare app):

```bash
cd /var/www        # or wherever your healthcare app lives, e.g. /home/your_username/apps
git clone https://github.com/billyjackhouze/fccchurch.git
cd fccchurch
```

---

## Step 5 — Configure Environment Variables

```bash
cd backend
cp .env.example .env
nano .env
```

Edit the file to match your database credentials:

```
DATABASE_URL=postgresql://fcc_user:your_password_here@localhost:5432/fcc_church
APP_PORT=8001
APP_HOST=0.0.0.0
```

> Use port **8001** (the healthcare app likely uses 8000 — this keeps them separate).
> Press **Ctrl+X**, then **Y**, then **Enter** to save in nano.

---

## Step 6 — Create Python Virtual Environment & Install Dependencies

```bash
# Still inside the backend/ directory
python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

---

## Step 7 — Load the Seed Data (Demo Records)

This populates the database with sample members, events, rooms, and giving records:

```bash
python seed.py
```

You should see: `✅  Seed data inserted successfully.`

---

## Step 8 — Test the App

Start the server temporarily to verify everything works:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

Open a browser and go to:
- `http://your.server.ip.address:8001/api/health` → should return `{"status":"ok",...}`
- `http://your.server.ip.address:8001/docs` → interactive API documentation (Swagger UI)

Press **Ctrl+C** to stop the test server.

---

## Step 9 — Run as a Background Service (PM2 or systemd)

### Option A — PM2 (recommended if healthcare app uses PM2)

```bash
# Install PM2 globally if not already installed
sudo npm install -g pm2

# Start the church app
cd /var/www/fccchurch/backend
source venv/bin/activate
pm2 start "uvicorn app.main:app --host 0.0.0.0 --port 8001" --name fcc-church

# Save PM2 process list so it restarts on reboot
pm2 save
pm2 startup    # follow the instructions it prints
```

### Option B — systemd service

```bash
sudo nano /etc/systemd/system/fcc-church.service
```

Paste this content (adjust paths to match your server):

```ini
[Unit]
Description=FFC Church Management App
After=network.target postgresql.service

[Service]
Type=simple
User=your_username
WorkingDirectory=/var/www/fccchurch/backend
Environment="PATH=/var/www/fccchurch/backend/venv/bin"
ExecStart=/var/www/fccchurch/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable fcc-church
sudo systemctl start fcc-church
sudo systemctl status fcc-church   # should show "active (running)"
```

---

## Step 10 — (Optional) Nginx Reverse Proxy

If you want the app available at a nice URL like `church.yourchurch.com` instead of a port number, add an Nginx config block:

```bash
sudo nano /etc/nginx/sites-available/fcc-church
```

```nginx
server {
    listen 80;
    server_name church.yourchurch.com;    # replace with your domain or subdomain

    location / {
        proxy_pass         http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection keep-alive;
        proxy_set_header   Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/fcc-church /etc/nginx/sites-enabled/
sudo nginx -t          # test config — should say "syntax is ok"
sudo systemctl reload nginx
```

---

## Updating the App (after code changes)

Whenever you push new code to GitHub:

```bash
cd /var/www/fccchurch
git pull origin main
cd backend
source venv/bin/activate
pip install -r requirements.txt   # only needed if requirements changed

# Restart the service
pm2 restart fcc-church            # if using PM2
# OR
sudo systemctl restart fcc-church # if using systemd
```

---

## Quick Reference

| What               | Value                                     |
|--------------------|-------------------------------------------|
| App port           | 8001                                      |
| Database name      | fcc_church                                |
| Database user      | fcc_user                                  |
| API docs           | http://your-server:8001/docs              |
| Health check       | http://your-server:8001/api/health        |
| GitHub repo        | https://github.com/billyjackhouze/fccchurch |
| Service name (PM2) | fcc-church                                |
