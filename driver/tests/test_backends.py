import threading
import time
import unittest

from driver.dofbot_driver.backends import SimBackend, WebotsBackend
from driver.dofbot_driver.errors import DofbotConnectionError, DofbotValidationError

try:
    import zmq
except Exception:  # pragma: no cover - runtime optional
    zmq = None


class TestSimBackend(unittest.TestCase):
    def test_command_all_and_readback(self):
        backend = SimBackend()
        backend.command_all([90, 80, 70, 60, 50, 40], duration_ms=500)
        self.assertEqual(backend.read_joint_angle(1), 90.0)
        self.assertEqual(backend.read_joint_angle(6), 40.0)

    def test_command_all_requires_six_values(self):
        backend = SimBackend()
        with self.assertRaises(DofbotValidationError):
            backend.command_all([90, 80], duration_ms=500)


@unittest.skipIf(zmq is None, "pyzmq is required for Webots backend tests")
class TestWebotsBackend(unittest.TestCase):
    ENDPOINT = "tcp://127.0.0.1:5667"

    def setUp(self):
        self._stop = threading.Event()
        self._angles = {idx: 90.0 for idx in range(1, 7)}
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        time.sleep(0.05)

    def tearDown(self):
        self._stop.set()
        control = zmq.Context.instance().socket(zmq.REQ)
        control.linger = 0
        control.rcvtimeo = 100
        control.sndtimeo = 100
        control.connect(self.ENDPOINT)
        try:
            control.send_json({"op": "stop"})
            control.recv_json()
        except Exception:
            pass
        control.close()
        self._thread.join(timeout=1.0)

    def _serve(self):
        self._context = zmq.Context()
        socket = self._context.socket(zmq.REP)
        socket.linger = 0
        socket.bind(self.ENDPOINT)
        poller = zmq.Poller()
        poller.register(socket, zmq.POLLIN)
        while not self._stop.is_set():
            events = dict(poller.poll(timeout=20))
            if socket not in events:
                continue
            payload = socket.recv_json()
            op = payload.get("op")
            if op == "ping":
                socket.send_json({"ok": True})
            elif op == "command_all":
                for idx, value in enumerate(payload["angles"], start=1):
                    self._angles[idx] = float(value)
                socket.send_json({"ok": True})
            elif op == "command_joint":
                self._angles[int(payload["joint_id"])] = float(payload["angle"])
                socket.send_json({"ok": True})
            elif op == "read_joint_angle":
                joint_id = int(payload["joint_id"])
                socket.send_json({"ok": True, "angle": self._angles[joint_id]})
            elif op == "read_joint_angles":
                socket.send_json({"ok": True, "angles": self._angles})
            elif op == "set_torque":
                socket.send_json({"ok": True})
            elif op == "stop":
                socket.send_json({"ok": True})
                self._stop.set()
            else:
                socket.send_json({"ok": False, "error": f"unknown {op}"})
        socket.close()
        self._context.term()

    def test_command_and_readback(self):
        backend = WebotsBackend(endpoint=self.ENDPOINT, timeout_ms=200)
        backend.command_all([91, 92, 93, 94, 95, 96], duration_ms=300)
        self.assertAlmostEqual(backend.read_joint_angle(3), 93.0)
        backend.command_joint(3, 77.0, duration_ms=200)
        self.assertAlmostEqual(backend.read_joint_angle(3), 77.0)
        self.assertEqual(len(backend.read_all_angles()), 6)
        backend.close()

    def test_validation(self):
        backend = WebotsBackend(endpoint=self.ENDPOINT, timeout_ms=200)
        with self.assertRaises(DofbotValidationError):
            backend.command_all([1, 2], duration_ms=1)
        with self.assertRaises(DofbotValidationError):
            backend.read_joint_angle(7)
        backend.close()

    def test_connection_error(self):
        with self.assertRaises(DofbotConnectionError):
            WebotsBackend(endpoint="tcp://127.0.0.1:5999", timeout_ms=50)
