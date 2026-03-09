import time
import math
from typing import Dict, List, Optional

from .dofbot_driver import DofbotConfig, DofbotDriver


class PwmBackend:
    def __init__(self):
        self._NAME_TO_IDX = {
            "joint1": 0,
            "joint2": 1,
            "joint3": 2,
            "joint4": 3,
            "joint5": 4,
            "joint6": 5,
        }
        self._TIME: int = 500

        self._current_state = {
            "joint1": math.radians(0),
            "joint2": math.radians(45),
            "joint3": math.radians(-60),
            "joint4": math.radians(-60),
            "joint5": math.radians(0),
            "joint6": math.radians(-60),
        }
        self._prev_state = self._current_state.copy()
        self._last_write_time_ms: int = 0
        self._last_duration_ms: int = self._TIME

        self._device = DofbotDriver(DofbotConfig())

    @staticmethod
    def _convert_to_input(radians: float) -> int:
        return int(math.degrees(radians) + 90)

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1e3)

    def read(self) -> Dict[str, float]:
        # res = {}
        # for i in range(1, 7):
        #     val = self._device.serial_servo_read(i)
        #     if val is not None:
        #         res[f"joint{i}"] = math.radians(val)

        # return res

        now_ms = self._now_ms()
        diff_ms = now_ms - self._last_write_time_ms
        ratio = min(1.0, diff_ms / self._last_duration_ms)
        state = self._prev_state.copy()
        for k, v in self._current_state.items():
            dv = v - self._prev_state[k]
            state[k] += dv * ratio

        return state

    def write(
        self,
        joint_positions_rad: Dict[str, float],
        time_ms: Optional[int] = None,
    ) -> None:
        self._prev_state = self._current_state.copy()
        self._current_state.update(joint_positions_rad)
        joints: List[float] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        for key, value in self._current_state.items():
            joints[self._NAME_TO_IDX[key]] = self._convert_to_input(value)
        self._last_duration_ms = self._TIME if time_ms is None else int(max(1, time_ms))
        self._last_write_time_ms = self._now_ms()
        self._device.command_all(joints, duration_ms=self._last_duration_ms)

    def get_positions(self, joint_names) -> List[float]:
        cur = self.read()
        return [cur.get(j, 0.0) for j in joint_names]

    def stop_motion(self) -> None:
        # E-stop-ish: command current pose with a very short duration
        self.write(self.read(), time_ms=1)
