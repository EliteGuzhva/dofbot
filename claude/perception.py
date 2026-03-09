"""
perception.py — Camera capture + lightweight object detection for Dofbot.

Runs on Jetson Nano. Uses OpenCV for capture, and optionally:
  - YOLOv8-nano via TensorRT for object detection
  - Simple color-based detection as a zero-dependency fallback

The key output for the LLM is a structured scene description:
  "I see a red cube at position (0.12, -0.05), a blue cylinder at (0.08, 0.10)"
"""

import cv2
import numpy as np
import base64
import time
from dataclasses import dataclass


@dataclass
class DetectedObject:
    label: str
    confidence: float
    x_px: int          # center x in pixels
    y_px: int          # center y in pixels
    width_px: int
    height_px: int
    x_m: float = 0.0   # estimated x in meters (arm frame)
    y_m: float = 0.0   # estimated y in meters (arm frame)


class Camera:
    """
    Capture frames from USB camera or CSI camera on Jetson.
    """

    def __init__(self, source=0, width=640, height=480):
        """
        source: 0 for USB camera, or GStreamer pipeline for CSI:
          "nvarguscamerasrc ! video/x-raw(memory:NVMM), width=640, height=480, "
          "framerate=30/1 ! nvvidconv ! video/x-raw, format=BGRx ! "
          "videoconvert ! video/x-raw, format=BGR ! appsink"
        """
        self.cap = cv2.VideoCapture(source)
        if isinstance(source, int):
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        if not self.cap.isOpened():
            print("[WARN] Camera not available — using dummy frames")
            self.cap = None

        self.width = width
        self.height = height

    def capture(self) -> np.ndarray | None:
        """Capture a single frame. Returns BGR numpy array or None."""
        if self.cap is None:
            # Return a dummy frame for testing
            return np.zeros((self.height, self.width, 3), dtype=np.uint8)
        ret, frame = self.cap.read()
        return frame if ret else None

    def capture_base64_jpeg(self, quality=70) -> str | None:
        """Capture a frame and return as base64-encoded JPEG (for sending to VLM)."""
        frame = self.capture()
        if frame is None:
            return None
        _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return base64.b64encode(buffer).decode("utf-8")

    def release(self):
        if self.cap:
            self.cap.release()


class ColorDetector:
    """
    Simple color-based object detection. No ML dependencies.
    Good enough for picking up colored blocks on a clean desk.

    Define colors you want to detect in HSV ranges.
    """

    # HSV ranges for common colors (tune for your lighting!)
    COLOR_RANGES = {
        "red":    {"lower": np.array([0, 120, 70]),   "upper": np.array([10, 255, 255])},
        "green":  {"lower": np.array([36, 50, 50]),   "upper": np.array([86, 255, 255])},
        "blue":   {"lower": np.array([94, 80, 50]),   "upper": np.array([130, 255, 255])},
        "yellow": {"lower": np.array([20, 100, 100]), "upper": np.array([35, 255, 255])},
    }

    MIN_CONTOUR_AREA = 500  # ignore tiny blobs

    def detect(self, frame: np.ndarray) -> list[DetectedObject]:
        """Detect colored objects in the frame."""
        if frame is None:
            return []

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        detections = []

        for color_name, ranges in self.COLOR_RANGES.items():
            mask = cv2.inRange(hsv, ranges["lower"], ranges["upper"])

            # Handle red wrapping around hue=0
            if color_name == "red":
                mask2 = cv2.inRange(hsv, np.array([170, 120, 70]), np.array([180, 255, 255]))
                mask = cv2.bitwise_or(mask, mask2)

            # Clean up mask
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5)))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5)))

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                area = cv2.contourArea(contour)
                if area < self.MIN_CONTOUR_AREA:
                    continue

                x, y, w, h = cv2.boundingRect(contour)
                cx, cy = x + w // 2, y + h // 2

                detections.append(DetectedObject(
                    label=f"{color_name} object",
                    confidence=min(area / 5000, 1.0),
                    x_px=cx, y_px=cy,
                    width_px=w, height_px=h,
                ))

        return detections


