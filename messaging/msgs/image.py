import numpy as np
from dataclasses import dataclass


@dataclass
class Image:
    width: int
    height: int
    channels: int

    @staticmethod
    def from_numpy(array: np.ndarray) -> "Image":
        return Image(
            width=array.shape[1],
            height=array.shape[0],
            channels=array.shape[2],
        )

    def to_numpy(self, raw_data: bytes) -> np.ndarray:
        return np.frombuffer(raw_data, dtype=np.uint8).reshape(
            self.height, self.width, self.channels
        )
