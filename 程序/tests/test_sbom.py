"""A15：发布副本使用 CycloneDX 1.5 表达依赖、工具和外部 Skill 来源。"""
import json
import tempfile
import unittest
from pathlib import Path

from scripts import distribution_build, sbom


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


FFMPEG_TOOL = {
    'version': 'ffmpeg version 9.0.1-essentials_build-www.gyan.dev Copyright (c) 2000-2026 the FFmpeg developers',
    'sha256': 'f' * 64, 'bytes': 1,
    'source': 'https://www.gyan.dev/ffmpeg/builds/', 'license': 'GPL-3.0-or-later',
}
NOTICE_MANIFEST = {'keep': ['运行环境/ffmpeg/'], 'exclude': ['程序/**']}


def _notice_source(root):
    """最小分发源：ffmpeg 锁 + 随包 LICENSE；其余 程序/ 文件全部显式排除。"""
    root = Path(root)
    program = root / '程序'
    program.mkdir(parents=True)
    (program / 'requirements.txt').write_text('requests==2.34.2\n', encoding='utf-8')
    (program / 'external_tools.lock.json').write_text(json.dumps({'tools': {
        '运行环境/ffmpeg/bin/ffmpeg.exe': dict(FFMPEG_TOOL),
        '运行环境/ffmpeg/bin/ffprobe.exe': dict(
            FFMPEG_TOOL, version='ffprobe version 9.0.1-essentials_build-www.gyan.dev'),
    }}), encoding='utf-8')
    voice = program / 'voice_engine'
    voice.mkdir()
    (voice / 'requirements.lock').write_text('numpy==1.26.4\n', encoding='utf-8')
    (voice / 'supply_chain.lock.json').write_text(json.dumps({
        'source_template': 'https://pypi.org/project/{name}/{version}/',
        'licenses': {'numpy': 'BSD-3-Clause'},
    }), encoding='utf-8')
    records = program / '维护记录'
    records.mkdir()
    (records / '外部技能包哈希.json').write_text(json.dumps({'packages': {}}), encoding='utf-8')
    ffmpeg = root / '运行环境' / 'ffmpeg'
    (ffmpeg / 'bin').mkdir(parents=True)
    (ffmpeg / 'bin' / 'ffmpeg.exe').write_text('ffmpeg', encoding='utf-8')
    (ffmpeg / 'bin' / 'ffprobe.exe').write_text('ffprobe', encoding='utf-8')
    (ffmpeg / 'LICENSE').write_text('GPL-3.0', encoding='utf-8')
    return root


class BundledNoticeTests(unittest.TestCase):
    """REL-10：随包 THIRD_PARTY_NOTICES.txt 与 ffmpeg/NOTICE.txt 的 GPL 披露。"""

    def _build(self, td, manifest=NOTICE_MANIFEST, **kwargs):
        source = _notice_source(Path(td) / 'src')
        dest = Path(td) / 'out'
        distribution_build.build(dest, source, manifest, **kwargs)
        return source, dest

    def test_bundled_ffmpeg_notice_carries_gpl_disclosure(self):
        with tempfile.TemporaryDirectory() as td:
            _, dest = self._build(td)
            notice = dest / '运行环境' / 'ffmpeg' / 'NOTICE.txt'
            self.assertTrue(notice.is_file(), '随包 ffmpeg/ 下缺 NOTICE.txt')
            text = notice.read_text(encoding='utf-8')
            notices = (dest / 'THIRD_PARTY_NOTICES.txt').read_text(encoding='utf-8')
        self.assertIn('GPL', text)
        self.assertIn('essentials', text)        # 构建类型：gyan.dev essentials build
        self.assertIn('ffmpeg.org', text)        # 完整对应源码获取方式
        self.assertIn('essentials', notices)
        self.assertIn('ffmpeg.org', notices)

    def test_missing_bundled_notice_fails_distribution_verify(self):
        with tempfile.TemporaryDirectory() as td:
            source, dest = self._build(td)
            (dest / '运行环境' / 'ffmpeg' / 'NOTICE.txt').unlink()
            verdict = distribution_build.verify(dest, source, NOTICE_MANIFEST)
        self.assertFalse(verdict['ok'], verdict)
        self.assertIn('运行环境/ffmpeg/NOTICE.txt',
                      verdict['checks']['supply_chain']['missing_notices'])

    def test_missing_third_party_notices_fails_distribution_verify(self):
        with tempfile.TemporaryDirectory() as td:
            source, dest = self._build(td)
            (dest / 'THIRD_PARTY_NOTICES.txt').unlink()
            verdict = distribution_build.verify(dest, source, NOTICE_MANIFEST)
        self.assertFalse(verdict['ok'], verdict)

    def test_noassertion_component_enters_release_blockers(self):
        with tempfile.TemporaryDirectory() as td:
            root = _notice_source(Path(td) / 'src')
            (root / '程序' / '维护记录' / '外部技能包哈希.json').write_text(json.dumps({'packages': {
                'skills/01 剧本准备SKILL/剧本锻造': {
                    'source': 'https://github.com/zhlmi/script-forging.git',
                    'commit': 'b' * 40, 'tree': 'c' * 40},
            }}), encoding='utf-8')
            skill = root / '程序' / 'skills' / '01 剧本准备SKILL' / '剧本锻造' / 'SKILL.md'
            skill.parent.mkdir(parents=True, exist_ok=True)
            skill.write_text('fixture', encoding='utf-8')
            manifest = {'keep': ['运行环境/ffmpeg/', '程序/skills/'], 'exclude': []}
            dest = Path(td) / 'out'
            distribution_build.build(dest, root, manifest, allow_undecided=True)
            verdict = distribution_build.verify(dest, root, manifest)
        self.assertIn('skill:skills/01 剧本准备SKILL/剧本锻造',
                      verdict['checks']['supply_chain']['release_blockers'])
        self.assertFalse(verdict['release_ready'], verdict)


class AboutPageTests(unittest.TestCase):
    """REL-10：账户页「关于与开源许可」块的数据助手与入口；不建 Tk 窗口。"""

    def test_about_page_block_lists_version_build_and_license_entry(self):
        from desktop_account_page import AccountPageMixin, about_info, about_lines
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / '分发清单.json').write_text(json.dumps({'commit': 'abc1234'}), encoding='utf-8')
            (root / 'THIRD_PARTY_NOTICES.txt').write_text('第三方清单', encoding='utf-8')
            info = about_info(root)
            text = '\n'.join(about_lines(info))
        self.assertTrue(hasattr(AccountPageMixin, '_account_about_card'),
                        '账户页缺「关于与开源许可」块')
        self.assertTrue(info['version'], '关于页要显示应用版本')
        self.assertEqual(info['commit'], 'abc1234')
        self.assertEqual(info['notices_text'], '第三方清单')
        self.assertIn('版本', text)
        self.assertIn('开源许可', text)
        self.assertIn('THIRD_PARTY_NOTICES.txt', text)

    def test_about_page_license_entry_survives_missing_bundle(self):
        from desktop_account_page import about_info, about_lines
        with tempfile.TemporaryDirectory() as td:
            info = about_info(Path(td))
            text = '\n'.join(about_lines(info))
        self.assertEqual(info['notices_text'], '')
        self.assertIn('开源许可', text)


if __name__ == '__main__':
    unittest.main()
