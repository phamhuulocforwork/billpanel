from fabric.widgets.box import Box
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.wayland import WaylandWindow

from billpanel.utils.hyprland_monitors import HyprlandMonitors
from billpanel.widgets.battery import Battery
from billpanel.widgets.bluetooth import Bluetooth
from billpanel.widgets.combined_controls import CombinedControlsButton
from billpanel.widgets.datetime import DateTimeWidget
from billpanel.widgets.language import LanguageWidget
from billpanel.widgets.network_status import NetworkStatus
from billpanel.widgets.ocr import OCRWidget
from billpanel.widgets.power import PowerButton
from billpanel.widgets.system_tray import SystemTray
from billpanel.widgets.vpn_status import VPNStatusWidget
from billpanel.widgets.workspaces import HyprlandWorkSpacesWidget


class StatusBar(WaylandWindow):
    """A widget to display the status bar panel."""

    def __init__(self, **kwargs):
        self.combined_controls = CombinedControlsButton()

        box = CenterBox(
            name="panel-inner",
            start_children=Box(
                spacing=4,
                orientation="h",
                children=[SystemTray(), HyprlandWorkSpacesWidget()],
            ),
            center_children=Box(
                spacing=4,
                orientation="h",
                children=None,
            ),
            end_children=Box(
                spacing=4,
                orientation="h",
                children=[
                    OCRWidget(),
                    Battery(),
                    self.combined_controls,
                    LanguageWidget(),
                    DateTimeWidget(),
                    Bluetooth(),
                    VPNStatusWidget(),
                    NetworkStatus(),
                    PowerButton(),
                ],
            ),
        )

        WaylandWindow.__init__(
            self,
            name="panel",
            layer="top",
            anchor="left top right",
            pass_through=False,
            monitor=HyprlandMonitors().get_current_gdk_monitor_id(),
            exclusivity="auto",
            visible=True,
            all_visible=False,
            child=box,
            **kwargs,
        )

    def set_osd_widget(self, osd_widget):
        """Set OSD widget reference for combined controls."""
        if hasattr(self, 'combined_controls'):
            self.combined_controls.set_osd_widget(osd_widget)
