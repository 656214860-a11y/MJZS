"""J21：各 *_gateway() 共用同一个 JSON 发布器底座，对外键集合不变。"""
import unittest

import stage_execution_service as service
from agent.core import save

JSON_ONLY = ('pet_performance_gateway', 'pet_test_gateway', 'desktop_settings_gateway',
             'asset_batch_settings_gateway', 'cloud_video_gateway', 'video_lifecycle_gateway',
             'confirm_gates_gateway', 'previs_routing_gateway', 'storyboard_edit_gateway')


class GatewayBaseTests(unittest.TestCase):
    def test_json_only_gateways_expose_exactly_the_shared_publisher(self):
        for name in JSON_ONLY:
            with self.subTest(name=name):
                self.assertEqual(getattr(service, name)(), {'publish_json': save})

    def test_legacy_adoption_adds_only_make_dir(self):
        gateway = service.legacy_adoption_gateway()
        self.assertEqual(set(gateway), {'publish_json', 'make_dir'})
        self.assertIs(gateway['publish_json'], save)


if __name__ == '__main__':
    unittest.main()
