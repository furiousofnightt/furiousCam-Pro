import threading
import os
import time
import logging
import numpy as np
from PySide6.QtCore import QObject, Signal
from .adb_manager import AdbManager
from decoder.video_receiver import VideoReceiver
from decoder.audio_receiver import AudioReceiver

logger = logging.getLogger(__name__)

class AppCore(QObject):
    connection_status = Signal(str)
    stats_updated = Signal(dict)
    camera_swapped = Signal()  # Fired when hot-swap completes, UI must reset render state
    stream_info_ui = Signal(int, int)  # width, height — fires on first frame metadata
    show_warning = Signal(str, str)  # title, message — shows a warning dialog
    audio_level = Signal(int)        # Nível de áudio (0 a 100) para a UI

    def __init__(self, base_path):
        super().__init__()
        self.base_path = base_path

        adb_path = os.path.join(base_path, "portables", "adb", "adb.exe")
        jar_path = os.path.join(base_path, "portables", "adb", "furious-core.jar")

        self.adb_manager = AdbManager(adb_path, jar_path)
        self.video_receiver = VideoReceiver(port=self.adb_manager.local_port)
        self.video_receiver.error_occurred.connect(self._handle_video_error)
        self.video_receiver.stream_info.connect(self._on_stream_info)

        # Áudio (Incremental)
        self._audio_enabled = False # Será ativado no próximo passo via UI/config
        self._audio_device = None
        self._audio_monitoring = False
        self._audio_noise_reduction = False
        self.audio_receiver = AudioReceiver(port=self.adb_manager.local_port)

        self.worker_thread = None
        self.running = False
        self.wifi_fallback_ip = None  # WiFi IP to try if USB fails

        # Reconnection State
        self._reconnecting = False
        self._reconnect_thread = None
        self._reconnect_attempts = 0
        self._is_wireless_last = False
        self._last_device_ip = None

        # Camera settings
        self.camera_id = 0
        self.fps = 30
        self.bitrate = 8_000_000
        self.width = 1920
        self.height = 1080
        self.camera_mode = True
        self.rotation = 0  # 0, 90, 180, 270
        self.is_mirrored = True

        # Live stats state
        self._last_fps_time = 0.0
        self._resolution = "---"
        self._source_mode = "Camera"
        self._stats_thread = None
        self._stats_log_ticks = 0      # Contador de ticks para log periódico (30s)
        self._session_start_time = 0.0 # Timestamp de início da sessão
        self._session_total_frames = 0 # Total de frames na sessão atual

        # OBS Virtual Camera
        self._virtual_cam = None
        self._virtual_cam_enabled = False
        self._virtual_cam_thread = None

        # Wi-Fi override: quando definido, a rotina de conexão usa esse serial
        # diretamente, pulando o reset TCP e o wait_for_device USB.
        self._force_wifi_serial: str | None = None

    # ─────────────────────────────
    #  Settings
    # ─────────────────────────────
    def set_audio_enabled(self, enabled: bool):
        self._audio_enabled = enabled

    def set_noise_reduction(self, enabled: bool):
        """Ativa/desativa a redução de ruído no AudioReceiver (thread-safe)."""
        self._audio_noise_reduction = enabled
        if hasattr(self, 'audio_receiver'):
            self.audio_receiver.set_noise_reduction(enabled)

    def set_monitoring(self, enabled: bool):
        """Ativa/desativa o monitoramento de áudio local no PC."""
        self._audio_monitoring = enabled
        if hasattr(self, 'audio_receiver'):
            self.audio_receiver.set_monitoring(enabled)

    def set_audio_device(self, device):
        self._audio_device = device
        if hasattr(self, 'audio_receiver'):
            self.audio_receiver.set_audio_device(device)

    def set_camera(self, camera_id: int):
        self.camera_id = camera_id

    def set_fps(self, fps: int):
        self.fps = fps

    def set_bitrate(self, bitrate: int):
        self.bitrate = bitrate

    def set_resolution(self, width: int, height: int):
        self.width = width
        self.height = height

    def set_rotation(self, degrees: int):
        """Set frame rotation: 0, 90, 180, or 270."""
        self.rotation = degrees % 360

    @property
    def effective_rotation(self) -> int:
        """Returns the rotation including the base sensor offset for the selected camera.
        Optimized so that 0° means the phone is held vertically upwards."""
        base_offset = 270 if self.camera_id == 0 else 90
        return (self.rotation + base_offset) % 360

    def set_mirrored(self, mirrored: bool):
        """Set whether the output image is horizontally mirrored."""
        self.is_mirrored = mirrored

    def switch_camera_live(self, camera_id: int):
        """Hot-swap camera while stream is active — no full reconnect needed."""
        if not self.running:
            return
        logger.info(f"Hot-swapping to camera {camera_id}...")
        self.camera_id = camera_id

        # Run in background to avoid freezing the UI thread
        threading.Thread(target=self._hot_swap_routine, daemon=True).start()

    def _hot_swap_routine(self):
        """Background thread for clean camera hot-swap. 
        Acts exactly like a manual 'Stop' and 'Start' to guarantee 100% success rate,
        while keeping the OBS virtual camera alive so the stream doesn't drop.
        """
        logger.info("Executando troca de câmera (Parar -> Aguardar -> Iniciar)...")
        self.connection_status.emit("Encerrando conexão atual...")
        
        # 1. Parar a conexão atual de forma idêntica ao botão 'Parar', 
        # MAS sem desligar a virtual cam (para o OBS não piscar preto)
        self.running = False
        self.video_receiver.stop()
        self.audio_receiver.stop()
        self.adb_manager.cleanup()
        self.adb_manager.cleanup_server_on_device()
        
        # 2. Aguardar 1.2 segundos. 
        # O Android já teve um tempo na função cleanup_server_on_device. 
        # 1.2s costuma ser o sweet-spot para a maioria dos aparelhos liberar a lente.
        self.connection_status.emit("Aguardando liberação da lente pelo Android...")
        time.sleep(1.2)
        
        # 3. Recriar o VideoReceiver zerado
        self.video_receiver = VideoReceiver(port=self.adb_manager.local_port)
        self.video_receiver.error_occurred.connect(self._handle_video_error)
        self.video_receiver.stream_info.connect(self._on_stream_info)
        self.video_receiver.frame_count = 0
        
        self.audio_receiver.stop()
        if self._audio_enabled:
            self.audio_receiver = AudioReceiver(port=self.adb_manager.local_port)
            self.audio_receiver.audio_level.connect(self.audio_level)
            
            # Restaura configurações de áudio para o novo receiver
            if self._audio_device is not None:
                self.audio_receiver.set_audio_device(self._audio_device)
            if self._audio_noise_reduction:
                self.audio_receiver.set_noise_reduction(True)
            if self._audio_monitoring:
                self.audio_receiver.set_monitoring(True)

        # 4. Reiniciar threads de conexão e stats (exatamente como start_connection)
        self.running = True
        self._last_fps_time = time.time()
        self.connection_status.emit("Reconectando...")
        self.worker_thread = threading.Thread(target=self._connection_routine, daemon=True)
        self.worker_thread.start()
        self._stats_thread = threading.Thread(target=self._stats_loop, daemon=True)
        self._stats_thread.start()

        # 5. Avisar a UI que terminou
        self.camera_swapped.emit()


    # ─────────────────────────────
    #  Stream info callback
    # ─────────────────────────────
    def _on_stream_info(self, info: dict):
        # Use the user-configured resolution for display (e.g. 1920x1080).
        # The raw stream may be slightly taller (e.g. 1088) due to H.264 requiring
        # dimensions to be multiples of 16 — that padding is invisible.
        self._resolution = f"{self.width}x{self.height}"
        self._source_mode = info.get('source', 'Camera')
        # Pass width/height so UI can auto-rotate portrait streams
        self.stream_info_ui.emit(info.get('width', 0), info.get('height', 0))

    # ─────────────────────────────
    #  OBS Virtual Camera
    # ─────────────────────────────
    def enable_virtual_cam(self, width: int = None, height: int = None) -> bool:
        """Start pushing frames into OBS Virtual Camera."""
        try:
            from obs.virtual_cam import VirtualCamOutput
        except ImportError:
            logger.error("obs module not found.")
            return False

        if self._virtual_cam is not None and self._virtual_cam.is_running:
            logger.warning("Virtual cam already running.")
            return True

        # Infer output resolution from the actual decoded frame if available.
        if width is None or height is None:
            latest = self.video_receiver.latest_frame
            if latest is not None:
                frame_h, frame_w = latest.shape[:2]
                if self.effective_rotation in (90, 270):
                    frame_w, frame_h = frame_h, frame_w
                w = frame_w if width is None else width
                h = frame_h if height is None else height
            else:
                parts = self._resolution.split("x") if "x" in self._resolution else []
                w = int(parts[0]) if len(parts) == 2 else (width or 1280)
                h = int(parts[1]) if len(parts) == 2 else (height or 720)
        else:
            w = width
            h = height

        self._virtual_cam = VirtualCamOutput(width=w, height=h, fps=self.fps)
        ok = self._virtual_cam.start()
        if ok:
            self._virtual_cam_enabled = True
            self._virtual_cam_thread = threading.Thread(
                target=self._virtual_cam_loop, daemon=True
            )
            self._virtual_cam_thread.start()
            logger.info("OBS Virtual Camera output started.")
        else:
            self.connection_status.emit("Erro: OBS Virtual Camera não disponível.")
        return ok

    def disable_virtual_cam(self):
        """Stop pushing frames into OBS Virtual Camera."""
        self._virtual_cam_enabled = False
        if self._virtual_cam:
            self._virtual_cam.stop()
            self._virtual_cam = None
        logger.info("OBS Virtual Camera output stopped.")

    def _virtual_cam_loop(self):
        """Sends the latest decoded frame to OBS virtual camera.
        Timing is controlled manually via frame diffing to prevent GIL deadlocks.
        latest_frame is already a numpy RGB array — safe to access cross-thread.
        """
        last_frame_count = -1
        while self._virtual_cam_enabled and self._virtual_cam:
            img_rgb = self.video_receiver.latest_frame
            current_count = self.video_receiver.frame_count
            
            if img_rgb is not None and current_count != last_frame_count:
                last_frame_count = current_count
                
                # Apply effective rotation to virtual cam
                rot = self.effective_rotation
                if rot == 90:
                    img_rgb = np.rot90(img_rgb, k=1)
                elif rot == 180:
                    img_rgb = np.rot90(img_rgb, k=2)
                elif rot == 270:
                    img_rgb = np.rot90(img_rgb, k=3)

                if self.is_mirrored:
                    img_rgb = np.fliplr(img_rgb)
                    
                if not img_rgb.flags['C_CONTIGUOUS']:
                    img_rgb = np.ascontiguousarray(img_rgb)

                try:
                    self._virtual_cam.send_frame(img_rgb)
                except Exception as e:
                    logger.error(f"Virtual cam frame error: {e}")
            else:
                time.sleep(0.01)

    # ─────────────────────────────
    #  Connection lifecycle
    # ─────────────────────────────
    def start_connection(self):
        self.running = True
        self._last_fps_time = time.time()
        self._session_start_time = time.time()
        self._session_total_frames = 0
        self._stats_log_ticks = 0

        # Recreate receivers to clear any stale socket state from previous session
        self.video_receiver.stop()
        self.video_receiver = VideoReceiver(port=self.adb_manager.local_port)
        self.video_receiver.error_occurred.connect(self._handle_video_error)
        self.video_receiver.stream_info.connect(self._on_stream_info)
        self.video_receiver.frame_count = 0
        
        self.audio_receiver.stop()
        if self._audio_enabled:
            self.audio_receiver = AudioReceiver(port=self.adb_manager.local_port)
            self.audio_receiver.audio_level.connect(self.audio_level)
            
            # Restaura configurações de áudio para o novo receiver
            if self._audio_device is not None:
                self.audio_receiver.set_audio_device(self._audio_device)
            if self._audio_noise_reduction:
                self.audio_receiver.set_noise_reduction(True)
            if self._audio_monitoring:
                self.audio_receiver.set_monitoring(True)

        self.worker_thread = threading.Thread(target=self._connection_routine, daemon=True)
        self.worker_thread.start()
        self._stats_thread = threading.Thread(target=self._stats_loop, daemon=True)
        self._stats_thread.start()

    def _connection_routine(self):
        try:
            self.connection_status.emit("Iniciando ADB...")
            self.adb_manager.start_server()

            if not self.running: return

            # Se o WifiManager já estabeleceu uma conexão Wi-Fi diretamente,
            # usamos o serial pré-estabelecido e pulamos o reset TCP + USB discovery.
            if self._force_wifi_serial:
                wifi_serial = self._force_wifi_serial
                self._force_wifi_serial = None  # Limpa a flag após o uso
                logger.info(f"Wi-Fi serial pré-estabelecido: {wifi_serial}. Pulando USB discovery.")
                self.adb_manager.device_serial = wifi_serial
                self.connection_status.emit(f"Usando conexão Wi-Fi: {wifi_serial}")
            else:
                # Limpar qualquer conexão TCP/WiFi residual no ADB antes de tentar USB.
                # Quando o app conecta via WiFi e o usuário para/reinicia, o ADB mantém
                # o device TCP ativo internamente. Isso impede a detecção correta do USB.
                logger.info("Limpando conexões TCP residuais...")
                self.adb_manager.disconnect_all()

                logger.info("Step 1: Tentando conectar via USB...")
                if not self.adb_manager.wait_for_device():
                    # USB não encontrado. Tentar WiFi fallback se disponível.
                    logger.info(f"Step 2: USB falhou. WiFi fallback IP: {self.wifi_fallback_ip}")
                    if self.wifi_fallback_ip:
                        logger.info(f"Step 3: Tentando WiFi fallback: {self.wifi_fallback_ip}")
                        self.connection_status.emit(f"USB não encontrado. Tentando WiFi: {self.wifi_fallback_ip}...")
                        
                        # Try to connect via WiFi
                        result = self.adb_manager.connect_direct_ip(self.wifi_fallback_ip)
                        logger.info(f"Step 4: connect_direct_ip retornou: {result}, device_serial agora: {self.adb_manager.device_serial}")
                        
                        if result:
                            logger.info(f"Step 5: WiFi conectado. Aguardando sincronização...")
                            # CRITICAL: Wait again to sync device after WiFi connection
                            time.sleep(0.5)
                            sync_ok = self.adb_manager.wait_for_device()
                            logger.info(f"Step 6: wait_for_device retornou: {sync_ok}")
                            if not sync_ok:
                                logger.error("Falha ao sincronizar device após WiFi")
                                self.connection_status.emit("Falha ao sincronizar com WiFi.")
                                return
                        else:
                            logger.error("Step 4: connect_direct_ip retornou False")
                            self.connection_status.emit("Falha ao conectar via WiFi fallback.")
                            return
                    else:
                        logger.error("Step 2: Sem WiFi fallback IP configurado")
                        self.connection_status.emit("Dispositivo não encontrado ou não autorizado.")
                        return

            logger.info("Device conectado! Continuando com fluxo...")
            if not self.running: return

            logger.info("Step 7: Enviando servidor...")
            if not self.adb_manager.push_server():
                logger.error("Step 7: FALHOU - push_server retornou False")
                self.connection_status.emit("Falha ao enviar servidor para o dispositivo.")
                return

            if not self.running: return

            logger.info("Step 8: Configurando port forward...")
            if not self.adb_manager.setup_port_forward():
                logger.error("Step 8: FALHOU - setup_port_forward retornou False")
                self.connection_status.emit("Falha ao redirecionar portas.")
                return

            if not self.running: return

            cam_name = "Traseira" if self.camera_id == 0 else "Frontal"
            self.connection_status.emit(f"Iniciando câmera {cam_name}...")
            
            ok = self.adb_manager.launch_android_server(
                camera_id=self.camera_id,
                width=self.width,
                height=self.height,
                fps=self.fps,
                bitrate=self.bitrate,
                force_fps=True,
                audio_enabled=self._audio_enabled
            )
            
            # Check if server fell back to screen mirror and notify user
            if self.adb_manager.fallback_used:
                logger.warning("[AVISO] Câmera não suportada. Usando espelhamento de tela.")
                warning_title = "Câmera Não Suportada"
                warning_msg = (
                    "Câmera nativa não suportada neste aparelho.\n\n"
                    "Suporte a câmera e espelhamento varia por modelo/fabricante "
                    "mesmo em Android 11+.\n\n"
                    "O app continuará com espelhamento de tela."
                )
                self.show_warning.emit(warning_title, warning_msg)
                self.connection_status.emit("Usando espelhamento de tela...")
            
            # If the exact FPS request crashes the server, fallback to the camera's default
            if not ok:
                logger.warning("Strict FPS mode failed. Retrying with default camera fps...")
                ok = self.adb_manager.launch_android_server(
                    camera_id=self.camera_id,
                    width=self.width,
                    height=self.height,
                    fps=self.fps,
                    bitrate=self.bitrate,
                    force_fps=False,
                    audio_enabled=self._audio_enabled
                )

            if not ok:
                self.connection_status.emit("Falha ao iniciar servidor.")
                return

            self.connection_status.emit("Conectando ao stream...")
            self.video_receiver.start()
            
            if self._audio_enabled and hasattr(self, 'audio_receiver'):
                # Espera máxima de 3s para o vídeo conectar o socket no servidor.
                # O servidor scrcpy COM áudio bloqueia a emissão de dados até o 2º socket conectar!
                # Por isso precisamos injetar a conexão de áudio neste exato momento (após o connect do vídeo).
                self.video_receiver.socket_connected_event.wait(timeout=3.0)
                self.audio_receiver.start()
                # Inicia monitor de headset para detectar plug/unplug e reiniciar o áudio
                self._start_headset_monitor()

        except Exception as e:
            logger.error(f"[CRASH] CRASH NA ROTINA DE CONEXÃO: {e}", exc_info=True)
            self.connection_status.emit(f"Erro: {str(e)}")

    def _stats_loop(self):
        """Emits live performance stats every second."""
        while self.running:
            time.sleep(1.0)
            now = time.time()
            elapsed = now - self._last_fps_time
            frames = self.video_receiver.frame_count
            self.video_receiver.frame_count = 0
            fps = frames / elapsed if elapsed > 0 else 0
            self._last_fps_time = now
            self._session_total_frames += frames
            self._stats_log_ticks += 1

            # Latency: cumulative drift between stream clock (PTS) and wall clock.
            # PTS is in microseconds (scrcpy units = 1 µs per unit).
            # Formula: wall_elapsed - stream_elapsed = buffering delay.
            latency_ms = None
            vr = self.video_receiver
            if (vr.first_pts is not None and vr.last_pts is not None
                    and vr.last_pts > vr.first_pts):
                stream_elapsed = (vr.last_pts - vr.first_pts) / 1_000_000  # seconds
                wall_elapsed = vr.last_pts_wall - vr.first_pts_wall        # seconds
                drift_ms = round((wall_elapsed - stream_elapsed) * 1000)
                latency_ms = max(0, drift_ms)

            self.stats_updated.emit({
                'fps': round(fps, 1),
                'resolution': self._resolution,
                'source': self._source_mode,
                'device': self.adb_manager.device_serial or '---',
                'bitrate_mbps': round(self.bitrate / 1_000_000, 1),
                'latency_ms': latency_ms,
            })

            # Log periódico de saúde a cada 10 ticks (10 segundos)
            # Compact, 1 linha, fácil de ler no Log Viewer
            if self._stats_log_ticks % 10 == 0:
                lat_str = f"{latency_ms}ms" if latency_ms is not None else "--ms"
                vcam = "ativo" if self._virtual_cam_enabled else "inativo"
                conn = "Wi-Fi" if self.is_connection_wireless() else "USB"
                uptime_s = int(now - self._session_start_time)
                mm, ss = divmod(uptime_s, 60)
                logger.info(
                    f"[Stream {mm:02d}:{ss:02d}] "
                    f"{fps:.1f} fps | lat {lat_str} | "
                    f"{self._resolution} | {round(self.bitrate / 1_000_000, 1)} Mbps | "
                    f"{conn} | OBS cam {vcam}"
                )

            # ─ BUG FIX #2: Reset PTS baseline for next cycle (measure per-cycle latency, not cumulative)
            if vr.first_pts is not None and vr.last_pts is not None:
                vr.first_pts = vr.last_pts
                vr.first_pts_wall = vr.last_pts_wall

    def stop_connection(self):
        """Stop stream and cleanup device-side resources, but keep ADB server running.
        Used during normal operation (WiFi operations, hot-swap, manual stop button)."""
        self.running = False
        self._reconnecting = False
        self.disable_virtual_cam()
        self.video_receiver.stop()
        if hasattr(self, 'audio_receiver'):
            self.audio_receiver.stop()
        self.adb_manager.cleanup_server_on_device()  # Clean up server on Android device
        self.adb_manager.cleanup()  # Remove port forwarding
        self.adb_manager.device_serial = None  # Reset device serial for fresh detection next time
        # NÃO zera wifi_fallback_ip aqui — é preciso para reconectar via Wi-Fi ao clicar em Iniciar novamente.
        # É zerado apenas explicitamente ao retornar para USB (action_return_to_usb).
        self._headset_monitor_active = False  # Para o monitor de headset

        # Log de resumo da sessão ao parar
        if self._session_start_time > 0:
            duration_s = int(time.time() - self._session_start_time)
            duration_str = f"{duration_s // 60}m{duration_s % 60:02d}s"
            logger.info(
                f"[Sessão encerrada] Durou {duration_str} | "
                f"{self._session_total_frames} frames entregues | "
                f"{self._resolution} @ {self.fps}fps"
            )
            self._session_start_time = 0.0

        self.connection_status.emit("Desconectado e pronto para próxima execução.")

    def cleanup_on_exit(self):
        """Full cleanup when app is closing. Stops everything including ADB server.
        Only call this from closeEvent()."""
        self.stop_connection()
        self.adb_manager.stop_adb_server()  # Kill ADB server completely - ONLY on app exit

    def connect_via_wifi_serial(self, ip_with_port: str):
        """Informa ao AppCore que a próxima conexão deve usar o IP Wi-Fi já estabelecido."""
        self._force_wifi_serial = ip_with_port

    def _start_headset_monitor(self):
        """Inicia o monitor de headset em background. Polling via ADB a cada 3s."""
        self._headset_monitor_active = True
        t = threading.Thread(target=self._headset_monitor_loop, daemon=True)
        t.start()

    def _headset_monitor_loop(self):
        """Detecta plug/unplug de fone de ouvido e reinicia o áudio automaticamente."""
        last_state = None
        while self._headset_monitor_active and self.running:
            try:
                result = self.adb_manager.run_adb("shell", "dumpsys", "audio", check=False)
                headset_on = False
                for line in result.stdout.splitlines():
                    ll = line.lower()
                    if 'wired_headset' in ll or 'wired_headphone' in ll:
                        if '= 1' in line or 'true' in ll or 'connected' in ll:
                            headset_on = True
                            break

                if last_state is not None and headset_on != last_state:
                    event = "conectado" if headset_on else "desconectado"
                    logger.info(f"[Áudio] Fone de ouvido {event}! Reiniciando stream de áudio...")
                    self._restart_audio_for_headset()

                last_state = headset_on
            except Exception as e:
                logger.debug(f"[HeadsetMonitor] erro: {e}")
            time.sleep(3.0)

    def _restart_audio_for_headset(self):
        """Reinicia apenas o AudioReceiver para capturar o microfone do fone/headset."""
        if not self.running or not self._audio_enabled:
            return
        try:
            from decoder.audio_receiver import AudioReceiver
            old = getattr(self, 'audio_receiver', None)
            if old:
                old.stop()
                old.wait(2000)

            new_ar = AudioReceiver(port=self.adb_manager.local_port)
            new_ar.audio_level.connect(self.audio_level)
            if self._audio_device is not None:
                new_ar.set_audio_device(self._audio_device)
            if self._audio_noise_reduction:
                new_ar.set_noise_reduction(True)
            if self._audio_monitoring:
                new_ar.set_monitoring(True)

            self.audio_receiver = new_ar
            new_ar.start()
            logger.info("[Áudio] Stream reiniciado para novo dispositivo de áudio.")
        except Exception as e:
            logger.error(f"[Áudio] Falha ao reiniciar após headset: {e}")

    def is_connection_wireless(self) -> bool:
        """Returns True if connected via Wi-Fi, False if USB.
        Wi-Fi connections have ':' in device_serial (format: IP:port), USB is plain serial."""
        return bool(self.adb_manager.device_serial and ":" in self.adb_manager.device_serial)

    def _handle_video_error(self, msg):
        if not self.running:
            return # User clicked Stop, ignore
        if self._reconnecting:
            return # Already reconnecting
            
        logger.warning(f"Desconexão detectada: '{msg}'. Iniciando smart reconnect...")
        
        # Guardamos o estado da conexão para saber como reconectar
        self._is_wireless_last = self.is_connection_wireless()
        self._last_device_ip = self.wifi_fallback_ip
        if self._is_wireless_last and self.adb_manager.device_serial:
            parts = self.adb_manager.device_serial.split(":")
            if len(parts) > 0:
                self._last_device_ip = parts[0] + ":5555"
                
        # Inicia a thread de reconexão
        self._reconnecting = True
        self._reconnect_attempts = 0
        self._reconnect_thread = threading.Thread(target=self._reconnect_routine, daemon=True)
        self._reconnect_thread.start()

    def _reconnect_routine(self):
        # 1. Parar receivers
        self.video_receiver.stop()
        if hasattr(self, 'audio_receiver'):
            self.audio_receiver.stop()
        
        # 2. Limpar redirecionamento e liberar servidor Android
        # (Mas manter a virtual cam ativa!)
        self.adb_manager.cleanup()
        self.adb_manager.cleanup_server_on_device()
        
        # Reseta estados de frames nas estatísticas
        self.video_receiver.frame_count = 0
        
        # Loop de reconexão
        backoff = 2.0
        while self.running and self._reconnecting:
            self._reconnect_attempts += 1
            msg = f"Conexão perdida. Tentando reconectar ({self._reconnect_attempts})..."
            self.connection_status.emit(msg)
            logger.info(f"[Smart Reconnect] Tentativa {self._reconnect_attempts}...")
            
            # Tenta restabelecer a conexão
            success = self._attempt_reconnect()
            if success:
                logger.info("[Smart Reconnect] Sucesso ao reconectar!")
                self._reconnecting = False
                
                # Recriar receivers com o novo socket/estado
                self.video_receiver = VideoReceiver(port=self.adb_manager.local_port)
                self.video_receiver.error_occurred.connect(self._handle_video_error)
                self.video_receiver.stream_info.connect(self._on_stream_info)
                self.video_receiver.frame_count = 0
                
                if self._audio_enabled:
                    self.audio_receiver = AudioReceiver(port=self.adb_manager.local_port)
                    self.audio_receiver.audio_level.connect(self.audio_level)
                    if self._audio_device is not None:
                        self.audio_receiver.set_audio_device(self._audio_device)
                    if self._audio_noise_reduction:
                        self.audio_receiver.set_noise_reduction(True)
                    if self._audio_monitoring:
                        self.audio_receiver.set_monitoring(True)
                
                # Avisa a UI
                self.connection_status.emit("Conectando ao stream...")
                
                # Inicia receivers novamente
                self.video_receiver.start()
                if self._audio_enabled:
                    # Espera pelo socket de vídeo conectar para liberar o de áudio
                    self.video_receiver.socket_connected_event.wait(timeout=3.0)
                    self.audio_receiver.start()
                
                return
                
            time.sleep(backoff)
            backoff = min(10.0, backoff * 1.5)
            
        if self._reconnecting:
            self._reconnecting = False
            self.running = False
            self.connection_status.emit("Erro: Falha ao reconectar após várias tentativas.")

    def _attempt_reconnect(self) -> bool:
        try:
            # Em cenários onde o cabo é puxado violentamente, o daemon do ADB no Windows
            # pode ficar preso num estado "fantasma" ou não detectar o device quando reconectado.
            # Matar o server força uma re-enumeração limpa das portas USB.
            logger.info("[Smart Reconnect] Reiniciando daemon do ADB para forçar detecção...")
            self.adb_manager.stop_adb_server()
            time.sleep(0.5)
            self.adb_manager.start_server()
            
            if self._is_wireless_last:
                if not self._last_device_ip:
                    return False
                ok = self.adb_manager.connect_direct_ip(self._last_device_ip)
                if not ok:
                    return False
                time.sleep(0.5)
                
            if not self.adb_manager.wait_for_device():
                return False
                
            if not self.adb_manager.push_server():
                return False
                
            if not self.adb_manager.setup_port_forward():
                return False
                
            ok = self.adb_manager.launch_android_server(
                camera_id=self.camera_id,
                width=self.width,
                height=self.height,
                fps=self.fps,
                bitrate=self.bitrate,
                force_fps=True,
                audio_enabled=self._audio_enabled
            )
            
            if not ok:
                ok = self.adb_manager.launch_android_server(
                    camera_id=self.camera_id,
                    width=self.width,
                    height=self.height,
                    fps=self.fps,
                    bitrate=self.bitrate,
                    force_fps=False,
                    audio_enabled=self._audio_enabled
                )
                
            return ok
        except Exception as e:
            logger.error(f"[Smart Reconnect] Erro na tentativa de reconexão: {e}")
            return False
