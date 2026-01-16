#!/bin/bash
set -e

echo "🔧 Fixing remaining mewline references..."

# Fix config.py - rename variable
sed -i 's/mewline_kb_file_path/billpanel_kb_file_path/g' src/billpanel/config.py

# Fix loguru paths
sed -i 's|/var/log/mewline|/var/log/billpanel|g' src/billpanel/utils/setup_loguru.py
sed -i 's|/tmp/mewline|/tmp/billpanel|g' src/billpanel/utils/setup_loguru.py
sed -i 's|mewline_app.log|billpanel_app.log|g' src/billpanel/utils/setup_loguru.py

# Fix VPN keyring service
sed -i 's/mewline-vpn/billpanel-vpn/g' src/billpanel/services/vpn.py

# Fix help text
sed -i 's/configuration for mewline/configuration for billpanel/g' src/billpanel/__main__.py

# Fix constants
sed -i 's/Styles for mewline/Styles for billpanel/g' src/billpanel/constants.py
sed -i 's/invoke-action mewline/invoke-action billpanel/g' src/billpanel/constants.py

# Fix any remaining config paths
sed -i 's|\.config/mewline|.config/billpanel|g' src/billpanel/constants.py

echo "✅ Done!"
