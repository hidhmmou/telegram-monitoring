#!/bin/bash
set -e

USER_NAME=$(logname)
HOME_DIR=$(eval echo "~$USER_NAME")

echo "[+] Installing dependencies"
sudo apt update --fix-missing || true
sudo apt install -y python3 python3-pip scrot

pip3 install --break-system-packages python-telegram-bot==20.4 python-dotenv

echo "[+] Preparing directories"
sudo mkdir -p /opt/study-monitor
sudo chown $USER_NAME:$USER_NAME /opt/study-monitor

sudo chmod +x /opt/study-monitor/*.py

echo "[+] Creating systemd services"

sudo tee /etc/systemd/system/study-monitor-screenshot.service > /dev/null <<EOF
[Unit]
Description=Study Monitor Screenshot
After=graphical.target

[Service]
Type=oneshot
User=$USER_NAME
Environment=DISPLAY=:0
Environment=XAUTHORITY=$HOME_DIR/.Xauthority
ExecStart=/usr/bin/python3 /opt/study-monitor/screenshot_sender.py
EOF

sudo tee /etc/systemd/system/study-monitor-screenshot.timer > /dev/null <<EOF
[Unit]
Description=Screenshot every 5 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Persistent=true

[Install]
WantedBy=timers.target
EOF

sudo tee /etc/systemd/system/study-monitor-bot.service > /dev/null <<EOF
[Unit]
Description=Study Monitor Telegram Bot
After=network.target

[Service]
User=$USER_NAME
ExecStart=/usr/bin/python3 /opt/study-monitor/bot_controller.py
Restart=always
EOF

sudo systemctl daemon-reload
sudo systemctl enable study-monitor-screenshot.timer
sudo systemctl enable study-monitor-bot.service
sudo systemctl start study-monitor-screenshot.timer
sudo systemctl start study-monitor-bot.service

echo "[✓] Installed successfully"

