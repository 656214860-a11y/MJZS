# -*- coding: utf-8 -*-
"""REQ-S07 测试锚定：分镜定稿（07）里标 ✅ 却没有测试锚点的 13 条需求。

覆盖 REQ-S07-05/10/11/12/16/17/18/19/20/21/30/31；REQ-S07-32 由
``tests/test_storyboard_final_controller.py`` 里已有的三条用例锚定（本轮只补 docstring）。
编号原登记在 ``维护记录/需求锚定基线.json`` 的 ``untested_done``；这里的锚点全部落在真实代码行为上：

- 资产对齐、绑定、台词编号、签名复用、同集写回、同步期间改动中止、原子发布包、
  发布后退役、来源血缘：都走真实的 ``storyboard_final.finalize``，在
  ``tempfile.TemporaryDirectory()`` 隔离出来的项目里真读真写真发图；
- 手动入口与无人值守自动定稿：在无 Tk 的桌面对象上调用 ``Desktop``／
  ``AutoFlowsMixin``／``AutomationTickMixin`` 的真实方法（不创建 Tk 根窗口）。

断言不 mock 被测事实；只在需要观察「是否异步派发」「是否重建页面」时替换回调。
"""
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import infra.pet_state as pet_state
import stage_flow
import stage_layout
import stage_parallel
from agent.core import file_hash, read, save
from desktop import Desktop
from desktop_auto_flows import AutoFlowsMixin
from orchestrator.desktop_auto_state import AutoState, AutoStateHolderMixin
from desktop_automation_tick import AutomationTickMixin
from stage_execution_service import asset_plan_gateway, publish_final_storyboard_bundle
from orchestrator.storyboard_final import finalize
from storyboard_storage import ALIAS_FILE
from tests.image_fixtures import png

PAGE = pet_state.PAGE_OF


def _project(root):
    """一集可定稿的最小项目：资产清单、已采用分镜、首帧、结构剧本都在临时目录里。"""
    project = Path(root).resolve()
    episode = project / 'episode'
    (episode / 'assets' / '资产清单').mkdir(parents=True)
    (episode / 'assets' / 'characters').mkdir(parents=True)
    (episode / 'frames').mkdir(parents=True)
    source_dir = project / '03初步分镜' / '分镜文档'
    source_dir.mkdir(parents=True)
    (project / '03初步分镜' / 'frames').mkdir(parents=True)
    save(project / 'config.json', {'episode_dir': str(episode),
                                   'asset_library_dir': str(episode)})
    script = project / '02剧本' / 'EP001_结构剧本.json'
    script.parent.mkdir(parents=True)
    script.write_text(json.dumps({'episode_id': 'EP001'}, ensure_ascii=False), encoding='utf-8')
    save(episode / 'assets' / '资产清单' / 'assets.json',
         {'CHAR_001': {'name': '主角'}, 'CHAR_002': {'name': '配角'},
          'LOC_001': {'name': '街道'}})
    save(episode / 'assets.json',
         {'CHAR_001': {'name': '主角', 'image': 'assets/characters/CHAR_001.png'},
          'LOC_001': {'name': '街道', 'image': 'assets/characters/LOC_001.png'}})
    (episode / 'assets' / 'characters' / 'CHAR_001.png').write_bytes(png())
    (episode / 'assets' / 'characters' / 'LOC_001.png').write_bytes(png(color='blue'))
    (project / '03初步分镜' / 'frames' / 'SH001.png').write_bytes(png())
    (project / '03初步分镜' / 'frames' / 'SH002.png').write_bytes(png(color='blue'))
    source = source_dir / 'EP001_分镜.json'
    shots = [
        {'id': 'SH001', 'title': '开场', 'duration': 5, 'characters': ['主角', 'CHAR_002'],
         'location': 'LOC_001', 'frame': 'frames/SH001.png', 'video_prompt': '开场镜头',
         'dialogue': [{'speaker': '主角', 'text': '你好'}]},
        {'id': 'SH002', 'title': '反应', 'duration': 4, 'characters': ['CHAR_001'],
         'location': 'LOC_001', 'frame': 'frames/SH002.png', 'video_prompt': '反应镜头',
         'dialogue': []},
    ]
    source.write_text(json.dumps({'episode_id': 'EP001', 'title': '第一集', 'shots': shots,
                                  'source_script': '02剧本/EP001_结构剧本.json'},
                                 ensure_ascii=False, indent=2), encoding='utf-8')
    save(project / 'ui_settings.json', {'adopted_storyboards': [str(source)],
                                        'frame_json': str(source)})
    return project, episode, source


