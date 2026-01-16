import subprocess

from fabric.widgets.box import Box
from fabric.widgets.label import Label
from gi.repository import GLib
from loguru import logger

from billpanel.shared.widget_container import ButtonWidget


class LanguageWidget(ButtonWidget):
    """A widget to display and switch Fcitx5 input methods.

    Displays current input method and allows switching between English and Vietnamese.
    Left-click to toggle between input methods.
    """

    def __init__(self):
        super().__init__(name="language")

        # Input method labels for display
        self.im_labels = {
            "keyboard-us": "EN",
            "keyboard-us-intl": "EN",
            "en": "EN",
            "us": "EN",
            "gonhanh": "VI",
            "unikey": "VI",
            "bamboo": "VI",
            "Bamboo": "VI",
            "VnTelex": "VI",
            "VnVni": "VI",
        }

        # Priority order for Vietnamese input methods
        self.vi_ims = ["gonhanh", "Bamboo", "unikey", "bamboo", "VnTelex", "VnVni"]

        # Priority order for English input methods
        self.en_ims = ["keyboard-us", "keyboard-us-intl", "en", "us"]

        # Create label widget
        self.label = Label(label="--")
        self.label.style_classes = ["panel-text-icon"]

        self.box = Box()
        self.box.children = self.label
        self.children = self.box

        # Connect click event
        self.connect("button-press-event", self.on_button_press)

        # Initial update
        self.update_display()

        # Poll for updates every 2 seconds
        GLib.timeout_add_seconds(2, self.update_display)

    def check_fcitx5_running(self):
        try:
            result = subprocess.run(
                ["fcitx5-remote", "--check"],
                capture_output=True,
                timeout=1,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_current_im(self):
        try:
            result = subprocess.run(
                ["fcitx5-remote", "-n"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.debug(f"Failed to get current IM: {e}")
        return None

    def get_available_ims(self):
        # This is a simplified version - Fcitx5 doesn't have a direct command
        # to list all IMs, so we check config files or use known common names
        available = []

        # Check common Vietnamese IMs
        for im in self.vi_ims:
            try:
                result = subprocess.run(
                    ["fcitx5-remote", "-s", im],
                    capture_output=True,
                    timeout=1,
                )
                if result.returncode == 0:
                    available.append(im)
            except Exception:
                pass

        # English is usually always available
        available.extend(["keyboard-us"])

        return available

    def switch_to_im(self, im_name):
        try:
            result = subprocess.run(
                ["fcitx5-remote", "-s", im_name],
                capture_output=True,
                timeout=2,
            )
            if result.returncode == 0:
                logger.info(f"Switched to input method: {im_name}")
                # Update display after a short delay
                GLib.timeout_add(200, self.update_display)
                return True
            else:
                logger.warning(f"Failed to switch to {im_name}")
        except Exception as e:
            logger.error(f"Failed to switch input method: {e}")
        return False

    def toggle_im(self):
        if not self.check_fcitx5_running():
            logger.warning("Fcitx5 is not running")
            return

        current = self.get_current_im()
        if not current:
            logger.warning("Could not get current input method")
            return

        # Determine current language
        is_vietnamese = self.im_labels.get(current, "").upper() == "VI"

        if is_vietnamese:
            # Switch to English
            for im in self.en_ims:
                if self.switch_to_im(im):
                    return
            logger.warning("Could not switch to English input method")
        else:
            # Switch to Vietnamese
            # First try to find which Vietnamese IM is available
            for im in self.vi_ims:
                if self.switch_to_im(im):
                    return
            logger.warning("No Vietnamese input method found")

    def update_display(self):
        if not self.check_fcitx5_running():
            self.label.set_label("--")
            self.set_tooltip_text("Fcitx5 is not running")
            return True

        current = self.get_current_im()
        if current:
            # Get display label
            display = self.im_labels.get(current, current[:2].upper())
            self.label.set_label(display)

            # Update tooltip
            self.set_tooltip_text(f"Input Method: {current}\nClick to toggle")
        else:
            self.label.set_label("??")
            self.set_tooltip_text("Could not detect input method")

        # Return True to keep the timeout running
        return True

    def on_button_press(self, _, event):
        if event.button == 1:  # Left click
            self.toggle_im()
