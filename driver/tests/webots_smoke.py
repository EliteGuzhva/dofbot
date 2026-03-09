"""Webots-gated smoke test.

Run only when DOFBOT_WEBOTS_TEST=1 and a Webots controller bridge is active.
"""

import os
import time

from driver.dofbot_driver import DofbotDriver


def main() -> int:
    if os.getenv("DOFBOT_WEBOTS_TEST") != "1":
        print("Skipping Webots smoke test. Set DOFBOT_WEBOTS_TEST=1 to run.")
        return 0

    endpoint = os.getenv("DOFBOT_WEBOTS_ENDPOINT", "tcp://127.0.0.1:5557")
    driver = DofbotDriver.webots(endpoint=endpoint, timeout_ms=1000)
    driver.set_torque(True)
    driver.command_all([90, 80, 70, 90, 110, 60], duration_ms=500)
    time.sleep(0.1)

    angles = driver.read_joint_angles()
    print("Readback:", angles)
    if len(angles) != 6:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
