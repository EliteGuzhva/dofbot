from typing import List
from dataclasses import dataclass


@dataclass
class Cmd:
    time: int
    position: List[float]
    gripper_open: bool
