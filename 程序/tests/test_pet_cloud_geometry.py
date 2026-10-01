# -*- coding: utf-8 -*-
import unittest

import pet_cloud_geometry


class PetCloudGeometryTests(unittest.TestCase):
    def test_rounded_parts_and_shift_keep_the_expected_geometry(self):
        parts = pet_cloud_geometry.rounded_parts(0, 0, 20, 10, 99)
        self.assertEqual(len(parts), 6)
        self.assertEqual(parts[2], ('oval', 5.0, 5.0, 5.0))
        self.assertEqual(pet_cloud_geometry.shift_part(('rect', 1, 2, 3, 4), 6), ('rect', 1, 8, 3, 10))

    def test_polygon_hit_testing_and_inflate_are_pure(self):
        triangle = [(0, 0), (4, 0), (0, 4)]
        self.assertTrue(pet_cloud_geometry._inside_polygon(triangle, 1, 1))
        self.assertFalse(pet_cloud_geometry._inside_polygon(triangle, 4, 4))
        self.assertEqual(pet_cloud_geometry.inflate(('oval', 2, 3, 4), 2), ('oval', 2, 3, 6))

    def test_square_and_tail_root_are_parameterized(self):
        self.assertEqual(len(pet_cloud_geometry.square_parts(100, 50, 0.1)), 6)
        self.assertEqual(pet_cloud_geometry.shape_root(100, 50, 0.86, 0.8), (86.0, 40.0))

    def test_inside_parts_handles_each_supported_primitive(self):
        parts = [('oval', 2, 2, 2), ('ellipse', 8, 2, 2, 1), ('rect', 0, 5, 4, 8),
                 ('poly', [(6, 5), (9, 5), (6, 8)])]
        self.assertTrue(pet_cloud_geometry.inside_parts(parts, 2, 2))
        self.assertTrue(pet_cloud_geometry.inside_parts(parts, 8, 2))
        self.assertTrue(pet_cloud_geometry.inside_parts(parts, 1, 7))
        self.assertTrue(pet_cloud_geometry.inside_parts(parts, 7, 6))
        self.assertFalse(pet_cloud_geometry.inside_parts(parts, 20, 20))


if __name__ == '__main__':
    unittest.main()
