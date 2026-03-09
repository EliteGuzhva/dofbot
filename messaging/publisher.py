import zmq
from dataclasses import is_dataclass, asdict

from .message import Message


class Publisher:
    def __init__(self, port: int = 5555):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind(f"tcp://*:{port}")

    def publish(self, message: Message):
        self.socket.send_string(message.topic, zmq.SNDMORE)
        self.socket.send_string(str(message.timestamp), zmq.SNDMORE)

        flags = zmq.SNDMORE if message.raw_data is not None else 0
        if is_dataclass(message.payload):
            self.socket.send_json(
                asdict(message.payload),  # type: ignore
                flags,
            )
        elif isinstance(message.payload, dict):
            self.socket.send_json(message.payload, flags)
        else:
            raise ValueError(
                f"Unsupported payload type: {type(message.payload)}"
            )

        if message.raw_data is not None:
            self.socket.send(message.raw_data)
