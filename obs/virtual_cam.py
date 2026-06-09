"""
obs/virtual_cam.py - OBS/Streamlabs Virtual Camera integration via pyvirtualcam.

Requirements: pip install pyvirtualcam
Requires one of:
  - OBS Studio >= 27 installed (includes obs-virtualcam driver on Windows)
  - Streamlabs Desktop installed (includes its own virtual camera driver)
"""
import logging
import numpy as np

logger = logging.getLogger(__name__)

try:
    import pyvirtualcam
    PYVIRTUALCAM_AVAILABLE = True
except ImportError:
    PYVIRTUALCAM_AVAILABLE = False
    logger.warning("pyvirtualcam not installed. Run: pip install pyvirtualcam")


# Order to try backends. 'obs' covers OBS Studio and Streamlabs (both install
# the same obs-virtualcam driver on Windows). 'unitycapture' is the fallback
# used by some older OBS versions and Unity setups.
_BACKENDS_TO_TRY = ["obs", "unitycapture"]


class VirtualCamOutput:
    """
    Pushes decoded video frames into a Virtual Camera output.
    Compatible with OBS Studio, Streamlabs, Discord, Zoom, Google Meet.
    """

    def __init__(self, width: int = 1920, height: int = 1080, fps: int = 30):
        self.width = width
        self.height = height
        self.fps = fps
        self._cam = None
        self._running = False
        self._backend_used = None
        # If True, call pyvirtualcam.sleep_until_next_frame() after send().
        # Disabling throttle attempts to send frames as fast as possible and
        # avoid additional driver-side buffering. This favors minimal latency
        # at the cost of potential frame drops or tearing on some backends.
        self._throttle = False
        # Lightweight send counter for reducing log spam
        self._send_count = 0

    @property
    def is_available(self) -> bool:
        return PYVIRTUALCAM_AVAILABLE

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self, width: int = None, height: int = None, fps: int = None) -> bool:
        """Open the virtual camera output, trying all known backends."""
        if not PYVIRTUALCAM_AVAILABLE:
            logger.error("pyvirtualcam not installed.")
            return False

        if self._running:
            return True

        self.width  = width  or self.width
        self.height = height or self.height
        self.fps    = fps    or self.fps

        # Try each backend in order until one works
        for backend in _BACKENDS_TO_TRY:
            try:
                self._cam = pyvirtualcam.Camera(
                    width=self.width,
                    height=self.height,
                    fps=self.fps,
                    fmt=pyvirtualcam.PixelFormat.RGB,
                    backend=backend,
                    print_fps=False,
                )
                self._running = True
                self._backend_used = backend
                logger.info(
                    f"Virtual camera started: {self.width}x{self.height}@{self.fps}fps "
                    f"via backend='{backend}' device='{self._cam.device}'"
                )
                return True
            except Exception as e:
                logger.warning(f"Backend '{backend}' failed: {e}")

        # All backends failed — try without specifying backend (last resort)
        try:
            self._cam = pyvirtualcam.Camera(
                width=self.width,
                height=self.height,
                fps=self.fps,
                fmt=pyvirtualcam.PixelFormat.RGB,
            )
            self._running = True
            self._backend_used = "auto"
            logger.info(
                f"Virtual camera started (auto-detect): {self.width}x{self.height}@{self.fps}fps "
                f"via '{self._cam.device}'"
            )
            return True
        except Exception as e:
            logger.error(
                f"All virtual camera backends failed. Last error: {e}\n"
                "Make sure OBS Studio (>= 27) or Streamlabs Desktop is installed\n"
                "and that the Virtual Camera driver has been activated at least once."
            )
            return False

    def _scale_frame(self, frame_rgb: np.ndarray) -> np.ndarray:
        """Scale source frame to the virtual camera output while preserving aspect ratio."""
        fh, fw = frame_rgb.shape[:2]
        if fw == self.width and fh == self.height:
            return frame_rgb

        output = np.zeros((self.height, self.width, 3), dtype=frame_rgb.dtype)
        src_ar = fw / fh
        dst_ar = self.width / self.height

        if src_ar > dst_ar:
            # Fit source width to destination width and letterbox top/bottom.
            x_idx = (np.linspace(0, fw - 1, self.width).round().astype(np.int32)).clip(0, fw - 1)
            resized = frame_rgb[:, x_idx]
            scaled_h = max(1, int(round(self.width / src_ar)))
            y_idx = (np.linspace(0, fh - 1, scaled_h).round().astype(np.int32)).clip(0, fh - 1)
            resized = resized[y_idx]
            y0 = (self.height - scaled_h) // 2
            output[y0:y0 + scaled_h, :, :] = resized
        else:
            # Fit source height to destination height and letterbox left/right.
            y_idx = (np.linspace(0, fh - 1, self.height).round().astype(np.int32)).clip(0, fh - 1)
            resized = frame_rgb[y_idx, :, :]
            scaled_w = max(1, int(round(self.height * src_ar)))
            x_idx = (np.linspace(0, fw - 1, scaled_w).round().astype(np.int32)).clip(0, fw - 1)
            resized = resized[:, x_idx, :]
            x0 = (self.width - scaled_w) // 2
            output[:, x0:x0 + scaled_w, :] = resized

        return output

    def send_frame(self, frame_rgb: np.ndarray):
        """
        Send an RGB numpy frame to the virtual camera.
        frame_rgb: numpy array of shape (H, W, 3) in RGB format.
        """
        if not self._running or self._cam is None:
            return

        try:
            fh, fw = frame_rgb.shape[:2]
            if fw != self.width or fh != self.height:
                frame_rgb = self._scale_frame(frame_rgb)

            if not frame_rgb.flags["C_CONTIGUOUS"]:
                frame_rgb = np.ascontiguousarray(frame_rgb)

            import time
            t0 = time.time()
            self._cam.send(frame_rgb)
            # Let the pyvirtualcam backend control pacing to avoid build-up
            if self._throttle and hasattr(self._cam, "sleep_until_next_frame"):
                try:
                    self._cam.sleep_until_next_frame()
                except Exception as e:
                    logger.debug(f"sleep_until_next_frame() failed: {e}")
            dur_ms = (time.time() - t0) * 1000.0
            # Reduce log spam: log only on slow sends or periodically every 120 frames
            self._send_count += 1
            if dur_ms > 25.0 or (self._send_count % 120) == 0:
                logger.info(f"Virtual cam send time: {dur_ms:.1f}ms (throttle={self._throttle})")

        except Exception as e:
            logger.error(f"Virtual cam send error: {e}")

    def stop(self):
        """Close the virtual camera output."""
        self._running = False
        if self._cam is not None:
            try:
                self._cam.close()
                logger.info("Virtual camera stopped.")
            except Exception as e:
                logger.warning(f"Error closing virtual camera: {e}")
            self._cam = None
        self._backend_used = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
