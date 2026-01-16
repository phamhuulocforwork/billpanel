# Mewline Development Commands & Workflows

## Essential Commands

### Installation & Setup
```bash
# Install uv package manager
pip install uv
# OR on Arch Linux
sudo pacman -S uv

# Clone repository
git clone https://github.com/meowrch/mewline && cd mewline

# Install dependencies
uv sync

# Install development dependencies
uv sync --dev
```

### Configuration
```bash
# Generate default config (~/.config/mewline/config.json)
uv run generate_default_config

# Generate Hyprland keybindings (~/.config/hypr/mewline.conf)
uv run create_keybindings

# Edit configuration
micro ~/.config/mewline/config.json
# OR
nvim ~/.config/mewline/config.json
```

### Running the Application
```bash
# Normal mode
uv run mewline

# Debug mode (with full GTK/GLib debugging)
uv run mewline --debug

# Direct Python execution
uv run python run.py

# From installed package
mewline
```

### Development Tools

#### Code Quality
```bash
# Run ruff linter
uv run ruff check src/

# Auto-fix linting issues
uv run ruff check --fix src/

# Format code
uv run ruff format src/

# Check for dead code
uv run vulture src/mewline whitelist-vulture

# Pre-commit hooks
uv run pre-commit run --all-files

# Install pre-commit hooks
uv run pre-commit install
```

#### Testing
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=mewline

# Run specific test file
uv run pytest tests/test_config.py

# Verbose output
uv run pytest -v
```

#### Security
```bash
# Scan for secrets
uv run detect-secrets scan

# Check against baseline
uv run detect-secrets scan --baseline .secrets.baseline
```

### Building & Packaging

#### Arch Linux Package
```bash
# Build development package
makepkg -si

# Build from PKGBUILD.stable
makepkg -si -p PKGBUILD.stable

# Install from AUR
yay -S mewline-git
```

#### Using Makefile
```bash
# Show available targets
make help

# Install dependencies
make install

# Run application
make run

# Run tests
make test

# Clean build artifacts
make clean
```

## System Dependencies Installation

### Arch Linux / meowrch
```bash
# All required dependencies
sudo pacman -S dart-sass tesseract tesseract-data-eng tesseract-data-rus slurp grim cliphist

# AUR packages
yay -S gnome-bluetooth-3.0 gray-git fabric-cli-git
```

### Debian/Ubuntu (if applicable)
```bash
# Note: Some packages might not be available
sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-rus
# fabric and other tools would need manual installation
```

## Debugging Workflows

### Debug Mode Features
When running with `--debug`:
- Full GTK/GDK debug output
- Memory debugging enabled
- Signal handlers for crashes
- System information logging
- Python fault handler enabled

### View Logs
```bash
# Follow mewline logs in journal
journalctl -f -t mewline

# View all mewline logs
journalctl -t mewline

# View logs with priority
journalctl -t mewline -p info

# View last 100 lines
journalctl -t mewline -n 100

# View logs since boot
journalctl -t mewline -b
```

### GDB Debugging
```bash
# Run with GDB (use provided script)
./debug_with_gdb.sh

# Or manually
gdb --args python -m mewline
```

### Memory Profiling
```bash
# Run with memory debugging
MALLOC_CHECK_=3 MALLOC_PERTURB_=42 uv run mewline --debug

# Use valgrind (if needed)
valgrind --leak-check=full uv run python -m mewline
```

## Configuration Workflows

### Theme Development
```bash
# 1. Create new theme
cp ~/.config/mewline/themes/default.scss ~/.config/mewline/themes/my_theme.scss

# 2. Edit theme
nvim ~/.config/mewline/themes/my_theme.scss

# 3. Update config.json to use new theme
# Change: "theme": { "name": "my_theme" }

# 4. App will auto-reload on save (if running)
```

### Config Hot-Reloading
The app monitors these files and auto-reloads:
- `~/.config/mewline/config.json` - Config changes
- `~/.config/mewline/themes/*.scss` - Theme changes
- `src/mewline/styles/*.scss` - Style changes (dev mode)

### Widget Configuration
Edit `~/.config/mewline/config.json`:
```json
{
  "options": {
    "screen_corners": true,
    "osd_enabled": true
  },
  "statusbar": {
    "widgets": {
      "left": ["workspaces"],
      "center": ["datetime"],
      "right": ["tray", "bluetooth", "network", "battery", "power"]
    }
  },
  "dynamic_island": {
    "enabled": true,
    "default_widget": "compact"
  }
}
```

## Project Management

### Version Control
```bash
# Create feature branch
git checkout -b feature/my-new-widget

# Commit changes
git add .
git commit -m "feat: add new widget"

# Push to remote
git push origin feature/my-new-widget
```

### Release Workflow
```bash
# 1. Update version in pyproject.toml
# 2. Update CHANGELOG.md
# 3. Create git tag
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin v0.2.0

# 4. Build package
makepkg -si

# 5. Update AUR package (if maintainer)
```

## Troubleshooting Commands

### Check Dependencies
```bash
# Verify Python version
python --version  # Should be >= 3.11

# Check if Fabric is available
python -c "import fabric; print(fabric.__version__)"

# Check GTK version
python -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk; print(Gtk.get_major_version())"

# Verify Wayland
echo $WAYLAND_DISPLAY  # Should show wayland-0 or similar
```

### Common Issues
```bash
# Config not found - generate default
uv run generate_default_config

# Keybindings not working - regenerate
uv run create_keybindings

# Theme not loading - check SCSS syntax
dart-sass ~/.config/mewline/themes/my_theme.scss /tmp/test.css

# Permission issues - check directories
ls -la ~/.config/mewline
ls -la ~/.cache/mewline
```

### Reset Configuration
```bash
# Backup current config
cp ~/.config/mewline/config.json ~/.config/mewline/config.json.bak

# Remove config directory
rm -rf ~/.config/mewline

# Regenerate
uv run generate_default_config
uv run create_keybindings
```

## IDE Setup

### VSCode
Recommended extensions:
- Python
- Pylance
- Ruff
- SCSS Formatter

Settings in `.vscode/`:
- Python interpreter: use venv from uv
- Ruff as default formatter
- Auto-format on save

### PyCharm
- Set Python interpreter to `.venv/bin/python`
- Enable ruff external tool
- Configure pytest as test runner

## Performance Monitoring

```bash
# Check CPU usage
top -p $(pgrep mewline)

# Memory usage
ps aux | grep mewline

# Detailed system info
uv run mewline --debug 2>&1 | grep "SYSTEM DEBUG INFO" -A 20
```

## Useful File Paths

### Configuration
- `~/.config/mewline/config.json` - Main config
- `~/.config/mewline/themes/` - Theme files
- `~/.config/hypr/mewline.conf` - Hyprland keybindings

### Cache & Runtime
- `~/.cache/mewline/` - Cache directory
- `~/.cache/mewline/dist/` - Compiled CSS
- `/tmp/` - Temporary files (screenshots, etc.)

### Source Code
- `src/mewline/__main__.py` - Entry point
- `src/mewline/config.py` - Config handling
- `src/mewline/constants.py` - Constants & paths
- `src/mewline/widgets/` - Widget implementations
- `src/mewline/services/` - Background services
- `src/mewline/styles/` - SCSS styles
