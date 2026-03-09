"""Calibration and diagnostics utility for the DOFBOT driver."""

from __future__ import annotations

import argparse
import time
from typing import Iterable

from driver.dofbot_driver import DofbotConfig, DofbotDriver, DofbotError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calibrate and diagnose DOFBOT joints.")
    parser.add_argument("--joint", type=int, choices=range(1, 7), help="Single joint to test.")
    parser.add_argument("--duration-ms", type=int, default=700, help="Motion duration in ms.")
    parser.add_argument("--pause-s", type=float, default=0.8, help="Pause between moves in seconds.")
    parser.add_argument("--min-angle", type=float, default=10.0, help="Min test angle for standard joints.")
    parser.add_argument("--max-angle", type=float, default=170.0, help="Max test angle for standard joints.")
    parser.add_argument("--joint5-min-angle", type=float, default=20.0, help="Min test angle for joint 5.")
    parser.add_argument("--joint5-max-angle", type=float, default=250.0, help="Max test angle for joint 5.")
    parser.add_argument(
        "--backend",
        choices=["hardware", "sim", "webots"],
        default="hardware",
        help="Driver backend to use.",
    )
    parser.add_argument(
        "--webots-endpoint",
        default="tcp://127.0.0.1:5557",
        help="Webots endpoint used when --backend webots.",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Deprecated alias for --backend sim.",
    )
    return parser.parse_args()


def test_joint(
    driver: DofbotDriver,
    joint_id: int,
    min_angle: float,
    max_angle: float,
    duration_ms: int,
    pause_s: float,
) -> None:
    center = (min_angle + max_angle) / 2.0
    sequence = [center, min_angle, center, max_angle, center]
    print(f"[joint {joint_id}] testing range {min_angle:.1f}..{max_angle:.1f}")
    for angle in sequence:
        print(f"  -> move to {angle:.1f}")
        driver.command_joint(joint_id, angle, duration_ms=duration_ms)
        time.sleep(max(pause_s, duration_ms / 1000.0))
        measured = driver.read_joint_angle(joint_id)
        print(f"     readback: {measured}")


def run(joints: Iterable[int], args: argparse.Namespace) -> None:
    backend = "sim" if args.simulate else args.backend
    if backend == "hardware":
        driver = DofbotDriver(DofbotConfig())
    elif backend == "sim":
        driver = DofbotDriver.simulation()
    elif backend == "webots":
        driver = DofbotDriver.webots(endpoint=args.webots_endpoint)
    else:  # pragma: no cover - argparse constrains this
        raise ValueError(f"Unsupported backend: {backend}")

    try:
        print("Hardware version:", driver.get_hardware_version())
    except DofbotError as exc:
        print("Warning: failed to read hardware version:", exc)

    driver.set_torque(True)
    for joint_id in joints:
        min_angle = args.joint5_min_angle if joint_id == 5 else args.min_angle
        max_angle = args.joint5_max_angle if joint_id == 5 else args.max_angle
        test_joint(
            driver=driver,
            joint_id=joint_id,
            min_angle=min_angle,
            max_angle=max_angle,
            duration_ms=args.duration_ms,
            pause_s=args.pause_s,
        )

    print("Final cached angles:", driver.get_cached_angles())


if __name__ == "__main__":
    cli_args = parse_args()
    selected = [cli_args.joint] if cli_args.joint else [1, 2, 3, 4, 5, 6]
    run(selected, cli_args)
