#!/bin/bash
set -e

echo "[+] Stopping services and timers"

sudo systemctl stop study-monitor-screenshot.timer || true
sudo systemctl stop study-monitor-screenshot.service || true
sudo systemctl stop study-monitor-bot.service || true

echo "[+] Disabling services and timers"

sudo systemctl disable study-monitor-screenshot.timer || true
sudo systemctl disable study-monitor-screenshot.service || true
sudo systemctl disable study-monitor-bot.service || true

echo "[+] Removing systemd unit files"

sudo rm -f /etc/systemd/system/study-monitor-screenshot.timer
sudo rm -f /etc/systemd/system/study-monitor-screenshot.service
sudo rm -f /etc/systemd/system/study-monitor-bot.service

echo "[+] Reloading systemd"
sudo systemctl daemon-reload
sudo systemctl reset-failed

echo "[✓] Study Monitor services and timer removed"

echo
echo "ℹ️  Project files remain in /opt/study-monitor"
echo "ℹ️  To fully remove data, run:"
echo "    sudo rm -rf /opt/study-monitor"

