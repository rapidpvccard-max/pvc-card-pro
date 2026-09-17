#!/bin/bash
set -e

echo "=========================================================="
echo "📦 Installing Nirmala UI Indian Script Fonts on Linux AWS"
echo "=========================================================="

FONT_DIR="/usr/local/share/fonts/nirmala"
sudo mkdir -p "$FONT_DIR"
sudo cp static/fonts/*.ttf "$FONT_DIR/"
sudo chmod 644 "$FONT_DIR"/*.ttf

echo "🔄 Rebuilding font cache..."
sudo fc-cache -f -v

echo "🔍 Verifying Nirmala UI installation..."
fc-list | grep -i "nirmala" || echo "Warning: Font not listed yet"

echo "🔄 Restarting pvc_pro service..."
sudo systemctl restart pvc_pro || true

echo "=========================================================="
echo "✅ Nirmala UI fonts installed and active on AWS!"
echo "=========================================================="
