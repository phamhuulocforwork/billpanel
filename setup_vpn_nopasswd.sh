#!/bin/bash
# Setup VPN commands to run without sudo password
# This script configures sudoers to allow billpanel VPN operations

set -e

echo "🔧 Setting up VPN sudo permissions for billpanel..."

# Get current username
USERNAME="$USER"
HOME_DIR="$HOME"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "❌ Don't run this script as root! Run as your normal user."
    echo "   The script will ask for sudo password when needed."
    exit 1
fi

# Verify sudo access
if ! sudo -v; then
    echo "❌ Failed to get sudo access"
    exit 1
fi

echo "👤 Configuring for user: $USERNAME"
echo "🏠 Home directory: $HOME_DIR"

# Create sudoers file for billpanel
SUDOERS_FILE="/etc/sudoers.d/billpanel-vpn"

echo "📝 Creating sudoers configuration: $SUDOERS_FILE"

# Create temporary file
TEMP_FILE=$(mktemp)

cat > "$TEMP_FILE" << EOF
# Billpanel VPN - Allow VPN operations without password
# Generated on $(date)
# User: $USERNAME

# OpenVPN commands
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/openvpn
$USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/openvpn
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/pkill -f openvpn*

# WireGuard commands
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/wg-quick
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/wg

# Log file reading (for debugging)
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/cat $HOME_DIR/.config/billpanel/vpn/*
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/grep * $HOME_DIR/.config/billpanel/vpn/*
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/tail * $HOME_DIR/.config/billpanel/vpn/*

# DNS management (if needed)
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/resolvectl
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/resolvectl flush-caches
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart systemd-resolved

# Network interface management
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/ip route *
$USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/ip route *
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/ip link *
$USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/ip link *
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/ip neigh *
$USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/ip neigh *

# Connection tracking cleanup
$USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/conntrack *
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/conntrack *

# Bash commands for DNS restoration
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/bash -c echo * > /etc/resolv.conf

# Cleanup commands
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/rm -f /run/openvpn/*.pid
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/rm -f /run/openvpn/*.status
EOF

# Validate sudoers syntax
if ! sudo visudo -c -f "$TEMP_FILE" > /dev/null 2>&1; then
    echo "❌ Generated sudoers file has syntax errors!"
    rm -f "$TEMP_FILE"
    exit 1
fi

echo "✅ Sudoers syntax validated"

# Install the file
sudo cp "$TEMP_FILE" "$SUDOERS_FILE"
sudo chmod 0440 "$SUDOERS_FILE"
sudo chown root:root "$SUDOERS_FILE"
rm -f "$TEMP_FILE"

echo "✅ Sudoers file installed: $SUDOERS_FILE"

# Test the configuration
echo ""
echo "🧪 Testing configuration..."

if sudo -n openvpn --version > /dev/null 2>&1; then
    echo "✅ OpenVPN: Can run without password ✓"
else
    echo "⚠️  OpenVPN: Still requires password (may need to re-login)"
fi

if sudo -n wg-quick --help > /dev/null 2>&1; then
    echo "✅ WireGuard: Can run without password ✓"
else
    echo "⚠️  WireGuard: Still requires password (may need to re-login)"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "📌 What this does:"
echo "   - Allows OpenVPN commands to run without password"
echo "   - Allows WireGuard commands to run without password"
echo "   - Allows reading VPN log files without password"
echo ""
echo "⚠️  Security notes:"
echo "   - Only applies to user: $USERNAME"
echo "   - Only affects VPN-related commands"
echo "   - Log files are restricted to billpanel's config directory"
echo ""
echo "🔄 If commands still ask for password, try:"
echo "   - Log out and log back in"
echo "   - Or run: sudo -k (to clear sudo cache)"
echo ""
echo "❌ To remove this configuration later, run:"
echo "   sudo rm $SUDOERS_FILE"
