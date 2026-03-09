"""Public high-level driver API."""

from __future__ import annotations

from typing import Dict, Iterable, Mapping, Optional

from .backends import BaseBackend, I2CBackend, SimBackend, WebotsBackend
from .config import DofbotConfig
from .errors import DofbotValidationError
from .transport import I2CTransport


class DofbotDriver:
    """Main DOFBOT driver using pluggable backend implementations."""

    def __init__(self, config: Optional[DofbotConfig] = None, backend: Optional[BaseBackend] = None):
        self.config = config or DofbotConfig()
        if backend is not None:
            self.backend = backend
        else:
            transport = I2CTransport(self.config)
            self.backend = I2CBackend(self.config, transport)

    @classmethod
    def simulation(cls) -> "DofbotDriver":
        return cls(backend=SimBackend())

    @classmethod
    def webots(cls, endpoint: str = "tcp://127.0.0.1:5557", timeout_ms: int = 1000) -> "DofbotDriver":
        return cls(backend=WebotsBackend(endpoint=endpoint, timeout_ms=timeout_ms))

    def command_joint(self, joint_id: int, angle: float, duration_ms: Optional[int] = None) -> None:
        self.backend.command_joint(joint_id, angle, self._normalize_duration(duration_ms))

    def command_joints(self, joint_angles: Mapping[int, float], duration_ms: Optional[int] = None) -> None:
        self.backend.command_joints(joint_angles, self._normalize_duration(duration_ms))

    def command_all(self, angles: Iterable[float], duration_ms: Optional[int] = None) -> None:
        self.backend.command_all(angles, self._normalize_duration(duration_ms))

    def read_joint_angle(self, joint_id: int) -> Optional[float]:
        return self.backend.read_joint_angle(joint_id)

    def read_joint_angles(self) -> Dict[int, float]:
        if hasattr(self.backend, "read_all_angles"):
            return self.backend.read_all_angles()  # type: ignore[no-any-return]
        values: Dict[int, float] = {}
        for joint_id in range(1, 7):
            angle = self.backend.read_joint_angle(joint_id)
            if angle is not None:
                values[joint_id] = angle
        return values

    def set_torque(self, enabled: bool) -> None:
        self.backend.set_torque(enabled)

    def get_cached_angles(self) -> Dict[int, float]:
        if hasattr(self.backend, "get_cached_angles"):
            return self.backend.get_cached_angles()  # type: ignore[no-any-return]
        return self.read_joint_angles()

    def get_hardware_version(self) -> str:
        if hasattr(self.backend, "get_hardware_version"):
            return self.backend.get_hardware_version()  # type: ignore[no-any-return]
        return "simulated"

    def reset_board(self) -> None:
        if hasattr(self.backend, "reset_board"):
            self.backend.reset_board()  # type: ignore[misc]

    def set_rgb(self, red: int, green: int, blue: int) -> None:
        if hasattr(self.backend, "set_rgb"):
            self.backend.set_rgb(red, green, blue)  # type: ignore[misc]

    def _normalize_duration(self, duration_ms: Optional[int]) -> int:
        duration = self.config.default_duration_ms if duration_ms is None else int(duration_ms)
        if duration <= 0 or duration > 65535:
            raise DofbotValidationError("duration_ms must be in range [1, 65535]")
        return duration
