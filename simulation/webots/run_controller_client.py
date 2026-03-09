#!/usr/bin/env python3
"""Quick command-line client for the Webots DOFBOT controller."""

from __future__ import annotations

import argparse
from typing import List

from driver.dofbot_driver import DofbotDriver


def parse_angles(raw: str) -> List[float]:
    parts = [segment.strip() for segment in raw.split(",") if segment.strip()]
    if len(parts) != 6:
        raise ValueError("Expected exactly 6 comma-separated angles.")
    return [float(value) for value in parts]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="tcp://127.0.0.1:5557")
    parser.add_argument("--angles", default="90,90,90,90,90,90")
    parser.add_argument("--duration-ms", type=int, default=500)
    args = parser.parse_args()

    driver = DofbotDriver.webots(endpoint=args.endpoint)
    angles = parse_angles(args.angles)
    driver.command_all(angles, duration_ms=args.duration_ms)
    print("Readback:", driver.read_joint_angles())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
