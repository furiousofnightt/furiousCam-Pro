import socket
import threading
import logging
import struct
import av
import numpy as np
from PySide6.QtCore import QObject, Signal
import time

logger = logging.getLogger(__name__)

class VideoReceiver(QObject):
    error_occurred = Signal(str)
    stream_info = Signal(dict)  # Emits {codec, width, height, source} on connect

    def __init__(self, host="127.0.0.1", port=27183):
        super().__init__()
        self.host = host
        self.port = port
        self.running = False
        self.socket = None
        self.thread = None
        self.latest_frame = None
        self.codec_context = None
        self.socket_connected_event = threading.Event()
        self.frame_count = 0  # Reset by AppCore stats loop
        self.last_pts = None   # Last PTS received (microseconds, scrcpy units)
        self.last_pts_wall = None  # Wall clock when last PTS arrived
        self.first_pts = None  # PTS at stream start (for cumulative latency)
        self.first_pts_wall = None  # Wall clock at stream start

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self.latest_frame = None
        self.codec_context = None
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
            except:
                pass
        self.socket = None

    def _recv_exact(self, n):
        data = bytearray()
        try:
            while len(data) < n:
                if not self.running:
                    return None
                chunk = self.socket.recv(n - len(data))
                if not chunk:
                    return None
                data.extend(chunk)
        except (socket.error, OSError):
            return None
        return bytes(data)

    def _receive_loop(self):
        logger.info(f"Connecting to {self.host}:{self.port}...")
        
        time.sleep(1) # Give ADB forward a moment

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        try:
            self.socket.connect((self.host, self.port))
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.socket.settimeout(10.0)  # Fail fast if stream goes silent
            logger.info("Connected to video stream.")
            self.socket_connected_event.set()
            
            # 1. Read dummy byte (scrcpy protocol requirement when send_dummy_byte=true)
            dummy = self._recv_exact(1)
            if not dummy:
                logger.error("Failed to read dummy byte.")
                return

            # 2. Read codec meta: Codec ID (4 bytes) + Width (4 bytes) + Height (4 bytes)
            meta = self._recv_exact(12)
            if not meta:
                logger.error("Failed to read codec meta.")
                return
            
            codec_id = struct.unpack(">I", meta[0:4])[0]
            w = struct.unpack(">I", meta[4:8])[0]
            h = struct.unpack(">I", meta[8:12])[0]
            
            # Setup FFmpeg decoder dynamically based on codec id
            codec_name = 'h264'
            codec_display = 'H.264'
            if codec_id == 0x68323635:
                codec_name = 'hevc'
                codec_display = 'HEVC (H.265)'

            logger.info(f"Video stream details: Codec ID 0x{codec_id:08x} ({codec_display}), Size: {w}x{h}")
            
            # Emit stream info for the UI stats panel
            self.stream_info.emit({
                'codec': codec_display,
                'width': w,
                'height': h,
                'source': 'Camera'
            })
            
            # Setup FFmpeg decoder
            self.codec_context = av.CodecContext.create(codec_name, "r")
            
            # 3. Read frames loop
            while self.running:
                # Frame header: 12 bytes (8 pts_flags + 4 size)
                header = self._recv_exact(12)
                if not header:
                    break
                
                pts_flags = struct.unpack(">Q", header[0:8])[0]
                size = struct.unpack(">I", header[8:12])[0]
                
                # Extract PTS (presentation timestamp)
                pts = pts_flags & 0x3FFFFFFFFFFFFFFF
                
                # Read frame data
                data = self._recv_exact(size)
                if not data:
                    break
                
                try:
                    packet = av.Packet(data)
                    packet.pts = pts
                    
                    frames = self.codec_context.decode(packet)
                    for frame in frames:
                        # Converter imediatamente para numpy RGB na thread do decoder.
                        # NUNCA passar o objeto av.VideoFrame entre threads — causa segfault!
                        arr = frame.to_ndarray(format='rgb24')
                        if not arr.flags['C_CONTIGUOUS']:
                            arr = np.ascontiguousarray(arr)
                        self.latest_frame = arr
                        self.frame_count += 1
                        now_wall = time.time()
                        if self.first_pts is None:
                            self.first_pts = pts
                            self.first_pts_wall = now_wall
                            logger.info(
                                f"Primeiro frame decodificado: "
                                f"{frame.width}x{frame.height} | "
                                f"formato {frame.format.name}"
                            )
                        self.last_pts = pts
                        self.last_pts_wall = now_wall
                except Exception as e:
                    # Configuration packets (SPS/PPS) might not return frames
                    # but if it's a real frame error, we log it
                    is_config = bool(pts_flags & (1 << 63))
                    if not is_config:
                        logger.error(f"Decode error: {e}")

            if self.running:
                logger.error("A câmera foi fechada inesperadamente (Outro app abriu a câmera?).")
                self.error_occurred.emit("A câmera foi interrompida (Em uso?).")

        except Exception as e:
            logger.error(f"Connection error: {e}")
            self.error_occurred.emit(str(e))
        finally:
            if self.socket:
                self.socket.close()
            logger.info("Video receiver stopped.")
