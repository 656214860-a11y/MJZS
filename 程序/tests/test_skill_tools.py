# -*- coding: utf-8 -*-
"""SKILL 工具入口的定向回归。"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import line_endings
import skill_tools
import asset_reference_search as reference_search


class RetiredToolTests(unittest.TestCase):
    def test_builtin_control_tools_are_not_exposed(self):
        retired = {'feed.validate', 'feed.gateCheck', 'feed.auditContract',
                   'style.lockRecommend', 'style.lockLadder'}
        self.assertFalse(retired.intersection(skill_tools.ready_names()))
        self.assertFalse(retired.intersection(skill_tools.READY))
        self.assertFalse(retired.intersection(skill_tools.PAGES))


class CopyrightFilterTests(unittest.TestCase):
    def test_restricted_or_ambiguous_license_never_passes_commercial_filter(self):
        for license_name in ('CC BY-NC', 'CC-BY-NC-SA 4.0', 'CC BY-ND',
                             'not CC BY', 'CC BY custom restrictions'):
            with self.subTest(license=license_name):
                item = {'url': 'https://example.org/a.png', 'page': 'https://example.org/a',
                        'author': 'Author', 'license': license_name}
                result = skill_tools.call('asset.copyrightFilter', {'candidates': [item]})
                self.assertEqual(result['filtered'], [])
                self.assertEqual(len(result['blocked']), 1)

    def test_attribution_and_share_alike_obligations_are_preserved(self):
        item = {'url': 'https://example.org/a.png', 'page': 'https://example.org/a',
                'author': 'Author', 'license': 'CC-BY-SA 4.0'}
        result = skill_tools.call('asset.copyrightFilter', {'candidates': [item]})
        self.assertEqual(len(result['filtered']), 1)
        self.assertIn('相同方式共享', result['filtered'][0]['obligations'])
        item['author'] = ''
        self.assertFalse(skill_tools.call('asset.copyrightFilter',
                                         {'candidates': [item]})['filtered'])
        self.assertEqual(reference_search.explain(item, {}, threshold=0)['state'],
                         'missing_attribution')

    def test_public_domain_and_explicit_switches(self):
        item = {'url': 'https://example.org/a.png', 'page': 'https://example.org/a',
                'license': 'CC0 1.0'}
        self.assertEqual(len(skill_tools.call('asset.copyrightFilter',
                                             {'candidates': [item]})['filtered']), 1)
        self.assertFalse(skill_tools.call('asset.copyrightFilter',
                                         {'candidates': [item], 'allowCC0': False})['filtered'])
        item.update(license='CC BY 4.0', author='Author')
        self.assertFalse(skill_tools.call('asset.copyrightFilter',
                                         {'candidates': [item], 'allowCCBY': False})['filtered'])

    def test_direct_adoption_rejects_restricted_license_before_download(self):
        for license_name in ('CC BY-NC', 'CC BY-ND', 'unknown'):
            with self.subTest(license=license_name), tempfile.TemporaryDirectory() as folder:
                calls = []
                manifest = Path(folder) / 'assets/资产清单/assets.json'
                manifest.parent.mkdir(parents=True)
                manifest.write_text('{"CHAR_001": {}}', encoding='utf-8')
                item = {'url': 'https://example.org/a.png', 'page': 'https://example.org/a',
                        'author': 'Author', 'license': license_name}
                reference_search.adopt(folder, 'CHAR_001', [item],
                                       fetch=lambda url: calls.append(url) or b'')
                self.assertEqual(calls, [])


class DeliveryManifestTests(unittest.TestCase):
    def test_delivery_manifest_is_valid_json_with_clean_line_endings(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / '交付清单.json'
            result = skill_tools.call('delivery.exportManifest', {
                'project': folder,
                'manifest': target,
                'results': [{'stage': 'delivery', 'ok': True}],
            })
            self.assertEqual(result['manifest'], str(target))
            self.assertEqual(json.loads(target.read_text(encoding='utf-8'))['stage_results'],
                             [{'stage': 'delivery', 'ok': True}])
            self.assertEqual(line_endings.problems(target), [])


if __name__ == '__main__':
    unittest.main()
