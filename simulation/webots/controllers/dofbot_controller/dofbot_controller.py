"""Webots controller for DOFBOT with a lightweight ZMQ command server.

Run this controller inside Webots. External Python code can command joints by
connecting to the configured endpoint (default: tcp://127.0.0.1:5557).
"""

from __future__ import annotations

import json
import os
from typing import Dict, List

from controller import Robot  # type: ignore

try:
    import zmq
except Exception as exc:  # pragma: no cover - requires runtime dependency
    raise RuntimeError("pyzmq is required for dofbot_controller") from exc


WEBOTS_JOINT_NAMES = ["joint1", "joint2", "joint3", "joint4", "joint5"]
SERVO_JOINT_COUNT = 6
DEFAULT_ANGLE_DEG = 90.0
# Match hardware calibration semantics used by I2C backend:
# joints 2-4 are logically inverted.
JOINT_SIGN_BY_ID = {
    1: 1.0,
    2: -1.0,
    3: -1.0,
    4: -1.0,
    5: 1.0,
    6: 1.0,
}


def angle_deg_to_rad(angle_deg: float) -> float:
    return angle_deg * 3.141592653589793 / 180.0


def angle_rad_to_deg(angle_rad: float) -> float:
    return angle_rad * 180.0 / 3.141592653589793


def servo_deg_to_joint_rad(joint_id: int, servo_deg: float) -> float:
    sign = JOINT_SIGN_BY_ID.get(joint_id, 1.0)
    centered_deg = sign * (float(servo_deg) - 90.0)
    return angle_deg_to_rad(centered_deg)


def joint_rad_to_servo_deg(joint_id: int, joint_rad: float) -> float:
    sign = JOINT_SIGN_BY_ID.get(joint_id, 1.0)
    centered_deg = sign * angle_rad_to_deg(float(joint_rad))
    return 90.0 + centered_deg


def load_endpoint(robot: Robot) -> str:
    from_env = os.getenv("DOFBOT_WEBOTS_ENDPOINT")
    if from_env:
        return from_env

    raw = robot.getCustomData() or ""
    raw = raw.strip()
    if not raw:
        return "tcp://127.0.0.1:5557"
    try:
        payload = json.loads(raw)
        value = payload.get("endpoint")
        if isinstance(value, str) and value:
            return value
    except json.JSONDecodeError:
        pass
    return "tcp://127.0.0.1:5557"


def main() -> int:
    robot = Robot()
    timestep = int(robot.getBasicTimeStep())

    motors: Dict[int, object] = {}
    sensors: Dict[int, object] = {}
    current_angles: Dict[int, float] = {}

    for joint_id in range(1, SERVO_JOINT_COUNT + 1):
        current_angles[joint_id] = DEFAULT_ANGLE_DEG

    for joint_id, joint_name in enumerate(WEBOTS_JOINT_NAMES, start=1):
        motor = robot.getDevice(joint_name)
        sensor = motor.getPositionSensor()
        sensor.enable(timestep)
        start_rad = servo_deg_to_joint_rad(joint_id, DEFAULT_ANGLE_DEG)
        motor.setPosition(start_rad)
        motors[joint_id] = motor
        sensors[joint_id] = sensor

    context = zmq.Context.instance()
    socket = context.socket(zmq.REP)
    socket.linger = 0
    endpoint = load_endpoint(robot)
    socket.bind(endpoint)
    print(f"[dofbot_controller] listening on {endpoint}")

    while robot.step(timestep) != -1:
        for joint_id, sensor in sensors.items():
            current_angles[joint_id] = joint_rad_to_servo_deg(joint_id, sensor.getValue())

        while True:
            try:
                raw = socket.recv_json(flags=zmq.NOBLOCK)
            except zmq.Again:
                break

            op = raw.get("op")
            if op == "ping":
                socket.send_json({"ok": True, "kind": "webots-controller"})
                continue

            if op == "command_joint":
                joint_id = int(raw["joint_id"])
                angle = float(raw["angle"])
                if joint_id in motors:
                    motors[joint_id].setPosition(servo_deg_to_joint_rad(joint_id, angle))
                current_angles[joint_id] = angle
                socket.send_json({"ok": True})
                continue

            if op == "command_all":
                angles: List[float] = [float(v) for v in raw["angles"]]
                if len(angles) != 6:
                    socket.send_json({"ok": False, "error": "command_all expects 6 values"})
                    continue
                for joint_id, angle in enumerate(angles, start=1):
                    if joint_id in motors:
                        motors[joint_id].setPosition(servo_deg_to_joint_rad(joint_id, angle))
                    current_angles[joint_id] = angle
                socket.send_json({"ok": True})
                continue

            if op == "read_joint_angle":
                joint_id = int(raw["joint_id"])
                value = current_angles.get(joint_id)
                socket.send_json({"ok": True, "angle": value})
                continue

            if op == "set_torque":
                # Servo torque toggling is not exposed directly in this controller;
                # keep no-op semantics for API compatibility.
                socket.send_json({"ok": True})
                continue

            if op == "read_joint_angles":
                socket.send_json({"ok": True, "angles": current_angles})
                continue

            socket.send_json({"ok": False, "error": f"unknown op: {op}"})

    socket.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
