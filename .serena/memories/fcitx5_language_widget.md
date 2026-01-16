# Fcitx5 Language Widget

## Overview
Widget quản lý input method của Fcitx5, cho phép chuyển đổi giữa tiếng Anh và tiếng Việt.

## Features
- ✅ Hiển thị input method hiện tại (EN/VI)
- ✅ Toggle giữa English và Vietnamese bằng click chuột
- ✅ Auto-detect input method hiện tại
- ✅ Auto-update mỗi 2 giây
- ✅ Tooltip hiển thị tên đầy đủ của input method
- ✅ Hỗ trợ nhiều Vietnamese IMs: gonhanh, Bamboo, unikey

## Implementation Details

### File Location
`src/mewline/widgets/language.py`

### Supported Input Methods

#### Vietnamese (VI)
Priority order:
1. `gonhanh` - Go Nhanh (Vietnamese input)
2. `Bamboo` - Bamboo input method
3. `unikey` - Unikey
4. `bamboo` - Bamboo (lowercase)
5. `VnTelex` - Vietnamese Telex
6. `VnVni` - Vietnamese VNI

#### English (EN)
Priority order:
1. `keyboard-us` - US Keyboard
2. `keyboard-us-intl` - US International
3. `en` - English
4. `us` - US

### Usage

#### In Status Bar
Widget đã được tích hợp vào StatusBar:
```python
from mewline.widgets.language import LanguageWidget

# Trong StatusBar.__init__
LanguageWidget(),  # Hiển thị trong status bar
```

#### User Interaction
- **Left Click**: Toggle giữa English ↔ Vietnamese
- **Tooltip**: Hiển thị tên đầy đủ và hướng dẫn

### Fcitx5 Commands Used

```bash
# Check if Fcitx5 is running
fcitx5-remote --check

# Get current input method name
fcitx5-remote -n

# Switch to specific input method
fcitx5-remote -s <imname>
```

### Example Commands

```bash
# Switch to English
fcitx5-remote -s keyboard-us

# Switch to Vietnamese (gonhanh)
fcitx5-remote -s gonhanh

# Check current IM
fcitx5-remote -n
```

## Configuration

### Required Dependencies
```bash
# Fcitx5 base
sudo pacman -S fcitx5

# Vietnamese input method (choose one)
sudo pacman -S fcitx5-unikey  # Unikey
yay -S fcitx5-bamboo-git      # Bamboo
# Or use built-in keyboard-us for English only
```

### Fcitx5 Environment Setup
Add to `~/.profile` or `~/.pam_environment`:
```bash
export GTK_IM_MODULE=fcitx
export QT_IM_MODULE=fcitx
export XMODIFIERS=@im=fcitx
```

### Fcitx5 Config
Config location: `~/.config/fcitx5/`

To add Vietnamese IM to Fcitx5:
1. Open Fcitx5 Configuration: `fcitx5-configtool`
2. Go to "Input Method" tab
3. Click "+" to add Vietnamese input method
4. Select "Vietnamese - Bamboo" or "Vietnamese - Unikey"
5. Click "Apply"

## Widget Behavior

### Display Labels
- `EN` - English input method active
- `VI` - Vietnamese input method active
- `--` - Fcitx5 not running
- `??` - Cannot detect input method

### Auto-Update
Widget polls Fcitx5 every 2 seconds to update display, ensuring it stays in sync even if input method is changed externally (e.g., via keyboard shortcut).

### Toggle Logic
1. Get current input method
2. If Vietnamese → Switch to first available English IM
3. If English → Switch to first available Vietnamese IM
4. Update display after 200ms delay

## Troubleshooting

### Widget shows "--"
Fcitx5 is not running. Start it:
```bash
fcitx5 &
```

Or add to Hyprland autostart:
```bash
# ~/.config/hypr/hyprland.conf
exec-once = fcitx5 -d
```

### Widget shows "??"
Cannot detect current input method. Check:
```bash
fcitx5-remote -n
```

### Vietnamese IM not found
Install Vietnamese input method:
```bash
sudo pacman -S fcitx5-unikey
# or
yay -S fcitx5-bamboo-git
```

Then add it in `fcitx5-configtool`.

### Toggle not working
1. Check Fcitx5 is running: `fcitx5-remote --check`
2. Check available IMs: `fcitx5-remote -n`
3. Try manual switch: `fcitx5-remote -s gonhanh`
4. Check logs: `journalctl -t mewline | grep -i language`

## Testing

### Test Widget Functionality
```python
# Test in Python
uv run python -c "
from mewline.widgets.language import LanguageWidget
from gi.repository import Gtk

# Create widget (requires GTK main loop)
widget = LanguageWidget()
print('Widget created successfully')
"
```

### Test Fcitx5 Commands
```bash
# Test toggle manually
current=$(fcitx5-remote -n)
echo "Current: $current"

fcitx5-remote -s keyboard-us
echo "Switched to: $(fcitx5-remote -n)"

fcitx5-remote -s gonhanh
echo "Switched to: $(fcitx5-remote -n)"
```

## Future Enhancements

### Potential Improvements
- [ ] Add more Vietnamese IMs (VnVNI, VnTelex variations)
- [ ] Add config option to customize display labels
- [ ] Add right-click menu to select specific IM
- [ ] Add keyboard shortcut support
- [ ] Show IM icon instead of text label
- [ ] Add animation on toggle
- [ ] Cache available IMs for better performance

### Config Structure (Proposed)
```json
{
  "modules": {
    "language": {
      "enabled": true,
      "labels": {
        "en": "🇬🇧",
        "vi": "🇻🇳"
      },
      "poll_interval": 2,
      "show_tooltip": true
    }
  }
}
```
