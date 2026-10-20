#!/bin/bash
# ==============================================================================
# 🔍 RAPID PVC PRO - AWS SERVER DEEP TECHNICAL AUDIT SCRIPT
# ==============================================================================
# Run this on your AWS EC2 instance:
#   bash server_audit.sh
# ==============================================================================

set -o pipefail

# Text formatting
BOLD='\033[1m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

pass_count=0
warn_count=0
fail_count=0

log_pass() { echo -e "  [${GREEN}PASS${NC}] $1"; ((pass_count++)); }
log_warn() { echo -e "  [${YELLOW}WARN${NC}] $1"; ((warn_count++)); }
log_fail() { echo -e "  [${RED}FAIL${NC}] $1"; ((fail_count++)); }
log_info() { echo -e "  [${CYAN}INFO${NC}] $1"; }

print_section() {
    echo ""
    echo -e "${BOLD}${BLUE}==============================================================================${NC}"
    echo -e "${BOLD}${CYAN} $1 ${NC}"
    echo -e "${BOLD}${BLUE}==============================================================================${NC}"
}

clear 2>/dev/null || true
echo -e "${BOLD}${CYAN}"
echo "  ____             _     _   ______     ______   ____            "
echo " |  _ \ __ _ _ __ (_) __| | |  _ \ \   / / ___| |  _ \ _ __ ___  "
echo " | |_) / _\` | '_ \| |/ _\` | | |_) \ \ / / |     | |_) | '__/ _ \ "
echo " |  _ < (_| | |_) | | (_| | |  __/ \ V /| |___  |  __/| | | (_) |"
echo " |_| \_\__,_| .__/|_|\__,_| |_|     \_/  \____| |_|   |_|  \___/ "
echo "            |_|                                                  "
echo "           🚀 AWS EC2 FULL PRODUCTION HEALTH & AUDIT 🚀         "
echo -e "${NC}"
echo -e " Timestamp: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo -e " Hostname : $(hostname) ($(uname -n))"
echo -e " Kernel   : $(uname -r)"

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -f "$APP_DIR/app.py" ] && [ -d "/home/ubuntu/PVC_Python_Tool" ]; then
    APP_DIR="/home/ubuntu/PVC_Python_Tool"
fi

# ==============================================================================
# 1. OS & UPTIME
# ==============================================================================
print_section "1. Operating System & System Uptime"
if [ -f /etc/os-release ]; then
    . /etc/os-release
    log_info "OS: $PRETTY_NAME"
    if [[ "$ID" == "ubuntu" || "$ID" == "debian" ]]; then
        log_pass "Debian/Ubuntu Linux environment detected"
    else
        log_warn "Non-standard Linux distro ($ID)"
    fi
else
    log_warn "Could not read /etc/os-release"
fi

uptime_str=$(uptime -p 2>/dev/null || uptime)
log_info "Uptime: $uptime_str"
load_avg=$(uptime | awk -F'load average:' '{ print $2 }')
log_info "Load Average:$load_avg"

# ==============================================================================
# 2. RAM & SWAP MEMORY HEALTH
# ==============================================================================
print_section "2. Memory & Swap Health (Critical for Chromium Card Rendering)"
ram_total_mb=$(free -m | awk '/^Mem:/{print $2}')
ram_avail_mb=$(free -m | awk '/^Mem:/{print $7}')
swap_total_mb=$(free -m | awk '/^Swap:/{print $2}')
swap_free_mb=$(free -m | awk '/^Swap:/{print $4}')

log_info "Physical RAM  : Total ${ram_total_mb} MB | Available ${ram_avail_mb} MB"
log_info "Swap Space    : Total ${swap_total_mb} MB | Free ${swap_free_mb} MB"

if [ "$ram_total_mb" -ge 1800 ]; then
    log_pass "Physical RAM is >= 2GB (${ram_total_mb} MB)"
elif [ "$ram_total_mb" -ge 900 ]; then
    log_info "Server is running on ~1GB RAM (t2.micro / t3.micro)"
else
    log_warn "Low physical RAM detected (< 1GB)"
fi

