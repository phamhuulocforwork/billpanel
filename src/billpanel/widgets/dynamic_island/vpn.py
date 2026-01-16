"""VPN Widget for Dynamic Island.

Provides UI for managing VPN connections including:
- Profile list with connection status
- Import/upload VPN profiles
- Credential management
- DNS and split tunneling settings
"""

import subprocess
from pathlib import Path
from threading import Lock

from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.entry import Entry
from fabric.widgets.label import Label
from fabric.widgets.scrolledwindow import ScrolledWindow
from gi.repository import GLib
from gi.repository import Gtk
from loguru import logger

from billpanel.services.vpn import DNSMode
from billpanel.services.vpn import get_vpn_service
from billpanel.services.vpn import VPNProfile
from billpanel.services.vpn import VPNStatus
from billpanel.services.vpn import VPNType
from billpanel.utils.widget_utils import setup_cursor_hover
from billpanel.utils.widget_utils import text_icon
from billpanel.widgets.dynamic_island.base import BaseDiWidget


class VPNProfileSlot(CenterBox):
    """Widget slot for a VPN profile."""

    STATUS_ICONS = {
        VPNStatus.DISCONNECTED: ("󰖂", "disconnected"),
        VPNStatus.CONNECTING: ("󰖩", "connecting"),
        VPNStatus.CONNECTED: ("󰖂", "connected"),
        VPNStatus.DISCONNECTING: ("󰖩", "disconnecting"),
        VPNStatus.ERROR: ("󰖂", "error"),
        VPNStatus.RECONNECTING: ("󰖩", "reconnecting"),
    }

    TYPE_ICONS = {
        VPNType.OPENVPN: "󰒃",
        VPNType.WIREGUARD: "󰖂",
    }

    def __init__(self, profile: VPNProfile, parent: "VPNConnections", **kwargs):
        super().__init__(
            orientation="horizontal",
            spacing=8,
            name="vpn-slot",
            **kwargs,
        )
        self.profile = profile
        self.parent = parent
        self.vpn_service = get_vpn_service()
        self._expanded = False
        self._credentials_shown = False

        # Check if this profile is currently connected
        current = self.vpn_service.current_profile
        self._is_connected = (
            current is not None
            and current.name == profile.name
            and self.vpn_service.status == VPNStatus.CONNECTED
        )

        # Main row elements
        self.type_icon = text_icon(
            self.TYPE_ICONS.get(profile.vpn_type, "󰖂"), size="16px"
        )
        self.name_label = Label(label=profile.name, h_expand=True)
        self.status_icon = text_icon(
            self._get_status_icon(), size="16px", name="vpn-status-icon"
        )

        # Connect/disconnect button
        self.connect_button = self._create_connect_button()

        # Settings button
        self.settings_button = Button(
            label="󰒓",
            name="vpn-settings-btn",
            tooltip_text="Settings",
        )
        setup_cursor_hover(self.settings_button)
        self.settings_button.connect("clicked", self._toggle_settings)

        # Delete button
        self.delete_button = Button(
            label="󰆴",
            name="vpn-delete-btn",
            tooltip_text="Delete profile",
        )
        setup_cursor_hover(self.delete_button)
        self.delete_button.connect("clicked", self._on_delete_clicked)

        # Main content box
        self.main_box = Box(
            orientation="horizontal",
            spacing=10,
            children=[self.type_icon, self.name_label, self.status_icon],
        )

        # Buttons box
        self.buttons_box = Box(
            spacing=4,
            h_align="end",
            children=[self.settings_button, self.delete_button, self.connect_button],
        )

        self.add_start(self.main_box)
        self.add_end(self.buttons_box)

        # Expanded settings panel (initially hidden)
        self.settings_panel = self._create_settings_panel()
        self.settings_panel.set_visible(False)

        # Apply connected style if connected
        if self._is_connected:
            self.add_style_class("connected")

    def _get_status_icon(self) -> str:
        """Get status icon based on current state."""
        if self._is_connected:
            return "󰖂"  # Connected icon
        return "󰖂"  # Default icon

    def _create_connect_button(self) -> Button:
        """Create connect/disconnect button."""
        is_connected = self._is_connected
        label = "Disconnect" if is_connected else "Connect"

        button = Button(
            label=label,
            name="vpn-connection-toggle-btn",
            h_align="end",
        )
        button.add_style_class("disconnect" if is_connected else "connect")
        setup_cursor_hover(button)
        button.connect("clicked", self._on_connect_clicked)
        return button

    def _on_connect_clicked(self, button):
        """Handle connect/disconnect button click."""
        if self._is_connected:
            self._disconnect()
        else:
            # Check if credentials are needed
            if self.profile.remember_credentials:
                creds = self.vpn_service.get_credentials(self.profile.name)
                if creds:
                    self._connect(creds[0], creds[1])
                    return

            # Show credentials input if OpenVPN and no saved credentials
            if self.profile.vpn_type == VPNType.OPENVPN:
                self._show_credentials_input()
            else:
                self._connect()

    def _show_credentials_input(self):
        """Show credentials input fields."""
        if self._credentials_shown:
            self._hide_credentials_input()
            return

        self._credentials_shown = True

        # Create credentials input
        self.username_entry = Entry(
            placeholder="Username",
            name="vpn-username-entry",
            h_expand=True,
        )

        self.password_entry = Entry(
            placeholder="Password",
            visibility=False,
            name="vpn-password-entry",
            h_expand=True,
        )

        self.remember_check = Gtk.CheckButton(label="Remember")
        self.remember_check.set_active(self.profile.remember_credentials)

        confirm_button = Button(
            label="Connect",
            name="vpn-confirm-btn",
        )
        setup_cursor_hover(confirm_button)
        confirm_button.connect("clicked", self._on_credentials_confirm)

        self.credentials_box = Box(
            orientation="vertical",
            spacing=8,
            name="vpn-credentials-box",
            children=[
                self.username_entry,
                self.password_entry,
                Box(
                    orientation="horizontal",
                    spacing=8,
                    children=[self.remember_check, confirm_button],
                ),
            ],
        )

        # Add to slot
        self.add(self.credentials_box)
        self.show_all()

    def _hide_credentials_input(self):
        """Hide credentials input fields."""
        if hasattr(self, "credentials_box") and self.credentials_box.get_parent():
            self.remove(self.credentials_box)
            self._credentials_shown = False

    def _on_credentials_confirm(self, button):
        """Handle credentials confirmation."""
        username = self.username_entry.get_text()
        password = self.password_entry.get_text()
        remember = self.remember_check.get_active()

        if remember:
            self.vpn_service.save_credentials(self.profile.name, username, password)

        self._hide_credentials_input()
        self._connect(username, password)

    def _connect(self, username: str | None = None, password: str | None = None):
        """Connect to VPN."""
        self.parent._show_status("Connecting...")
        self.connect_button.set_sensitive(False)
        self.connect_button.set_label("Connecting...")
        self.connect_button.remove_style_class("connect")
        self.connect_button.add_style_class("loading")

        def on_result(success: bool, message: str):
            self.connect_button.set_sensitive(True)
            self.connect_button.remove_style_class("loading")
            if success:
                self._is_connected = True
                self.add_style_class("connected")
                self.connect_button.set_label("Disconnect")
                self.connect_button.add_style_class("disconnect")
                self.parent._show_status("Connected!", 2000)
            else:
                self.connect_button.set_label("Connect")
                self.connect_button.add_style_class("connect")
                self.parent._show_status(f"Failed: {message}", 3000)

            self.parent.queue_refresh()

        self.vpn_service.connect(self.profile.name, username, password, on_result)

    def _disconnect(self):
        """Disconnect from VPN."""
        self.parent._show_status("Disconnecting...")
        self.connect_button.set_sensitive(False)
        self.connect_button.set_label("Disconnecting...")
        self.connect_button.remove_style_class("disconnect")
        self.connect_button.add_style_class("loading")

        def on_result(success: bool, message: str):
            self.connect_button.set_sensitive(True)
            self.connect_button.remove_style_class("loading")
            if success:
                self._is_connected = False
                self.remove_style_class("connected")
                self.connect_button.set_label("Connect")
                self.connect_button.add_style_class("connect")
                self.parent._show_status("Disconnected", 2000)
            else:
                self.connect_button.set_label("Disconnect")
                self.connect_button.add_style_class("disconnect")
                self.parent._show_status(f"Failed: {message}", 3000)

            self.parent.queue_refresh()

        self.vpn_service.disconnect(on_result)

    def _toggle_settings(self, button):
        """Toggle settings panel visibility."""
        self._expanded = not self._expanded
        
        if self._expanded:
            # Show settings panel
            if self.settings_panel.get_parent() is None:
                self.add(self.settings_panel)
            self.settings_panel.set_visible(True)
            self.settings_panel.show_all()
        else:
            # Hide settings panel
            self.settings_panel.set_visible(False)

    def _create_settings_panel(self) -> Box:
        """Create settings panel for the profile."""
        panel = Box(
            orientation="vertical",
            spacing=8,
            name="vpn-settings-panel",
        )

        # DNS Settings section
        dns_label = Label(label="DNS Settings", name="vpn-section-label")
        dns_label.set_halign(Gtk.Align.START)

        # DNS mode buttons
        self.dns_vpn_btn = Button(label="VPN DNS", name="vpn-dns-btn")
        self.dns_system_btn = Button(label="System DNS", name="vpn-dns-btn")
        self.dns_custom_btn = Button(label="Custom DNS", name="vpn-dns-btn")

        for btn in [self.dns_vpn_btn, self.dns_system_btn, self.dns_custom_btn]:
            setup_cursor_hover(btn)

        # Set active state based on profile
        self._update_dns_button_states()

        self.dns_vpn_btn.connect(
            "clicked", lambda _: self._set_dns_mode(DNSMode.VPN_DNS)
        )
        self.dns_system_btn.connect(
            "clicked", lambda _: self._set_dns_mode(DNSMode.SYSTEM_DNS)
        )
        self.dns_custom_btn.connect(
            "clicked", lambda _: self._set_dns_mode(DNSMode.CUSTOM_DNS)
        )

        dns_buttons_box = Box(
            orientation="horizontal",
            spacing=4,
            children=[self.dns_vpn_btn, self.dns_system_btn, self.dns_custom_btn],
        )

        # Custom DNS entry
        self.custom_dns_entry = Entry(
            placeholder="8.8.8.8, 1.1.1.1",
            name="vpn-custom-dns-entry",
            h_expand=True,
        )
        if self.profile.custom_dns:
            self.custom_dns_entry.set_text(", ".join(self.profile.custom_dns))

        self.custom_dns_entry.set_visible(
            self.profile.dns_mode == DNSMode.CUSTOM_DNS
        )

        # Split tunneling section
        split_label = Label(label="Split Tunneling", name="vpn-section-label")
        split_label.set_halign(Gtk.Align.START)

        self.split_toggle = Gtk.CheckButton(label="Enable split tunneling")
        self.split_toggle.set_active(self.profile.split_tunnel_enabled)
        self.split_toggle.connect("toggled", self._on_split_toggle)

        self.split_ips_entry = Entry(
            placeholder="IPs to bypass (e.g., 192.168.1.0/24)",
            name="vpn-split-entry",
            h_expand=True,
        )
        if self.profile.split_tunnel_ips:
            self.split_ips_entry.set_text(", ".join(self.profile.split_tunnel_ips))

        self.split_ips_entry.set_visible(self.profile.split_tunnel_enabled)

        # Credentials section
        creds_label = Label(label="Credentials", name="vpn-section-label")
        creds_label.set_halign(Gtk.Align.START)

        self.clear_creds_btn = Button(
            label="Clear saved credentials",
            name="vpn-clear-creds-btn",
        )
        setup_cursor_hover(self.clear_creds_btn)
        self.clear_creds_btn.connect("clicked", self._on_clear_credentials)
        self.clear_creds_btn.set_sensitive(self.profile.remember_credentials)

        # Save settings button
        save_btn = Button(label="Save Settings", name="vpn-save-btn")
        setup_cursor_hover(save_btn)
        save_btn.connect("clicked", self._on_save_settings)

        # Add all to panel
        panel.add(dns_label)
        panel.add(dns_buttons_box)
        panel.add(self.custom_dns_entry)
        panel.add(split_label)
        panel.add(self.split_toggle)
        panel.add(self.split_ips_entry)
        panel.add(creds_label)
        panel.add(self.clear_creds_btn)
        panel.add(save_btn)

        return panel

    def _update_dns_button_states(self):
        """Update DNS button active states."""
        for btn in [self.dns_vpn_btn, self.dns_system_btn, self.dns_custom_btn]:
            btn.remove_style_class("active")

        if self.profile.dns_mode == DNSMode.VPN_DNS:
            self.dns_vpn_btn.add_style_class("active")
        elif self.profile.dns_mode == DNSMode.SYSTEM_DNS:
            self.dns_system_btn.add_style_class("active")
        else:
            self.dns_custom_btn.add_style_class("active")

    def _set_dns_mode(self, mode: DNSMode):
        """Set DNS mode."""
        self.profile.dns_mode = mode
        self._update_dns_button_states()
        self.custom_dns_entry.set_visible(mode == DNSMode.CUSTOM_DNS)

    def _on_split_toggle(self, toggle):
        """Handle split tunneling toggle."""
        enabled = toggle.get_active()
        self.split_ips_entry.set_visible(enabled)

    def _on_clear_credentials(self, button):
        """Clear saved credentials."""
        self.vpn_service.clear_credentials(self.profile.name)
        self.clear_creds_btn.set_sensitive(False)
        self.parent._show_status("Credentials cleared", 2000)

    def _on_save_settings(self, button):
        """Save profile settings."""
        # Parse custom DNS
        custom_dns = []
        if self.profile.dns_mode == DNSMode.CUSTOM_DNS:
            dns_text = self.custom_dns_entry.get_text()
            if dns_text:
                custom_dns = [d.strip() for d in dns_text.split(",") if d.strip()]

        # Parse split tunnel IPs
        split_ips = []
        if self.split_toggle.get_active():
            ips_text = self.split_ips_entry.get_text()
            if ips_text:
                split_ips = [ip.strip() for ip in ips_text.split(",") if ip.strip()]

        # Update profile
        self.vpn_service.update_profile_settings(
            self.profile.name,
            dns_mode=self.profile.dns_mode,
            custom_dns=custom_dns,
            split_tunnel_enabled=self.split_toggle.get_active(),
            split_tunnel_ips=split_ips,
        )

        self.parent._show_status("Settings saved", 2000)

    def _on_delete_clicked(self, button):
        """Handle delete button click."""
        self.parent._show_status("Deleting profile...")

        def on_result(success: bool, message: str):
            if success:
                self.parent._show_status("Profile deleted", 2000)
            else:
                self.parent._show_status(f"Failed: {message}", 3000)
            self.parent.queue_refresh()

        self.vpn_service.delete_profile(self.profile.name, on_result)

    def update_status(self, status: VPNStatus):
        """Update the slot's status display."""
        current = self.vpn_service.current_profile
        self._is_connected = (
            current is not None
            and current.name == self.profile.name
            and status == VPNStatus.CONNECTED
        )

        if self._is_connected:
            self.add_style_class("connected")
            self.connect_button.set_label("Disconnect")
            self.connect_button.remove_style_class("connect")
            self.connect_button.add_style_class("disconnect")
        else:
            self.remove_style_class("connected")
            self.connect_button.set_label("Connect")
            self.connect_button.remove_style_class("disconnect")
            self.connect_button.add_style_class("connect")


