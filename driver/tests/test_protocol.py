import unittest

from driver.dofbot_driver.config import JointCalibration
from driver.dofbot_driver.protocol import angle_to_position, position_to_angle


class TestProtocolConversions(unittest.TestCase):
    def test_standard_joint_midpoint(self):
        calibration = JointCalibration(0, 180, 900, 3100, invert=False)
        pos = angle_to_position(90, calibration)
        self.assertEqual(pos, 2000)
        self.assertAlmostEqual(position_to_angle(pos, calibration), 90.0, places=3)

    def test_inverted_joint_mapping(self):
        calibration = JointCalibration(0, 180, 900, 3100, invert=True)
        pos_0 = angle_to_position(0, calibration)
        pos_180 = angle_to_position(180, calibration)
        self.assertEqual(pos_0, 3100)
        self.assertEqual(pos_180, 900)
        self.assertAlmostEqual(position_to_angle(pos_0, calibration), 0.0, places=3)
        self.assertAlmostEqual(position_to_angle(pos_180, calibration), 180.0, places=3)

    def test_joint5_extended_range(self):
        calibration = JointCalibration(0, 270, 380, 3700, invert=False)
        pos = angle_to_position(135, calibration)
        self.assertAlmostEqual(position_to_angle(pos, calibration), 135.0, places=3)

    def test_out_of_range_decode(self):
        calibration = JointCalibration(0, 180, 900, 3100, invert=False)
        self.assertIsNone(position_to_angle(100, calibration))
        self.assertIsNone(position_to_angle(4000, calibration))


if __name__ == "__main__":
    unittest.main()
