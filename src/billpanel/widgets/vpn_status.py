from threading import Lock

from fabric.utils import exec_shell_command_async
from gi.repository import GLib
from loguru import logger

import billpanel.constants as cnst
from billpanel.services.vpn import get_vpn_service
from billpanel.services.vpn import VPNStatus
from billpanel.shared.widget_container import ButtonWidget
from billpanel.utils.widget_utils import text_icon


class VPNStatusWidget(ButtonWidget):

    # Icons for different VPN states
    ICONS = {
        VPNStatus.DISCONNECTED: "󰦞",  # VPN off
        VPNStatus.CONNECTING: "󱘖",  # Connecting
        VPNStatus.CONNECTED: "󰦝",  # VPN on/connected
        VPNStatus.DISCONNECTING: "󱘖",  # Disconnecting
        VPNStatus.ERROR: "󰦞",  # Error state
        VPNStatus.RECONNECTING: "󱘖",  # Reconnecting
    }

    def __init__(self, **kwargs):
        super().__init__(name="vpn-status", **kwargs)
        self._update_lock = Lock()
        self._vpn_service = get_vpn_service()

        self.set_tooltip_text("VPN Status")
        self._update_icon()

        # Subscribe to VPN status changes
        self._vpn_service.add_status_callback(self._on_status_change)

        # Click to open VPN widget
        self.connect(
            "clicked",
            lambda *_: exec_shell_command_async(
                cnst.kb_di_open.format(module="vpn")
            ),
        )

        # Periodic update as fallback
        GLib.timeout_add_seconds(5, self._periodic_update)

    def _on_status_change(self, status: VPNStatus, message: str | None):
        GLib.idle_add(self._update_icon)

    def _periodic_update(self) -> bool:
        self._update_icon()
        return True

    def _update_icon(self):
        try:
            status = self._vpn_service.status
            current_profile = self._vpn_service.current_profile

            icon = self.ICONS.get(status, "󰦞")

            # Update tooltip with connection info
            if status == VPNStatus.CONNECTED and current_profile:
                tooltip = f"VPN: {current_profile.name}"
                style_class = "panel-text-icon vpn-connected"
            elif status == VPNStatus.CONNECTING:
                tooltip = "VPN: Connecting..."
                style_class = "panel-text-icon vpn-connecting"
            elif status == VPNStatus.RECONNECTING:
                tooltip = "VPN: Reconnecting..."
                style_class = "panel-text-icon vpn-connecting"
            elif status == VPNStatus.ERROR:
                tooltip = "VPN: Error"
                style_class = "panel-text-icon vpn-error"
            else:
                tooltip = "VPN: Disconnected"
                style_class = "panel-text-icon vpn-disconnected"

            self.set_tooltip_text(tooltip)
            self.children = text_icon(icon, "16px", style_classes=style_class)

        except Exception as e:
            logger.error(f"Failed to update VPN status: {e}")
            self.children = text_icon(
                "󰦞", "16px", style_classes="panel-text-icon vpn-error"
            )
