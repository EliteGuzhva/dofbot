"""High-level DOFBOT arm controller built on robust board driver."""

import time
import math
import numpy as np
from typing import Dict

from driver.dofbot_driver import DofbotConfig, DofbotDriver

# Dofbot DH parameters (approximate; tune for your hardware)
LINK_LENGTHS = {
    "L1": 0.061,
    "L2": 0.1045,
    "L3": 0.08285,
    "L4": 0.061,
}

JOINT_IDS = {
    "base": 1,
    "shoulder": 2,
    "elbow": 3,
    "wrist_pitch": 4,
    "wrist_roll": 5,
    "gripper": 6,
}

# Public joint limits in degrees
SERVO_LIMITS = {
    "base": (0, 180),
    "shoulder": (0, 180),
    "elbow": (0, 180),
    "wrist_pitch": (0, 180),
    "wrist_roll": (0, 270),
    "gripper": (20, 90),
}

HOME_POSITION = {
    "base": 90,
    "shoulder": 90,
    "elbow": 90,
    "wrist_pitch": 90,
    "wrist_roll": 90,
    "gripper": 60,
}

class DofbotArm:
    """High-level controller (IK + smooth interpolation) for DOFBOT."""

    def __init__(self, simulate: bool = False):
        self.simulate = simulate
        self.driver = DofbotDriver.simulation() if simulate else DofbotDriver(DofbotConfig())
        self.current_joints = dict(HOME_POSITION)
        self._apply_joints(self.current_joints, duration_ms=800)

    def _apply_joints(self, joints: Dict[str, float], duration_ms: int = 60) -> None:
        """Send joint angles to hardware and update cached state."""
        id_to_angle = {}
        for name, angle in joints.items():
            lo, hi = SERVO_LIMITS[name]
            clamped = max(lo, min(hi, angle))
            if self.driver:
                id_to_angle[JOINT_IDS[name]] = clamped
            self.current_joints[name] = clamped
        if id_to_angle:
            self.driver.command_joints(id_to_angle, duration_ms=duration_ms)

    def set_joints(self, joints: Dict[str, float], duration: float = 1.0, steps: int = 20):
        """Move to target joint angles with smooth interpolation."""
        target = dict(self.current_joints)
        target.update(joints)

        if steps <= 0:
            self._apply_joints(target, duration_ms=max(1, int(duration * 1000)))
            return self.current_joints

        start = dict(self.current_joints)
        step_duration_s = duration / steps
        step_duration_ms = max(1, int(step_duration_s * 1000))
        for i in range(steps + 1):
            t = i / steps
            t_smooth = t * t * (3 - 2 * t)
            intermediate = {}
            for name in self.current_joints:
                intermediate[name] = start[name] + (target[name] - start[name]) * t_smooth
            self._apply_joints(intermediate, duration_ms=step_duration_ms)
            time.sleep(step_duration_s)

        return self.current_joints

    def go_home(self, duration: float = 1.5):
        self.set_joints(HOME_POSITION, duration=duration)
        return HOME_POSITION

    def open_gripper(self):
        self.set_joints({"gripper": 90}, duration=0.5)
        return "gripper opened"

    def close_gripper(self):
        self.set_joints({"gripper": 20}, duration=0.5)
        return "gripper closed"

    def move_to_xyz(self, x: float, y: float, z: float, duration: float = 1.5):
        """Move end-effector to (x, y, z) in meters relative to base."""
        joints = self._solve_ik(x, y, z)
        if joints is None:
            return {"error": f"Position ({x:.3f}, {y:.3f}, {z:.3f}) is unreachable"}
        self.set_joints(joints, duration=duration)
        return {"status": "ok", "joints": self.current_joints, "target": {"x": x, "y": y, "z": z}}

    def _solve_ik(self, x: float, y: float, z: float) -> dict | None:
        """Simplified 3-DOF geometric IK for the Dofbot."""
        L1 = LINK_LENGTHS["L1"]
        L2 = LINK_LENGTHS["L2"]
        L3 = LINK_LENGTHS["L3"]
        L4 = LINK_LENGTHS["L4"]

        base_rad = math.atan2(y, x)
        base_deg = math.degrees(base_rad) + 90

        r = math.sqrt(x**2 + y**2)
        z_wrist = z - L1 + L4

        D = (r**2 + z_wrist**2 - L2**2 - L3**2) / (2 * L2 * L3)

        if abs(D) > 1.0:
            return None

        elbow_rad = math.atan2(-math.sqrt(1 - D**2), D)
        elbow_deg = math.degrees(elbow_rad) + 90

        shoulder_rad = math.atan2(z_wrist, r) - math.atan2(
            L3 * math.sin(elbow_rad),
            L2 + L3 * math.cos(elbow_rad)
        )
        shoulder_deg = 90 - math.degrees(shoulder_rad)

        wrist_pitch_deg = 90 - (shoulder_deg - 90) - (elbow_deg - 90)
        wrist_pitch_deg = max(0, min(180, wrist_pitch_deg))

        for name, val in [("base", base_deg), ("shoulder", shoulder_deg), ("elbow", elbow_deg)]:
            lo, hi = SERVO_LIMITS[name]
            if val < lo or val > hi:
                return None

        return {
            "base": base_deg,
            "shoulder": shoulder_deg,
            "elbow": elbow_deg,
            "wrist_pitch": wrist_pitch_deg,
            "wrist_roll": 90,
        }

    def _solve_ik_rtb(self, x: float, y: float, z: float):
        """
        Full 6-DOF IK using roboticstoolbox-python.
        Uncomment and use if you need orientation control.

        pip3 install roboticstoolbox-python

        from roboticstoolbox import DHRobot, RevoluteDH
        import spatialmath as sm

        # Define your DH parameters here
        robot = DHRobot([
            RevoluteDH(d=0.061,  a=0,       alpha=math.pi/2),
            RevoluteDH(d=0,      a=0.1045,  alpha=0),
            RevoluteDH(d=0,      a=0.08285, alpha=0),
            RevoluteDH(d=0,      a=0,       alpha=math.pi/2),
            RevoluteDH(d=0.061,  a=0,       alpha=0),
        ], name="dofbot")

        T = sm.SE3(x, y, z) * sm.SE3.Rz(0)  # target pose
        sol = robot.ikine_LM(T, q0=np.zeros(5))
        if sol.success:
            return np.degrees(sol.q)
        return None
        """
        pass

    def get_joint_angles(self) -> dict:
        return dict(self.current_joints)

    def get_end_effector_position(self) -> dict:
        """Approximate FK from current joint angles."""
        j = self.current_joints
        L1 = LINK_LENGTHS["L1"]
        L2 = LINK_LENGTHS["L2"]
        L3 = LINK_LENGTHS["L3"]
        L4 = LINK_LENGTHS["L4"]

        base_rad = math.radians(j["base"] - 90)
        shoulder_rad = math.radians(90 - j["shoulder"])
        elbow_rad = math.radians(j["elbow"] - 90)

        r = L2 * math.cos(shoulder_rad) + L3 * math.cos(shoulder_rad + elbow_rad)
        z = L1 + L2 * math.sin(shoulder_rad) + L3 * math.sin(shoulder_rad + elbow_rad) - L4

        x = r * math.cos(base_rad)
        y = r * math.sin(base_rad)

        return {"x": round(x, 4), "y": round(y, 4), "z": round(z, 4)}


if __name__ == "__main__":
    arm = DofbotArm(simulate=True)
    print("Home position:", arm.get_joint_angles())
    print("End-effector:", arm.get_end_effector_position())

    result = arm.move_to_xyz(0.15, 0.0, 0.05)
    print("Move result:", result)
    print("End-effector after move:", arm.get_end_effector_position())
