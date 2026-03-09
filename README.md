# DOFBOT Python Stack

Python control stack for the Yahboom DOFBOT arm, with:

- a refactored hardware driver (`0x15` I2C protocol),
- deterministic local simulation backend,
- Webots bridge backend (no ROS required),
- IK-based `Arm` wrapper, demos, and smoke tests,
- optional LLM control app under `claude/`.

## Project Layout

- `driver/dofbot_driver/`: core driver package (`DofbotDriver`, config, protocol, transports, backends)
- `driver/arm.py`: IK wrapper around `DofbotDriver` with `set_position`, `set_state`, gripper helpers
- `driver/calibrate_dofbot.py`: calibration/diagnostics CLI
- `simulation/webots/`: URDF conversion, Webots world, controller bridge, and client
- `scripts/webots_demo.sh`: one-command Webots demo workflow
- `ik.py`: simple trajectory demo using the `Arm` wrapper
- `claude/`: optional Claude-powered agent loop and tool-calling integration
- `description/urdf/dofbot.urdf`: source URDF used by IK and conversion scripts

## Backends

`DofbotDriver` supports three backend modes:

1. **hardware** (default): real I2C board on address `0x15`
2. **sim**: in-memory deterministic simulation
3. **webots**: ZMQ bridge to `simulation/webots/controllers/dofbot_controller`

All three expose the same high-level API (`command_joint`, `command_all`, `read_joint_angles`, `set_torque`, etc.).

## Quick Start

### 1) Install dependencies

From repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

For the optional LLM app:

```bash
python3 -m pip install -r claude/requirements.txt
```

### 2) Use the driver API

```python
from driver.dofbot_driver import DofbotDriver, DofbotConfig

driver = DofbotDriver(DofbotConfig())  # hardware
driver.set_torque(True)
driver.command_all([90, 90, 90, 90, 90, 60], duration_ms=800)
print(driver.read_joint_angles())
```

Simulation backend:

```python
from driver.dofbot_driver import DofbotDriver

sim = DofbotDriver.simulation()
sim.command_all([90, 80, 70, 90, 120, 60], duration_ms=500)
print(sim.read_joint_angles())
```

### 3) Run IK demo

```bash
python3 ik.py --backend sim
```

Backend options:

- `--backend hardware`
- `--backend sim`
- `--backend webots --webots-endpoint tcp://127.0.0.1:5557`

## Webots Workflow (No ROS)

### Option A: one-command demo

```bash
./scripts/webots_demo.sh
```

If Webots is already open:

```bash
./scripts/webots_demo.sh --no-launch
```

### Option B: manual steps

```bash
python3 simulation/webots/convert_urdf.py
webots simulation/webots/worlds/dofbot.wbt
python3 simulation/webots/run_controller_client.py --angles 90,70,80,90,120,60
```

Notes:

- Default bridge endpoint is `tcp://127.0.0.1:5557` (override via `DOFBOT_WEBOTS_ENDPOINT`).
- Webots model has physical joints `1..5`; joint `6` is emulated in controller state so the 6-servo API remains stable.
- In Webots, press **Play** to start controllers.

## Calibration and Diagnostics

Single-joint test:

```bash
python3 -m driver.calibrate_dofbot --joint 1
```

Custom ranges (including joint 5 extended range):

```bash
python3 -m driver.calibrate_dofbot --min-angle 15 --max-angle 165 --joint5-max-angle 240
```

You can also run diagnostics against `sim` or `webots`:

```bash
python3 -m driver.calibrate_dofbot --backend sim
python3 -m driver.calibrate_dofbot --backend webots
```

## Tests

Unit tests:

```bash
python3 -m unittest driver.tests.test_protocol driver.tests.test_backends driver.tests.test_arm_sim
```

Hardware smoke test (guarded):

```bash
DOFBOT_HW_TEST=1 python3 -m driver.tests.hw_smoke
```

Webots smoke test (guarded):

```bash
DOFBOT_WEBOTS_TEST=1 python3 -m driver.tests.webots_smoke
```

## Optional: Claude Agent App

The `claude/` directory contains an agentic loop (`claude/main.py`) that lets Claude call movement/scene tools.

Typical run:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python3 claude/main.py --simulate
```

This path is optional and separate from the core driver + simulation stack.
