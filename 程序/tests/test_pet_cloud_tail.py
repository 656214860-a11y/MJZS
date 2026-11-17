# -*- coding: utf-8 -*-
import unittest

from ui import pet_cloud_tail


class PetCloudTailTests(unittest.TestCase):
    def test_tail_points_preserve_endpoints_and_tip(self):
        points = pet_cloud_tail.tail_points((0, 0), (10, 0), (5, 8), steps=3)
        self.assertEqual(len(points), 7)
        self.assertEqual(points[0], (0, 0))
        self.assertEqual(points[3], (5.0, 8.0))
        self.assertEqual(points[-1], (10.0, 0.0))

    def test_curve_is_deterministic_for_a_short_edge(self):
        self.assertEqual(pet_cloud_tail._side_curve((0, 0), (1, 0), (0, 1), steps=1), [(1.0, 0.0)])


if __name__ == '__main__':
    unittest.main()
