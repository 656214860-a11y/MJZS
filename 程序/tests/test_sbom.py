"""A15：发布副本使用 CycloneDX 1.5 表达依赖、工具和外部 Skill 来源。"""
import json
import tempfile
import unittest
from pathlib import Path

from scripts import sbom


class SbomTests(unittest.TestCase):
    @staticmethod
    def _optional_asr(program):
        voice = program / 'voice_engine'
        voice.mkdir()
        (voice / 'requirements.lock').write_text('numpy==1.26.4\n', encoding='utf-8')
        (voice / 'supply_chain.lock.json').write_text(json.dumps({
            'source_template': 'https://pypi.org/project/{name}/{version}/',
            'licenses': {'numpy': 'BSD-3-Clause'},
        }), encoding='utf-8')

    def test_build_collects_locked_packages_tools_and_skills(self):
        with tempfile.TemporaryDirectory() as td:
            program = Path(td)
            self._optional_asr(program)
            (program / 'requirements.txt').write_text('requests==2.34.2\n', encoding='utf-8')
            (program / 'external_tools.lock.json').write_text(json.dumps({
                'tools': {'运行环境/Python/python.exe': {
                    'version': 'Python 3.14.7', 'sha256': 'a' * 64, 'bytes': 1,
                    'source': 'https://python.org/', 'license': 'PSF-2.0'}},
            }), encoding='utf-8')
            records = program / '维护记录'
            records.mkdir()
            (records / '外部技能包哈希.json').write_text(json.dumps({'packages': {
                'skills/example': {'source': 'https://github.com/x/y.git',
                                   'commit': 'b' * 40, 'tree': 'c' * 40},
            }}), encoding='utf-8')
            document, notices = sbom.build(program, app_version='1.2.3')
        self.assertEqual((document['bomFormat'], document['specVersion']), ('CycloneDX', '1.5'))
        components = {item['bom-ref']: item for item in document['components']}
        self.assertEqual(components['pkg:pypi/requests@2.34.2']['licenses'][0]['license']['id'], 'Apache-2.0')
        self.assertEqual(components['tool:运行环境/Python/python.exe']['hashes'][0]['alg'], 'SHA-256')
        self.assertEqual(components['skill:skills/example']['hashes'][0]['alg'], 'SHA-1')
        self.assertEqual(components['optional-asr:pkg:pypi/numpy@1.26.4']['scope'], 'optional')
        self.assertIn('requests 2.34.2', notices)
        self.assertIn('skills/example', notices)

    def test_unknown_production_package_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            program = Path(td)
            (program / 'requirements.txt').write_text('unknown==1.0\n', encoding='utf-8')
            (program / 'external_tools.lock.json').write_text('{"tools": {}}', encoding='utf-8')
            records = program / '维护记录'; records.mkdir()
            (records / '外部技能包哈希.json').write_text('{"packages": {}}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '许可证/来源'):
                sbom.build(program)

    def test_asr_supply_chain_must_exactly_match_the_full_lock(self):
        with tempfile.TemporaryDirectory() as td:
            program = Path(td)
            self._optional_asr(program)
            supply = program / 'voice_engine/supply_chain.lock.json'
            supply.write_text(json.dumps({'source_template': 'https://pypi.org/{name}/{version}',
                                          'licenses': {}}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '完整锁不一致'):
                sbom._optional_asr_packages(program)


if __name__ == '__main__':
    unittest.main()
