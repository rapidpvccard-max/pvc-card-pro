#!/bin/bash
set -e

echo "=========================================================="
echo "📦 Installing Nirmala UI Indian Script Fonts on Linux AWS"
echo "=========================================================="

FONT_DIR="/usr/local/share/fonts/nirmala"
mkdir -p "$FONT_DIR"
cp static/fonts/*.ttf "$FONT_DIR/"
chmod 644 "$FONT_DIR"/*.ttf

echo "🔄 Rebuilding font cache..."
fc-cache -f -v

echo "🔍 Verifying Nirmala UI installation..."
fc-list | grep -i "nirmala" || echo "Warning: Font not listed yet"

echo "🔄 Restarting pvc_pro service..."
systemctl restart pvc_pro || true

echo "=========================================================="
echo "✅ Nirmala UI fonts installed and active on AWS!"
echo "=========================================================="
