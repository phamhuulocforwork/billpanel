from fabric.audio import Audio
from fabric.bluetooth import BluetoothClient

from billpanel.services.audio_visualizer import AudioVisualizerService
from billpanel.services.battery import BatteryService
from billpanel.services.brightness import BrightnessService
from billpanel.services.cache_notification import NotificationCacheService
from billpanel.services.notifications import MyNotifications
from billpanel.services.privacy import PrivacyService

audio_service = Audio()
audio_visualizer_service = AudioVisualizerService(bar_count=6, fps=30)

notification_service = MyNotifications()
cache_notification_service = NotificationCacheService()
brightness_service = BrightnessService()
battery_service = BatteryService()
privacy_service = PrivacyService()

bluetooth_client = BluetoothClient()
# to run notify closures thus display the status
# without having to wait until an actual change
bluetooth_client.notify("scanning")
bluetooth_client.notify("enabled")
