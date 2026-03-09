"""Backend implementations for hardware and simulation."""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
import time
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .config import DofbotConfig, JointCalibration
from .errors import DofbotConnectionError, DofbotValidationError
from .protocol import (
    Register,
    angle_to_position,
    decode_firmware_word,
    encode_joint_command,
    encode_sync_duration,
    encode_sync_positions,
    position_to_angle,
)
from .transport import Transport

LOGGER = logging.getLogger(__name__)


class BaseBackend(ABC):
    @abstractmethod
    def command_joint(self, joint_id: int, angle: float, duration_ms: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def command_joints(self, joint_angles: Mapping[int, float], duration_ms: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def command_all(self, angles: Iterable[float], duration_ms: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def read_joint_angle(self, joint_id: int) -> Optional[float]:
        raise NotImplementedError

    @abstractmethod
    def set_torque(self, enabled: bool) -> None:
        raise NotImplementedError


class I2CBackend(BaseBackend):
    def __init__(self, config: DofbotConfig, transport: Transport):
        self._config = config
        self._transport = transport
        self._last_angles: Dict[int, float] = {joint_id: 90.0 for joint_id in config.joints}

    def command_joint(self, joint_id: int, angle: float, duration_ms: int) -> None:
        calibration = self._get_calibration(joint_id)
        validated = self._validate_angle(joint_id, angle, calibration)
        position = angle_to_position(validated, calibration)
        register, payload = encode_joint_command(joint_id, position, duration_ms)
        self._transport.write_block(register, payload)
        self._last_angles[joint_id] = validated

    def command_joints(self, joint_angles: Mapping[int, float], duration_ms: int) -> None:
        for joint_id, angle in joint_angles.items():
            self.command_joint(joint_id, angle, duration_ms)

    def command_all(self, angles: Iterable[float], duration_ms: int) -> None:
        values = list(angles)
        if len(values) != 6:
            raise DofbotValidationError("command_all expects exactly 6 values")
        raw_positions: List[int] = []
        for joint_id, angle in enumerate(values, start=1):
            calibration = self._get_calibration(joint_id)
            validated = self._validate_angle(joint_id, angle, calibration)
            raw_positions.append(angle_to_position(validated, calibration))
            self._last_angles[joint_id] = validated
        self._transport.write_block(int(Register.SERVO_WRITE6_TIME), encode_sync_duration(duration_ms))
        self._transport.write_block(int(Register.SERVO_WRITE6), encode_sync_positions(raw_positions))

    def read_joint_angle(self, joint_id: int) -> Optional[float]:
        calibration = self._get_calibration(joint_id)
        register = int(Register.SERVO_READ_BASE) + joint_id
        self._transport.write_byte(register, 0x00)
        time.sleep(0.003)
        raw_word = self._transport.read_word(register)
        if raw_word == 0:
            return None
        position = decode_firmware_word(raw_word)
        angle = position_to_angle(position, calibration)
        if angle is not None:
            self._last_angles[joint_id] = angle
        return angle

    def read_all_angles(self) -> Dict[int, float]:
        values: Dict[int, float] = {}
        for joint_id in sorted(self._config.joints):
            value = self.read_joint_angle(joint_id)
            if value is not None:
                values[joint_id] = value
        return values

    def set_torque(self, enabled: bool) -> None:
        self._transport.write_byte(int(Register.SERVO_TORQUE), 0x01 if enabled else 0x00)

    def get_cached_angles(self) -> Dict[int, float]:
        return dict(self._last_angles)

    def get_hardware_version(self) -> str:
        self._transport.write_byte(int(Register.VERSION), 0x01)
        time.sleep(0.001)
        return f"0.{self._transport.read_byte(int(Register.VERSION))}"

    def reset_board(self) -> None:
        self._transport.write_byte(int(Register.RESET), 0x01)

    def set_rgb(self, red: int, green: int, blue: int) -> None:
        self._transport.write_block(int(Register.RGB), [red & 0xFF, green & 0xFF, blue & 0xFF])

    def _get_calibration(self, joint_id: int) -> JointCalibration:
        calibration = self._config.joints.get(joint_id)
        if calibration is None:
            raise DofbotValidationError(f"Invalid joint_id {joint_id}; expected 1..6")
        return calibration

    def _validate_angle(self, joint_id: int, angle: float, calibration: JointCalibration) -> float:
        value = float(angle)
        if calibration.angle_min <= value <= calibration.angle_max:
            return value
        if self._config.clamp_inputs:
            LOGGER.warning("Clamping joint %s angle %.2f to configured limits", joint_id, value)
            return max(calibration.angle_min, min(calibration.angle_max, value))
        raise DofbotValidationError(
            f"Joint {joint_id} angle {value} outside range "
            f"[{calibration.angle_min}, {calibration.angle_max}]"
        )


class SimBackend(BaseBackend):
    """Deterministic simulation backend for testing or development."""

    def __init__(self):
        self._angles: Dict[int, float] = {idx: 90.0 for idx in range(1, 7)}

    def command_joint(self, joint_id: int, angle: float, duration_ms: int) -> None:
        del duration_ms
        self._angles[joint_id] = float(angle)

    def command_joints(self, joint_angles: Mapping[int, float], duration_ms: int) -> None:
        del duration_ms
        for joint_id, angle in joint_angles.items():
            self._angles[joint_id] = float(angle)

    def command_all(self, angles: Iterable[float], duration_ms: int) -> None:
        del duration_ms
        values = list(angles)
        if len(values) != 6:
            raise DofbotValidationError("command_all expects exactly 6 values")
        for index, angle in enumerate(values, start=1):
            self._angles[index] = float(angle)

    def read_joint_angle(self, joint_id: int) -> Optional[float]:
        return self._angles.get(joint_id)

    def set_torque(self, enabled: bool) -> None:
        del enabled

    def read_all_angles(self) -> Dict[int, float]:
        return dict(self._angles)

    def get_cached_angles(self) -> Dict[int, float]:
        return dict(self._angles)

    def get_hardware_version(self) -> str:
        return "simulated"


class WebotsBackend(BaseBackend):
    """Webots-backed backend using a simple ZMQ JSON RPC bridge."""

    def __init__(self, endpoint: str = "tcp://127.0.0.1:5557", timeout_ms: int = 1000):
        try:
            import zmq  # type: ignore
        except Exception as exc:
            raise DofbotConnectionError("pyzmq is required for Webots backend") from exc

        self._zmq = zmq
        self._context = zmq.Context.instance()
        self._socket = self._context.socket(zmq.REQ)
        self._socket.linger = 0
        self._socket.rcvtimeo = timeout_ms
        self._socket.sndtimeo = timeout_ms
        self._socket.connect(endpoint)
        self._angles: Dict[int, float] = {idx: 90.0 for idx in range(1, 7)}
        try:
            self._ping()
        except Exception:
            self.close()
            raise

    def _ping(self) -> None:
        self._request({"op": "ping"})

    def _request(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        try:
            self._socket.send_json(dict(payload))
            response = self._socket.recv_json()
        except Exception as exc:
            raise DofbotConnectionError(f"Webots bridge request failed: {exc}") from exc

        if not isinstance(response, dict):
            raise DofbotConnectionError("Webots bridge returned invalid response")
        if not response.get("ok", False):
            message = response.get("error", "unknown Webots bridge error")
            raise DofbotConnectionError(str(message))
        return response

    @staticmethod
    def _validate_joint(joint_id: int) -> int:
        value = int(joint_id)
        if value < 1 or value > 6:
            raise DofbotValidationError(f"Invalid joint_id {joint_id}; expected 1..6")
        return value

    def command_joint(self, joint_id: int, angle: float, duration_ms: int) -> None:
        del duration_ms
        normalized_joint = self._validate_joint(joint_id)
        normalized_angle = float(angle)
        self._request({"op": "command_joint", "joint_id": normalized_joint, "angle": normalized_angle})
        self._angles[normalized_joint] = normalized_angle

    def command_joints(self, joint_angles: Mapping[int, float], duration_ms: int) -> None:
        del duration_ms
        for joint_id, angle in joint_angles.items():
            self.command_joint(joint_id, angle, 0)

    def command_all(self, angles: Iterable[float], duration_ms: int) -> None:
        del duration_ms
        values = [float(angle) for angle in angles]
        if len(values) != 6:
            raise DofbotValidationError("command_all expects exactly 6 values")
        self._request({"op": "command_all", "angles": values})
        for index, angle in enumerate(values, start=1):
            self._angles[index] = angle

    def read_joint_angle(self, joint_id: int) -> Optional[float]:
        normalized_joint = self._validate_joint(joint_id)
        response = self._request({"op": "read_joint_angle", "joint_id": normalized_joint})
        angle = response.get("angle")
        if angle is None:
            return None
        value = float(angle)
        self._angles[normalized_joint] = value
        return value

    def read_all_angles(self) -> Dict[int, float]:
        response = self._request({"op": "read_joint_angles"})
        raw = response.get("angles", {})
        if not isinstance(raw, dict):
            return dict(self._angles)
        normalized: Dict[int, float] = {}
        for key, value in raw.items():
            joint_id = int(key)
            if 1 <= joint_id <= 6:
                normalized[joint_id] = float(value)
        if normalized:
            self._angles.update(normalized)
        return dict(self._angles)

    def set_torque(self, enabled: bool) -> None:
        self._request({"op": "set_torque", "enabled": bool(enabled)})

    def get_cached_angles(self) -> Dict[int, float]:
        return dict(self._angles)

    def get_hardware_version(self) -> str:
        return "webots"

    def close(self) -> None:
        try:
            self._socket.close()
        except Exception:
            pass

    def __del__(self) -> None:  # pragma: no cover - best effort cleanup
        self.close()
