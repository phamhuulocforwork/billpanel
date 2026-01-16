# Mewline Architecture & Design Patterns

## Application Architecture

### Main Application Flow
1. **Initialization** (`__main__.py:main()`)
   - Setup loguru logging (journal, file, console)
   - Configure debug mode if enabled
   - Enable GLib/GTK debugging in debug mode
   - Start output capture to systemd journal

2. **Widget Creation**
   - Create optional screen corners
   - Create OSD container if enabled
   - Create StatusBar and link OSD
   - Create DynamicIsland
   - Initialize Fabric Application

3. **Theming System**
   - Copy theme SCSS to working directory
   - Monitor style files for changes
   - Monitor config.json for theme changes
   - Auto-compile SCSS → CSS via dart-sass
   - Hot-reload on file changes

4. **Application Run**
   - Set process title to "mewline"
   - Create cache directories
   - Run GTK main loop

## Key Design Patterns

### 1. Modular Widget System
- Each widget is a self-contained component
- Widgets can be enabled/disabled via config
- Clear separation: Status Bar vs Dynamic Island
- Widget communication via shared services

### 2. Service Layer Pattern
Services provide centralized state management:
- `BatteryService` - Battery monitoring
- `BrightnessService` - Brightness control
- `MPRISService` - Media player integration
- `NotificationService` - Notification handling
- `CacheNotificationService` - Notification persistence

### 3. Configuration Management
- Pydantic models for type safety
- JSON configuration file
- Hot-reloading support
- Default config generation
- Validation on load

### 4. Theming Architecture
```
Theme SCSS → dart-sass → CSS → GTK Style Context
    ↓
File Monitor → Auto-recompile on change
    ↓
Config Monitor → Theme swap support
```

### 5. Event-Driven Architecture
- File monitoring (config, styles)
- D-Bus signal subscriptions
- GTK signal handlers
- Service observers/callbacks

## Directory Organization

### Widget Structure
```
widgets/
├── __init__.py              # StatusBar main widget
├── battery.py               # Battery widget
├── bluetooth.py             # Bluetooth widget
├── combined_controls.py     # Volume + Brightness
├── datetime.py              # Date/Time widget
├── language.py              # Keyboard layout
├── network_status.py        # Network indicator
├── ocr.py                   # OCR functionality
├── osd.py                   # On-screen display
├── power.py                 # Power button
├── screen_corners.py        # Interactive corners
├── system_tray.py           # System tray
├── workspaces.py            # Workspace switcher
└── dynamic_island/          # Dynamic Island widgets
    ├── __init__.py          # DynamicIsland main
    ├── base.py              # Base widget class
    ├── compact.py           # Compact mode
    ├── notifications.py     # Notification center
    ├── power.py             # Power menu
    ├── date_notification.py # Calendar
    ├── bluetooth.py         # BT manager
    ├── app_launcher.py      # App launcher
    ├── wallpapers.py        # Wallpaper picker
    ├── emoji.py             # Emoji picker
    ├── clipboard.py         # Clipboard manager
    ├── network.py           # Network manager
    └── workspaces.py        # Window manager
```

### Service Structure
```
services/
├── __init__.py
├── battery.py               # Battery state
├── brightness.py            # Brightness control
├── cache_notification.py    # Notification cache
├── mpris.py                 # Media players
└── notifications.py         # Notification daemon
```

## Configuration System

### Config Loading Flow
1. Check if config file exists
2. Load and parse JSON
3. Validate with Pydantic models
4. Merge with defaults
5. Return Config object

### Config Structure (Pydantic)
```python
Config
├── options: Options          # Global settings
├── theme: Theme              # Theme configuration
├── statusbar: StatusBar      # Status bar config
├── dynamic_island: DI        # Dynamic island config
└── keybindings: dict         # Keybinding mappings
```

## Hyprland Integration

### IPC Communication
- Uses Hyprland socket for workspace info
- Monitors compositor events
- Sends window management commands
- Keybinding integration

### Keybinding System
1. Define bindings in constants.py
2. Generate Hyprland config file
3. Write to ~/.config/hypr/mewline.conf
4. Auto-source in main hyprland.conf
5. IPC commands trigger widget actions

## Logging & Debugging

### Loguru Configuration
Three log destinations:
1. **Systemd Journal** (INFO level)
   - Production logging
   - Searchable with journalctl

2. **File Log** (DEBUG level)
   - Detailed debugging
   - Persistent logs

3. **Console** (INFO level)
   - Development feedback
   - Colored output

### Debug Mode Features
When `--debug` flag is used:
- G_DEBUG: fatal-warnings, gc-friendly
- G_SLICE: debug-blocks, always-malloc
- GTK_DEBUG: all categories
- GDK_DEBUG: all categories
- GOBJECT_DEBUG: objects, signals
- Memory debugging (MALLOC_CHECK_=3)
- Python fault handler
- Signal handlers for crashes
- System info logging

### Output Capture
- Redirects stdout/stderr to journal
- Captures GTK warnings/errors
- Preserves log levels
- Maintains structured logging

## CSS/Styling System

### SCSS Compilation
```
themes/my_theme.scss
    ↓ copy to
~/.config/mewline/themes/my_theme.scss
    ↓ dart-sass compile
~/.cache/mewline/dist/style.css
    ↓ apply to
GTK Style Context
```

### Style Monitoring
- Watches all files in styles folder
- Auto-recompiles on any change
- Applies new CSS without restart
- Theme hot-swapping support

## Error Handling

### Error Types (errors/)
Custom error classes for:
- Configuration errors
- Service errors
- Widget errors
- IPC communication errors

### Error Propagation
1. Service errors → logged + recovered
2. Widget errors → isolated, don't crash app
3. Config errors → use defaults + warn
4. Critical errors → clean shutdown

## Performance Optimizations

### Resource Management
1. **Lazy Loading**: Services initialized on-demand
2. **Caching**: 
   - Notification cache
   - Icon cache
   - Config cache
3. **Efficient Updates**:
   - Only redraw changed widgets
   - Debounced file monitoring
   - Throttled D-Bus signals

### Memory Efficiency
- Proper cleanup on widget destroy
- D-Bus connection pooling
- Image optimization
- GTK object lifecycle management

## Extension Points

### Adding New Widgets
1. Create widget file in `widgets/` or `widgets/dynamic_island/`
2. Inherit from appropriate base class
3. Implement required methods
4. Add to config schema
5. Register in main widget initialization

### Adding New Services
1. Create service file in `services/`
2. Implement service interface
3. Add singleton pattern if needed
4. Connect to D-Bus if required
5. Export in `services/__init__.py`

### Adding New Themes
1. Create SCSS file in theme folder
2. Follow existing variable structure
3. Test hot-reload functionality
4. Document theme variables

## Testing Strategy
Located in `tests/`:
- Unit tests for services
- Widget integration tests
- Config validation tests
- Mock D-Bus for testing
- pytest framework