if [ "$swap_total_mb" -ge 2000 ]; then
    log_pass "Swap space is properly configured (${swap_total_mb} MB) - Prevents Chromium OOM crashes"
elif [ "$swap_total_mb" -gt 0 ]; then
    log_warn "Swap is active but under 2GB (${swap_total_mb} MB). Recommend 4GB swap for high traffic."
else
    log_fail "NO SWAP SPACE DETECTED! High risk of Chromium OOM browser crashes on PDF generation!"
fi

# ==============================================================================
# 3. STORAGE & DISK SPACE
# ==============================================================================
print_section "3. Disk Space & Temporary Files Accumulation"
root_disk_pct=$(df -h / | awk 'NR==2 {print $5}' | tr -d '%')
root_disk_free=$(df -h / | awk 'NR==2 {print $4}')
root_disk_total=$(df -h / | awk 'NR==2 {print $2}')

log_info "Root Partition (/): Total ${root_disk_total} | Free ${root_disk_free} (${root_disk_pct}% used)"

if [ "$root_disk_pct" -lt 75 ]; then
    log_pass "Sufficient disk space available (< 75% used)"
elif [ "$root_disk_pct" -lt 90 ]; then
    log_warn "Disk space is over 75% full (${root_disk_pct}% used)"
else
    log_fail "CRITICAL: Disk space nearly full (${root_disk_pct}% used)!"
fi

if [ -d "$APP_DIR" ]; then
    log_info "Checking app directory storage: $APP_DIR"
    for sub in uploads output static/renders tests_output; do
        if [ -d "$APP_DIR/$sub" ]; then
            sub_count=$(find "$APP_DIR/$sub" -type f | wc -l)
            sub_size=$(du -sh "$APP_DIR/$sub" 2>/dev/null | cut -f1)
            log_info "  - $sub: ${sub_count} files (${sub_size})"
            if [ "$sub_count" -gt 1500 ]; then
                log_warn "  Folder $sub has ${sub_count} files. Auto-cleanup recommended."
            fi
        fi
    done
fi

# ==============================================================================
# 4. FASTAPI / UVICORN APPLICATION SERVICE (`pvc_pro`)
# ==============================================================================
print_section "4. FastAPI / Uvicorn Service Status (pvc_pro)"
if command -v systemctl >/dev/null 2>&1; then
    svc_status=$(systemctl is-active pvc_pro 2>/dev/null || true)
    svc_enabled=$(systemctl is-enabled pvc_pro 2>/dev/null || true)
    
    if [ "$svc_status" = "active" ]; then
        log_pass "pvc_pro service is RUNNING (active)"
    else
        log_fail "pvc_pro service is NOT running! Status: ${svc_status:-unknown}"
    fi

    if [ "$svc_enabled" = "enabled" ]; then
        log_pass "pvc_pro service is ENABLED on boot"
    else
        log_warn "pvc_pro service is NOT enabled to auto-start on server reboot"
    fi

    uvicorn_workers=$(pgrep -f "uvicorn app:app" | wc -l)
    if [ "$uvicorn_workers" -gt 0 ]; then
        log_pass "Active Uvicorn worker processes detected ($uvicorn_workers processes)"
    else
        log_fail "No active Uvicorn processes found for app:app"
    fi
else
    log_warn "systemctl command not found (Docker/Container environment?)"
fi

