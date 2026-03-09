#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORLD_PATH="${ROOT_DIR}/simulation/webots/worlds/dofbot.wbt"
ENDPOINT="${DOFBOT_WEBOTS_ENDPOINT:-tcp://127.0.0.1:5557}"
LAUNCH_WEBOTS=1

if [[ "${1:-}" == "--no-launch" ]]; then
  LAUNCH_WEBOTS=0
fi

echo "[demo] generating Webots assets from URDF..."
python3 "${ROOT_DIR}/simulation/webots/convert_urdf.py"

WEBOTS_PID=""
if [[ "${LAUNCH_WEBOTS}" -eq 1 ]]; then
  if ! command -v webots >/dev/null 2>&1; then
    echo "[demo] 'webots' command not found; assuming Webots is already open (manual mode)." >&2
    LAUNCH_WEBOTS=0
  else
    echo "[demo] launching Webots world: ${WORLD_PATH}"
    webots "${WORLD_PATH}" >/dev/null 2>&1 &
    WEBOTS_PID="$!"
    trap '[[ -n "${WEBOTS_PID}" ]] && kill "${WEBOTS_PID}" >/dev/null 2>&1 || true' EXIT
  fi
fi

echo "[demo] waiting for Webots controller at ${ENDPOINT}..."
export DOFBOT_WEBOTS_ENDPOINT="${ENDPOINT}"
python3 - <<'PY'
import os
import time
from driver.dofbot_driver import DofbotDriver

endpoint = os.getenv("DOFBOT_WEBOTS_ENDPOINT", "tcp://127.0.0.1:5557")
for _ in range(120):
    try:
        driver = DofbotDriver.webots(endpoint=endpoint, timeout_ms=200)
        if hasattr(driver.backend, "close"):
            driver.backend.close()
        print("[demo] Webots bridge is online")
        raise SystemExit(0)
    except Exception:
        time.sleep(0.25)
print("[demo] Webots bridge did not become ready in time")
print("[demo] Make sure Webots simulation is running (press Play), not paused.")
print("[demo] If Webots is open, verify the world has no load errors and set Webots Preferences -> Python command to a valid python3 executable.")
raise SystemExit(3)
PY

echo "[demo] running motion sequence..."
python3 - <<'PY'
import os
import time
from driver.dofbot_driver import DofbotDriver

driver = DofbotDriver.webots(
    endpoint=os.getenv("DOFBOT_WEBOTS_ENDPOINT", "tcp://127.0.0.1:5557"),
    timeout_ms=500,
)
poses = [
    [90, 90, 90, 90, 90, 90],
    [90, 70, 110, 90, 120, 60],
    [110, 90, 80, 120, 100, 60],
    [70, 100, 95, 70, 80, 100],
    [90, 90, 90, 90, 90, 90],
]
for pose in poses:
    driver.command_all(pose, duration_ms=800)
    time.sleep(0.9)
    print("[demo] readback:", driver.read_joint_angles())
if hasattr(driver.backend, "close"):
    driver.backend.close()
print("[demo] done")
PY
