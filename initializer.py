import os
import sys
import json
import subprocess
import time
from pathlib import Path

CREDS_FILE = Path.home() / ".net-deepagent" / "creds.json"
PREFS_FILE = Path.home() / ".net-deepagent" / "preferences.json"

def ensure_config_dir():
    CREDS_FILE.parent.mkdir(parents=True, exist_ok=True)

def gather_features():
    print("--- 🚀 WorkerXY Initializer ---")
    features = {
        "mcp": True,
        "headless": False,
        "discord": False,
        "webui": False
    }
    
    print("\nSelect features to activate (y/N for optional features):")
    print("[*] MCP Server (Required) - Activated")
    
    ans = input("[?] Enable Headless Worker (requires RabbitMQ)? [y/N]: ").strip().lower()
    if ans == 'y': features["headless"] = True
    
    ans = input("[?] Enable Discord Bot bridge (requires RabbitMQ)? [y/N]: ").strip().lower()
    if ans == 'y': features["discord"] = True
    
    ans = input("[?] Enable Streamlit Web UI? [y/N]: ").strip().lower()
    if ans == 'y': features["webui"] = True
    
    return features

def gather_credentials():
    print("\n--- 🔐 Credentials Configuration ---")
    ensure_config_dir()
    
    creds = {}
    if CREDS_FILE.exists():
        try:
            with open(CREDS_FILE, 'r') as f:
                creds = json.load(f)
        except json.JSONDecodeError:
            print("[!] Invalid JSON in creds.json, starting fresh.")
            
    keys_needed = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
    for key in keys_needed:
        if key not in creds or not creds[key].strip():
            val = input(f"[?] Enter {key} (leave blank to skip): ").strip()
            if val:
                creds[key] = val
        else:
            print(f"[*] {key} is already configured.")
            
    with open(CREDS_FILE, 'w') as f:
        json.dump(creds, f, indent=4)
        print(f"[*] Credentials saved to {CREDS_FILE}")

def set_preferences():
    print("\n--- ⚙️ User Preferences ---")
    ensure_config_dir()
    
    prefs = {}
    if PREFS_FILE.exists():
        try:
            with open(PREFS_FILE, 'r') as f:
                prefs = json.load(f)
        except json.JSONDecodeError:
            pass
            
    print("Default Models:")
    print(" 1) gpt-5.1")
    print(" 2) claude-sonnet-4-5-20250929")
    print(" 3) gpt-5-mini")
    
    choice = input("[?] Select default model [1-3, or press Enter to keep current]: ").strip()
    if choice == '1':
        prefs["default_model"] = "gpt-5.1"
    elif choice == '2':
        prefs["default_model"] = "claude-sonnet-4-5-20250929"
    elif choice == '3':
        prefs["default_model"] = "gpt-5-mini"
        
    ch_choice = input("[?] Default Discord Channel ID (leave blank to skip/keep current): ").strip()
    if ch_choice:
        prefs["discord_channel"] = ch_choice
        
    with open(PREFS_FILE, 'w') as f:
        json.dump(prefs, f, indent=4)
        print(f"[*] Preferences saved to {PREFS_FILE}")

def start_services(features):
    print("\n--- 🛠 Starting Background Services ---")
    
    processes = []
    
    if features.get("mcp"):
        print("[*] Starting MCP Server in background...")
        proc = subprocess.Popen(["workerxy", "mcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        processes.append(("MCP Server", proc))
        
    if features.get("headless") or features.get("discord"):
        print("[*] Ensuring RabbitMQ is running...")
        print("    (Run `sudo systemctl start rabbitmq-server` manually if not already running)")
        
    if features.get("headless"):
        print("[*] Starting Headless Worker...")
        proc = subprocess.Popen(["workerxy", "headless"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        processes.append(("Headless Worker", proc))
        
    if features.get("discord"):
        print("[*] Starting Discord Bridge...")
        proc = subprocess.Popen(["workerxy", "discord"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        processes.append(("Discord Bridge", proc))
        
    if features.get("webui"):
        print("[*] Starting Web UI Dashboard...")
        proc = subprocess.Popen(["workerxy", "ui"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        processes.append(("Web UI", proc))
        
    time.sleep(2)
    print("\n--- ✅ Initialization Complete ---")
    for name, p in processes:
        if p.poll() is None:
            print(f" [OK] {name} is running (PID {p.pid})")
        else:
            print(f" [FAIL] {name} failed to start or exited immediately.")

def main():
    try:
        features = gather_features()
        gather_credentials()
        set_preferences()
        
        start = input("\n[?] Do you want to start the selected background services now? [Y/n]: ").strip().lower()
        if start != 'n':
            start_services(features)
        else:
            print("[*] Service startup skipped. You can run them manually via `workerxy <component>`.")
            
    except KeyboardInterrupt:
        print("\n[!] Initialization aborted by user.")
        sys.exit(1)

if __name__ == "__main__":
    main()
