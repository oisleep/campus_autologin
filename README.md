给女朋友准备的CUMT校园网强制下线后自动登录脚本
# Campus AutoLogin (macOS)

Auto-login helper for university campus networks with captive portal (锐捷/深澜/Drcom-like).  
Works in the background via `launchd`, so your Mac stays online for remote control (AnyDesk, SSH, etc.) even when locked.

---

## Features
- Detects captive portal (redirect check).
- Extracts form action + hidden fields (CSRF tokens).
- Reads credentials securely from macOS Keychain.
- Retries with backoff, logs to `/tmp/campus_autologin.log`.
- Runs via `launchd` every 60s and on network changes.

---

## Installation

### 1. Clone repo
```bash
git clone https://github.com/oisleep/campus_autologin.git
cd campus_autologin
