"""Low-level register definitions and encode/decode helpers."""

from __future__ import annotations

from enum import IntEnum
from typing import List, Optional

from .config import JointCalibration


class Register(IntEnum):
    VERSION = 0x01
    RGB = 0x02
    RESET = 0x05
    BUZZER = 0x06

    SERVO_BASE = 0x10
    SERVO_TORQUE = 0x1A
    SERVO_WRITE6 = 0x1D
    SERVO_WRITE6_TIME = 0x1E
    SERVO_READ_BASE = 0x30


def encode_joint_command(joint_id: int, pos: int, duration_ms: int) -> tuple[int, List[int]]:
    register = int(Register.SERVO_BASE) + joint_id
    payload = [(pos >> 8) & 0xFF, pos & 0xFF, (duration_ms >> 8) & 0xFF, duration_ms & 0xFF]
    return register, payload


def encode_sync_duration(duration_ms: int) -> List[int]:
    return [(duration_ms >> 8) & 0xFF, duration_ms & 0xFF]


def encode_sync_positions(positions: List[int]) -> List[int]:
    payload: List[int] = []
    for pos in positions:
        payload.extend([(pos >> 8) & 0xFF, pos & 0xFF])
    return payload


def decode_firmware_word(raw_word: int) -> int:
    return ((raw_word >> 8) & 0xFF) | ((raw_word << 8) & 0xFF00)


def angle_to_position(angle: float, calibration: JointCalibration) -> int:
    logical = calibration.angle_max - angle if calibration.invert else angle
    return int(
        (calibration.pos_max - calibration.pos_min)
        * (logical - calibration.angle_min)
        / (calibration.angle_max - calibration.angle_min)
        + calibration.pos_min
    )


def position_to_angle(position: int, calibration: JointCalibration) -> Optional[float]:
    if position < min(calibration.pos_min, calibration.pos_max):
        return None
    if position > max(calibration.pos_min, calibration.pos_max):
        return None
    angle = (
        (calibration.angle_max - calibration.angle_min)
        * (position - calibration.pos_min)
        / (calibration.pos_max - calibration.pos_min)
        + calibration.angle_min
    )
    if calibration.invert:
        angle = calibration.angle_max - angle
    if angle < calibration.angle_min or angle > calibration.angle_max:
        return None
    return float(angle)