# ==============================================================================
# 5. PLAYWRIGHT CHROMIUM RENDERING ENGINE
# ==============================================================================
print_section "5. Chromium & Playwright Rendering Engine"
if [ -d "$APP_DIR/venv" ]; then
    if "$APP_DIR/venv/bin/python" -c "import playwright" 2>/dev/null; then
        log_pass "Playwright Python library is installed in venv"
    else
        log_fail "Playwright library is MISSING in Python venv!"
    fi

    chrom_test=$("$APP_DIR/venv/bin/python" -c "
from playwright.sync_api import sync_playwright
try:
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        b.close()
    print('OK')
except Exception as e:
    print('ERR:', e)
" 2>/dev/null || echo "FAIL")

    if [[ "$chrom_test" =~ "OK" ]]; then
        log_pass "Headless Chromium launches cleanly and executes without missing Linux shared libraries!"
    else
        log_fail "Headless Chromium failed to launch! Details: $chrom_test"
        log_info "Fix: run './venv/bin/playwright install-deps chromium'"
    fi
fi

# ==============================================================================
# 6. REGIONAL & INDIC FONTS AUDIT
# ==============================================================================
print_section "6. Regional & Indic Fonts Audit (Nirmala UI & Noto Sans)"
if command -v fc-list >/dev/null 2>&1; then
    nirmala_fonts=$(fc-list : family | grep -i "Nirmala" | sort -u | head -n 3 | tr '\n' ',' | sed 's/,$//')
    noto_devanagari=$(fc-list : family | grep -i "Devanagari" | head -n 1)
    noto_gujarati=$(fc-list : family | grep -i "Gujarati" | head -n 1)

    if [ -n "$nirmala_fonts" ]; then
        log_pass "Nirmala UI Font active: $nirmala_fonts"
    else
        log_warn "Nirmala UI font not detected in system cache. Static fallback fonts will be used."
        log_info "Fix: run 'bash install_fonts.sh'"
    fi

    if [ -n "$noto_devanagari" ] || [ -n "$noto_gujarati" ]; then
        log_pass "Indic regional language fonts (Hindi/Gujarati) installed"
    else
        log_warn "Indic fonts package missing. Run: 'sudo apt install -y fonts-indic fonts-noto-extra'"
    fi
else
    log_warn "fontconfig (fc-list) not installed"
fi

# ==============================================================================
# 7. NGINX REVERSE PROXY & CONFIGURATION
# ==============================================================================
print_section "7. Nginx Reverse Proxy & HTTP Server"
if command -v nginx >/dev/null 2>&1; then
    nginx_status=$(systemctl is-active nginx 2>/dev/null || true)
    if [ "$nginx_status" = "active" ]; then
        log_pass "Nginx is RUNNING (active)"
    else
        log_fail "Nginx is NOT running!"
    fi

    nginx_t_output=$(nginx -t 2>&1)
    if [[ "$nginx_t_output" =~ "syntax is ok" ]]; then
        log_pass "Nginx configuration syntax is OK"
    else
        log_fail "Nginx syntax error detected! $nginx_t_output"
    fi

    # Check client_max_body_size
    max_body=$(grep -r "client_max_body_size" /etc/nginx/ 2>/dev/null | head -n 1 | awk '{print $2}' | tr -d ';')
    if [ -n "$max_body" ]; then
        log_pass "Nginx client_max_body_size configured: $max_body"
    else
        log_warn "client_max_body_size not explicitly set in Nginx (Default is 1MB - may block large PDF uploads). Recommended: 30M"
    fi
else
    log_warn "Nginx not installed"
fi

# ==============================================================================
# 8. NETWORK PORTS & LOCAL CONNECTIVITY
# ==============================================================================
print_section "8. Ports & Localhost Connectivity"
check_port() {
    local port=$1
    if command -v ss >/dev/null 2>&1; then
        ss -tuln | grep -q ":$port "
    elif command -v netstat >/dev/null 2>&1; then
        netstat -tuln | grep -q ":$port "
    else
        return 1
    fi
}

if check_port 80; then
    log_pass "Port 80 (HTTP) is listening"
else
    log_warn "Port 80 (HTTP) is NOT listening"
fi

if check_port 443; then
    log_pass "Port 443 (HTTPS) is listening"
else
    log_info "Port 443 (HTTPS) not listening directly on Nginx (Cloudflare or SSL termination in use?)"
fi

if check_port 8000; then
    log_pass "Port 8000 (FastAPI Uvicorn) is listening on internal loopback"
else
    log_fail "Port 8000 (FastAPI Uvicorn) is NOT listening!"
fi

# Test direct local API response
local_resp=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health 2>/dev/null || echo "FAIL")
if [ "$local_resp" = "200" ]; then
    log_pass "Localhost health endpoint http://127.0.0.1:8000/health returned 200 OK"
else
    log_warn "Localhost health endpoint returned: $local_resp"
fi

