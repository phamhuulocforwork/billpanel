<div align="center">
	<h1> 🎯 Billpanel </h1>
	<a href="https://github.com/phamhuulocforwork/billpanel/issues">
		<img src="https://img.shields.io/github/issues/phamhuulocforwork/billpanel?color=ffb29b&labelColor=1C2325&style=for-the-badge">
	</a>
	<a href="https://github.com/phamhuulocforwork/billpanel/stargazers">
		<img src="https://img.shields.io/github/stars/phamhuulocforwork/billpanel?color=fab387&labelColor=1C2325&style=for-the-badge">
	</a>
	<a href="./LICENSE">
		<img src="https://img.shields.io/github/license/phamhuulocforwork/billpanel?color=FCA2AA&labelColor=1C2325&style=for-the-badge">
	</a>
</div>
<br>

> **Note:** This is a fork of [mewline](https://github.com/meowrch/mewline) by meowrch.  
> Original project licensed under MIT License.

## 🌟 About

An elegant, extensible status bar written in Python using the [Fabric](https://github.com/Fabric-Development/fabric) framework. Combines minimalist design with powerful functionality.

## 🚀 Installation

### From AUR (Arch Linux)

```bash
# Development version
yay -S billpanel-git

# Stable version
yay -S billpanel
```

### From Source

```bash
# Install dependencies
sudo pacman -S python uv git

# Clone repository
git clone https://github.com/phamhuulocforwork/billpanel
cd billpanel

# Install dependencies
uv sync

# Run
uv run python run.py
```

## ⚙️ Configuration

Configuration file: `~/.config/billpanel/config.json`

Generate default config:
```bash
uv run generate_default_config
```

Generate Hyprland keybindings:
```bash
uv run create_keybindings
```

## 🔧 Development

```bash
# Run in debug mode
uv run billpanel --debug

# Run linter
uv run ruff check src/

# Run tests
uv run pytest
```

## 📄 License

MIT License - See [LICENSE](./LICENSE) for details.

Original project: [mewline](https://github.com/meowrch/mewline) by meowrch

## 🙏 Credits

- Original project: [mewline](https://github.com/meowrch/mewline) by [@meowrch](https://github.com/meowrch)
- Framework: [Fabric](https://github.com/Fabric-Development/fabric)
