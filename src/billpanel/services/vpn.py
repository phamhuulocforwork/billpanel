import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from pathlib import Path
from threading import Lock
from threading import Thread
from typing import Callable

from gi.repository import GLib
from loguru import logger

import billpanel.constants as cnst

# Try to import keyring for secure credential storage
try:
    import keyring

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    logger.warning("keyring not available, credentials will not be stored securely")


class VPNStatus(Enum):
    """VPN connection status."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    ERROR = "error"
    RECONNECTING = "reconnecting"


class VPNType(Enum):

    OPENVPN = "openvpn"
    WIREGUARD = "wireguard"


class DNSMode(Enum):

    VPN_DNS = "vpn"  # Use VPN's DNS
    SYSTEM_DNS = "system"  # Keep system DNS
    CUSTOM_DNS = "custom"  # Use custom DNS servers


@dataclass
class VPNProfile:

    name: str
    config_path: Path
    vpn_type: VPNType
    auto_connect: bool = False
    remember_credentials: bool = False
    dns_mode: DNSMode = DNSMode.VPN_DNS
    custom_dns: list[str] = field(default_factory=list)
    split_tunnel_enabled: bool = False
    split_tunnel_apps: list[str] = field(default_factory=list)
    split_tunnel_ips: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "config_path": str(self.config_path),
            "vpn_type": self.vpn_type.value,
            "auto_connect": self.auto_connect,
            "remember_credentials": self.remember_credentials,
            "dns_mode": self.dns_mode.value,
            "custom_dns": self.custom_dns,
            "split_tunnel_enabled": self.split_tunnel_enabled,
            "split_tunnel_apps": self.split_tunnel_apps,
            "split_tunnel_ips": self.split_tunnel_ips,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VPNProfile":
        return cls(
            name=data["name"],
            config_path=Path(data["config_path"]),
            vpn_type=VPNType(data["vpn_type"]),
            auto_connect=data.get("auto_connect", False),
            remember_credentials=data.get("remember_credentials", False),
            dns_mode=DNSMode(data.get("dns_mode", "vpn")),
            custom_dns=data.get("custom_dns", []),
            split_tunnel_enabled=data.get("split_tunnel_enabled", False),
            split_tunnel_apps=data.get("split_tunnel_apps", []),
            split_tunnel_ips=data.get("split_tunnel_ips", []),
        )


class VPNService:

    KEYRING_SERVICE = "billpanel-vpn"
    VPN_DIR = cnst.APP_SETTINGS_FOLDER / "vpn"
    PROFILES_FILE = VPN_DIR / "profiles.json"
    PID_DIR = VPN_DIR / "pids"

    def __init__(self):
        self._status = VPNStatus.DISCONNECTED
        self._current_profile: VPNProfile | None = None
        self._profiles: dict[str, VPNProfile] = {}
        self._status_callbacks: list[Callable[[VPNStatus, str | None], None]] = []
        self._lock = Lock()
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3
        self._reconnect_delay = 5  # seconds
        self._monitor_thread: Thread | None = None
        self._should_monitor = False
        self._original_dns: list[str] = []
        self._original_resolv_conf: str = ""

        # Ensure directories exist
        self.VPN_DIR.mkdir(parents=True, exist_ok=True)
        self.PID_DIR.mkdir(parents=True, exist_ok=True)

        # Load existing profiles
        self._load_profiles()

        # Check for any running VPN connections
        self._check_existing_connections()

    @property
    def status(self) -> VPNStatus:
        return self._status

    @property
    def current_profile(self) -> VPNProfile | None:
        return self._current_profile

    @property
    def profiles(self) -> dict[str, VPNProfile]:
        return self._profiles.copy()

    def add_status_callback(
        self, callback: Callable[[VPNStatus, str | None], None]
    ) -> None:
        self._status_callbacks.append(callback)

    def remove_status_callback(
        self, callback: Callable[[VPNStatus, str | None], None]
    ) -> None:
        if callback in self._status_callbacks:
            self._status_callbacks.remove(callback)

    def _notify_status_change(self, message: str | None = None) -> None:
        for callback in self._status_callbacks:
            try:
                GLib.idle_add(callback, self._status, message)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")

    def _set_status(self, status: VPNStatus, message: str | None = None) -> None:
        self._status = status
        self._notify_status_change(message)

    def _load_profiles(self) -> None:
        if not self.PROFILES_FILE.exists():
            return

        try:
            with open(self.PROFILES_FILE, encoding="utf-8") as f:
                data = json.load(f)

            for profile_data in data.get("profiles", []):
                profile = VPNProfile.from_dict(profile_data)
                if profile.config_path.exists():
                    self._profiles[profile.name] = profile
                else:
                    logger.warning(
                        f"Profile config not found: {profile.config_path}, skipping"
                    )

        except Exception as e:
            logger.error(f"Failed to load VPN profiles: {e}")

    def _save_profiles(self) -> None:
        try:
            data = {"profiles": [p.to_dict() for p in self._profiles.values()]}

            with open(self.PROFILES_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save VPN profiles: {e}")

    def _check_existing_connections(self) -> None:
        # Check for running OpenVPN processes
        for pid_file in self.PID_DIR.glob("*.pid"):
            try:
                pid = int(pid_file.read_text().strip())
                if self._is_process_running(pid):
                    profile_name = pid_file.stem
                    if profile_name in self._profiles:
                        self._current_profile = self._profiles[profile_name]
                        self._set_status(VPNStatus.CONNECTED)
                        self._start_monitor()
                        return
                else:
                    # Clean up stale PID file
                    pid_file.unlink()
            except Exception:
                pid_file.unlink(missing_ok=True)

        # Check for active WireGuard interfaces
        try:
            result = subprocess.run(
                ["wg", "show", "interfaces"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                interfaces = result.stdout.strip().split()
                for iface in interfaces:
                    # Try to match with a profile
                    for profile in self._profiles.values():
                        if (
                            profile.vpn_type == VPNType.WIREGUARD
                            and profile.name in iface
                        ):
                            self._current_profile = profile
                            self._set_status(VPNStatus.CONNECTED)
                            self._start_monitor()
                            return
        except Exception:
            pass

    def _is_process_running(self, pid: int) -> bool:
        try:
            # First try os.kill (works for own processes)
            os.kill(pid, 0)
            return True
        except OSError:
            # If that fails (permission denied for root processes), check /proc
            try:
                proc_path = Path(f"/proc/{pid}")
                return proc_path.exists()
            except Exception:
                return False

    def validate_config_file(self, file_path: Path) -> tuple[bool, str, VPNType | None]:
        if not file_path.exists():
            return False, "File does not exist", None

        suffix = file_path.suffix.lower()

        if suffix == ".ovpn":
            return self._validate_openvpn_config(file_path)
        elif suffix in (".conf", ".wg"):
            return self._validate_wireguard_config(file_path)
        else:
            return False, f"Unsupported file type: {suffix}", None

    def _validate_openvpn_config(
        self, file_path: Path
    ) -> tuple[bool, str, VPNType | None]:
        try:
            content = file_path.read_text()

            # Check for required directives
            required = ["remote", "dev"]
            missing = []

            for directive in required:
                if not re.search(rf"^\s*{directive}\s+", content, re.MULTILINE):
                    missing.append(directive)

            if missing:
                return False, f"Missing required directives: {', '.join(missing)}", None

            # Check for either embedded certs or cert file references
            has_certs = any(
                tag in content
                for tag in ["<ca>", "<cert>", "<key>", "ca ", "cert ", "key "]
            )

            if not has_certs:
                return (
                    False,
                    "No certificates found (embedded or referenced)",
                    None,
                )

            return True, "Valid OpenVPN configuration", VPNType.OPENVPN

        except Exception as e:
            return False, f"Error reading file: {e}", None

    def _validate_wireguard_config(
        self, file_path: Path
    ) -> tuple[bool, str, VPNType | None]:
        try:
            content = file_path.read_text()

            # Check for required sections
            if "[Interface]" not in content:
                return False, "Missing [Interface] section", None

            if "[Peer]" not in content:
                return False, "Missing [Peer] section", None

            # Check for required keys
            if not re.search(r"^\s*PrivateKey\s*=", content, re.MULTILINE):
                return False, "Missing PrivateKey in [Interface]", None

            if not re.search(r"^\s*PublicKey\s*=", content, re.MULTILINE):
                return False, "Missing PublicKey in [Peer]", None

            return True, "Valid WireGuard configuration", VPNType.WIREGUARD

        except Exception as e:
            return False, f"Error reading file: {e}", None

    def import_profile(
        self,
        file_path: Path,
        name: str | None = None,
        callback: Callable[[bool, str], None] | None = None,
    ) -> None:
        """Import a VPN profile from a configuration file.

        Args:
            file_path: Path to the configuration file
            name: Optional custom name for the profile
            callback: Callback function (success, message)
        """

        def do_import():
            try:
                # Validate the config file
                is_valid, message, vpn_type = self.validate_config_file(file_path)

                if not is_valid:
                    if callback:
                        GLib.idle_add(callback, False, message)
                    return

                # Generate profile name if not provided
                profile_name = name or file_path.stem

                # Ensure unique name
                original_name = profile_name
                counter = 1
                while profile_name in self._profiles:
                    profile_name = f"{original_name}_{counter}"
                    counter += 1

                # Copy config file to VPN directory
                dest_path = self.VPN_DIR / f"{profile_name}{file_path.suffix}"
                shutil.copy2(file_path, dest_path)

                # Create profile
                profile = VPNProfile(
                    name=profile_name,
                    config_path=dest_path,
                    vpn_type=vpn_type,
                )

                with self._lock:
                    self._profiles[profile_name] = profile
                    self._save_profiles()

                if callback:
                    GLib.idle_add(
                        callback, True, f"Profile '{profile_name}' imported successfully"
                    )

            except Exception as e:
                logger.error(f"Failed to import profile: {e}")
                if callback:
                    GLib.idle_add(callback, False, f"Import failed: {e}")

        Thread(target=do_import, daemon=True).start()

    def delete_profile(
        self, name: str, callback: Callable[[bool, str], None] | None = None
    ) -> None:
        def do_delete():
            try:
                if name not in self._profiles:
                    if callback:
                        GLib.idle_add(callback, False, "Profile not found")
                    return

                # Disconnect if this profile is connected
                if self._current_profile and self._current_profile.name == name:
                    self._disconnect_sync()

                profile = self._profiles[name]

                # Delete config file
                if profile.config_path.exists():
                    profile.config_path.unlink()

                # Delete PID file if exists
                pid_file = self.PID_DIR / f"{name}.pid"
                pid_file.unlink(missing_ok=True)

                # Clear credentials
                self.clear_credentials(name)

                # Remove from profiles
                with self._lock:
                    del self._profiles[name]
                    self._save_profiles()

                if callback:
                    GLib.idle_add(callback, True, f"Profile '{name}' deleted")

            except Exception as e:
                logger.error(f"Failed to delete profile: {e}")
                if callback:
                    GLib.idle_add(callback, False, f"Delete failed: {e}")

        Thread(target=do_delete, daemon=True).start()

    def save_credentials(self, profile_name: str, username: str, password: str) -> bool:
        if not KEYRING_AVAILABLE:
            logger.warning("Keyring not available, cannot save credentials")
            return False

        try:
            # Store username and password as JSON
            credentials = json.dumps({"username": username, "password": password})
            keyring.set_password(self.KEYRING_SERVICE, profile_name, credentials)

            # Update profile
            if profile_name in self._profiles:
                self._profiles[profile_name].remember_credentials = True
                self._save_profiles()

            return True
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
            return False

    def get_credentials(self, profile_name: str) -> tuple[str, str] | None:
        if not KEYRING_AVAILABLE:
            return None

        try:
            credentials_json = keyring.get_password(self.KEYRING_SERVICE, profile_name)
            if credentials_json:
                credentials = json.loads(credentials_json)
                return credentials.get("username", ""), credentials.get("password", "")
        except Exception as e:
            logger.error(f"Failed to get credentials: {e}")

        return None

    def clear_credentials(self, profile_name: str) -> bool:
        if not KEYRING_AVAILABLE:
            return False

        try:
            keyring.delete_password(self.KEYRING_SERVICE, profile_name)

            if profile_name in self._profiles:
                self._profiles[profile_name].remember_credentials = False
                self._save_profiles()

            return True
        except Exception as e:
            logger.error(f"Failed to clear credentials: {e}")
            return False

    def connect(
        self,
        profile_name: str,
        username: str | None = None,
        password: str | None = None,
        callback: Callable[[bool, str], None] | None = None,
    ) -> None:
        # Capture credentials in local variables for closure
        conn_username = username
        conn_password = password

        def do_connect():
            nonlocal conn_username, conn_password
            try:
                if profile_name not in self._profiles:
                    if callback:
                        GLib.idle_add(callback, False, "Profile not found")
                    return

                profile = self._profiles[profile_name]

                # Disconnect any existing connection first
                if self._status == VPNStatus.CONNECTED:
                    self._disconnect_sync()

                self._set_status(VPNStatus.CONNECTING, f"Connecting to {profile_name}...")

                # Get credentials if needed and not provided
                if conn_username is None and conn_password is None:
                    saved_creds = self.get_credentials(profile_name)
                    if saved_creds:
                        conn_username, conn_password = saved_creds

                # Save DNS state before connecting
                self._save_dns_state()

                # Connect based on VPN type
                if profile.vpn_type == VPNType.OPENVPN:
                    success, message = self._connect_openvpn(
                        profile, conn_username, conn_password
                    )
                else:
                    success, message = self._connect_wireguard(profile)

                if success:
                    self._current_profile = profile
                    self._reconnect_attempts = 0

                    # Apply DNS settings
                    self._apply_dns_settings(profile)

                    # Apply split tunneling if enabled
                    if profile.split_tunnel_enabled:
                        self._apply_split_tunneling(profile)

                    self._set_status(VPNStatus.CONNECTED, f"Connected to {profile_name}")
                    self._start_monitor()

                    if callback:
                        GLib.idle_add(callback, True, message)
                else:
                    self._set_status(VPNStatus.ERROR, message)
                    if callback:
                        GLib.idle_add(callback, False, message)

            except Exception as e:
                logger.error(f"Connection failed: {e}")
                self._set_status(VPNStatus.ERROR, str(e))
                if callback:
                    GLib.idle_add(callback, False, f"Connection failed: {e}")

        Thread(target=do_connect, daemon=True).start()

    def _connect_openvpn(
        self, profile: VPNProfile, username: str | None, password: str | None
    ) -> tuple[bool, str]:
        try:
            # Kill any existing OpenVPN processes for this profile first
            logger.info(f"Cleaning up any existing OpenVPN processes for {profile.name}")
            subprocess.run(
                ["sudo", "pkill", "-f", f"openvpn.*{profile.name}"],
                check=False,
                timeout=5
            )
            
            # Wait for cleanup
            import time
            time.sleep(1)
            
            # Create log file for debugging
            log_file = self.VPN_DIR / f"openvpn_{profile.name}.log"
            
            # Write PID to a file that OpenVPN will create
            pid_file = self.PID_DIR / f"{profile.name}.pid"
            
            cmd = [
                "openvpn",
                "--config", str(profile.config_path),
                "--daemon",
                "--log", str(log_file),
                "--verb", "3",
                "--writepid", str(pid_file),  # Let OpenVPN write its own PID
            ]
            logger.info(f"Starting OpenVPN with log file: {log_file}")

            # Add auth-user-pass if credentials provided
            if username and password:
                # Create persistent auth file (only if it doesn't exist or needs update)
                auth_file = self.VPN_DIR / f".auth_{profile.name}"
                if not auth_file.exists():
                    auth_file.write_text(f"{username}\n{password}")
                    auth_file.chmod(0o600)
                cmd.extend(["--auth-user-pass", str(auth_file)])
            else:
                # Check if auth file already exists from previous connection
                auth_file = self.VPN_DIR / f".auth_{profile.name}"
                if auth_file.exists():
                    cmd.extend(["--auth-user-pass", str(auth_file)])

            # Add management interface for monitoring
            mgmt_socket = self.VPN_DIR / f".mgmt_{profile.name}.sock"
            # Remove old socket file if exists
            if mgmt_socket.exists():
                mgmt_socket.unlink()
            cmd.extend(["--management", str(mgmt_socket), "unix"])

            # Run with sudo if needed
            logger.info(f"Running OpenVPN command: {' '.join(cmd)}")
            result = subprocess.run(
                ["sudo"] + cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            logger.info(f"OpenVPN return code: {result.returncode}")
            if result.stdout:
                logger.info(f"OpenVPN stdout: {result.stdout}")
            if result.stderr:
                logger.warning(f"OpenVPN stderr: {result.stderr}")

            if result.returncode != 0:
                # Read log file for more details
                try:
                    if log_file.exists():
                        time.sleep(1)  # Wait for log to be written
                        # Use sudo to read log file since OpenVPN runs as root
                        log_result = subprocess.run(
                            ["sudo", "cat", str(log_file)],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if log_result.returncode == 0:
                            log_content = log_result.stdout
                            logger.error(f"OpenVPN log:\n{log_content[-2000:]}")  # Last 2000 chars
                        return False, f"OpenVPN failed. Check log: {log_file}"
                except Exception as e:
                    logger.error(f"Failed to read log: {e}")
                return False, f"OpenVPN failed: {result.stderr}"

            # Wait for daemon to start and write PID file
            logger.info("Waiting for OpenVPN daemon to start...")
            time.sleep(5)
            
            # Read PID from file that OpenVPN wrote
            if pid_file.exists():
                try:
                    pid = int(pid_file.read_text().strip())
                    logger.info(f"OpenVPN daemon started with PID: {pid}")
                    
                    # Check if process is running
                    is_running = self._is_process_running(pid)
                    logger.debug(f"Process running check: {is_running}")
                    
                    # Check log file for successful initialization
                    init_success = False
                    for attempt in range(10):  # Wait up to 10 seconds
                        try:
                            log_result = subprocess.run(
                                ["sudo", "grep", "-q", "Initialization Sequence Completed", str(log_file)],
                                timeout=2
                            )
                            if log_result.returncode == 0:
                                logger.info("OpenVPN initialization completed successfully!")
                                init_success = True
                                break
                        except Exception:
                            pass
                        
                        # Also check if process died
                        if not self._is_process_running(pid):
                            logger.error(f"OpenVPN process {pid} died during initialization")
                            break
                        
                        logger.debug(f"Waiting for OpenVPN initialization... (attempt {attempt+1}/10)")
                        time.sleep(1)
                    
                    if not init_success:
                        logger.error(f"OpenVPN failed to initialize properly")
                        if log_file.exists():
                            try:
                                log_result = subprocess.run(
                                    ["sudo", "tail", "-100", str(log_file)],
                                    capture_output=True,
                                    text=True,
                                    timeout=5
                                )
                                if log_result.returncode == 0:
                                    logger.error(f"OpenVPN log (last 100 lines):\n{log_result.stdout}")
                            except Exception as e:
                                logger.error(f"Failed to read log: {e}")
                        return False, f"OpenVPN initialization failed. Check log: {log_file}"
                    
                except Exception as e:
                    logger.error(f"Error checking OpenVPN status: {e}")
                    return False, f"Could not verify OpenVPN status: {e}"
            else:
                logger.warning("PID file not created by OpenVPN")
                # Check log file
                if log_file.exists():
                    try:
                        time.sleep(1)
                        log_result = subprocess.run(
                            ["sudo", "cat", str(log_file)],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if log_result.returncode == 0:
                            logger.error(f"OpenVPN log after failed start:\n{log_result.stdout[-2000:]}")
                    except Exception as e:
                        logger.error(f"Failed to read log: {e}")
                return False, f"OpenVPN PID file not created. Check log: {log_file}"

            return True, "Connected successfully"

        except subprocess.TimeoutExpired:
            logger.error("OpenVPN connection timeout")
            return False, "Connection timeout"
        except Exception as e:
            logger.error(f"OpenVPN error: {e}", exc_info=True)
            return False, f"OpenVPN error: {e}"

    def _connect_wireguard(self, profile: VPNProfile) -> tuple[bool, str]:
        try:
            # Use wg-quick for easy setup
            result = subprocess.run(
                ["sudo", "wg-quick", "up", str(profile.config_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return False, f"WireGuard failed: {result.stderr}"

            return True, "Connected successfully"

        except subprocess.TimeoutExpired:
            return False, "Connection timeout"
        except Exception as e:
            return False, f"WireGuard error: {e}"

    def disconnect(self, callback: Callable[[bool, str], None] | None = None) -> None:
        def do_disconnect():
            try:
                self._set_status(VPNStatus.DISCONNECTING, "Disconnecting...")
                self._should_monitor = False

                success, message = self._disconnect_sync()

                if success:
                    self._set_status(VPNStatus.DISCONNECTED, "Disconnected")
                    if callback:
                        GLib.idle_add(callback, True, message)
                else:
                    self._set_status(VPNStatus.ERROR, message)
                    if callback:
                        GLib.idle_add(callback, False, message)

            except Exception as e:
                logger.error(f"Disconnect failed: {e}")
                self._set_status(VPNStatus.ERROR, str(e))
                if callback:
                    GLib.idle_add(callback, False, f"Disconnect failed: {e}")

        Thread(target=do_disconnect, daemon=True).start()

    def _disconnect_sync(self) -> tuple[bool, str]:
        if not self._current_profile:
            return True, "Not connected"

        profile = self._current_profile

        try:
            import time
            
            # Get VPN interface name before disconnecting
            vpn_interface = "tun0" if profile.vpn_type == VPNType.OPENVPN else profile.name

            if profile.vpn_type == VPNType.OPENVPN:
                # Kill ALL OpenVPN processes for this profile to avoid conflicts
                try:
                    # First try to kill by PID file
                    pid_file = self.PID_DIR / f"{profile.name}.pid"
                    if pid_file.exists():
                        pid = int(pid_file.read_text().strip())
                        try:
                            subprocess.run(["sudo", "kill", str(pid)], check=True, timeout=5)
                        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                            subprocess.run(["sudo", "kill", "-9", str(pid)], check=False)
                        pid_file.unlink()
                    
                    # Also kill any remaining openvpn processes for this config
                    subprocess.run(
                        ["sudo", "pkill", "-f", f"openvpn.*{profile.name}"],
                        check=False,
                        timeout=5
                    )
                    
                    # Wait a bit for processes to die
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.warning(f"Error killing OpenVPN processes: {e}")

            else:  # WireGuard
                subprocess.run(
                    ["sudo", "wg-quick", "down", str(profile.config_path)],
                    capture_output=True,
                    check=False,
                )

            logger.info("Starting enhanced cleanup after VPN disconnect...")

            # 1. Remove split tunneling rules
            if profile.split_tunnel_enabled:
                self._remove_split_tunneling(profile)

            # 2. Flush routing cache for the VPN interface
            try:
                logger.info(f"Flushing routes for interface {vpn_interface}")
                subprocess.run(
                    ["sudo", "ip", "route", "flush", "dev", vpn_interface],
                    check=False,
                    timeout=3
                )
            except Exception as e:
                logger.warning(f"Failed to flush routes: {e}")

            # 3. Remove VPN interface if it still exists
            try:
                # Check if interface exists
                result = subprocess.run(
                    ["ip", "link", "show", vpn_interface],
                    capture_output=True,
                    timeout=2
                )
                if result.returncode == 0:
                    logger.info(f"Removing VPN interface {vpn_interface}")
                    subprocess.run(
                        ["sudo", "ip", "link", "delete", vpn_interface],
                        check=False,
                        timeout=3
                    )
            except Exception as e:
                logger.warning(f"Failed to remove interface: {e}")

            # 4. Flush DNS cache (systemd-resolved)
            try:
                logger.info("Flushing DNS cache")
                subprocess.run(
                    ["sudo", "resolvectl", "flush-caches"],
                    check=False,
                    timeout=3
                )
            except Exception as e:
                logger.warning(f"Failed to flush DNS cache: {e}")

            # 5. Clear connection tracking entries
            try:
                logger.info("Clearing conntrack entries")
                subprocess.run(
                    ["sudo", "conntrack", "-D"],
                    check=False,
                    timeout=3,
                    stderr=subprocess.DEVNULL  # Suppress "no entries" error
                )
            except Exception as e:
                logger.debug(f"Conntrack flush (optional): {e}")

            # 6. Flush ARP cache
            try:
                logger.info("Flushing ARP cache")
                subprocess.run(
                    ["sudo", "ip", "neigh", "flush", "all"],
                    check=False,
                    timeout=3
                )
            except Exception as e:
                logger.warning(f"Failed to flush ARP cache: {e}")

            # 7. Restore DNS settings (do this after DNS flush)
            self._restore_dns_state()
            
            # 8. Restart systemd-resolved to ensure clean DNS state
            try:
                logger.info("Restarting systemd-resolved")
                subprocess.run(
                    ["sudo", "systemctl", "restart", "systemd-resolved"],
                    check=False,
                    timeout=5
                )
                time.sleep(0.5)  # Wait for service to restart
            except Exception as e:
                logger.warning(f"Failed to restart systemd-resolved: {e}")

            # 9. Wait a bit for everything to settle
            time.sleep(1)

            # 10. Verify DNS is working
            try:
                logger.info("Verifying DNS connectivity...")
                test_domains = ["google.com", "api.github.com", "1.1.1.1"]
                dns_ok = False
                
                for domain in test_domains:
                    result = subprocess.run(
                        ["nslookup", domain],
                        capture_output=True,
                        timeout=3
                    )
                    if result.returncode == 0:
                        logger.info(f"DNS verification OK: {domain}")
                        dns_ok = True
                        break
                
                if not dns_ok:
                    logger.warning("DNS verification failed, trying one more flush...")
                    subprocess.run(
                        ["sudo", "resolvectl", "flush-caches"],
                        check=False,
                        timeout=3
                    )
                    time.sleep(0.5)
            except Exception as e:
                logger.warning(f"DNS verification warning: {e}")

            logger.info("VPN cleanup completed successfully")
            self._current_profile = None
            return True, "Disconnected successfully"

        except Exception as e:
            logger.error(f"Disconnect error: {e}", exc_info=True)
            return False, f"Disconnect error: {e}"

    def _save_dns_state(self) -> None:
        try:
            resolv_conf = Path("/etc/resolv.conf")
            if resolv_conf.exists():
                self._original_resolv_conf = resolv_conf.read_text()

            # Also try to get DNS from NetworkManager
            result = subprocess.run(
                ["nmcli", "-t", "-f", "IP4.DNS", "device", "show"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                dns_lines = [
                    line.split(":")[1]
                    for line in result.stdout.splitlines()
                    if line.startswith("IP4.DNS")
                ]
                self._original_dns = dns_lines

        except Exception as e:
            logger.error(f"Failed to save DNS state: {e}")

    def _restore_dns_state(self) -> None:
        try:
            if self._original_resolv_conf:
                # Use resolvconf or direct write
                subprocess.run(
                    ["sudo", "bash", "-c", f'echo "{self._original_resolv_conf}" > /etc/resolv.conf'],
                    check=False,
                )
        except Exception as e:
            logger.error(f"Failed to restore DNS state: {e}")

    def _apply_dns_settings(self, profile: VPNProfile) -> None:
        """Apply DNS settings based on profile configuration."""
        if profile.dns_mode == DNSMode.SYSTEM_DNS:
            # Keep system DNS, restore original
            self._restore_dns_state()

        elif profile.dns_mode == DNSMode.CUSTOM_DNS and profile.custom_dns:
            # Apply custom DNS
            try:
                dns_content = "\n".join(
                    f"nameserver {dns}" for dns in profile.custom_dns
                )
                subprocess.run(
                    ["sudo", "bash", "-c", f'echo "{dns_content}" > /etc/resolv.conf'],
                    check=True,
                )
            except Exception as e:
                logger.error(f"Failed to apply custom DNS: {e}")

        # DNSMode.VPN_DNS - let VPN handle DNS (default behavior)

    def _apply_split_tunneling(self, profile: VPNProfile) -> None:
        try:
            # Get VPN interface
            if profile.vpn_type == VPNType.WIREGUARD:
                iface = profile.name
            else:
                # For OpenVPN, typically tun0
                iface = "tun0"

            # Mark packets from specific apps/IPs to bypass VPN
            for ip in profile.split_tunnel_ips:
                # Add route to bypass VPN for specific IPs
                subprocess.run(
                    ["sudo", "ip", "route", "add", ip, "via", "default"],
                    check=False,
                )

            # For app-based split tunneling, we'd need cgroups or iptables marking
            # This is a simplified implementation
            logger.info(f"Split tunneling applied for {len(profile.split_tunnel_ips)} IPs")

        except Exception as e:
            logger.error(f"Failed to apply split tunneling: {e}")

    def _remove_split_tunneling(self, profile: VPNProfile) -> None:
        try:
            for ip in profile.split_tunnel_ips:
                subprocess.run(
                    ["sudo", "ip", "route", "del", ip],
                    check=False,
                )
        except Exception as e:
            logger.error(f"Failed to remove split tunneling: {e}")

    def _start_monitor(self) -> None:
        self._should_monitor = True

        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        self._monitor_thread = Thread(target=self._monitor_connection, daemon=True)
        self._monitor_thread.start()
        logger.info("VPN connection monitor started")

    def _monitor_connection(self) -> None:
        import time

        # Wait a bit before first check to let VPN establish
        time.sleep(3)
        logger.info("VPN monitor: Starting connection checks")

        while self._should_monitor:
            time.sleep(5)

            if not self._current_profile:
                logger.info("VPN monitor: No current profile, stopping")
                break

            is_connected = self._is_vpn_connected()
            logger.debug(f"VPN monitor: Connection check result: {is_connected}")

            if not is_connected:
                logger.warning("VPN connection lost")

                if self._reconnect_attempts < self._max_reconnect_attempts:
                    self._reconnect_attempts += 1
                    self._set_status(
                        VPNStatus.RECONNECTING,
                        f"Reconnecting (attempt {self._reconnect_attempts}/{self._max_reconnect_attempts})...",
                    )

                    time.sleep(self._reconnect_delay)

                    # Try to reconnect
                    profile = self._current_profile
                    creds = self.get_credentials(profile.name)
                    username, password = creds if creds else (None, None)

                    # If no credentials in keyring, check for existing auth file
                    if not username and not password and profile.vpn_type == VPNType.OPENVPN:
                        auth_file = self.VPN_DIR / f".auth_{profile.name}"
                        if auth_file.exists():
                            try:
                                auth_content = auth_file.read_text().strip().split('\n')
                                if len(auth_content) >= 2:
                                    username, password = auth_content[0], auth_content[1]
                                    logger.info(f"Using existing auth file for reconnection")
                            except Exception as e:
                                logger.error(f"Failed to read auth file: {e}")

                    if profile.vpn_type == VPNType.OPENVPN:
                        success, _ = self._connect_openvpn(profile, username, password)
                    else:
                        success, _ = self._connect_wireguard(profile)

                    if success:
                        self._reconnect_attempts = 0
                        self._set_status(VPNStatus.CONNECTED, "Reconnected")
                else:
                    self._set_status(VPNStatus.ERROR, "Max reconnection attempts reached")
                    self._should_monitor = False

    def _is_vpn_connected(self) -> bool:
        if not self._current_profile:
            return False

        profile = self._current_profile

        if profile.vpn_type == VPNType.OPENVPN:
            # Check for tun interface instead of just PID
            # This is more reliable as the interface exists only when connected
            try:
                result = subprocess.run(
                    ["ip", "link", "show"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                # Check if tun0 or tun1 interface exists
                has_tun_interface = "tun0" in result.stdout or "tun1" in result.stdout
                
                if not has_tun_interface:
                    logger.debug("No tun interface found, VPN not connected")
                    return False
                
                # Also check if process is running
                pid_file = self.PID_DIR / f"{profile.name}.pid"
                if pid_file.exists():
                    try:
                        pid = int(pid_file.read_text().strip())
                        is_running = self._is_process_running(pid)
                        logger.debug(f"OpenVPN PID {pid} running: {is_running}")
                        return is_running
                    except Exception as e:
                        logger.debug(f"Error checking PID: {e}")
                        # If PID check fails but interface exists, assume connected
                        return has_tun_interface
                
                # Interface exists but no PID file - might be starting up
                logger.debug("TUN interface exists but no PID file yet")
                return has_tun_interface
                
            except Exception as e:
                logger.error(f"Error checking VPN connection: {e}")
                return False

        else:  # WireGuard
            try:
                result = subprocess.run(
                    ["wg", "show", "interfaces"],
                    capture_output=True,
                    text=True,
                )
                return profile.name in result.stdout
            except Exception:
                return False

    def update_profile_settings(
        self,
        profile_name: str,
        dns_mode: DNSMode | None = None,
        custom_dns: list[str] | None = None,
        split_tunnel_enabled: bool | None = None,
        split_tunnel_ips: list[str] | None = None,
        auto_connect: bool | None = None,
    ) -> bool:
        if profile_name not in self._profiles:
            return False

        profile = self._profiles[profile_name]

        if dns_mode is not None:
            profile.dns_mode = dns_mode
        if custom_dns is not None:
            profile.custom_dns = custom_dns
        if split_tunnel_enabled is not None:
            profile.split_tunnel_enabled = split_tunnel_enabled
        if split_tunnel_ips is not None:
            profile.split_tunnel_ips = split_tunnel_ips
        if auto_connect is not None:
            profile.auto_connect = auto_connect

        self._save_profiles()
        return True

    def get_connection_info(self) -> dict | None:
        if not self._current_profile or self._status != VPNStatus.CONNECTED:
            return None

        info = {
            "profile_name": self._current_profile.name,
            "vpn_type": self._current_profile.vpn_type.value,
            "status": self._status.value,
            "dns_mode": self._current_profile.dns_mode.value,
        }

        # Try to get IP address
        try:
            result = subprocess.run(
                ["curl", "-s", "ifconfig.me"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                info["public_ip"] = result.stdout.strip()
        except Exception:
            pass

        return info


# Singleton instance
_vpn_service: VPNService | None = None


def get_vpn_service() -> VPNService:
    global _vpn_service
    if _vpn_service is None:
        _vpn_service = VPNService()
    return _vpn_service
