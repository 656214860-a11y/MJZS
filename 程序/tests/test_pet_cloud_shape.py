# -*- coding: utf-8 -*-
import unittest

import pet_cloud_shape


class PetCloudShapeTests(unittest.TestCase):
    def test_unknown_shape_uses_the_default_configuration(self):
        values = {'cloud': 344, 'tag': 316}
        self.assertEqual(pet_cloud_shape.normalized('missing', tuple(values), 'cloud'), 'cloud')
        self.assertEqual(pet_cloud_shape.configured_value('missing', tuple(values), 'cloud', values), 344)

    def test_text_box_honors_padding_and_minimum_size(self):
        self.assertEqual(pet_cloud_shape.text_box(400, 200, 16), (16, 16, 368, 168))
        self.assertEqual(pet_cloud_shape.text_box(10, 10, 16), (16, 16, 40, 20))


if __name__ == '__main__':
    unittest.main()
