from typing import Any, Optional
from dataclasses import dataclass


@dataclass
class Message:
    topic: str
    timestamp: float
    payload: Any
    raw_data: Optional[bytes] = None
