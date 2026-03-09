"""
main.py — Main agent loop for LLM-controlled Dofbot.

This is the brain of the system. It:
  1. Takes a user command (text)
  2. Sends it to Claude API with tool definitions
  3. Executes any tool calls Claude makes
  4. Feeds results back to Claude
  5. Repeats until Claude gives a final text response

Usage:
  export ANTHROPIC_API_KEY="sk-ant-..."
  python3 main.py

  # Or with --simulate for testing without hardware:
  python3 main.py --simulate
"""

import os
import sys
import json
import argparse

from anthropic import Anthropic

from arm_controller import DofbotArm
from perception import Perception
from tools import ToolRegistry


# ─── System Prompt ──────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an intelligent controller for a 6-DOF Yahboom Dofbot robotic arm.

## Your Capabilities
You have tools to:
- Look at the workspace (get_scene_description) to see what objects are present
- Move the arm to XYZ coordinates (move_to_xyz) or set joint angles (move_joints)
- Open/close the gripper (open_gripper, close_gripper)
- Return to home position (go_home)
- Check arm state (get_arm_state)

## Coordinate Frame
- x = forward (away from base), y = left, z = up
- Origin at arm base center, table level
- Typical reach: x ∈ [0.05, 0.25], y ∈ [-0.15, 0.15], z ∈ [0.0, 0.25]
- Table surface: z ≈ 0.01m
- Safe hover height: z ≈ 0.06m

## Pick-and-Place Procedure
To pick up an object:
1. First call get_scene_description to see what's on the table
2. Open the gripper
3. Move to hover above the target: move_to_xyz(obj_x, obj_y, 0.06)
4. Lower to grasp height: move_to_xyz(obj_x, obj_y, 0.015)
5. Close the gripper
6. Lift up: move_to_xyz(obj_x, obj_y, 0.08)
7. Move to destination hover: move_to_xyz(dest_x, dest_y, 0.08)
8. Lower: move_to_xyz(dest_x, dest_y, 0.015)
9. Open gripper to release
10. Lift away and go_home

## Safety Rules
- ALWAYS start by looking at the scene (get_scene_description)
- NEVER move below z=0.005 (table collision)
- If move_to_xyz returns an error, the position is unreachable — try a different approach
- When uncertain, go_home first
- Move slowly and deliberately — one action at a time

## Communication
- Be concise in your text responses
- Explain what you're doing and why
- If a task seems impossible, explain why and suggest alternatives
"""


# ─── Agent Loop ─────────────────────────────────────────────────────────

class DofbotAgent:
    """
    Agentic loop: user → Claude API (with tools) → execute → repeat.
    """

    def __init__(self, simulate=False, use_vision=False):
        self.client = Anthropic()  # reads ANTHROPIC_API_KEY from env
        self.arm = DofbotArm(simulate=simulate)
        self.perception = Perception(camera_source=0)
        self.tools = ToolRegistry(self.arm, self.perception)
        self.use_vision = use_vision

        # Conversation history for multi-turn
        self.messages = []

        # Model to use — claude-sonnet-4-20250514 is fast + good at tool use
        # Switch to claude-opus-4-20250514 for harder reasoning tasks
        self.model = "claude-sonnet-4-20250514"
        self.max_tokens = 1024

    def run_command(self, user_input: str) -> str:
        """
        Process a user command through the full agent loop.
        Returns Claude's final text response.
        """
        # Build user message
        user_message = {"role": "user", "content": user_input}

        # Optionally attach a camera image for vision-language reasoning
        if self.use_vision:
            image_b64 = self.perception.get_frame_base64()
            if image_b64:
                user_message = {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": user_input},
                    ],
                }

        self.messages.append(user_message)

        # Agent loop: keep calling Claude until we get a final text response
        while True:
            print(f"\n--- Calling Claude ({self.model}) ---")

            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                tools=self.tools.get_tool_schemas(),
                messages=self.messages,
            )

            # Process response content blocks
            assistant_content = response.content
            self.messages.append({"role": "assistant", "content": assistant_content})

            # Check if Claude wants to use tools
            tool_use_blocks = [b for b in assistant_content if b.type == "tool_use"]
            text_blocks = [b for b in assistant_content if b.type == "text"]

            # Print any text Claude said
            for tb in text_blocks:
                if tb.text.strip():
                    print(f"Claude: {tb.text}")

            # If no tool calls, we're done
            if not tool_use_blocks:
                final_text = " ".join(tb.text for tb in text_blocks).strip()
                return final_text if final_text else "(no response)"

            # Execute each tool call and collect results
            tool_results = []
            for tool_block in tool_use_blocks:
                print(f"  → Tool: {tool_block.name}({json.dumps(tool_block.input)})")
                result = self.tools.execute(tool_block.name, tool_block.input)
                print(f"  ← Result: {result[:200]}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": result,
                })

            # Feed results back to Claude
            self.messages.append({"role": "user", "content": tool_results})

            # Safety: limit iterations to prevent runaway loops
            if len(self.messages) > 30:
                print("[WARN] Too many messages — breaking loop")
                return "I've taken too many steps. Please simplify the task."

        # If stop_reason is "end_turn", Claude is done

    def reset_conversation(self):
        """Clear conversation history for a fresh start."""
        self.messages = []

    def shutdown(self):
        """Clean up resources."""
        self.arm.go_home()
        self.perception.release()


# ─── CLI Interface ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LLM-controlled Dofbot arm")
    parser.add_argument("--simulate", action="store_true",
                        help="Run without real hardware")
    parser.add_argument("--vision", action="store_true",
                        help="Send camera images to Claude (uses vision API)")
    parser.add_argument("--model", default="claude-sonnet-4-20250514",
                        help="Claude model to use")
    args = parser.parse_args()

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: Set ANTHROPIC_API_KEY environment variable")
        print("  export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)

    agent = DofbotAgent(simulate=args.simulate, use_vision=args.vision)
    agent.model = args.model

    print("=" * 60)
    print("  Dofbot LLM Controller")
    print(f"  Model: {agent.model}")
    print(f"  Mode:  {'simulation' if args.simulate else 'LIVE HARDWARE'}")
    print(f"  Vision: {'enabled' if args.vision else 'text-only'}")
    print("=" * 60)
    print()
    print("Commands:")
    print("  Type any instruction for the arm (e.g., 'pick up the red block')")
    print("  'reset' — clear conversation history")
    print("  'home'  — move arm to home position")
    print("  'state' — show arm state")
    print("  'quit'  — exit")
    print()

    try:
        while True:
            user_input = input("You: ").strip()

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                break
            if user_input.lower() == "reset":
                agent.reset_conversation()
                print("Conversation reset.")
                continue
            if user_input.lower() == "home":
                agent.arm.go_home()
                print("Arm moved to home position.")
                continue
            if user_input.lower() == "state":
                print(f"Joints: {agent.arm.get_joint_angles()}")
                print(f"Position: {agent.arm.get_end_effector_position()}")
                continue

            response = agent.run_command(user_input)
            print(f"\nClaude: {response}\n")

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        agent.shutdown()
        print("Done.")


if __name__ == "__main__":
    main()
