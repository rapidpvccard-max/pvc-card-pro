#!/bin/bash
set -e

echo "=========================================================="
echo "🚀 Starting Automated Production Setup for PVC Card Pro"
echo "=========================================================="

# 1. Setup 4GB Swap Space for ultra-fast Playwright Chromium rendering
if [ ! -f /swapfile ]; then
    echo "📦 Creating 4GB swap space..."
    fallocate -l 4G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# 2. Update System & Install Required Packages & Indic Fonts
echo "📦 Installing system dependencies and Indic fonts..."
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential \
    libzbar0 \
    tesseract-ocr \
    fontconfig \
    fonts-noto-core \
    fonts-noto-cjk \
    fonts-noto-extra \
    fonts-indic \
    python3-pip \
    python3-venv \
    git \
    nginx \
    curl

fc-cache -f -v || true

# 3. Clone Repository
echo "📦 Fetching latest code from GitHub..."
cd /home/ubuntu
rm -rf PVC_Python_Tool
git clone https://github.com/rapidpvccard-max/pvc-card-pro.git PVC_Python_Tool
cd /home/ubuntu/PVC_Python_Tool

# 4. Setup Python Virtual Environment & Playwright
echo "📦 Setting up Python virtual environment and Playwright..."
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
./venv/bin/playwright install chromium
./venv/bin/playwright install-deps chromium

# 5. Prepare directories & environment file
mkdir -p uploads output static/renders
if [ ! -f .env ]; then
    cp .env.example .env
fi
chown -R ubuntu:ubuntu /home/ubuntu/PVC_Python_Tool

# 6. Configure systemd service
echo "📦 Configuring background systemd service..."
cat << 'EOF' > /etc/systemd/system/pvc_pro.service
[Unit]
Description=PVC Card Pro FastAPI Production Service
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/PVC_Python_Tool
Environment="PATH=/home/ubuntu/PVC_Python_Tool/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/ubuntu/PVC_Python_Tool/venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable pvc_pro
systemctl restart pvc_pro

# 7. Configure Nginx Reverse Proxy
echo "📦 Configuring Nginx Reverse Proxy on port 80..."
cat << 'EOF' > /etc/nginx/sites-available/default
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    client_max_body_size 30M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 120s;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }
}
EOF

nginx -t && systemctl reload nginx

# 8. Success Output
PUBLIC_IP=$(curl -s http://checkip.amazonaws.com || echo "13.204.69.68")
echo ""
echo "=========================================================="
echo "🎉 CONGRATULATIONS! PVC CARD PRO IS LIVE ON AWS!"
echo "👉 Open Website: http://${PUBLIC_IP}/"
echo "=========================================================="
