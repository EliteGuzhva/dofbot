"""Configuration models for DOFBOT driver behavior and calibration."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Dict, Mapping


@dataclass(frozen=True)
class JointCalibration:
    angle_min: float
    angle_max: float
    pos_min: int
    pos_max: int
    invert: bool = False


@dataclass(frozen=True)
class DofbotConfig:
    i2c_bus: int = 1
    i2c_address: int = 0x15
    retries: int = 3
    retry_delay_s: float = 0.002
    clamp_inputs: bool = False
    default_duration_ms: int = 500
    joints: Mapping[int, JointCalibration] = field(
        default_factory=lambda: {
            1: JointCalibration(0, 180, 900, 3100, invert=False),
            2: JointCalibration(0, 180, 900, 3100, invert=True),
            3: JointCalibration(0, 180, 900, 3100, invert=True),
            4: JointCalibration(0, 180, 900, 3100, invert=True),
            5: JointCalibration(0, 270, 380, 3700, invert=False),
            6: JointCalibration(0, 180, 900, 3100, invert=False),
        }
    )

    @staticmethod
    def from_json(path: str) -> "DofbotConfig":
        """Load config overrides from a JSON file."""
        payload = json.loads(Path(path).read_text())
        joints: Dict[int, JointCalibration] = {}
        for raw_joint_id, values in payload.get("joints", {}).items():
            joint_id = int(raw_joint_id)
            joints[joint_id] = JointCalibration(
                angle_min=float(values["angle_min"]),
                angle_max=float(values["angle_max"]),
                pos_min=int(values["pos_min"]),
                pos_max=int(values["pos_max"]),
                invert=bool(values.get("invert", False)),
            )
        return DofbotConfig(
            i2c_bus=int(payload.get("i2c_bus", 1)),
            i2c_address=int(payload.get("i2c_address", 0x15)),
            retries=int(payload.get("retries", 3)),
            retry_delay_s=float(payload.get("retry_delay_s", 0.002)),
            clamp_inputs=bool(payload.get("clamp_inputs", False)),
            default_duration_ms=int(payload.get("default_duration_ms", 500)),
            joints=joints if joints else DofbotConfig().joints,
        )
