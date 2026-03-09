import math
import numpy as np
from time import sleep
from typing import Optional
from ikpy.chain import Chain  # type: ignore

from .dofbot_driver import DofbotConfig, DofbotDriver


class Arm:
    def __init__(
        self,
        urdf_file: str = "description/urdf/dofbot.urdf",
        read_timeout_s: float = 1.0,
        read_interval_s: float = 0.01,
        backend: str = "hardware",
        webots_endpoint: str = "tcp://127.0.0.1:5557",
        driver: Optional[DofbotDriver] = None,
    ):
        self.GRIPPER_OPEN_ANGLE = math.radians(-90)
        self.GRIPPER_CLOSED_ANGLE = math.radians(90)
        self._read_timeout_s = read_timeout_s
        self._read_interval_s = read_interval_s

        if driver is not None:
            self.driver = driver
        elif backend == "hardware":
            self.driver = DofbotDriver(DofbotConfig())
        elif backend == "sim":
            self.driver = DofbotDriver.simulation()
        elif backend == "webots":
            self.driver = DofbotDriver.webots(endpoint=webots_endpoint)
        else:
            raise ValueError(f"Unknown backend '{backend}', expected hardware|sim|webots")
        self._state_cache = np.zeros(6)
        self.chain = Chain.from_urdf_file(
            urdf_file,
            active_links_mask=[False, True, True, True, True, True],
        )

    @staticmethod
    def to_state(v: float):
        return math.radians(v - 90)

    @staticmethod
    def from_state(v: float):
        return math.degrees(v) + 90

    def _read_joint_with_timeout(self, joint_id: int, timeout_s: Optional[float] = None) -> float:
        timeout = self._read_timeout_s if timeout_s is None else timeout_s
        deadline = timeout if timeout > 0 else 0
        elapsed = 0.0
        while True:
            value = self.driver.read_joint_angle(joint_id)
            if value is not None:
                return float(value)
            if timeout <= 0:
                break
            sleep(self._read_interval_s)
            elapsed += self._read_interval_s
            if elapsed >= deadline:
                break
        raise TimeoutError(f"Timeout reading joint {joint_id} after {timeout:.2f}s")

    def get_state(self, timeout_s: Optional[float] = None):
        state = []
        for i in range(1, 7):
            value = self._read_joint_with_timeout(i, timeout_s=timeout_s)
            state.append(self.to_state(value))

        new_state = np.array(state, dtype=float)
        self._state_cache = new_state
        return new_state

    def set_state(self, state: np.ndarray, duration_ms: int = 500):
        values = np.asarray(state, dtype=float).flatten()
        if values.shape[0] != 6:
            raise ValueError(f"state must contain exactly 6 joints, got {values.shape[0]}")
        if not np.all(np.isfinite(values)):
            raise ValueError("state contains non-finite values")

        joints = []
        for v in values:
            joints.append(self.from_state(v))

        self.driver.command_all(joints, duration_ms=duration_ms)
        self._state_cache = values
        sleep(duration_ms * 1e-3)

    def get_position(self) -> np.ndarray:
        state = self.get_state()
        return self.chain.forward_kinematics(state[:6])

    def set_position(
        self,
        position: np.ndarray,
        orientation: Optional[np.ndarray] = None,
        mode: Optional[str] = None,
        duration_ms: int = 500,
        open_gripper: Optional[bool] = None,
        use_readback: bool = False,
    ):
        current_state = self.get_state() if use_readback else self._state_cache.copy()
        target_orientation = np.zeros(3) if orientation is None else orientation
        joints = self.chain.inverse_kinematics(position, target_orientation, mode)[1:]
        gripper_state = current_state[5]
        if open_gripper is not None:
            gripper_state = (
                self.GRIPPER_OPEN_ANGLE
                if open_gripper
                else self.GRIPPER_CLOSED_ANGLE
            )
        joints = np.append(joints, gripper_state)
        self.set_state(joints, duration_ms=duration_ms)

    def close_gripper(self, duration_ms: int = 500):
        value = int(self.from_state(self.GRIPPER_CLOSED_ANGLE))
        self.driver.command_joint(6, value, duration_ms=duration_ms)
        self._state_cache[5] = self.GRIPPER_CLOSED_ANGLE
        sleep(duration_ms * 1e-3)

    def open_gripper(self, duration_ms: int = 500):
        value = int(self.from_state(self.GRIPPER_OPEN_ANGLE))
        self.driver.command_joint(6, value, duration_ms=duration_ms)
        self._state_cache[5] = self.GRIPPER_OPEN_ANGLE
        sleep(duration_ms * 1e-3)
