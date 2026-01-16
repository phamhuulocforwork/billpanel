# Mewline Project Overview

## Description
**Mewline** is an elegant, extensible status bar for the [meowrch](https://github.com/meowrch/meowrch) distribution, written in Python using the [Fabric](https://github.com/Fabric-Development/fabric) framework. It combines a minimalist design with powerful functionality.

## Key Technologies
- **Language**: Python (>=3.11)
- **Framework**: Fabric (GTK-based GUI framework)
- **Package Manager**: `uv` (for dependency management)
- **UI Toolkit**: GTK 3.0 with Wayland support
- **Build System**: pyproject.toml with uv

## Project Structure
```
mewline/
├── src/mewline/           # Main source code
│   ├── widgets/           # UI widgets
│   │   └── dynamic_island/  # Dynamic Island widgets
│   ├── services/          # Background services
│   ├── utils/             # Utility functions
│   ├── styles/            # CSS/SCSS styling
│   ├── shared/            # Shared components
│   ├── errors/            # Error handling
│   ├── __main__.py        # Entry point
│   ├── config.py          # Configuration management
│   └── constants.py       # Application constants
├── tests/                 # Test files
├── docs/                  # Documentation
├── assets/                # Images and assets
├── pyproject.toml         # Project configuration
├── run.py                 # Run script
└── Makefile              # Build automation
```

## Main Features
1. **Modular architecture** - Extensible widget system
2. **Customization** - JSON-based configuration
3. **Theme support** - SCSS themes with hot-reloading
4. **Full meowrch integration** - Native Hyprland integration
5. **Animated transitions** - Smooth UI effects
6. **Low resource usage** - Optimized performance
7. **Keyboard control** - Full keybinding support

## Widget Categories

### Status Bar Widgets
- `tray` - System tray
- `workspaces` - Workspace management (Hyprland)
- `datetime` - Date and time display
- `brightness` - Screen brightness control
- `volume` - Audio volume control
- `battery` - Battery charge information
- `power` - Power menu button
- `ocr` - Text recognition from screenshots

### Dynamic Island Widgets
- `compact` - Active window and music player
- `notifications` - Notification center
- `power_menu` - Power management (Super+Alt+P)
- `date_notification` - Calendar and history (Super+Alt+D)
- `bluetooth` - Bluetooth manager (Super+Alt+B)
- `app_launcher` - Application launcher (Super+Alt+A)
- `wallpapers` - Wallpaper picker (Super+Alt+W)
- `emoji` - Emoji picker (Super+Alt+.)
- `clipboard` - Clipboard manager (Super+Alt+V)
- `network` - Wi-Fi/Ethernet manager (Super+Alt+N)
- `workspaces` - Window/workspace manager (Super+Alt+Tab)

### Other Components
- `osd` - On-screen display for volume/brightness
- `screen_corners` - Interactive screen corners

## Key Services
Located in `src/mewline/services/`:
- `battery.py` - Battery monitoring
- `brightness.py` - Brightness control
- `cache_notification.py` - Notification caching
- `mpris.py` - Media player control
- `notifications.py` - Notification management

## Entry Points
Defined in pyproject.toml:
- `mewline` - Main application entry
- `generate_default_config` - Config generation
- `create_keybindings` - Hyprland keybinding setup

## Configuration System
- Config location: `~/.config/mewline/config.json`
- Themes location: `~/.config/mewline/themes/`
- Hot-reloading supported for both config and themes
- SCSS → CSS compilation via dart-sass
- Hyprland keybindings auto-generated

## Dependencies
### Required System Packages
- `dart-sass` - CSS preprocessing
- `tesseract` + language data - OCR functionality
- `slurp`, `grim` - Screenshot tools
- `cliphist` - Clipboard history
- `gnome-bluetooth-3.0` - Bluetooth support
- `gray-git` - Wallpaper tool
- `fabric-cli-git` - Fabric framework CLI

### Python Dependencies
Main libraries:
- `fabric` - UI framework (from git)
- `loguru` - Advanced logging
- `pydantic` - Configuration validation
- `pillow` - Image processing
- `pytesseract` - OCR wrapper
- `psutil` - System monitoring
- `dbus-python` - D-Bus integration
- `emoji` - Emoji support
- `setproctitle` - Process naming

## Development Setup
```bash
# Install uv package manager
pip install uv  # or: sudo pacman -S uv

# Install dependencies
uv sync

# Generate config
uv run generate_default_config

# Generate Hyprland keybindings
uv run create_keybindings

# Run application
uv run mewline

# Debug mode
uv run mewline --debug
```

## Build System
- **PKGBUILD** - Arch Linux package files (stable and git versions)
- **Makefile** - Build automation
- **pre-commit** - Code quality checks
- **ruff** - Linting and formatting
- **vulture** - Dead code detection
- **detect-secrets** - Security scanning

## Code Quality Tools
Configured in pyproject.toml:
- **Ruff**: Linting (Pyflakes, pycodestyle, isort, pydocstyle, etc.)
- **Target Python**: 3.11+
- **Line length**: 88 characters
- **Style**: Google docstring convention

## Debugging Features
The `--debug` flag enables:
- GLib/GTK fatal warnings and criticals
- Memory debugging (MALLOC_CHECK_, MALLOC_PERTURB_)
- Full GTK/GDK debug output
- Python fault handler
- Signal handlers for SIGSEGV/SIGABRT
- System info logging
- Output capture to systemd journal

## Special Acknowledgments
Inspired by and borrows ideas from:
- **HyDePanel** - Modular architecture, some widgets/styles
- **Ax-Shell** - System event handling, IPC mechanisms
