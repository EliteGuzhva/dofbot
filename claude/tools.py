"""
tools.py — Tool definitions for the Claude API tool-use protocol.

Each tool is:
  1. A JSON schema (sent to Claude so it knows what tools exist)
  2. A handler function (executed locally when Claude calls the tool)

This is the bridge between the LLM's reasoning and the physical arm.
"""

from arm_controller import DofbotArm
from perception import Perception


# ─── Tool Registry ──────────────────────────────────────────────────────

class ToolRegistry:
    """
    Manages the set of tools available to the LLM.
    Provides JSON schemas for the API call + dispatches tool invocations.
    """

    def __init__(self, arm: DofbotArm, perception: Perception):
        self.arm = arm
        self.perception = perception

    def get_tool_schemas(self) -> list[dict]:
        """
        Return tool definitions in Anthropic's tool-use format.
        These get sent in the `tools` parameter of the API call.
        """
        return [
            {
                "name": "get_scene_description",
                "description": (
                    "Look at the workspace with the camera and describe what objects "
                    "are visible, including their positions in arm coordinates (meters). "
                    "Call this before deciding what to pick up."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "move_to_xyz",
                "description": (
                    "Move the arm's end-effector (gripper) to a target position in 3D space. "
                    "Coordinates are in meters relative to the arm base. "
                    "x=forward, y=left, z=up. Typical reach is 0.05-0.25m. "
                    "Table surface is at z≈0.01. Use z≈0.05 to hover above an object, "
                    "z≈0.01 to touch the table."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "x": {
                            "type": "number",
                            "description": "Forward distance in meters (0.05 to 0.25)",
                        },
                        "y": {
                            "type": "number",
                            "description": "Left/right distance in meters (-0.15 to 0.15)",
                        },
                        "z": {
                            "type": "number",
                            "description": "Height in meters (0.0 to 0.25)",
                        },
                    },
                    "required": ["x", "y", "z"],
                },
            },
            {
                "name": "move_joints",
                "description": (
                    "Directly set joint angles in degrees. Use this for fine control "
                    "or if move_to_xyz fails. Joints: base (0-180, 90=center), "
                    "shoulder (0-180, 90=upright), elbow (0-180, 90=straight), "
                    "wrist_pitch (0-180), wrist_roll (0-180). "
                    "Only specify the joints you want to change."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "base":         {"type": "number", "description": "Base rotation, 0-180°"},
                        "shoulder":     {"type": "number", "description": "Shoulder angle, 0-180°"},
                        "elbow":        {"type": "number", "description": "Elbow angle, 0-180°"},
                        "wrist_pitch":  {"type": "number", "description": "Wrist pitch, 0-180°"},
                        "wrist_roll":   {"type": "number", "description": "Wrist roll, 0-180°"},
                    },
                    "required": [],
                },
            },
            {
                "name": "open_gripper",
                "description": "Open the gripper to release an object or prepare to grab.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "close_gripper",
                "description": "Close the gripper to grab/hold an object.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "go_home",
                "description": (
                    "Move all joints to the home/neutral position (arm upright, gripper open). "
                    "Use this to reset the arm or when done with a task."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "get_arm_state",
                "description": (
                    "Get the current state of the arm: joint angles and estimated "
                    "end-effector position."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        ]

    def execute(self, tool_name: str, tool_input: dict) -> str:
        """
        Execute a tool call and return the result as a string.
        This is called when Claude's response includes a tool_use block.
        """
        try:
            if tool_name == "get_scene_description":
                return self.perception.get_scene_description()

            elif tool_name == "move_to_xyz":
                result = self.arm.move_to_xyz(
                    x=tool_input["x"],
                    y=tool_input["y"],
                    z=tool_input["z"],
                )
                return str(result)

            elif tool_name == "move_joints":
                result = self.arm.set_joints(tool_input)
                return f"Joints set to: {result}"

            elif tool_name == "open_gripper":
                return self.arm.open_gripper()

            elif tool_name == "close_gripper":
                return self.arm.close_gripper()

            elif tool_name == "go_home":
                result = self.arm.go_home()
                return f"Moved to home position: {result}"

            elif tool_name == "get_arm_state":
                joints = self.arm.get_joint_angles()
                position = self.arm.get_end_effector_position()
                return f"Joints: {joints}\nEnd-effector position: {position}"

            else:
                return f"Unknown tool: {tool_name}"

        except Exception as e:
            return f"Tool execution error: {e}"