class PixelToWorldMapper:
    """
    Maps pixel coordinates to arm-frame coordinates (meters).

    Simple approach: assume objects are on the table surface (z ≈ 0),
    use a pre-calibrated homography or linear mapping.

    For calibration:
      1. Place markers at known positions (e.g., 4 corners of a rectangle)
      2. Record their pixel coordinates
      3. Compute homography: pixel → world
    """

    def __init__(self):
        # Default: simple linear mapping (REPLACE with your calibration!)
        # These map pixel center (320, 240) to arm's straight-ahead position
        # and scale pixels to meters.
        #
        # Rough calibration for 640x480 camera looking down at ~30cm height:
        #   ~1 pixel ≈ 0.5mm at the table surface
        self.camera_center_x = 320
        self.camera_center_y = 240
        self.scale_x = 0.0005   # meters per pixel (horizontal)
        self.scale_y = 0.0005   # meters per pixel (vertical)
        self.offset_x = 0.15    # arm-frame X offset to camera center
        self.offset_y = 0.00    # arm-frame Y offset to camera center

        # For better accuracy, use cv2.findHomography() with 4+ calibration points
        self.homography = None

    def calibrate(self, pixel_points: np.ndarray, world_points: np.ndarray):
        """
        Compute homography from matched pixel↔world point pairs.

        pixel_points: Nx2 array of (px_x, px_y)
        world_points: Nx2 array of (arm_x, arm_y)
        """
        self.homography, _ = cv2.findHomography(pixel_points, world_points)

    def pixel_to_world(self, px_x: int, px_y: int) -> tuple[float, float]:
        """Convert pixel coordinates to arm-frame (x, y) in meters."""
        if self.homography is not None:
            pt = np.array([[[px_x, px_y]]], dtype=np.float64)
            world = cv2.perspectiveTransform(pt, self.homography)
            return float(world[0, 0, 0]), float(world[0, 0, 1])

        # Fallback: linear mapping
        x = self.offset_x + (self.camera_center_y - px_y) * self.scale_y
        y = self.offset_y + (self.camera_center_x - px_x) * self.scale_x
        return round(x, 4), round(y, 4)


class Perception:
    """
    Combined perception pipeline: camera → detection → world coordinates.
    """

    def __init__(self, camera_source=0):
        self.camera = Camera(source=camera_source)
        self.detector = ColorDetector()
        self.mapper = PixelToWorldMapper()
        self._last_frame = None
        self._last_detections = []

    def update(self) -> list[DetectedObject]:
        """Capture, detect, and map to world coordinates."""
        self._last_frame = self.camera.capture()
        self._last_detections = self.detector.detect(self._last_frame)

        # Map pixel positions to world coordinates
        for det in self._last_detections:
            det.x_m, det.y_m = self.mapper.pixel_to_world(det.x_px, det.y_px)

        return self._last_detections

    def get_scene_description(self) -> str:
        """
        Produce a text description of the scene for the LLM.
        This is the bridge between perception and language.
        """
        detections = self.update()

        if not detections:
            return "The workspace is empty. No objects detected."

        lines = [f"I see {len(detections)} object(s) on the table:"]
        for i, det in enumerate(detections, 1):
            lines.append(
                f"  {i}. {det.label} at position "
                f"(x={det.x_m:.3f}m, y={det.y_m:.3f}m), "
                f"size ~{det.width_px}x{det.height_px}px, "
                f"confidence={det.confidence:.1%}"
            )

        lines.append("")
        lines.append("Coordinate frame: x=forward, y=left, z=up. "
                      "Origin at arm base. Objects are on the table (z≈0.01m).")
        return "\n".join(lines)

    def get_frame_base64(self) -> str | None:
        """Get latest frame as base64 JPEG for sending to a vision-language model."""
        return self.camera.capture_base64_jpeg()

    def release(self):
        self.camera.release()


# ─── Quick test ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    p = Perception(camera_source=0)
    print(p.get_scene_description())
    p.release()
