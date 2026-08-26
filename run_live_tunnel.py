import subprocess
import re
import sys
import os
import time

# Ensure UTF-8 output encoding for Windows command line
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def start_server_and_tunnel():
    print("=========================================================")
    print("  [*] Starting Rapid PVC Card Pro & Cloudflare Live Tunnel")
    print("=========================================================")
    
    # Check venv python
    python_exe = sys.executable
    if os.path.exists(os.path.join("venv", "Scripts", "python.exe")):
        python_exe = os.path.join("venv", "Scripts", "python.exe")
    
    # 1. Start FastAPI backend
    print("[1/2] Starting local FastAPI server on port 8000...")
    env = os.environ.copy()
    env["ENVIRONMENT"] = "production"
    server_process = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
        encoding="utf-8",
        errors="replace"
    )
    
    time.sleep(2)
    
    # 2. Start Cloudflare Tunnel
    print("[2/2] Connecting to Cloudflare global network...")
    cloudflared_bin = "cloudflared.exe" if os.path.exists("cloudflared.exe") else "cloudflared"
    tunnel_process = subprocess.Popen(
        [cloudflared_bin, "tunnel", "--url", "http://127.0.0.1:8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace"
    )
    
    live_url = None
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
    
    try:
        for line in tunnel_process.stdout:
            match = url_pattern.search(line)
            if match:
                live_url = match.group(0)
                print("\n" + "="*65)
                print("  RAPID PVC CARD PRO IS NOW 100% LIVE ON THE INTERNET!")
                print(f"  >>> LIVE URL: {live_url} <<<")
                print("="*65)
                print("\n  You can open this link on your Mobile or send to anyone.")
                print("  Press Ctrl+C anytime to stop.\n")
                
                with open("LIVE_LINK.txt", "w", encoding="utf-8") as f:
                    f.write(f"LIVE URL: {live_url}\nGenerated at: {time.ctime()}\n")
                break
        
        # Keep processes running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping server and tunnel...")
        tunnel_process.terminate()
        server_process.terminate()
        print("Server stopped.")

if __name__ == "__main__":
    start_server_and_tunnel()
