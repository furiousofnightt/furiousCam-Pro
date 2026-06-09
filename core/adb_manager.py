import os
import subprocess
import time
import logging
import random

logger = logging.getLogger(__name__)

class AdbManager:
    def __init__(self, adb_path: str, server_jar_path: str):
        self.adb_path = adb_path
        self.server_jar_path = server_jar_path
        self.device_serial = None
        self.local_port = 27183
        self.scid = -1
        self.socket_name = "scrcpy"
        self.fallback_used = False  # Track if we fell back to screen mirror

    def run_adb(self, *args, check=True) -> subprocess.CompletedProcess:
        cmd = [self.adb_path]
        if self.device_serial:
            cmd.extend(["-s", self.device_serial])
        cmd.extend(args)
        logger.debug(f"Running ADB: {' '.join(cmd)}")
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return subprocess.run(cmd, capture_output=True, text=True, check=check, startupinfo=si)

    def start_server(self):
        """Ensures ADB server is running."""
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run([self.adb_path, "start-server"], startupinfo=si)
            logger.info("ADB Server started.")
        except Exception as e:
            logger.error(f"Failed to start ADB server: {e}")

    def wait_for_device(self) -> bool:
        """Waits for a device to be connected and authorized.
        USB devices (no ':' in serial) always take priority over Wi-Fi/TCP devices."""
        logger.info("Waiting for device...")
        for _ in range(5):  # 5 seconds timeout (was 10)
            result = self.run_adb("devices", check=False)
            lines = result.stdout.strip().split('\n')[1:]
            
            usb_devices = []
            wifi_devices = []
            for line in lines:
                if 'device' in line and 'unauthorized' not in line and 'offline' not in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        serial = parts[0]
                        # ':' in serial means TCP/WiFi (e.g. "192.168.0.6:5555")
                        if ':' in serial:
                            wifi_devices.append(serial)
                        else:
                            usb_devices.append(serial)
            
            # USB always takes priority
            if usb_devices:
                self.device_serial = usb_devices[0]
                logger.info(f"Device found (USB): {self.device_serial}")
                return True
            elif wifi_devices:
                self.device_serial = wifi_devices[0]
                logger.info(f"Device found (Wi-Fi): {self.device_serial}")
                return True
            
            time.sleep(1)
        logger.error("No authorized device found.")
        return False

    def push_server(self) -> bool:
        """Pushes the server jar to the device with retry logic for EOF errors."""
        remote_path = "/data/local/tmp/furious-core.jar"
        logger.info(f"Pushing {self.server_jar_path} to {remote_path}...")
        
        for attempt in range(2):
            try:
                result = self.run_adb("push", self.server_jar_path, remote_path, check=False)
                
                # Check if file was actually pushed (output contains "pushed" or "skipped")
                if "pushed" in result.stdout.lower() or "skipped" in result.stdout.lower():
                    # Even if there's EOF error in stderr, if file was pushed, consider it success
                    time.sleep(0.5)  # Give device time to sync filesystem
                    return True
                elif "EOF" in result.stderr or result.returncode != 0:
                    if attempt == 0:
                        logger.warning(f"Push attempt 1 failed with EOF/error, retrying...")
                        time.sleep(1)
                        continue
                    else:
                        logger.error(f"Failed to push server after 2 attempts: {result.stderr}")
                        return False
                else:
                    return True
                    
            except subprocess.CalledProcessError as e:
                if attempt == 0:
                    logger.warning(f"Push attempt 1 failed: {e.stderr}, retrying...")
                    time.sleep(1)
                    continue
                else:
                    logger.error(f"Failed to push server after 2 attempts: {e.stderr}")
                    return False
        
        return False

    def get_device_ip(self) -> str | None:
        """Attempts to find the device's local IP address."""
        if not self.device_serial:
            return None
            
        ip = None
        # Try ip route
        res = self.run_adb("shell", "ip", "route", check=False)
        if res.stdout:
            import re
            match = re.search(r'src\s+(192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(?:1[6-9]|2[0-9]|3[0-1])\.\d+\.\d+)', res.stdout)
            if match:
                ip = match.group(1)
                
        if not ip:
            # Fallback to ip addr show
            res = self.run_adb("shell", "ip", "-f", "inet", "addr", "show", check=False)
            if res.stdout:
                import re
                matches = re.findall(r'inet\s+(192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(?:1[6-9]|2[0-9]|3[0-1])\.\d+\.\d+)', res.stdout)
                if matches:
                    ip = matches[0] if isinstance(matches[0], str) else matches[0][0]
                    
        return ip

    def enable_tcpip(self) -> bool:
        """Enables ADB over TCP on port 5555."""
        try:
            self.run_adb("tcpip", "5555")
            logger.info("ADB TCP/IP enabled on port 5555.")
            return True
        except Exception as e:
            logger.error(f"Failed to enable tcpip: {e}")
            return False

    def connect_direct_ip(self, ip_with_port: str) -> bool:
        """Connects ADB directly to an IP."""
        if ":" not in ip_with_port:
            ip_with_port += ":5555"
            
        res = self.run_adb("connect", ip_with_port, check=False)
        out = res.stdout.lower()
        
        if "connected to" in out or "already connected" in out or "failed to authenticate" in out:
            self.device_serial = ip_with_port  # Updates current device serial to the IP
            logger.info(f"Connected to Wi-Fi device: {ip_with_port}")
            return True
            
        logger.error(f"Failed to connect to Wi-Fi device: {out}")
        return False

    def disconnect_ip(self, ip_with_port: str):
        """Disconnects an IP device."""
        self.run_adb("disconnect", ip_with_port, check=False)
        if self.device_serial == ip_with_port:
            self.device_serial = None
        logger.info(f"Disconnected Wi-Fi device: {ip_with_port}")

    def disconnect_all(self):
        """Disconnects all TCP/IP devices."""
        self.run_adb("disconnect", check=False)
        logger.info("Disconnected all TCP/IP devices.")

    def _grant_audio_permission(self):
        """Concede RECORD_AUDIO ao processo shell via ADB. Compatível com Android 11-15."""
        # Método 1: appops por UID (mais confiável, funciona no Android 14/15)
        # UID 2000 = shell user, que é o contexto que roda o nosso servidor Java
        try:
            res = self.run_adb(
                "shell", "cmd", "appops", "set", "--uid", "2000",
                "RECORD_AUDIO", "allow",
                check=False
            )
            logger.info(f"[Áudio] appops RECORD_AUDIO UID-2000: {res.stdout.strip() or 'OK'} | stderr: {res.stderr.strip() or '-'}")
        except Exception as e:
            logger.debug(f"[Áudio] appops uid falhou: {e}")

        # Método 2: pm grant como fallback (Android 11-13)
        try:
            self.run_adb(
                "shell", "pm", "grant", "com.android.shell",
                "android.permission.RECORD_AUDIO",
                check=False
            )
        except Exception:
            pass

    def setup_port_forward(self) -> bool:
        """Clears stale forwards, generates a new socket name, and sets up fresh adb forward."""
        try:
            # Generate a new random SCID to prevent "Address already in use" on Android socket during hot-swaps
            self.scid = f"{random.randint(0, 0x7FFFFFFF):08x}"
            self.socket_name = f"scrcpy_{self.scid}"
            
            # Remove stale forward first (ignore errors)
            self.run_adb("forward", "--remove", f"tcp:{self.local_port}", check=False)
            self.run_adb("forward", f"tcp:{self.local_port}", f"localabstract:{self.socket_name}")
            logger.info(f"Port forwarded: tcp:{self.local_port} -> localabstract:{self.socket_name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to forward port: {e.stderr}")
            return False

    def launch_android_server(self, camera_id=0, width=1920, height=1080, fps=30, bitrate=8000000, force_fps=True, audio_enabled=False):
        """Launches the scrcpy-style server on Android in CAMERA mode."""
        self.fallback_used = False  # Reset fallback flag for new connection
        logger.info(f"Launching server in CAMERA mode (cam={camera_id}, {width}x{height}@{fps}fps, force_fps={force_fps})...")
        
        cmd = [
            "shell",
            "CLASSPATH=/data/local/tmp/furious-core.jar",
            "app_process", "/", "com.genymobile.scrcpy.Server",
            "3.3.4",
            "tunnel_forward=true",
            f"audio={'true' if audio_enabled else 'false'}",
            "audio_source=mic",
            "control=false",
            "cleanup=true",
            f"scid={self.scid}",
            "send_dummy_byte=true",
            "send_device_meta=false",
            "send_codec_meta=true",
            "send_frame_meta=true",
            "video=true",
            f"video_source=camera",
            f"camera_facing={'back' if camera_id == 0 else 'front'}",
            f"max_size={max(width, height)}",
            f"video_bit_rate={bitrate}",
        ]
        
        cmd.append(f"max_fps={fps}")
        
        if force_fps:
            cmd.append(f"camera_fps={fps}")
        
        full_cmd = [self.adb_path]
        if self.device_serial:
            full_cmd.extend(["-s", self.device_serial])
        full_cmd.extend(cmd)
        
        if audio_enabled:
            self._grant_audio_permission()
        
        logger.debug(f"Server launch cmd: {' '.join(full_cmd)}")
        self.server_process = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        time.sleep(1.5)  # give server time to start
        
        # Check if server immediately died
        if self.server_process.poll() is not None:
            stderr = self.server_process.stderr.read().decode('utf-8', 'ignore')
            logger.error(f"Server died immediately! stderr: {stderr}")
            # Fallback to screen mode if camera mode fails
            logger.warning("Camera mode failed, falling back to screen mirroring...")
            return self._launch_screen_fallback()
        
        return True

    def launch_android_server_camera_only(
        self, camera_id=0, width=1920, height=1080, fps=30, bitrate=8000000, force_fps=True, audio_enabled=False
    ) -> bool:
        """Like launch_android_server but NEVER falls back to screen. Used for hot-swap."""
        logger.info(f"Launching CAMERA-ONLY server (cam={camera_id}, {width}x{height}@{fps}fps, force_fps={force_fps})...")
        cmd = [
            "shell",
            "CLASSPATH=/data/local/tmp/furious-core.jar",
            "app_process", "/", "com.genymobile.scrcpy.Server",
            "3.3.4",
            "tunnel_forward=true",
            f"audio={'true' if audio_enabled else 'false'}",
            "audio_source=mic",
            "control=false",
            "cleanup=true",
            f"scid={self.scid}",
            "send_dummy_byte=true",
            "send_device_meta=false",
            "send_codec_meta=true",
            "send_frame_meta=true",
            "video=true",
            f"video_source=camera",
            f"camera_facing={'back' if camera_id == 0 else 'front'}",
            f"max_size={max(width, height)}",
            f"video_bit_rate={bitrate}",
        ]
        
        cmd.append(f"max_fps={fps}")
            
        if force_fps:
            cmd.append(f"camera_fps={fps}")
        full_cmd = [self.adb_path]
        if self.device_serial:
            full_cmd.extend(["-s", self.device_serial])
        full_cmd.extend(cmd)

        if audio_enabled:
            self._grant_audio_permission()
        
        self.server_process = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        time.sleep(1.5)

        if self.server_process.poll() is not None:
            stderr = self.server_process.stderr.read().decode('utf-8', 'ignore').strip()
            logger.error(f"Camera-only server died: {stderr}")
            return False

        return True

    def _launch_screen_fallback(self):
        """Fallback to screen mirroring if camera mode is unsupported."""
        self.fallback_used = True  # Mark that we're using screen mirror fallback
        logger.info("Launching server in SCREEN MIRROR fallback mode...")
        cmd = [
            "shell",
            "CLASSPATH=/data/local/tmp/furious-core.jar",
            "app_process", "/", "com.genymobile.scrcpy.Server",
            "3.3.4",
            "tunnel_forward=true",
            "audio=false",
            "control=false",
            "cleanup=true",
            f"scid={self.scid}",
            "send_dummy_byte=true",
            "send_device_meta=false",
            "send_codec_meta=true",
            "send_frame_meta=true",
        ]
        full_cmd = [self.adb_path]
        if self.device_serial:
            full_cmd.extend(["-s", self.device_serial])
        full_cmd.extend(cmd)
        
        self.server_process = subprocess.Popen(
            full_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        time.sleep(1)
        return True

    def cleanup(self):
        """Removes port forwarding and kills server."""
        if hasattr(self, 'server_process') and self.server_process:
            try:
                self.server_process.terminate()
            except:
                pass
        if self.device_serial:
            try:
                self.run_adb("forward", "--remove", f"tcp:{self.local_port}", check=False)
            except:
                pass

    def cleanup_server_on_device(self):
        """Forces the scrcpy server to stop gracefully to immediately free the camera."""
        if not self.device_serial:
            return
        
        # 1. Wait briefly for scrcpy to exit naturally (since we closed its sockets)
        for _ in range(3):
            time.sleep(0.5)
            if not self.run_adb("shell", "pgrep", "-f", "scrcpy", check=False).stdout.strip():
                logger.info("Server exited gracefully.")
                return

        # 2. Send SIGTERM (allows scrcpy to call CameraDevice.close())
        logger.info("Sending SIGTERM to server on device...")
        self.run_adb("shell", "pkill", "-f", "scrcpy", check=False)
        for _ in range(4):
            time.sleep(0.5)
            if not self.run_adb("shell", "pgrep", "-f", "scrcpy", check=False).stdout.strip():
                logger.info("Server exited after SIGTERM.")
                return
                
        # 3. Fallback to SIGKILL (this will cause a 5s Camera HAL lock)
        logger.warning("Server ignoring SIGTERM, forcing SIGKILL...")
        self.run_adb("shell", "pkill", "-9", "-f", "scrcpy", check=False)
        self.run_adb("shell", "killall", "-9", "app_process", check=False)

    def stop_adb_server(self):
        """Kills the ADB server completely to free all resources."""
        try:
            logger.info("Stopping ADB server...")
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run([self.adb_path, "kill-server"], check=False, startupinfo=si)
            logger.info("ADB server stopped.")
        except Exception as e:
            logger.error(f"Failed to stop ADB server: {e}")
