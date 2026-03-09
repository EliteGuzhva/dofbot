"""Hardware-gated smoke test for real DOFBOT arm.

Run only when DOFBOT_HW_TEST=1 is set.
"""

import os
import time

from driver.dofbot_driver import DofbotConfig, DofbotDriver


def main() -> int:
    if os.getenv("DOFBOT_HW_TEST") != "1":
        print("Skipping hardware smoke test. Set DOFBOT_HW_TEST=1 to run.")
        return 0

    driver = DofbotDriver(DofbotConfig())
    print("Hardware version:", driver.get_hardware_version())
    driver.set_torque(True)

    safe_pose = [90, 90, 90, 90, 90, 60]
    driver.command_all(safe_pose, duration_ms=800)
    time.sleep(0.9)

    angles = driver.read_joint_angles()
    print("Readback:", angles)
    if not angles:
        print("No readback angles received.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
