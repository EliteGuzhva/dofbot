# Dofbot LLM Control — Architecture Sketch

## Overview

Cloud LLM (Claude/GPT) controls a Yahboom Dofbot arm via tool-calling.
No ROS, no MoveIt — just Python, I2C servos, and an API.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    YOUR PC / PHONE                   │
│              (optional: web UI / terminal)            │
└──────────────────────┬──────────────────────────────┘
                       │ user prompt
                       ▼
┌─────────────────────────────────────────────────────┐
│                  CLOUD LLM (Claude API)              │
│                                                      │
│  System prompt: "You are a robotic arm controller."  │
│  Tools registered:                                   │
│    - get_scene_description()                         │
│    - move_to_xyz(x, y, z)                           │
│    - move_joints(j1..j6)                            │
│    - open_gripper() / close_gripper()               │
│    - go_home()                                       │
│                                                      │
│  LLM reasons → calls tools → gets results → repeats │
└──────────────────────┬──────────────────────────────┘
                       │ tool calls (JSON)
                       ▼
┌─────────────────────────────────────────────────────┐
│               JETSON NANO (Ubuntu 18.04)             │
│                                                      │
│  ┌──────────────┐  ┌────────────────────────────┐   │
│  │  main.py     │  │  arm_controller.py          │   │
│  │  (API loop)  │──│  - FK/IK (roboticstoolbox)  │   │
│  │              │  │  - PCA9685 servo driver      │   │
│  └──────┬───────┘  └────────────────────────────┘   │
│         │                                            │
│  ┌──────┴───────┐  ┌────────────────────────────┐   │
│  │  perception  │  │  tools.py                   │   │
│  │  - camera    │  │  - tool definitions for LLM │   │
│  │  - YOLO-nano │  │  - tool execution dispatch  │   │
│  │  - (opt) depth│  └────────────────────────────┘   │
│  └──────────────┘                                    │
│                                                      │
│  Hardware: PCA9685 ──I2C──▶ 6x servos + gripper     │
│            USB camera                                │
└─────────────────────────────────────────────────────┘
```

## Files

| File | Runs on | Purpose |
|------|---------|---------|
| `arm_controller.py` | Jetson Nano | Low-level servo control + IK |
| `perception.py` | Jetson Nano | Camera + object detection |
| `tools.py` | Jetson Nano | Tool definitions for the LLM |
| `main.py` | Jetson Nano | Main loop: talks to Claude API |
| `requirements.txt` | Jetson Nano | Python dependencies |

## How It Works

1. `main.py` captures a camera frame, runs object detection
2. Sends scene description + user command to Claude API
3. Claude reasons and calls tools (e.g., `move_to_xyz`)
4. `main.py` executes the tool call on real hardware
5. Returns result to Claude, which may call more tools
6. Loop until Claude says "done"

## Quick Start

```bash
# On Jetson Nano
pip3 install anthropic opencv-python adafruit-pca9685 roboticstoolbox-python
export ANTHROPIC_API_KEY="sk-ant-..."
python3 main.py
```
