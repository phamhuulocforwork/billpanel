#!/bin/bash
set -e

echo "🔧 Fixing remaining billpanel references..."

# Fix config.py - rename variable
sed -i 's/billpanel_kb_file_path/billpanel_kb_file_path/g' src/billpanel/config.py

# Fix loguru paths
sed -i 's|/var/log/billpanel|/var/log/billpanel|g' src/billpanel/utils/setup_loguru.py
sed -i 's|/tmp/billpanel|/tmp/billpanel|g' src/billpanel/utils/setup_loguru.py
sed -i 's|billpanel_app.log|billpanel_app.log|g' src/billpanel/utils/setup_loguru.py

# Fix VPN keyring service
sed -i 's/billpanel-vpn/billpanel-vpn/g' src/billpanel/services/vpn.py

# Fix help text
sed -i 's/configuration for billpanel/configuration for billpanel/g' src/billpanel/__main__.py

# Fix constants
sed -i 's/Styles for billpanel/Styles for billpanel/g' src/billpanel/constants.py
sed -i 's/invoke-action billpanel/invoke-action billpanel/g' src/billpanel/constants.py

# Fix any remaining config paths
sed -i 's|\.config/billpanel|.config/billpanel|g' src/billpanel/constants.py

echo "✅ Done!"
