from fabric.utils import exec_shell_command_async

import billpanel.constants as cnst
from billpanel.config import cfg
from billpanel.services import bluetooth_client
from billpanel.shared.widget_container import ButtonWidget
from billpanel.utils.widget_utils import text_icon


class Bluetooth(ButtonWidget):
    """A button for open the Bluetooth menu."""

    def __init__(self, **kwargs):
        super().__init__(name="power", **kwargs)
        self.config = cfg.modules.power

        self.set_tooltip_text("Bluetooth")
        self.update_icon()

        self.connect(
            "clicked",
            lambda *_: exec_shell_command_async(
                cnst.kb_di_open.format(module="bluetooth")
            ),
        )
        bluetooth_client.connect(
            "notify::enabled",
            lambda *_: self.update_icon(),
        )

    def update_icon(self):
        if bluetooth_client.enabled:
            icon = cnst.icons["bluetooth"]["bluetooth_connected"]
        else:
            icon = cnst.icons["bluetooth"]["bluetooth_disconnected"]

        self.children = text_icon(
            icon,
            "16px",
            style_classes="panel-text-icon",
        )
