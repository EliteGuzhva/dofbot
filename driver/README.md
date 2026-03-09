# DOFBOT Driver Package

Refactored, non-backward-compatible driver stack for DOFBOT expansion boards
using the `0x15` I2C protocol.

## Architecture

- `dofbot_driver/config.py`: calibration + bus settings (with JSON loader)
- `dofbot_driver/protocol.py`: register map and encode/decode helpers
- `dofbot_driver/transport.py`: transport abstraction + I2C transport
- `dofbot_driver/backends.py`: `BaseBackend`, `I2CBackend`, `SimBackend`, `WebotsBackend`
- `dofbot_driver/driver.py`: public driver API
- `dofbot_driver/errors.py`: typed exceptions

## Public API

```python
from driver.dofbot_driver import DofbotDriver, DofbotConfig

driver = DofbotDriver(DofbotConfig())
driver.set_torque(True)
driver.command_all([90, 90, 90, 90, 90, 60], duration_ms=800)
print(driver.read_joint_angles())
```

Methods:

- `command_joint(joint_id, angle, duration_ms=None)`
- `command_joints({joint_id: angle, ...}, duration_ms=None)`
- `command_all([j1..j6], duration_ms=None)`
- `read_joint_angle(joint_id)`
- `read_joint_angles()`
- `set_torque(enabled)`
- `get_hardware_version()`
- `reset_board()`
- `set_rgb(r, g, b)`

## Simulation

```python
from driver.dofbot_driver import DofbotDriver

sim = DofbotDriver.simulation()
sim.command_all([90, 80, 70, 90, 120, 60], duration_ms=500)
print(sim.read_joint_angles())
```

Webots bridge simulation:

```python
from driver.dofbot_driver import DofbotDriver

webots = DofbotDriver.webots(endpoint="tcp://127.0.0.1:5557")
webots.command_all([90, 80, 70, 90, 120, 60], duration_ms=500)
print(webots.read_joint_angles())
```

## Webots Workflow (No ROS)

Install conversion utility:

```bash
pip3 install urdf2webots
```

Generate simulation URDF and PROTO:

```bash
python3 simulation/webots/convert_urdf.py
```

Open world:

```bash
webots simulation/webots/worlds/dofbot.wbt
```

Drive the simulated robot:

```bash
python3 simulation/webots/run_controller_client.py --angles 90,70,80,90,120,60
```

One-command demo (converts URDF, launches Webots, runs sample motion):

```bash
./scripts/webots_demo.sh
```

If Webots is already open manually (common on macOS):

```bash
./scripts/webots_demo.sh --no-launch
```

If `webots` is not available in your shell PATH, the demo script automatically
falls back to manual mode and waits for the running Webots controller bridge.

Notes:

- Source URDF uses `package://dofbot_description/meshes/...` mesh URIs.
- `simulation/webots/convert_urdf.py` rewrites these to local mesh paths so non-ROS tools can resolve them.
- Webots controller endpoint defaults to `tcp://127.0.0.1:5557` and can be changed with `DOFBOT_WEBOTS_ENDPOINT`.

## Calibration and Diagnostics

```bash
python3 -m driver.calibrate_dofbot --joint 1
python3 -m driver.calibrate_dofbot --min-angle 15 --max-angle 165 --joint5-max-angle 240
```

## Testing

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
