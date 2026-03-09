# Webots simulation workflow

This directory contains a non-ROS simulation path for DOFBOT.

## 1) Build Webots assets from URDF

From repository root:

```bash
python3 simulation/webots/convert_urdf.py
```

This generates:

- `simulation/webots/dofbot.sim.urdf` (mesh URIs rewritten for local files)
- `simulation/webots/protos/Dofbot.proto` (via `urdf2webots`, if installed)

By default conversion uses:

- box collision approximation (`--box-collision`) to reduce unstable mesh contacts
- fixed-base patching so the arm stays anchored in place

If you only want URI rewriting:

```bash
python3 simulation/webots/convert_urdf.py --skip-convert
```

## 2) Launch Webots world

Open:

- `simulation/webots/worlds/dofbot.wbt`

The robot uses controller `dofbot_controller` and binds a ZMQ REP socket on
`tcp://127.0.0.1:5557` by default.

Important on macOS:

- In Webots, set `Preferences -> Python command` to your Python executable
  (for example `/usr/bin/python3` or your venv python path).
- If the controller cannot start, the external bridge will never come online.
- Press **Play** in Webots; controllers run only while simulation is active.

## 3) Drive the simulated robot from Python

```bash
python3 simulation/webots/run_controller_client.py --angles 90,70,80,90,120,60
```

Or use project scripts with `--backend webots`.

Note: the physical Webots model currently has joints 1..5. Joint 6 from the
driver API is emulated in controller state so your 6-servo API stays unchanged.
