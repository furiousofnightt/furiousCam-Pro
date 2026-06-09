import socket
import struct
import logging
import threading
import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices
import time

logger = logging.getLogger(__name__)

SAMPLE_RATE = 48000  # Opus padrão do Scrcpy

class AudioReceiver(QThread):
    """
    Recebedor de Áudio com decodificação Opus real-time via PyAV,
    cálculo de RMS logarítmico para VU meter e redução de ruído via spectral gating.
    """
    
    audio_stats = Signal(dict)
    audio_level = Signal(int)
    
    def __init__(self, port: int):
        super().__init__()
        self.port = port
        self.running = False
        self.socket = None
        
        # Estatísticas para Log
        self.bytes_received = 0
        self.packets_received = 0
        
        # Redução de Ruído
        self._noise_reduction = False
        self._noise_profile = None
        self._noise_frames = []
        self._noise_profile_ready = False
        self._noise_lock = threading.Lock()
        self._last_gain = None
        self._noise_warmup_remaining = 15  # Frames a ignorar antes de coletar perfil (warmup do codec)
        
        # Saída Principal de Áudio (Sempre ativa, vai para o dispositivo selecionado ex: VB-Cable)
        self._main_device = None
        self._main_stream = None
        self._main_sink = None
        self._main_lock = threading.Lock()
        self._needs_main_init = False
        
        # Monitor de Áudio ("Ouvir Retorno", passthrough para o alto-falante padrão)
        self._monitoring = False
        self._monitor_stream = None
        self._monitor_sink = None
        self._monitor_lock = threading.Lock()
        self._needs_monitor_init = False
    
    def set_noise_reduction(self, enabled: bool):
        """Toggle thread-safe da redução de ruído."""
        with self._noise_lock:
            self._noise_reduction = enabled
            if enabled:
                self._noise_profile_ready = False
                self._noise_frames = []
                self._last_gain = None
                self._noise_warmup_remaining = 15  # Warmup para o codec estabilizar antes de coletar perfil
                logger.info("[Áudio] Redução de ruído: ATIVADA. Aguardando warmup e capturando perfil nos próximos 0.5s...")
            else:
                logger.info("[Áudio] Redução de ruído: DESATIVADA")

    def set_monitoring(self, enabled: bool):
        """Liga/desliga o monitor de áudio (passthrough para o alto-falante PADRÃO do PC)."""
        with self._monitor_lock:
            self._monitoring = enabled
            if enabled:
                if getattr(self, 'running', False):
                    self._needs_monitor_init = True
            else:
                if getattr(self, '_monitor_sink', None) is not None:
                    try:
                        self._monitor_sink.stop()
                    except:
                        pass
                    self._monitor_sink = None
                self._monitor_stream = None
                logger.info("[Áudio] Monitor desativado.")

    def _init_monitor_sink(self):
        """Inicializa a saída de monitoramento (Alto-falante Padrão)"""
        # Assume _monitor_lock
        if getattr(self, '_monitor_sink', None) is not None:
            try:
                self._monitor_sink.stop()
            except: pass
            self._monitor_sink = None
            self._monitor_stream = None
            
        try:
            format = QAudioFormat()
            format.setSampleRate(SAMPLE_RATE)
            format.setChannelCount(2)
            format.setSampleFormat(QAudioFormat.Float)
            
            # Precisamos manter referência do device? Por segurança, sim.
            self._monitor_device = QMediaDevices.defaultAudioOutput()
            
            # Se o Windows estiver com o Cabo Virtual como padrão, o monitor iria para o cabo virtual!
            # Vamos ser espertos e forçar o monitor a usar um alto-falante real.
            if "CABLE" in self._monitor_device.description().upper() or "VB-AUDIO" in self._monitor_device.description().upper():
                for dev in QMediaDevices.audioOutputs():
                    desc = dev.description().upper()
                    if "CABLE" not in desc and "VB-AUDIO" not in desc:
                        self._monitor_device = dev
                        break
                        
            self._monitor_sink = QAudioSink(self._monitor_device, format, self)
            self._monitor_sink.setBufferSize(38400)  # ~100ms buffer to prevent underrun crackles
            self._monitor_sink.setVolume(1.0)
            self._monitor_stream = self._monitor_sink.start()
            logger.info(f"[Áudio] Monitor ativado no dispositivo real: {self._monitor_device.description()}")
        except Exception as e:
            logger.error(f"[Áudio] Falha ao abrir stream de monitor: {e}")
            self._monitoring = False
            self._monitor_stream = None

    def set_audio_device(self, device):
        """Define o dispositivo de áudio principal e o aplica imediatamente se estiver rodando."""
        with self._main_lock:
            self._main_device = device
            if getattr(self, 'running', False):
                self._needs_main_init = True

    def _init_main_sink(self):
        """Inicializa ou reinicializa a saída de áudio principal."""
        # Assume que _main_lock já foi adquirido
        if self._main_sink is not None:
            try:
                self._main_sink.stop()
            except:
                pass
            self._main_sink = None
            self._main_stream = None
            
        try:
            format = QAudioFormat()
            format.setSampleRate(SAMPLE_RATE)
            format.setChannelCount(2)
            format.setSampleFormat(QAudioFormat.Float)
            
            device = self._main_device
            if device is None:
                device = QMediaDevices.defaultAudioOutput()
                
            self._main_sink = QAudioSink(device, format, self)
            self._main_sink.setBufferSize(38400)  # ~100ms buffer to prevent underrun crackles
            self._main_sink.setVolume(1.0)
            self._main_stream = self._main_sink.start()
            logger.info(f"[Áudio] Saída principal ativada no dispositivo: {device.description()}")
        except Exception as e:
            logger.error(f"[Áudio] Falha ao inicializar saída principal de áudio: {e}")

    def run(self):
        self.running = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Desabilita o algoritmo de Nagle para menor latência
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        try:
            logger.info(f"Tentando conectar ao socket de ÁUDIO em 127.0.0.1:{self.port}...")
            self.socket.connect(("127.0.0.1", self.port))
            logger.info("Socket de ÁUDIO conectado com sucesso!")

            # O protocolo pode ou não enviar um dummy byte (0x00) na segunda conexão.
            # Vamos ler 4 bytes. Se o primeiro for 0x00, lemos mais 1 byte.
            meta = self._recv_exact(4)
            if not meta:
                logger.error("Falha ao ler meta do codec de áudio.")
                return
            
            if meta[0] == 0x00:
                logger.debug("Dummy byte 0x00 detectado no socket de áudio.")
                extra = self._recv_exact(1)
                meta = meta[1:] + extra
                
            codec_name = 'opus' # Padrão do scrcpy para áudio
            logger.info(f"Audio codec recebido: {meta} (esperado b'opus' ou b'aac ')")

            try:
                import av
                import numpy as np
                self.codec_context = av.CodecContext.create(codec_name, "r")
            except Exception as e:
                logger.error(f"Falha ao inicializar decoder de áudio: {e}")
                return

            # Inicia o áudio principal assim que o socket conectar
            with self._main_lock:
                self._init_main_sink()
                
            with self._monitor_lock:
                if self._monitoring:
                    self._init_monitor_sink()

            # 3. Loop de leitura de pacotes
            while self.running:
                # Frame header: 12 bytes (8 pts_flags + 4 size)
                header = self._recv_exact(12)
                if not header:
                    break
                
                size = struct.unpack(">I", header[8:12])[0]
                
                # Ler pacote
                data = self._recv_exact(size)
                if not data:
                    break
                
                self.bytes_received += len(data)
                self.packets_received += 1
                
                try:
                    packet = av.Packet(data)
                    frames = self.codec_context.decode(packet)
                    for frame in frames:
                        arr = frame.to_ndarray()
                        
                        if arr.size > 0:
                            arr_f = arr.astype(np.float32)
                            
                            # ── Redução de Ruído (Spectral Subtraction, numpy puro) ──
                            with self._noise_lock:
                                nr_enabled = self._noise_reduction
                                nr_ready = self._noise_profile_ready
                                
                            # Fase 1: Coleta de perfil (apenas quando NR habilitado, após warmup do codec)
                            if nr_enabled and not nr_ready:
                                if self._noise_warmup_remaining > 0:
                                    self._noise_warmup_remaining -= 1
                                elif len(self._noise_frames) < 26:
                                    mono_ref = arr_f[0] if arr_f.ndim > 1 else arr_f
                                    self._noise_frames.append(mono_ref.copy())
                                    if len(self._noise_frames) == 26:
                                        # Calcula o perfil de ruído usando janelas sobrepostas de tamanho 2N
                                        # para bater perfeitamente com a fase de processamento (Overlap-Add)
                                        fft_list = []
                                        N = len(self._noise_frames[0])
                                        wnd = np.hanning(2*N + 1)[:-1]
                                        prev_f = self._noise_frames[0]
                                        for i in range(1, 26):
                                            cur_f = self._noise_frames[i]
                                            w2n = np.concatenate([prev_f, cur_f]) * wnd
                                            fft_list.append(np.abs(np.fft.rfft(w2n)) ** 2)
                                            prev_f = cur_f
                                        self._noise_profile = np.mean(fft_list, axis=0)
                                        self._noise_profile_ready = True
                                        
                                        # Inicializa o estado do Overlap-Add
                                        self._ola_buffer = np.zeros(N)
                                        self._prev_mono = np.zeros(N)
                                        self._ola_window = wnd
                                        logger.info(f"[Áudio] Perfil de ruído capturado (OLA): {len(self._noise_profile)} bins FFT")
                            
                            # Fase 2: Spectral Subtraction com Overlap-Add (Zero Clicks)
                            if nr_enabled and self._noise_profile_ready:
                                try:
                                    mono = arr_f[0] if arr_f.ndim > 1 else arr_f
                                    N = len(mono)
                                    
                                    # Fallback se a resolução mudar no meio do stream (raro)
                                    if not hasattr(self, '_ola_buffer') or len(self._ola_buffer) != N:
                                        self._ola_buffer = np.zeros(N)
                                        self._prev_mono = np.zeros(N)
                                        self._ola_window = np.hanning(2*N + 1)[:-1]
                                        
                                    # Cria janela 2N com o frame anterior e atual
                                    windowed = np.concatenate([self._prev_mono, mono]) * self._ola_window
                                    
                                    fft = np.fft.rfft(windowed)
                                    magnitude = np.abs(fft)
                                    phase = np.angle(fft)
                                    
                                    # Calcula ganho por frequência
                                    alpha = 1.5
                                    noise_mag = np.sqrt(self._noise_profile)
                                    
                                    gain = np.ones_like(magnitude)
                                    mask = magnitude > 1e-6
                                    gain[mask] = (magnitude[mask] - alpha * noise_mag[mask]) / magnitude[mask]
                                    gain = np.clip(gain, 0.1, 1.0)
                                    
                                    # Suavização temporal do ganho (Attack/Release)
                                    if self._last_gain is None or len(self._last_gain) != len(gain):
                                        self._last_gain = gain
                                    else:
                                        gamma = np.where(gain > self._last_gain, 0.15, 0.85)
                                        gain = gamma * self._last_gain + (1.0 - gamma) * gain
                                        self._last_gain = gain
                                        
                                    clean_mag = magnitude * gain
                                    
                                    # Reconstrói sinal de tamanho 2N
                                    cleaned_2n = np.fft.irfft(clean_mag * np.exp(1j * phase), n=2*N)
                                    
                                    # Overlap-Add: Junta a 1ª metade processada com a 2ª metade do frame passado
                                    output_mono = cleaned_2n[:N] + self._ola_buffer
                                    
                                    # Atualiza estado para o próximo frame
                                    self._ola_buffer = cleaned_2n[N:]
                                    self._prev_mono = mono.copy()
                                    
                                    # Restaura stereo se necessário
                                    arr_f = np.stack([output_mono, output_mono]) if arr_f.ndim > 1 else output_mono
                                except Exception as nr_err:
                                    logger.debug(f"[Áudio] OLA spectral gate error: {nr_err}")
                            # ─────────────────────────────────────────────────────
                            
                            rms = np.sqrt(np.mean(np.square(arr_f)))
                            
                            # Log nos primeiros frames para debug
                            if self.packets_received <= 5:
                                max_val = np.max(np.abs(arr_f))
                                logger.info(f"[Áudio] Pacote decodificado: shape={arr.shape}, dtype={arr.dtype}, max_abs={max_val:.6f}, RMS={rms:.6f}")
                            
                            # Normaliza int16 se necessário
                            if arr.dtype == np.int16:
                                rms = rms / 32768.0
                            
                            # Escala logarítmica (dB) — padrão da indústria
                            import math
                            if rms > 1e-9:
                                db = 20.0 * math.log10(rms)
                                vol_percent = max(0, min(100, int((db + 90) / 90 * 100)))
                            else:
                                vol_percent = 0
                                
                            self.audio_level.emit(vol_percent)
                            
                            # ── Saídas de Áudio (Principal e Monitor) ──
                            is_main_virtual = False
                            with self._main_lock:
                                if self._main_device is not None:
                                    desc = self._main_device.description().upper()
                                    is_main_virtual = "CABLE" in desc or "VB-AUDIO" in desc

                            needs_main = False
                            with self._main_lock:
                                if self._needs_main_init:
                                    self._init_main_sink()
                                    self._needs_main_init = False
                                    
                                if self._main_stream is not None:
                                    # Se for cabo virtual, áudio sempre flui para o OBS
                                    if is_main_virtual:
                                        needs_main = True
                                    # Se for um fone normal, só toca se o usuário clicou em "Me Ouvir"
                                    else:
                                        needs_main = self._monitoring
                            
                            needs_monitor = False
                            with self._monitor_lock:
                                if self._needs_monitor_init:
                                    self._init_monitor_sink()
                                    self._needs_monitor_init = False
                                    
                                # O monitor secundário só é necessário se a saída principal for pro OBS
                                if is_main_virtual:
                                    needs_monitor = (self._monitoring and self._monitor_stream is not None)
                                else:
                                    needs_monitor = False
                                
                            if needs_main or needs_monitor:
                                try:
                                    # qt espera bytes interleaved L R L R
                                    # arr_f tem shape (channels, frames) → transpor e forçar contiguidade
                                    play_buf = np.ascontiguousarray(arr_f.T, dtype=np.float32)
                                    
                                    # Soft limiter com tanh (sem distorção, sem apitos)
                                    # Opus float32 vem em range [-1, 1] mas pode ser muito baixo.
                                    # Aplicamos +12dB de boost (x4) e depois passamos pelo tanh
                                    # que comprime suavemente sem clipar bruscamente.
                                    # Aplicamos +6dB de boost (x2) em vez de x4 para evitar
                                    # distorção/estralos quando o usuário fala alto.
                                    play_buf = np.tanh(play_buf * 2.0)
                                    play_bytes = play_buf.tobytes()
                                    
                                    # Escreve na stream principal (ex: VB-Cable)
                                    if needs_main:
                                        with self._main_lock:
                                            if self._main_stream is not None:
                                                try:
                                                    self._main_stream.write(play_bytes)
                                                except Exception as e:
                                                    pass
                                                    
                                    # Escreve na stream do monitor (ex: Alto-falante padrão)
                                    if needs_monitor:
                                        with self._monitor_lock:
                                            if self._monitor_stream is not None:
                                                try:
                                                    self._monitor_stream.write(play_bytes)
                                                except Exception as e:
                                                    pass
                                except Exception as err:
                                    logger.debug(f"[Áudio] audio write error: {err}")
                            # ────────────────────────────────────────────────────

                except Exception as e:
                    if self.packets_received < 10:
                        logger.error(f"[Áudio] Erro decodificando pacote Opus: {e}")
                
                if self.packets_received <= 5:
                    logger.info(f"[Áudio] Recebido pacote {self.packets_received} com tamanho {size} bytes")
                elif self.packets_received % 50 == 0:
                    logger.info(f"[Áudio] Recebidos {self.packets_received} pacotes ({self.bytes_received / 1024:.1f} KB)")

        except ConnectionRefusedError:
            logger.error("Falha ao conectar no socket de áudio (Conexão recusada).")
        except Exception as e:
            if self.running:
                logger.error(f"Erro no AudioReceiver: {e}")
        finally:
            self.stop()
            logger.info("AudioReceiver finalizado.")

    def _recv_exact(self, n: int) -> bytes:
        """Helper para ler exatamente n bytes."""
        data = bytearray()
        while len(data) < n and self.running:
            try:
                packet = self.socket.recv(n - len(data))
                if not packet:
                    return b""
                data.extend(packet)
            except Exception:
                return b""
        return bytes(data)

    def stop(self):
        self.running = False
        # Fecha o monitor de áudio se estiver ativo
        self.set_monitoring(False)
        # Fecha a saída principal de áudio
        with self._main_lock:
            if getattr(self, '_main_sink', None) is not None:
                try:
                    self._main_sink.stop()
                except:
                    pass
                self._main_sink = None
            self._main_stream = None

        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None
