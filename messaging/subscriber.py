import zmq
import json
import threading
from typing import Callable, Dict, List

from .message import Message


class Subscriber:
    def __init__(self, host: str = "192.168.4.227", port: int = 5555):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(f"tcp://{host}:{port}")

        self.should_stop = False
        self.thread = None
        self.callbacks: Dict[str, Callable[[Message], None]] = {}

    def subscribe(self, topic: str, callback: Callable[[Message], None]):
        self.socket.subscribe(topic)
        self.callbacks[topic] = callback

    def _parse_message(self, raw_msg: List[bytes]) -> Message:
        return Message(
            topic=raw_msg[0].decode("utf-8"),
            timestamp=float(raw_msg[1]),
            payload=json.loads(raw_msg[2].decode("utf-8")),
            raw_data=raw_msg[3] if len(raw_msg) > 3 else None,
        )

    def loop(self):
        while not self.should_stop:
            # Drain the queue to get only the latest message
            raw_msg = None
            while True:
                try:
                    raw_msg = self.socket.recv_multipart(zmq.NOBLOCK)
                except zmq.Again:
                    # No more messages in queue, use the last one we got
                    break

            # If no messages were available, wait for one
            if raw_msg is None:
                raw_msg = self.socket.recv_multipart()

            msg = self._parse_message(raw_msg)
            self.callbacks[msg.topic](msg)

    def start(self):
        self.thread = threading.Thread(target=self.loop)
        self.thread.start()

    def stop(self):
        self.should_stop = True
        if self.thread is not None:
            self.thread.join()
