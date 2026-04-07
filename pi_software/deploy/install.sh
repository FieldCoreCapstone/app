#!/bin/bash
# Install FieldCore systemd services on the Raspberry Pi.
# Run as: sudo bash deploy/install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== FieldCore Service Installer ==="

# Install unclutter for cursor hiding (kiosk mode)
if ! command -v unclutter &> /dev/null; then
    echo "Installing unclutter..."
    apt-get install -y unclutter
fi

# Make kiosk script executable
chmod +x "$SCRIPT_DIR/kiosk.sh"

# Copy service files
echo "Copying service files to /etc/systemd/system/ ..."
cp "$SCRIPT_DIR/fieldcore-web.service" /etc/systemd/system/
cp "$SCRIPT_DIR/fieldcore-lora.service" /etc/systemd/system/
cp "$SCRIPT_DIR/fieldcore-mock.service" /etc/systemd/system/
cp "$SCRIPT_DIR/fieldcore-kiosk.service" /etc/systemd/system/

# Reload and enable
echo "Reloading systemd..."
systemctl daemon-reload

echo "Enabling services..."
systemctl enable fieldcore-web
systemctl enable fieldcore-lora
systemctl enable fieldcore-mock
systemctl enable fieldcore-kiosk

echo ""
echo "=== Done ==="
echo "Services enabled. They will start on next boot."
echo ""
echo "To start now:  sudo systemctl start fieldcore-web fieldcore-lora fieldcore-mock fieldcore-kiosk"
echo "To check:      systemctl status fieldcore-*"
echo "To view logs:  journalctl -u fieldcore-web -f"