# ==============================================================================
# 9. ENVIRONMENT SECURITY & DATABASE INTEGRITY
# ==============================================================================
print_section "9. Environment & Database Configuration"
if [ -f "$APP_DIR/.env" ]; then
    log_pass ".env configuration file exists"
    env_perms=$(stat -c "%a" "$APP_DIR/.env" 2>/dev/null || ls -l "$APP_DIR/.env" | awk '{print $1}')
    log_info ".env file permissions: $env_perms"
    
    # Check if real secrets are set (presence test, not displaying value)
    has_secret=$(grep -E "^SECRET_KEY=" "$APP_DIR/.env" | cut -d'=' -f2)
    has_google=$(grep -E "^GOOGLE_CLIENT_ID=" "$APP_DIR/.env" | cut -d'=' -f2)
    has_payu=$(grep -E "^PAYU_MERCHANT_KEY=" "$APP_DIR/.env" | cut -d'=' -f2)
    has_cashfree=$(grep -E "^CASHFREE_APP_ID=" "$APP_DIR/.env" | cut -d'=' -f2)

    [ -n "$has_secret" ] && log_pass "JWT SECRET_KEY configured" || log_warn "SECRET_KEY missing in .env"
    [ -n "$has_google" ] && log_pass "Google OAuth credentials configured" || log_info "Google OAuth not configured"
    [ -n "$has_payu" ] && log_pass "PayU Gateway credentials configured" || log_info "PayU credentials not present"
    [ -n "$has_cashfree" ] && log_pass "Cashfree Gateway credentials configured" || log_info "Cashfree credentials not present"
else
    log_fail ".env file NOT FOUND in $APP_DIR!"
fi

if [ -f "$APP_DIR/app.db" ]; then
    db_size=$(du -sh "$APP_DIR/app.db" | cut -f1)
    log_pass "SQLite database active: $APP_DIR/app.db ($db_size)"
else
    log_info "No local app.db (PostgreSQL / Supabase URL in use?)"
fi

# ==============================================================================
# 10. RECENT SYSTEM & APPLICATION ERROR LOGS
# ==============================================================================
print_section "10. Recent Application Logs & Exceptions (Last 15 Lines)"
if command -v journalctl >/dev/null 2>&1; then
    err_count=$(journalctl -u pvc_pro --since "1 hour ago" -p err 2>/dev/null | grep -v "^--" | wc -l)
    log_info "Errors in pvc_pro logs in last 1 hour: $err_count"
    echo -e "${CYAN}--- journalctl -u pvc_pro -n 12 --no-pager ---${NC}"
    journalctl -u pvc_pro -n 12 --no-pager 2>/dev/null || echo "Could not read journalctl"
else
    log_info "journalctl not available"
fi

# ==============================================================================
# FINAL AUDIT SUMMARY & SCORE
# ==============================================================================
print_section "🏆 AUDIT SUMMARY & SYSTEM RATING"
total_checks=$((pass_count + warn_count + fail_count))
if [ "$total_checks" -gt 0 ]; then
    health_score=$(( (pass_count * 100) / total_checks ))
else
    health_score=0
fi

echo ""
echo -e "  Checks Passed   : ${GREEN}${pass_count}${NC}"
echo -e "  Warnings        : ${YELLOW}${warn_count}${NC}"
echo -e "  Critical Errors : ${RED}${fail_count}${NC}"
echo ""

if [ "$fail_count" -eq 0 ] && [ "$warn_count" -eq 0 ]; then
    echo -e "  ${BOLD}${GREEN}🌟 SYSTEM RATING: 100% HEALTHY - PERFECT PRODUCTION READY!${NC}"
elif [ "$fail_count" -eq 0 ]; then
    echo -e "  ${BOLD}${GREEN}✅ SYSTEM RATING: ${health_score}% HEALTHY - PRODUCTION STABLE (Minor warnings)${NC}"
else
    echo -e "  ${BOLD}${RED}⚠️ SYSTEM RATING: ${health_score}% - ATTENTION REQUIRED (${fail_count} errors)${NC}"
fi

echo ""
echo -e "${BOLD}${BLUE}==============================================================================${NC}"
echo -e " Audit complete! If you have any warnings or errors above, share this output."
echo -e "${BOLD}${BLUE}==============================================================================${NC}"
echo ""
