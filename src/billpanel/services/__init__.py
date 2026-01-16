from fabric.audio import Audio
from fabric.bluetooth import BluetoothClient

from billpanel.services.battery import BatteryService
from billpanel.services.brightness import BrightnessService
from billpanel.services.cache_notification import NotificationCacheService
from billpanel.services.notifications import MyNotifications

audio_service = Audio()

notification_service = MyNotifications()
cache_notification_service = NotificationCacheService()
brightness_service = BrightnessService()
battery_service = BatteryService()

bluetooth_client = BluetoothClient()
# to run notify closures thus display the status
# without having to wait until an actual change
bluetooth_client.notify("scanning")
bluetooth_client.notify("enabled")
