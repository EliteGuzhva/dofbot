import cv2
import time
import numpy as np
import argparse

from driver.arm import Arm
from messaging import Subscriber, Publisher, Message, msgs

arm: Arm


def process_cmd(msg: Message):
    print(msg)
    cmd = msgs.Cmd(**msg.payload)
    arm.set_position(
        np.array(cmd.position),
        duration_ms=cmd.time,
        open_gripper=cmd.gripper_open,
    )

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DOFBOT camera + command bridge")
    parser.add_argument(
        "--backend",
        choices=["hardware", "sim", "webots"],
        default="hardware",
        help="Driver backend to use.",
    )
    parser.add_argument(
        "--webots-endpoint",
        default="tcp://127.0.0.1:5557",
        help="Webots ZMQ endpoint used when --backend webots.",
    )
    parser.add_argument("--camera-index", type=int, default=0)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    arm = Arm(backend=args.backend, webots_endpoint=args.webots_endpoint)
    cap = cv2.VideoCapture(args.camera_index)

    subscriber = Subscriber()
    subscriber.subscribe("/cmd", process_cmd)
    subscriber.start()

    publisher = Publisher()

    while True:
        try:
            if not cap.grab():
                continue

            ts = time.time()
            ret, frame = cap.retrieve()
            if not ret:
                continue

            msg = Message(
                topic="/image",
                timestamp=ts,
                payload=msgs.Image.from_numpy(frame),
                raw_data=frame.tobytes(),
            )
            print(msg.topic, msg.timestamp, msg.payload)
            publisher.publish(msg)
        except KeyboardInterrupt:
            subscriber.stop()
            break
