# Fork Changes: mewline → billpanel

## What Changed

This is a fork of [mewline](https://github.com/meowrch/mewline) with the following changes:

### Project Renaming
- **Project name**: `mewline` → `billpanel`
- **Package name**: `mewline` → `billpanel`
- **Command**: `mewline` → `billpanel`
- **AUR packages**: `mewline-git` / `mewline` → `billpanel-git` / `billpanel`

### Path Changes
- Config: `~/.config/mewline` → `~/.config/billpanel`
- Cache: `~/.cache/mewline` → `~/.cache/billpanel`
- Logs: `/var/log/mewline` → `/var/log/billpanel`
- Hyprland config: `~/.config/hypr/mewline.conf` → `~/.config/hypr/billpanel.conf`

### Service Changes
- VPN keyring: `mewline-vpn` → `billpanel-vpn`
- Fabric action: `invoke-action mewline` → `invoke-action billpanel`

### Repository
- **Original**: https://github.com/meowrch/mewline
- **Fork**: https://github.com/phamhuulocforwork/billpanel

## Migration Guide

If you're migrating from mewline:

```bash
# Backup your config
cp -r ~/.config/mewline ~/.config/mewline.backup

# Rename config directory
mv ~/.config/mewline ~/.config/billpanel

# Rename cache directory
mv ~/.cache/mewline ~/.cache/billpanel

# Update Hyprland config
sed -i 's/mewline/billpanel/g' ~/.config/hypr/hyprland.conf

# Uninstall old package
yay -R mewline-git  # or mewline

# Install new package
yay -S billpanel-git  # or billpanel
```

## License

This fork maintains the MIT License from the original project.
See [LICENSE](./LICENSE) for details.