class VPNConnections(BaseDiWidget, Box):
    """VPN connections management widget for Dynamic Island."""

    focuse_kb = True

    def __init__(self, **kwargs):
        Box.__init__(
            self,
            orientation="vertical",
            spacing=8,
            name="vpn",
            **kwargs,
        )

        self.vpn_service = get_vpn_service()
        self._pending_refresh = False
        self._slots_lock = Lock()
        self._profile_slots: dict[str, VPNProfileSlot] = {}

        # Subscribe to status changes
        self.vpn_service.add_status_callback(self._on_vpn_status_change)

        self._initialize_ui()
        self._load_profiles()

    def _initialize_ui(self):
        """Initialize the widget UI."""
        # Title
        self.title_label = Label(style_classes="title", label="VPN")

        # Scan & Import button
        import_box = Box(
            orientation="horizontal",
            spacing=6,
            children=[
                text_icon("󰘤", size="14px"),
                Label(label="Scan"),
            ],
        )
        self.import_button = Button(
            name="vpn-import-btn",
            tooltip_text="Scan import folder for VPN configs",
            child=import_box,
        )
        setup_cursor_hover(self.import_button)
        self.import_button.connect("clicked", self._on_import_clicked)

        # Refresh button
        self.refresh_button = Button(
            name="vpn-refresh-btn",
            child=text_icon("󰑓"),
            tooltip_text="Refresh",
        )
        setup_cursor_hover(self.refresh_button)
        self.refresh_button.connect("clicked", self._on_refresh_clicked)

        # Connection info label
        self.info_label = Label(
            label="",
            name="vpn-info-label",
        )
        self.info_label.set_visible(False)

        # Header
        self.header_box = CenterBox(
            name="controls",
            start_children=Box(
                spacing=6,
                children=[self.import_button, self.refresh_button],
            ),
            center_children=self.title_label,
            end_children=self.info_label,
        )

        # Profiles container
        self.profiles_box = Box(orientation="vertical", spacing=4)

        # Scrolled window for profiles
        self.scrolled_window = ScrolledWindow(
            child=self.profiles_box,
            min_content_height=200,
            propagate_natural_height=True,
        )

        # Empty state with import instructions
        self.empty_box = Box(
            orientation="vertical",
            spacing=12,
            name="vpn-empty-box",
            h_align="center",
            v_align="center",
        )

        empty_icon = text_icon("󰖂", size="48px", name="vpn-empty-icon")

        self.empty_label = Label(
            label="No VPN profiles configured",
            name="vpn-empty-label",
        )

        # Import folder path
        import_folder = self.vpn_service.VPN_DIR / "import"
        import_folder.mkdir(parents=True, exist_ok=True)

        self.empty_sublabel = Label(
            label="Copy .ovpn, .conf, or .wg files to:",
            name="vpn-empty-sublabel",
        )

        # Show import folder path
        self.import_path_label = Label(
            label=str(import_folder),
            name="vpn-import-path",
        )

        self.empty_box.add(empty_icon)
        self.empty_box.add(self.empty_label)
        self.empty_box.add(self.empty_sublabel)
        self.empty_box.add(self.import_path_label)

        self.add(self.header_box)
        self.add(self.scrolled_window)

    def _show_status(self, message: str, timeout: int | None = None):
        """Show status message."""
        self.title_label.set_label(message)

        if timeout:
            GLib.timeout_add(timeout, self._reset_title)

    def _reset_title(self):
        """Reset title to default."""
        self.title_label.set_label("VPN")
        return False

    def _on_vpn_status_change(self, status: VPNStatus, message: str | None):
        """Handle VPN status changes."""
        # Update all slots
        for slot in self._profile_slots.values():
            slot.update_status(status)

        # Update info label
        if status == VPNStatus.CONNECTED:
            current = self.vpn_service.current_profile
            if current:
                self.info_label.set_label(f"󰖂 {current.name}")
                self.info_label.set_visible(True)
        else:
            self.info_label.set_visible(False)

        # Show status message
        if message:
            self._show_status(message, 3000)

    def _load_profiles(self):
        """Load VPN profiles."""
        self._show_status("Loading profiles...")

        def do_load():
            profiles = self.vpn_service.profiles

            GLib.idle_add(self._update_profiles_ui, profiles)

        GLib.Thread.new(None, do_load)

    def _update_profiles_ui(self, profiles: dict[str, VPNProfile]):
        """Update profiles UI."""
        with self._slots_lock:
            # Clear existing slots
            for child in list(self.profiles_box.get_children()):
                self.profiles_box.remove(child)

            self._profile_slots.clear()

            if not profiles:
                # Show empty state with import button
                self.profiles_box.add(self.empty_box)
            else:
                # Remove empty box if present
                if self.empty_box.get_parent():
                    self.profiles_box.remove(self.empty_box)

                # Add slots for each profile
                for name, profile in profiles.items():
                    slot = VPNProfileSlot(profile, self)
                    self._profile_slots[name] = slot
                    self.profiles_box.add(slot)

            self.profiles_box.show_all()

        self._reset_title()

    def queue_refresh(self):
        """Queue a refresh of the profiles list."""
        if self._pending_refresh:
            return

        self._pending_refresh = True
        GLib.idle_add(self._do_refresh)

    def _do_refresh(self):
        """Perform refresh."""
        self._load_profiles()
        self._pending_refresh = False
        return False

    def _on_refresh_clicked(self, button):
        """Handle refresh button click."""
        self.queue_refresh()

    def _on_import_clicked(self, button):
        """Handle import button click - scan import folder for new configs."""
        self._scan_and_import_configs()

    def _scan_and_import_configs(self):
        """Scan the import folder for VPN configs and import them."""
        import_folder = self.vpn_service.VPN_DIR / "import"
        import_folder.mkdir(parents=True, exist_ok=True)

        # Find all VPN config files in the import folder
        config_extensions = [".ovpn", ".conf", ".wg"]
        found_files = []

        for ext in config_extensions:
            found_files.extend(import_folder.glob(f"*{ext}"))

        if not found_files:
            # Show info about import folder
            self._show_import_info()
            return

        # Import each found file
        imported_count = 0
        for config_file in found_files:
            self.vpn_service.import_profile(
                config_file,
                callback=lambda success, msg, f=config_file: self._on_scan_import_result(
                    success, msg, f
                ),
            )
            imported_count += 1

        self._show_status(f"Importing {imported_count} profile(s)...", 2000)

    def _on_scan_import_result(self, success: bool, message: str, config_file: Path):
        """Handle import result from scan and optionally delete source file."""
        if success:
            # Delete the source file after successful import
            try:
                config_file.unlink()
                logger.info(f"Deleted imported file: {config_file}")
            except Exception as e:
                logger.warning(f"Could not delete imported file: {e}")

        self._show_status(message, 3000)
        self.queue_refresh()

    def _show_import_info(self):
        """Show information about how to import VPN configs."""
        self._show_status("No configs found.", 3000)

    def _on_import_result(self, success: bool, message: str):
        """Handle import result."""
        self._show_status(message, 3000)
        if success:
            self.queue_refresh()

    def open_widget_from_di(self):
        """Called when widget is opened from Dynamic Island."""
        self.queue_refresh()

    def close_widget_from_di(self):
        """Called when widget is closed from Dynamic Island."""
        pass
