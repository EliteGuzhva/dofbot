import math
import unittest

import numpy as np

from driver.arm import Arm


class TestArmSimulation(unittest.TestCase):
    def test_set_and_get_state_in_sim_backend(self):
        arm = Arm(backend="sim")
        target = np.array(
            [
                math.radians(10),
                math.radians(-10),
                math.radians(20),
                math.radians(-20),
                math.radians(15),
                math.radians(-30),
            ],
            dtype=float,
        )
        arm.set_state(target, duration_ms=1)
        observed = arm.get_state(timeout_s=0.1)
        np.testing.assert_allclose(observed, target, atol=1e-3)

    def test_invalid_backend(self):
        with self.assertRaises(ValueError):
            Arm(backend="unknown")
