from time import sleep
import math
import numpy as np
import argparse
from scipy.spatial.transform import Rotation

from driver.arm import Arm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simple DOFBOT IK trajectory demo")
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
    return parser.parse_args()


args = parse_args()
arm = Arm(backend=args.backend, webots_endpoint=args.webots_endpoint)

# arm.arm.serial_servo_write(5, 90, 300)

# arm.set_position(np.array([0, 0.1, 0.27]))
# sleep(0.5)
# state = arm.get_state()
# state[3] -= math.radians(10)
# state[4] -= math.radians(30)
# while True:
#     state[3] += math.radians(40)
#     state[4] += math.radians(60)
#     arm.set_state(state, 300)
#     sleep(0.3)

#     state[3] -= math.radians(40)
#     state[4] -= math.radians(60)
#     arm.set_state(state, 200)
#     sleep(0.2)

# for i in range(10):
#     arm.set_position(np.array([0.0, 0.01 * i + 0.1, 0.13]))
#     if i == 0:
#         arm.close_gripper()
#     elif i == 9:
#         arm.open_gripper()

center = np.array([0.0, 0.1, 0.2])
radius = 0.05
angle = 0
speed = 20
for _ in range(100):
    t = center + radius * np.array([math.cos(math.radians(angle)), 0.0, math.sin(math.radians(angle))])
    angle += speed
    if angle >= 360:
        angle = 0

    arm.set_position(t, duration_ms=200)