def _ids_project(root):
    """资产全部用编号引用的项目：无人值守扫描口径用。"""
    project, episode, source = _project(root)
    data = read(source)
    data['shots'][0]['characters'] = ['CHAR_001', 'CHAR_002']
    data['shots'][0]['dialogue'] = []
    save(source, data)
    return project, episode, source


def _finals(project):
    return sorted(p.parent for p in (Path(project) / '07分镜定稿' / '分镜').glob('*/episode.json'))


def _adopt(project, path):
    save(project / 'ui_settings.json', {'adopted_storyboards': [str(path)],
                                        'frame_json': str(path)})


def _alias(project, source, dest):
    alias = Path(project) / '07分镜定稿' / '分镜' / ALIAS_FILE
    save(alias, {Path(source).resolve().relative_to(Path(project).resolve()).as_posix():
                 (Path(dest) / 'episode.json').resolve().relative_to(
                     Path(project).resolve()).as_posix()})


class _Status:
    def __init__(self):
        self.text = ''

    def set(self, value):
        self.text = value


class _DesktopStub(AutoStateHolderMixin):
    """只带真实方法需要的属性；方法本身用 Desktop／AutoFlowsMixin 的真实现。"""

    apply_final = Desktop.apply_final
    poll_auto_final = AutoFlowsMixin.poll_auto_final
    auto_final_scan = AutomationTickMixin.auto_final_scan

    def __init__(self, project, episode):
        import queue
        self.auto = AutoState()   # R1985：自动化状态收进 desktop.auto，旧属性名经转发
        self.root = project
        self.episode = episode
        self.studio = object()
        self.worker = False
        self.video_sessions = {}
        self.status = _Status()
        self.pet = mock.Mock()
        self.pet.should_auto_run.return_value = True
        self.auto.final_signature = None
        self.auto.final_notice = None
        self.auto.final_blocked = False
        self.auto.final_busy = False
        self.auto.final_due = 0.0
        self.auto.final_error = ''
        self.auto.final_queue = queue.Queue()
        self.page_index = PAGE['final']
        self.shown = []
        self.remembered = []
        self.jobs = []
        self.report = None

    def asset_base(self):
        return self.episode

    def remember_frame_json(self, path):
        self.remembered.append(path)

    def show(self, index):
        self.shown.append(index)

    def pet_report(self, stage, text, ok=True):
        self.report = (stage, text, ok)

    def async_(self, work, finish):
        self.jobs.append((work, finish))


