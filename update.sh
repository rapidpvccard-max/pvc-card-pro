#!/bin/bash
set -e

echo "=========================================================="
echo "🔄 Updating PVC Card Pro on AWS EC2"
echo "=========================================================="

cd "$(dirname "$0")"

echo "📦 Pulling latest changes from GitHub..."
git pull origin main

echo "📦 Verifying Python dependencies..."
./venv/bin/pip install -r requirements.txt --quiet

echo "📦 Verifying fonts..."
if [ -d "static/fonts" ]; then
    sudo mkdir -p /usr/local/share/fonts/nirmala
    sudo cp static/fonts/*.ttf /usr/local/share/fonts/nirmala/ 2>/dev/null || true
    sudo chmod 644 /usr/local/share/fonts/nirmala/*.ttf 2>/dev/null || true
    sudo fc-cache -f 2>/dev/null || true
fi

echo "🔄 Restarting pvc_pro systemd service..."
sudo systemctl daemon-reload
sudo systemctl restart pvc_pro

echo "🔍 Checking service status..."
sudo systemctl status pvc_pro --no-pager -l

echo ""
echo "=========================================================="
echo "✅ PVC Card Pro successfully updated and live!"
echo "=========================================================="
