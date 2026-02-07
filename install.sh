#!/bin/bash
set -e

# Detect the desktop user (who is logged into the X session)
DESKTOP_USER=$(who | grep '(:0)' | awk '{print $1}' | head -n1)
if [ -z "$DESKTOP_USER" ]; then
    echo "Error: No user found logged into X display :0"
    echo "Please make sure someone is logged into the desktop session"
    exit 1
fi

USER_NAME=$DESKTOP_USER
HOME_DIR=$(eval echo "~$USER_NAME")

echo "[+] Detected desktop user: $USER_NAME"
echo "[+] Installing dependencies"
sudo apt update --fix-missing || true
sudo apt install -y python3 python3-pip scrot

pip3 install --break-system-packages python-telegram-bot==20.4 python-dotenv

echo "[+] Preparing directories"
sudo mkdir -p /opt/study-monitor
sudo chown -R $USER_NAME:$USER_NAME /opt/study-monitor
sudo chmod 755 /opt/study-monitor

sudo chmod +x /opt/study-monitor/*.py

# Initialize state.json with correct ownership
sudo touch /opt/study-monitor/state.json
sudo chown $USER_NAME:$USER_NAME /opt/study-monitor/state.json
sudo chmod 664 /opt/study-monitor/state.json

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
StandardOutput=journal
StandardError=journal
EOF

sudo tee /etc/systemd/system/study-monitor-screenshot.timer > /dev/null <<EOF
[Unit]
Description=Screenshot every 5 minutes

[Timer]
OnBootSec=2min
OnActiveSec=5min
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
StandardOutput=journal
StandardError=journal
EOF

sudo systemctl daemon-reload
sudo systemctl enable study-monitor-screenshot.timer
sudo systemctl enable study-monitor-bot.service
sudo systemctl start study-monitor-screenshot.timer
sudo systemctl start study-monitor-bot.service

echo "[✓] Installed successfully"