class S07AnchorTests(unittest.TestCase):
    def test_req_s07_05_busy_production_blocks_manual_and_waits_auto(self):
        """REQ-S07-05：定稿期间不得有制作任务在跑；手动入口拒绝，自动入口等待。"""
        with tempfile.TemporaryDirectory() as td:
            project, episode, source = _project(Path(td) / 'p')
            stub = _DesktopStub(project, episode)
            stub.worker = object()
            with self.assertRaisesRegex(ValueError, '等待当前制作任务结束'):
                Desktop.make_final_storyboard(stub, source=source)
            stub.worker = False
            stub.video_sessions = {'v': SimpleNamespace(busy=True)}
            with self.assertRaisesRegex(ValueError, '等待当前制作任务结束'):
                Desktop.make_final_storyboard(stub, source=source)
            self.assertEqual(stub.jobs, [])
            # 自动入口遇忙只记「定稿在等」，不抢跑、不起后台定稿。
            stub.video_sessions = {}
            stub.auto_final_target = lambda: source
            stub.busy_production = lambda: True
            AutoFlowsMixin.poll_auto_final(stub)
            self.assertTrue(stub.auto.final_blocked)
            self.assertFalse(stub.auto.final_busy)
            self.assertTrue(stub.auto.final_queue.empty())

    def test_req_s07_10_asset_names_resolve_to_ids_or_fail_loudly(self):
        """REQ-S07-10：角色／场景／道具先解析成资产编号，解析不到就报错，不静默跳过。"""
        with tempfile.TemporaryDirectory() as td:
            project, episode, source = _project(Path(td) / 'p')
            dest = finalize(project, episode, source, retire_working=lambda *a: None,
                            gateway=asset_plan_gateway())
            shots = read(dest / 'episode.json')['shots']
            self.assertEqual(shots[0]['characters'], ['CHAR_001', 'CHAR_002'])
            self.assertEqual(shots[0]['location'], 'LOC_001')
            self.assertEqual(read(episode / 'assets' / '资产清单' / '名称编号对照.json'),
                             {'CHAR:主角': 'CHAR_001'})
            before = (dest / 'episode.json').read_bytes()
            data = read(source)
            data['shots'][1]['characters'] = [{'description': '没有编号也没有名称'}]
            save(source, data)
            with self.assertRaisesRegex(ValueError, '无法匹配资产编号：None'):
                finalize(project, episode, source, retire_working=lambda *a: None,
                         gateway=asset_plan_gateway())
            self.assertEqual(_finals(project), [dest])           # 不新建目录
            self.assertEqual((dest / 'episode.json').read_bytes(), before)
            self.assertTrue(source.is_file())                    # 源稿没被动过

    def test_req_s07_11_asset_bindings_and_missing_assets_are_recorded(self):
        """REQ-S07-11：每镜写 asset_bindings／reference_images／asset_status，缺图汇入 missing_assets。"""
        with tempfile.TemporaryDirectory() as td:
            project, episode, source = _project(Path(td) / 'p')
            dest = finalize(project, episode, source, retire_working=lambda *a: None,
                            gateway=asset_plan_gateway())
            bundle = read(dest / 'episode.json')
            first, second = bundle['shots']
            self.assertEqual(first['asset_bindings']['CHAR_001'],
                             {'name': '主角', 'image': 'assets/characters/CHAR_001.png',
                              'status': '已导入'})
            self.assertEqual(first['asset_bindings']['CHAR_002'],
                             {'name': '配角', 'image': None, 'status': '待导入'})
            self.assertEqual(first['asset_status'], '待补齐资产')
            self.assertEqual(second['asset_status'], '已匹配资产')
            # 参考图只收已导入资产的图，缺图的编号不混进去。
            self.assertEqual(first['reference_images'],
                             ['assets/characters/CHAR_001.png',
                              'assets/characters/LOC_001.png'])
            self.assertEqual(bundle['missing_assets'], ['CHAR_002'])
            self.assertFalse(bundle['assets_ready'])
            self.assertNotIn('image', read(dest / 'assets.json')['CHAR_002'])

    def test_req_s07_12_dialogue_speaker_is_replaced_by_the_character_id(self):
        """REQ-S07-12：台词 speaker 按名称映射替换为角色编号。"""
        with tempfile.TemporaryDirectory() as td:
            project, episode, source = _project(Path(td) / 'p')
            dest = finalize(project, episode, source, retire_working=lambda *a: None,
                            gateway=asset_plan_gateway())
            dialogue = read(dest / 'episode.json')['shots'][0]['dialogue']
            self.assertEqual(dialogue, [{'speaker': 'CHAR_001', 'text': '你好'}])

    def test_req_s07_16_identical_content_reuses_the_existing_final(self):
        """REQ-S07-16：内容签名相同的定稿直接复用，不新建，只补血缘并按需退役工作稿。"""
        with tempfile.TemporaryDirectory() as td:
            project, episode, source = _project(Path(td) / 'p')
            retired = []
            first = finalize(project, episode, source,
                             retire_working=lambda *a: retired.append(a),
                             gateway=asset_plan_gateway())
            again = finalize(project, episode, source,
                             retire_working=lambda *a: retired.append(a),
                             gateway=asset_plan_gateway())
            self.assertEqual(first, again)
            self.assertEqual(_finals(project), [first])
            self.assertEqual(len(retired), 2)                    # 复用路径仍要退役工作稿
            self.assertEqual(len(read(first / '产物来源关系.json')['entries']), 1)
            # 内容一变签名就变，不能再复用旧目录。
            data = read(source)
            data['shots'][1]['title'] = '改过的反应'
            save(source, data)
            changed = finalize(project, episode, source, retire_working=lambda *a: None,
                               gateway=asset_plan_gateway())
            self.assertNotEqual(changed, first)
            self.assertEqual(len(_finals(project)), 2)

    def test_req_s07_17_the_same_episode_writes_back_to_the_same_directory(self):
        """REQ-S07-17：同一集再定稿写回同一目录（别名映射或源本身就是定稿）。"""
        with tempfile.TemporaryDirectory() as td:
            project, episode, source = _project(Path(td) / 'p')
            dest = finalize(project, episode, source, retire_working=lambda *a: None,
                            gateway=asset_plan_gateway())
            _alias(project, source, dest)
            data = read(source)
            data['title'] = '改过的标题'
            save(source, data)
            moved = finalize(project, episode, source, retire_working=lambda *a: None,
                             gateway=asset_plan_gateway())
            self.assertEqual(moved, dest)
            self.assertEqual(len(_finals(project)), 1)
            self.assertEqual(read(dest / 'episode.json')['title'], '改过的标题')
        with tempfile.TemporaryDirectory() as td:
            project, episode, source = _project(Path(td) / 'p')
            dest = finalize(project, episode, source, retire_working=lambda *a: None,
                            gateway=asset_plan_gateway())
            final_doc = dest / 'episode.json'
            data = read(final_doc)
            data['title'] = '定稿后改的标题'
            save(final_doc, data)
            _adopt(project, final_doc)
            back = finalize(project, episode, final_doc, retire_working=lambda *a: None,
                            gateway=asset_plan_gateway())
            self.assertEqual(back, dest)
            self.assertEqual(len(_finals(project)), 1)
            self.assertEqual(read(final_doc)['title'], '定稿后改的标题')

    def test_req_s07_18_source_changed_during_sync_aborts_and_publishes_nothing(self):
        """REQ-S07-18：同步期间源被修改即中止、保留原 JSON；发布前后各校验一次。"""
        with tempfile.TemporaryDirectory() as td:
            project, episode, source = _project(Path(td) / 'p')
            import contract.shot_batches as shot_batches
            real_assign = shot_batches.assign
            original = source.read_bytes()

            def tamper(shots):
                source.write_bytes(source.read_bytes() + b' ')
                return real_assign(shots)

            with mock.patch.object(shot_batches, 'assign', tamper):
                with self.assertRaisesRegex(ValueError, '同步期间已修改'):
                    finalize(project, episode, source, retire_working=lambda *a: None,
                             gateway=asset_plan_gateway())
            self.assertEqual(list((project / '07分镜定稿' / '分镜').glob('*/episode.json')), [])
            self.assertEqual(source.read_bytes(), original + b' ')   # 原 JSON 保留，未被改写
        with tempfile.TemporaryDirectory() as td:
            project, episode, source = _project(Path(td) / 'p')
            from writing import validate_episode as real_validate
            calls = []

            def counting(value, base, assets=None):
                calls.append(Path(base))
                return real_validate(value, base, assets)

            with mock.patch('writing.validate_episode', counting):
                dest = finalize(project, episode, source, retire_working=lambda *a: None,
                                gateway=asset_plan_gateway())
            self.assertGreaterEqual(len(calls), 2)               # 发布前 + 发布时
            real_validate(read(dest / 'episode.json'), dest, read(dest / 'assets.json'))

    def test_req_s07_19_bundle_is_paired_copied_and_rolled_back_on_failure(self):
        """REQ-S07-19：episode.json 与 assets.json 成对落盘，图复制进定稿目录，重名加后缀，失败回滚。"""
        with tempfile.TemporaryDirectory() as td:
            project, episode, source = _project(Path(td) / 'p')
            dest = finalize(project, episode, source, retire_working=lambda *a: None,
                            gateway=asset_plan_gateway())
            self.assertTrue((dest / 'episode.json').is_file())
            self.assertTrue((dest / 'assets.json').is_file())
            self.assertTrue((dest / 'assets' / 'characters' / 'CHAR_001.png').is_file())
            self.assertEqual(sorted(p.name for p in (dest / 'frames').glob('*.png')),
                             ['SH001.png', 'SH002.png'])
            self.assertEqual(read(dest / 'assets.json')['CHAR_001']['image'],
                             'assets/characters/CHAR_001.png')
            # 同名不同内容：加哈希后缀，并把 assets／reference_images／asset_bindings 一起改写。
            _alias(project, source, dest)
            (episode / 'assets' / 'characters' / 'CHAR_001.png').write_bytes(png(color='blue'))
            moved = finalize(project, episode, source, retire_working=lambda *a: None,
                             gateway=asset_plan_gateway())
            self.assertEqual(moved, dest)
            suffixed = [p for p in (dest / 'assets' / 'characters').glob('CHAR_001_*.png')]
            self.assertEqual(len(suffixed), 1)
            relative = suffixed[0].relative_to(dest).as_posix()
            shot = read(dest / 'episode.json')['shots'][0]
            self.assertEqual(shot['reference_images'][0], relative)
            self.assertEqual(shot['asset_bindings']['CHAR_001']['image'], relative)
            self.assertEqual(read(dest / 'assets.json')['CHAR_001']['image'], relative)
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            episode_file, asset_file = folder / 'episode.json', folder / 'assets.json'
            save(episode_file, {'old': 'episode'})
            save(asset_file, {'old': 'assets'})

            def reject(_episode, _assets):
                raise ValueError('校验失败')

            with self.assertRaisesRegex(ValueError, '校验失败'):
                publish_final_storyboard_bundle(episode_file, asset_file,
                                                {'shots': []}, {}, reject)
            self.assertEqual(read(episode_file), {'old': 'episode'})
            self.assertEqual(read(asset_file), {'old': 'assets'})
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            episode_file, asset_file = folder / 'episode.json', folder / 'assets.json'
            with self.assertRaises(ValueError):
                publish_final_storyboard_bundle(episode_file, asset_file, {'shots': []}, {},
                                                lambda *_: (_ for _ in ()).throw(ValueError('x')))
            self.assertFalse(episode_file.exists())
            self.assertFalse(asset_file.exists())

    def test_req_s07_20_retire_happens_only_after_publish_and_only_for_working_sources(self):
        """REQ-S07-20：发布完成后才退役工作稿；源是定稿时不退役；缺注入即抛 TypeError。"""
        with tempfile.TemporaryDirectory() as td:
            project, episode, source = _project(Path(td) / 'p')
            seen = {}

            def retire(project_, source_, target_, expected_):
                seen.update(source=Path(source_), target=Path(target_),
                            published=Path(target_).is_file(), expected=expected_)

            dest = finalize(project, episode, source, retire_working=retire,
                            gateway=asset_plan_gateway())
            self.assertTrue(seen['published'])                   # 退役时定稿已落盘
            self.assertEqual(seen['target'], dest / 'episode.json')
            self.assertEqual(seen['source'], source.resolve())
            self.assertEqual(seen['expected'], file_hash(source))
        with tempfile.TemporaryDirectory() as td:
            project, episode, source = _project(Path(td) / 'p')
            with self.assertRaisesRegex(TypeError, 'L3'):
                finalize(project, episode, source, gateway=asset_plan_gateway())
            finals = _finals(project)
            self.assertEqual(len(finals), 1)                     # 抛错发生在发布之后
            self.assertTrue((finals[0] / 'episode.json').is_file())
        with tempfile.TemporaryDirectory() as td:
            project, episode, source = _project(Path(td) / 'p')
            dest = finalize(project, episode, source, retire_working=lambda *a: None,
                            gateway=asset_plan_gateway())
            _adopt(project, dest / 'episode.json')

            def must_not_retire(*_args):
                raise AssertionError('源本身是定稿，不应退役')

            back = finalize(project, episode, dest / 'episode.json',
                            retire_working=must_not_retire, gateway=asset_plan_gateway())
            self.assertEqual(back, dest)

    def test_req_s07_21_lineage_points_at_the_structured_script_not_the_working_json(self):
        """REQ-S07-21：血缘追溯到源 JSON 的 source_script；源本身是定稿时不新记。"""
        with tempfile.TemporaryDirectory() as td:
            project, episode, source = _project(Path(td) / 'p')
            dest = finalize(project, episode, source, retire_working=lambda *a: None,
                            gateway=asset_plan_gateway())
            entries = read(dest / '产物来源关系.json')['entries']
            entry = next(row for row in entries
                         if row['artifact'].endswith('episode.json'))
            self.assertEqual(entry['source'], '02剧本/EP001_结构剧本.json')
            self.assertNotEqual(entry['source'],
                                source.resolve().relative_to(project).as_posix())
            before = (dest / '产物来源关系.json').read_bytes()
            _adopt(project, dest / 'episode.json')
            finalize(project, episode, dest / 'episode.json',
                     retire_working=lambda *a: None, gateway=asset_plan_gateway())
            self.assertEqual((dest / '产物来源关系.json').read_bytes(), before)

    def test_req_s07_30_manual_entry_runs_async_reports_and_rebuilds_the_page(self):
        """REQ-S07-30：手动入口「手动同步资产」异步定稿，完成后三虎播报并重建定稿页。"""
        with tempfile.TemporaryDirectory() as td:
            project, episode, source = _project(Path(td) / 'p')
            stub = _DesktopStub(project, episode)
            self.assertEqual(stage_flow.MANUAL_LABELS['final'], '手动同步资产')
            Desktop.make_final_storyboard(stub, source=source)
            self.assertEqual(len(stub.jobs), 1)
            folder = stub.jobs[0][0]()
            with mock.patch('stage_execution_service.refresh_storyboard_studios'), \
                    mock.patch('storyboard_selection.remember_final_view'):
                stub.jobs[0][1](folder)
            self.assertIsNotNone(stub.report, '定稿完成后没有三虎播报')
            self.assertEqual(stub.report[0], 'final')
            self.assertIn('已刷新', stub.report[1])
            self.assertEqual(stub.shown, [PAGE['final']])
            self.assertEqual([Path(p).name for p in stub.remembered], ['episode.json'])

    def test_req_s07_31_unattended_runs_only_when_ticked_for_a_working_source_once(self):
        """REQ-S07-31：无人值守仅在勾选时、对工作稿、同一签名只跑一次；失败退避 5 分钟。"""
        with tempfile.TemporaryDirectory() as td:
            project, episode, source = _project(Path(td) / 'p')
            off = _DesktopStub(project, episode)
            off.pet.should_auto_run.return_value = False
            off.auto.final_signature = ('s', 'h')
            off.auto.final_blocked = True
            AutoFlowsMixin.poll_auto_final(off)
            self.assertIsNone(off.auto.final_signature)
            self.assertFalse(off.auto.final_blocked)
            self.assertFalse(off.auto.final_busy)

            waiting = _DesktopStub(project, episode)
            waiting.auto_final_target = lambda: source
            waiting.busy_production = lambda: True
            AutoFlowsMixin.poll_auto_final(waiting)
            self.assertTrue(waiting.auto.final_blocked)
            self.assertFalse(waiting.auto.final_busy)

            repeat = _DesktopStub(project, episode)
            repeat.auto_final_target = lambda: source
            repeat.busy_production = lambda: False
            repeat.auto.final_signature = (str(source), file_hash(source))
            repeat.auto.final_blocked = True
            AutoFlowsMixin.poll_auto_final(repeat)
            self.assertFalse(repeat.auto.final_blocked)
            self.assertFalse(repeat.auto.final_busy)             # 同一份稿不重复定稿

            dispatch = _DesktopStub(project, episode)
            dispatch.auto_final_target = lambda: source
            dispatch.busy_production = lambda: False
            AutoFlowsMixin.poll_auto_final(dispatch)
            self.assertTrue(dispatch.auto.final_busy)
            ok, value, signature = dispatch.auto.final_queue.get(timeout=60)
            self.assertTrue(ok)
            self.assertEqual(Path(value[0]).name, 'EP001_分镜定稿_' + time.strftime('%Y%m%d'))
            self.assertFalse(source.is_file())                   # 工作稿已退役

        with tempfile.TemporaryDirectory() as td:
            project, episode, source = _project(Path(td) / 'p')
            failed = _DesktopStub(project, episode)
            failed.auto.final_busy = True
            failed.auto.final_signature = ('s', 'h')
            failed.auto.final_queue.put((False, '自动定稿未完成：磁盘已满', ('s', 'h')))
            failed.apply_final = lambda project_, folder_: 'ok'
            failed.kick_unattended = lambda name: None
            failed._poll_auto_due = lambda *args, **kwargs: False
            started = time.monotonic()
            AutoFlowsMixin._tick_auto_final(failed)
            self.assertIsNone(failed.auto.final_signature)
            self.assertGreaterEqual(failed.auto.final_due - started, 290)
            self.assertIn('磁盘已满', failed.status.text)

        with tempfile.TemporaryDirectory() as td:
            project, episode, source = _ids_project(Path(td) / 'p')
            scan = _DesktopStub(project, episode)
            state = AutomationTickMixin.auto_final_scan(scan)
            self.assertEqual(state['pending'], [source])
            self.assertIsNone(state['target'])
            self.assertEqual(state['missing'], {'CHAR_002'})
            self.assertIsNone(AutomationTickMixin.auto_final_target(scan))
            (episode / 'assets' / 'characters' / 'CHAR_002.png').write_bytes(png())
            registry = read(episode / 'assets.json')
            registry['CHAR_002'] = {'name': '配角',
                                    'image': 'assets/characters/CHAR_002.png'}
            save(episode / 'assets.json', registry)
            self.assertEqual(AutomationTickMixin.auto_final_target(scan), source)
            final_dir = project / '07分镜定稿' / '分镜' / 'EP001_分镜定稿_20260101'
            final_dir.mkdir(parents=True)
            save(final_dir / 'episode.json', {'episode_id': 'EP001', 'shots': []})
            _adopt(project, final_dir / 'episode.json')
            save(project / 'ui_settings.json',
                 {'adopted_storyboards': [str(final_dir / 'episode.json'), str(source)],
                  'frame_json': str(source)})
            state = AutomationTickMixin.auto_final_scan(scan)
            self.assertNotIn(final_dir, [p.parent for p in state['pending']])

    def test_req_s07_03_depends_is_data_graph_and_sg_gates_are_business_preconditions(self):
        """REQ-S07-03：DEPENDS['final'] 只表数据依赖；连贯性／资产前置由 SG-02／SG-01 表达。"""
        self.assertEqual(stage_flow.DEPENDS['final'], ('storyboard',))
        gates = {row['id']: row for row in stage_parallel.GATES}
        self.assertEqual((gates['SG-01']['to'], gates['SG-01']['check']),
                         ('continuity', 'assets_locked'))
        self.assertEqual((gates['SG-02']['to'], gates['SG-02']['check']),
                         ('final', 'ledger_ready'))

    def test_req_s07_45_ledger_artifacts_are_real_paths_in_both_blocking_branches(self):
        """REQ-S07-45：SG-02 陈旧与待办分支都返回实际读到的台账文件。"""
        matching = [{'id': 'SH001', 'characters': ['CHAR_001'], 'location': 'LOC_001'}]
        stale_shots = [{'id': 'SH002', 'characters': ['CHAR_001'], 'location': 'LOC_001'}]
        for folder in ('06连贯性清单', '05连贯性清单'):
            with self.subTest(layout=folder), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                file = root / folder / 'output' / 'continuity_ledger.json'
                save(file, {'version': 1, 'stage': 'continuity',
                            'batches': [{'batch_id': 'B01', 'shot_ids': ['SH001']}],
                            'summary': {'ok': True, 'problems': []}})

                with mock.patch.object(stage_parallel, '_current_shots',
                                       return_value=stale_shots):
                    stale = stage_parallel.ledger_ready(str(root))
                self.assertFalse(stale['ok'])
                self.assertTrue(stale['problems'])
                self.assertEqual(Path(stale['artifacts'][0]), file)
                self.assertTrue(Path(stale['artifacts'][0]).is_file())

                with mock.patch.object(stage_parallel, '_current_shots',
                                       return_value=matching), \
                        mock.patch('continuity_ledger.open_problems',
                                   return_value=('待裁决问题',)):
                    pending = stage_parallel.ledger_ready(str(root))
                self.assertFalse(pending['ok'])
                self.assertEqual(Path(pending['artifacts'][0]), file)
                self.assertTrue(Path(pending['artifacts'][0]).is_file())

        with tempfile.TemporaryDirectory() as temporary:
            empty = stage_parallel.ledger_ready(temporary)
        self.assertEqual(empty['artifacts'], ())

    def test_req_s07_15_batch_assignment_failure_aborts_finalize(self):
        """REQ-S07-15：切批失败中止定稿：抛含中文原因的 ValueError，原异常作 __cause__，不写任何定稿产物。"""
        with tempfile.TemporaryDirectory() as td:
            project, episode, source = _project(Path(td) / 'p')
            original = source.read_bytes()
            finals_root = project / '07分镜定稿' / '分镜'
            import contract.shot_batches as shot_batches
            failure = RuntimeError('三元组字典损坏')
            retired = []
            with mock.patch.object(shot_batches, 'assign', side_effect=failure):
                with self.assertRaises(ValueError) as caught:
                    finalize(project, episode, source, retire_working=lambda *a: retired.append(a),
                             gateway=asset_plan_gateway())
            message = str(caught.exception)
            self.assertIn('批次', message)
            self.assertIn('三元组字典损坏', message)
            self.assertIs(caught.exception.__cause__, failure)
            self.assertEqual(retired, [])                         # 不触发工作稿退役
            self.assertEqual([p for p in finals_root.iterdir() if p.is_dir()]
                             if finals_root.is_dir() else [], [])
            self.assertFalse((finals_root / ALIAS_FILE).is_file())
            self.assertEqual(source.read_bytes(), original)
            from stage_layout import dirname_of, paths
            docs = paths(project, dirname_of('final'))['docs']
            self.assertEqual(sorted(p.name for p in docs.glob('*.md')) if docs.is_dir() else [], [])

    def test_req_s07_44_finalize_derives_batch_plan_and_shot_table(self):
        """REQ-S07-44：定稿写出后按 stage_layout 的 docs/ 派生批次说明与镜头表，只由定稿数据派生。"""
        import contract.shot_batches as shot_batches
        from stage_layout import dirname_of, paths
        with tempfile.TemporaryDirectory() as td:
            project, episode, source = _project(Path(td) / 'p')
            dest = finalize(project, episode, source, retire_working=lambda *a: None,
                            gateway=asset_plan_gateway())
            bundle = read(dest / 'episode.json')
            docs = paths(project, dirname_of('final'))['docs']
            plan, table = docs / 'batch_plan.md', docs / 'shot_table.md'
            self.assertTrue(plan.is_file())
            self.assertTrue(table.is_file())
            plan_text = plan.read_text(encoding='utf-8')
            grouped = shot_batches.batches(bundle['shots'])
            self.assertGreaterEqual(len(grouped), 2)
            for name, items in grouped.items():
                self.assertIn(name, plan_text)
                for item in items:
                    self.assertIn(str(item.get('shot_id')), plan_text)
            self.assertIn('三元组', plan_text)
            rows = [line for line in table.read_text(encoding='utf-8').splitlines()
                    if line.startswith('| ') and not line.startswith('| ---')]
            self.assertEqual(len(rows), len(bundle['shots']) + 1)   # 表头 + 一镜一行
            for item, line in zip(bundle['shots'], rows[1:]):
                self.assertIn(str(item['shot_id']), line)
                self.assertIn(str(item['batch_id']), line)
                self.assertIn(str(item['scene_id']), line)
                self.assertIn(str(item['estimated_duration']), line)
            # 同一份输入再定稿（签名复用）内容不变，不重复生成多份。
            again = finalize(project, episode, source, retire_working=lambda *a: None,
                             gateway=asset_plan_gateway())
            self.assertEqual(again, dest)
            self.assertEqual(plan.read_text(encoding='utf-8'), plan_text)
            self.assertEqual(sorted(p.name for p in docs.iterdir() if p.suffix == '.md'),
                             ['batch_plan.md', 'shot_table.md'])
        # 切批失败路径不派生这两份文件。
        with tempfile.TemporaryDirectory() as td:
            project, episode, source = _project(Path(td) / 'p')
            with mock.patch.object(shot_batches, 'assign', side_effect=RuntimeError('坏批次')):
                with self.assertRaises(ValueError):
                    finalize(project, episode, source, retire_working=lambda *a: None,
                             gateway=asset_plan_gateway())
            docs = paths(project, dirname_of('final'))['docs']
            self.assertFalse((docs / 'batch_plan.md').is_file())
            self.assertFalse((docs / 'shot_table.md').is_file())

    def test_req_s07_43_stage_layout_declares_the_real_final_files(self):
        """REQ-S07-43：07 声明实际产出的 episode.json＋assets.json，08／09／11 输入与各自实际读取一致。"""
        by_stage = {row[1]: row for row in stage_layout.STAGES}
        self.assertEqual(by_stage['final'][5], ('episode.json', 'assets.json'))
        self.assertEqual(by_stage['keyframe'][4], ('episode.json', 'assets.json'))
        self.assertEqual(by_stage['previs'][4], ('episode.json', 'assets.json', 'frames.json'))
        self.assertEqual(by_stage['audio'][4], ('episode.json',))
        declared = [name for row in stage_layout.STAGES for name in row[4] + row[5]]
        self.assertNotIn('storyboard_final.json', declared)
        self.assertIn(('episode.json · batch_id', '07分镜定稿/docs/batch_plan.md',
                       '批次是机器切的，说明给人看'), stage_layout.json_md_rows())

    def test_req_s07_53_skill_describes_registration_not_unimplemented_snapshots(self):
        """REQ-S07-53：内置版本 SKILL 已清理，工具登记文案如实描述登记而非未实现快照。"""
        import skill_tools
        from orchestrator.skill_project_layer import RETIRED_BUILTIN_SKILL_IDS

        self.assertFalse((Path(__file__).resolve().parents[1] / 'skills' /
                          '07分镜定稿SKILL' / 'storyboard-version-snapshot.skill.md').exists())
        self.assertIn('storyboard-version-snapshot', RETIRED_BUILTIN_SKILL_IDS)
        self.assertIn('登记这份分镜', skill_tools.READY['storyboard.save'][1])


if __name__ == '__main__':
    unittest.main(verbosity=2)
