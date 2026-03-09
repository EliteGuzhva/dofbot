"""Transport abstraction and concrete I2C implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
import time
from typing import List, Optional

from .config import DofbotConfig
from .errors import DofbotConnectionError

LOGGER = logging.getLogger(__name__)


class Transport(ABC):
    @abstractmethod
    def write_byte(self, register: int, value: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def write_block(self, register: int, data: List[int]) -> None:
        raise NotImplementedError

    @abstractmethod
    def read_byte(self, register: int) -> int:
        raise NotImplementedError

    @abstractmethod
    def read_word(self, register: int) -> int:
        raise NotImplementedError


class I2CTransport(Transport):
    def __init__(self, config: DofbotConfig):
        self._config = config
        self._bus = self._open_bus(config.i2c_bus)

    def write_byte(self, register: int, value: int) -> None:
        self._retry(lambda: self._bus.write_byte_data(self._config.i2c_address, register, value))

    def write_block(self, register: int, data: List[int]) -> None:
        self._retry(lambda: self._bus.write_i2c_block_data(self._config.i2c_address, register, data))

    def read_byte(self, register: int) -> int:
        return self._retry(lambda: self._bus.read_byte_data(self._config.i2c_address, register))

    def read_word(self, register: int) -> int:
        return self._retry(lambda: self._bus.read_word_data(self._config.i2c_address, register))

    @staticmethod
    def _open_bus(bus_id: int):
        try:
            import smbus  # type: ignore

            return smbus.SMBus(bus_id)
        except Exception as exc:
            raise DofbotConnectionError(f"Failed to open I2C bus {bus_id}: {exc}") from exc

    def _retry(self, operation):
        last_error: Optional[Exception] = None
        for _ in range(self._config.retries):
            try:
                return operation()
            except Exception as exc:
                last_error = exc
                LOGGER.warning("I2C retry after error: %s", exc)
                time.sleep(self._config.retry_delay_s)
        raise DofbotConnectionError(f"I2C operation failed after retries: {last_error}")
