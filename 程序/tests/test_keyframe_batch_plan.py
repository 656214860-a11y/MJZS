# -*- coding: utf-8 -*-
"""O25 首帧批次统一目标集：只补缺失／重试失败／显式替换与跳过原因。运行：python test_keyframe_batch_plan.py"""
import json, os, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
os.chdir(HERE)

from skip_reasons import PLATFORM_TKINTER
import keyframe_batch as kb


def make_episode(root, folder='episode', episode_id='EP001', shots=('SH001', 'SH002', 'SH003'),
                 frames=(), empty=(), deleted=()):
    base = Path(root) / folder
    (base / 'frames').mkdir(parents=True, exist_ok=True)
    rows = []
    for sid in shots:
        shot = {'id': sid, 'title': sid + ' 内容', 'duration': 5, 'frame': 'frames/%s.png' % sid,
                'frame_prompt': sid + ' 的提示词', 'characters': ['CHAR_001'], 'location': 'LOC_001'}
        if sid in deleted:
            shot['frame_deleted'] = True
        rows.append(shot)
    src = base / 'episode.json'
    src.write_text(json.dumps({'episode_id': episode_id, 'title': 'T', 'shots': rows}, ensure_ascii=False),
                   encoding='utf-8')
    for sid in frames:
        (base / 'frames' / (sid + '.png')).write_bytes(b'\x89PNG\r\n\x1a\n' + b'0' * 16)
    for sid in empty:
        (base / 'frames' / (sid + '.png')).write_bytes(b'')
    return src


def write_attempt(src, sid, state='uncertain'):
    folder = Path(src).parent / '首帧任务'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ('seedream_%s.json' % sid)).write_text(
        json.dumps({'state': state, 'shot_id': sid}), encoding='utf-8')


def target_ids(plan):
    return [item['shot_id'] for item in plan['targets']]


def skipped_reason(plan, sid):
    return next((item['reason'] for item in plan['skipped'] if item['shot_id'] == sid), '')


class MissingModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_only_shots_without_a_frame_are_targets(self):
        src = make_episode(self.tmp.name, frames=('SH001',), deleted=('SH003',))
        plan = kb.batch_plan(src)
        self.assertEqual(target_ids(plan), ['SH002'])
        self.assertEqual(plan['mode_label'], '只补缺失')
        self.assertEqual(plan['episode'], 'EP001')
        self.assertIn('已有可用首帧', skipped_reason(plan, 'SH001'))
        self.assertIn('已删除', skipped_reason(plan, 'SH003'))
        self.assertEqual(plan['counts'], {'targets': 1, 'skipped': 2})

    def test_an_empty_file_is_reported_not_silently_done(self):
        src = make_episode(self.tmp.name, frames=('SH001',), empty=('SH002',), deleted=('SH003',))
        plan = kb.batch_plan(src)
        self.assertEqual(target_ids(plan), [])
        self.assertIn('空文件', skipped_reason(plan, 'SH002'))

    def test_an_unset_or_outside_path_cannot_be_generated(self):
        src = make_episode(self.tmp.name, frames=('SH001',))
        episode = json.loads(Path(src).read_text(encoding='utf-8'))
        episode['shots'][1]['frame'] = ''                 # SH002 未配置
        episode['shots'][2]['frame'] = '../../outside.png'  # SH003 越界
        Path(src).write_text(json.dumps(episode, ensure_ascii=False), encoding='utf-8')
        plan = kb.batch_plan(src)
        self.assertEqual(target_ids(plan), [])
        self.assertIn('未配置', skipped_reason(plan, 'SH002'))
        self.assertIn('越界', skipped_reason(plan, 'SH003'))

    def test_an_attempted_shot_is_not_resubmitted_when_filling_gaps(self):
        src = make_episode(self.tmp.name, frames=('SH001',), deleted=('SH003',))
        write_attempt(src, 'SH002', 'uncertain')
        plan = kb.batch_plan(src)
        self.assertEqual(target_ids(plan), [])           # 结果待核实的旧任务不在这里重复付费
        reason = skipped_reason(plan, 'SH002')
        self.assertIn('重试失败', reason)
        self.assertIn('结果待核实', reason)

    def test_a_successful_shot_is_never_in_the_target_set(self):
        src = make_episode(self.tmp.name, frames=('SH001', 'SH002', 'SH003'))
        for mode in (kb.MODE_MISSING, kb.MODE_RETRY, kb.MODE_REPLACE):
            self.assertEqual(target_ids(kb.batch_plan(src, mode=mode)), [], mode)


class RetryModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_retry_covers_only_previously_attempted_shots(self):
        src = make_episode(self.tmp.name, shots=('SH001', 'SH002', 'SH004'), frames=('SH001',))
        write_attempt(src, 'SH002', 'uncertain')
        plan = kb.batch_plan(src, mode=kb.MODE_RETRY)
        self.assertEqual(target_ids(plan), ['SH002'])
        self.assertEqual(plan['targets'][0]['intent_label'], '重试失败')
        self.assertIn('结果待核实', plan['targets'][0]['note'])
        self.assertIn('只补缺失', skipped_reason(plan, 'SH004'))   # 没提交过的镜头不归重试管
        self.assertIn('已有可用首帧', skipped_reason(plan, 'SH001'))

    def test_a_cancelled_attempt_is_still_a_retry(self):
        src = make_episode(self.tmp.name, shots=('SH001', 'SH002'), frames=('SH001',))
        write_attempt(src, 'SH002', 'cancelled')
        plan = kb.batch_plan(src, mode=kb.MODE_RETRY)
        self.assertEqual(target_ids(plan), ['SH002'])
        self.assertIn('上次已放弃', plan['targets'][0]['note'])

    def test_the_recorded_state_can_be_injected(self):
        src = make_episode(self.tmp.name, shots=('SH001', 'SH002'), frames=('SH001',))
        plan = kb.batch_plan(src, mode=kb.MODE_RETRY, attempts={'SH002': 'sending'})
        self.assertEqual(target_ids(plan), ['SH002'])
        self.assertIn('提交中', plan['targets'][0]['note'])


class ReplaceModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_explicit_replace_targets_an_existing_shot(self):
        src = make_episode(self.tmp.name, frames=('SH001', 'SH002', 'SH003'))
        plan = kb.batch_plan(src, shot_ids=['SH001', 'SH002'], mode=kb.MODE_REPLACE)
        self.assertEqual(target_ids(plan), ['SH001', 'SH002'])
        for item in plan['targets']:
            self.assertTrue(item['will_replace'])
            self.assertIn('覆盖', item['note'])
        self.assertEqual(plan['skipped'], [])            # SH003 没点名，不列入

    def test_a_deleted_frame_is_never_revived_in_any_mode(self):
        src = make_episode(self.tmp.name, deleted=('SH003',))
        for mode in (kb.MODE_MISSING, kb.MODE_RETRY, kb.MODE_REPLACE):
            plan = kb.batch_plan(src, shot_ids=['SH003'], mode=mode)
            self.assertEqual(target_ids(plan), [], mode)
            self.assertIn('已删除', skipped_reason(plan, 'SH003'), mode)


class EpisodeScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_the_plan_is_scoped_to_one_episode(self):
        src_a = make_episode(self.tmp.name, folder='epA', episode_id='EPA')
        src_b = make_episode(self.tmp.name, folder='epB', episode_id='EPB', frames=('SH001', 'SH002'))
        plan = kb.batch_plan(src_a)
        self.assertEqual(plan['episode'], 'EPA')
        self.assertEqual(Path(plan['source']), Path(src_a).resolve())
        self.assertEqual(target_ids(plan), ['SH001', 'SH002', 'SH003'])   # B 集的首帧不影响 A 集

    def test_the_model_and_references_ride_along_with_each_target(self):
        src = make_episode(self.tmp.name, shots=('SH001', 'SH002'))
        plan = kb.batch_plan(src, model='本地 ComfyUI FLUX',
                             references=lambda shot: ['CHAR_001', 'LOC_001'])
        self.assertEqual(plan['model'], '本地 ComfyUI FLUX')
        for item in plan['targets']:
            self.assertEqual(item['references'], ['CHAR_001', 'LOC_001'])
            self.assertEqual(item['reference_count'], 2)
            self.assertTrue(item['prompt'])


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_the_summary_names_intent_episode_model_and_skips(self):
        src = make_episode(self.tmp.name, frames=('SH001',), deleted=('SH003',))
        plan = kb.batch_plan(src, model='本地 ComfyUI')
        text = kb.plan_summary(plan)
        self.assertIn('只补缺失', text)
        self.assertIn('EP001', text)
        self.assertIn('本地 ComfyUI', text)
        self.assertIn('目标 1 镜', text)
        self.assertIn('SH002', text)
        self.assertIn('跳过 2 镜', text)
        self.assertIn('SH003', text)


class PendingShotsStateTests(unittest.TestCase):
    def test_pending_shots_uses_the_same_frame_state(self):
        from keyframe_comfy import pending_shots
        with tempfile.TemporaryDirectory() as td:
            src = make_episode(td, shots=('SH001', 'SH002', 'SH003', 'SH004', 'SH005', 'SH006'),
                               frames=('SH001',), empty=('SH006',), deleted=('SH003',))
            episode = json.loads(Path(src).read_text(encoding='utf-8'))
            episode['shots'][3]['frame'] = ''                 # SH004 未配置
            episode['shots'][4]['frame'] = '../../outside.png'  # SH005 越界
            Path(src).write_text(json.dumps(episode, ensure_ascii=False), encoding='utf-8')
            shots = json.loads(Path(src).read_text(encoding='utf-8'))['shots']
            self.assertEqual([shot['id'] for shot in pending_shots(shots, Path(src).parent)], ['SH002'])


class DialogPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def widgets(self, widget, kind):
        found = [widget] if isinstance(widget, kind) else []
        for child in widget.winfo_children():
            found.extend(self.widgets(child, kind))
        return found

    def test_the_window_shows_the_batch_intent_and_plan_preview(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import tkinter as tk
        from tkinter import ttk
        import keyframe_comfy
        from test_keyframe_comfy import StubApp, make_project
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'batch_config.json'
            target.write_text(json.dumps({'url': 'http://127.0.0.1:8188', 'model': '', 'text_encoder': '',
                                          'vae': '', 'width': 768, 'height': 432}), encoding='utf-8')
            original = keyframe_comfy.CONFIG_FILE
            keyframe_comfy.CONFIG_FILE = target
            self.addCleanup(setattr, keyframe_comfy, 'CONFIG_FILE', original)
            proj, src = make_project(td)
            win = tk.Tk(); win.geometry('900x700+30+30')
            win._tick_images = [tk.PhotoImage(width=12, height=12), tk.PhotoImage(width=12, height=12)]
            self.addCleanup(win.destroy)
            app = StubApp(win, proj, src)
            dialog = keyframe_comfy.show(app, src)
            self.addCleanup(dialog.destroy)
            win.update()
            labels = [str(w.cget('text')) for w in self.widgets(dialog, ttk.Label)]
            self.assertIn('批次意图', labels)
            boxes = [list(box['values']) for box in self.widgets(dialog, ttk.Combobox)]
            self.assertIn(['只补缺失', '重试失败'], boxes)
            variables = [str(w.cget('textvariable')) for w in self.widgets(dialog, ttk.Label)]
            text = ' '.join(str(dialog.getvar(value) or '') for value in variables if value)
            self.assertIn('只补缺失', text)
            self.assertIn('SH002', text)          # 目标集预览把缺首帧的镜头写出来


if __name__ == '__main__':
    unittest.main(verbosity=2)