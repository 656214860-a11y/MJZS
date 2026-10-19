# -*- coding: utf-8 -*-
"""第 47 期第 2 条：白模预演的制作监视页（在浏览器里看制作，不再弹桌面 Blender）。

用户这一轮的要求：点「手动制作白模」时在浏览器里看进度，不要另外弹一个桌面 Blender 窗口。
这一份盯住三件事：

* 这一页本身：进度读 Blender 脚本写出来的那份「<镜头>_进度.json」，收尾状态不写百分比；
  只列本项目的镜头；起得来就复用同一个地址，停得干净。
* 派发那一侧：手动派发把监视页起起来，并把地址说在 summary 里（无人值守不弹浏览器）。
* 引擎那一侧：工作线程不再打开桌面 Blender（回归：原来那条 native_apps.open_blender）。

运行：python test_previs_monitor.py
"""
import json, os, shutil, sys, tempfile, time, unittest, urllib.request
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

import previs_monitor
from agent.core import save
from file_cache import clear


def progress_file(directory, sid, **fields):
    """摆一份 Blender 脚本会写出来的进度 JSON。"""
    path = Path(directory) / (sid + '_进度.json')
    path.write_text(json.dumps(dict(fields, shot_id=sid), ensure_ascii=False), encoding='utf-8')
    return path


class ProgressTests(unittest.TestCase):
    """REQ-S09-23：这一镜走到哪一步了；进度只认 Blender 写出的帧数，缺失／无效保持制作中。"""

    def test_a_missing_file_still_says_it_is_being_made(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(previs_monitor.progress_of({'log_dir': td}, 'SH001'), '制作中')

    def test_there_is_nothing_to_read_without_a_log_directory(self):
        self.assertEqual(previs_monitor.progress_of({}, 'SH001'), '制作中')
        self.assertEqual(previs_monitor.progress_of(None, 'SH001'), '制作中')

    def test_render_progress_is_a_percentage(self):
        with tempfile.TemporaryDirectory() as td:
            progress_file(td, 'SH001', stage='render', completed=3, total=10)
            self.assertEqual(previs_monitor.progress_of({'log_dir': td}, 'SH001'), '渲染 3/10 帧（30%）')

    def test_a_broken_count_falls_back_to_the_plain_word(self):
        with tempfile.TemporaryDirectory() as td:
            progress_file(td, 'SH001', stage='render', completed=2, total=0)
            self.assertEqual(previs_monitor.progress_of({'log_dir': td}, 'SH001'), '渲染中')
            progress_file(td, 'SH001', stage='render', completed=True, total=10)
            self.assertEqual(previs_monitor.progress_of({'log_dir': td}, 'SH001'), '渲染中')

    def test_someone_elses_shot_file_is_not_this_shot(self):
        with tempfile.TemporaryDirectory() as td:
            path = progress_file(td, 'SH001', stage='render', completed=1, total=4)
            path.write_text(json.dumps({'shot_id': 'SH002', 'stage': 'render', 'completed': 1, 'total': 4},
                                       ensure_ascii=False), encoding='utf-8')
            self.assertEqual(previs_monitor.progress_of({'log_dir': td}, 'SH001'), '制作中')

    def test_the_stage_words(self):
        with tempfile.TemporaryDirectory() as td:
            progress_file(td, 'SH001', stage='scene')
            self.assertEqual(previs_monitor.progress_of({'log_dir': td}, 'SH001'), '准备场景')
            progress_file(td, 'SH001', stage='encoding')
            self.assertEqual(previs_monitor.progress_of({'log_dir': td}, 'SH001'), '合成视频')
            progress_file(td, 'SH001', stage='cancelled')
            self.assertEqual(previs_monitor.progress_of({'log_dir': td}, 'SH001'), '渲染已停止')
            progress_file(td, 'SH001', stage='看不懂的一步')
            self.assertEqual(previs_monitor.progress_of({'log_dir': td}, 'SH001'), '制作中')

    def test_a_broken_file_is_not_a_crash(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'SH001_进度.json').write_text('这不是 JSON', encoding='utf-8')
            self.assertEqual(previs_monitor.progress_of({'log_dir': td}, 'SH001'), '制作中')

    def test_progress_reader_observes_atomic_republish(self):
        with tempfile.TemporaryDirectory() as td:
            self.addCleanup(clear)
            path = Path(td) / 'SH001_进度.json'
            save(path, {'shot_id': 'SH001', 'stage': 'render', 'completed': 1, 'total': 4})
            self.assertEqual(previs_monitor.progress_of({'log_dir': td}, 'SH001'), '渲染 1/4 帧（25%）')
            save(path, {'shot_id': 'SH001', 'stage': 'render', 'completed': 3, 'total': 4})
            self.assertEqual(previs_monitor.progress_of({'log_dir': td}, 'SH001'), '渲染 3/4 帧（75%）')


class RowTests(unittest.TestCase):
    """这一页那张表：只有本项目的镜头。"""

    def test_only_this_project_is_listed(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'p'
            state = {'status': {str(project) + '|SH001': '排队中',
                                str(Path(td) / '别的项目') + '|SH009': '排队中'}}
            self.assertEqual([row[0] for row in previs_monitor.rows(state, project)], ['SH001'])

    def test_a_finished_shot_has_no_percentage(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'p'; directory = Path(td) / 'log'; directory.mkdir()
            progress_file(directory, 'SH001', stage='render', completed=9, total=10)
            state = {'log_dir': str(directory), 'status': {str(project) + '|SH001': '已就绪'}}
            self.assertEqual(previs_monitor.rows(state, project), [('SH001', '已就绪', '—')])

    def test_failed_and_stopped_also_have_no_percentage(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'p'; directory = Path(td) / 'log'; directory.mkdir()
            progress_file(directory, 'SH001', stage='render', completed=9, total=10)
            state = {'log_dir': str(directory),
                     'status': {str(project) + '|SH001': '失败：输出未通过校验',
                                str(project) + '|SH002': '已强制停止'}}
            self.assertEqual([row[2] for row in previs_monitor.rows(state, project)], ['—', '—'])

    def test_a_running_shot_keeps_its_progress(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'p'; directory = Path(td) / 'log'; directory.mkdir()
            progress_file(directory, 'SH001', stage='render', completed=5, total=10)
            state = {'log_dir': str(directory), 'status': {str(project) + '|SH001': 'ChatGPT / Codex 制作中'}}
            self.assertEqual(previs_monitor.rows(state, project),
                             [('SH001', 'ChatGPT / Codex 制作中', '渲染 5/10 帧（50%）')])

    def test_the_order_is_the_shot_number(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'p'
            state = {'status': {str(project) + '|SH002': '排队中', str(project) + '|SH001': '排队中'}}
            self.assertEqual([row[0] for row in previs_monitor.rows(state, project)], ['SH001', 'SH002'])

    def test_an_empty_batch_is_an_empty_table(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(previs_monitor.rows({}, Path(td)), [])


class PageTests(unittest.TestCase):
    """REQ-S09-23：整页 HTML（自检直接读字符串），每 5 秒自己刷新。"""

    def test_the_page_carries_the_shot_numbers_and_the_closing_row(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'p'
            state = {'status': {str(project) + '|SH001': '已就绪'}, 'summary': '自动制作结束：1/1 就绪'}
            page = previs_monitor.render(state, project)
            self.assertIn('SH001', page)
            self.assertIn('已就绪', page)
            self.assertIn('—', page)
            self.assertIn('自动制作结束：1/1 就绪', page)
            self.assertIn('这一批已经收工', page)
            self.assertIn('白模预演 · 制作监视页', page)

    def test_a_running_batch_says_it_is_running(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'p'
            page = previs_monitor.render({'busy': True, 'status': {str(project) + '|SH001': '排队中'}}, project)
            self.assertIn('正在制作', page)

    def test_a_batch_without_shots_says_so(self):
        with tempfile.TemporaryDirectory() as td:
            page = previs_monitor.render({}, Path(td) / 'p')
            self.assertIn('这一批还没有镜头记录', page)

    def test_the_text_is_escaped(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'p'
            state = {'status': {str(project) + '|<script>': '排队中'}}
            page = previs_monitor.render(state, project)
            self.assertNotIn('<script>', page)
            self.assertIn('&lt;script&gt;', page)

    def test_a_failed_shot_is_painted_as_a_failure(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'p'
            page = previs_monitor.render({'status': {str(project) + '|SH001': '失败：输出未通过校验'}}, project)
            self.assertIn('class="bad"', page)

    def test_the_page_refreshes_itself(self):
        with tempfile.TemporaryDirectory() as td:
            page = previs_monitor.render({}, Path(td) / 'p')
            self.assertIn('http-equiv="refresh"', page)
            self.assertIn('每 %d 秒' % previs_monitor.REFRESH_SECONDS, page)


class MonitorServerTests(unittest.TestCase):
    """真起一个本地服务：能取到页、地址复用、停得干净。"""

    def setUp(self):
        self.state = {}
        self.opened = []
        self.addCleanup(previs_monitor.stop, self.state)

    def start(self, project):
        return previs_monitor.start(self.state, project, opener=self.opened.append)

    def test_the_page_is_served_from_127_0_0_1_and_the_address_is_reused(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'p'
            self.state['status'] = {str(project) + '|SH001': '排队中'}
            monitor = self.start(project)
            self.assertIsNotNone(monitor, '监视页该起得来')
            url = previs_monitor.url_of(self.state)
            self.assertTrue(url.startswith('http://127.0.0.1:'), url)
            self.assertEqual(self.opened, [url], '浏览器打开的就是这一页')
            body = urllib.request.urlopen(url, timeout=10).read().decode('utf-8')
            self.assertIn('SH001', body)
            self.assertIn('白模预演 · 制作监视页', body)
            self.assertIs(self.start(project), monitor, '连点两次沿用同一个地址')
            self.assertEqual(len(self.opened), 1, '连点两次不会开两扇窗')

    def test_stop_closes_the_port(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'p'
            previs_monitor.start(self.state, project, opener=lambda url: None)
            url = previs_monitor.url_of(self.state)
            self.assertTrue(url)
            self.assertEqual(previs_monitor.stop(self.state), url)
            self.assertEqual(previs_monitor.url_of(self.state), '')
            with self.assertRaises(Exception):
                urllib.request.urlopen(url, timeout=3).read()
            self.assertIsNone(previs_monitor.stop(self.state), '已经停了是空操作')

    def test_a_missing_state_is_not_a_crash(self):
        self.assertIsNone(previs_monitor.start(None, Path('.')))
        self.assertIsNone(previs_monitor.stop(None))
        self.assertEqual(previs_monitor.url_of(None), '')

    def test_only_get_is_answered(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'p'
            self.start(project)
            url = previs_monitor.url_of(self.state)
            request = urllib.request.Request(url, data=b'x', method='POST')
            with self.assertRaises(Exception):
                urllib.request.urlopen(request, timeout=10)


class Watched(dict):
    """把写进 summary 的每一句话都记下来：收尾时 summary 会被覆盖，只看最后一句就漏了。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.summaries = []

    def __setitem__(self, key, value):
        if key == 'summary':
            self.summaries.append(str(value))
        super().__setitem__(key, value)


def make_episode(td, ids=('SH001',)):
    project = Path(td) / 'p'; project.mkdir(parents=True)
    source = project / '分镜.json'
    source.write_text(json.dumps({'shots': [{'id': sid, 'duration': 5} for sid in ids]},
                                 ensure_ascii=False), encoding='utf-8')
    return project, source


class DispatchTests(unittest.TestCase):
    """REQ-S09-23：派发那一条线：手动派发开监视页；无人值守不弹浏览器。"""

    def setUp(self):
        import native_apps, previs_automation, previs_batch_service, previs_routing
        import white_model_service, workflow_engines, workflow_settings
        self.automation = previs_automation
        self.stub(previs_routing, 'partition',
                  lambda project, source, ids: ({'simple': [], 'medium': [], 'complex': list(ids)}, {}))
        self.stub(previs_routing, 'ready', lambda project, sid, source=None: False)
        self.stub(workflow_settings, 'current',
                  lambda project, stage: {'engine': 'codex', 'model': 'm', 'program': '', 'skill': ''})
        self.stub(workflow_settings, 'find_program', lambda config: 'codex.exe')
        self.stub(white_model_service, 'find_blender', lambda refresh=False: Path('D:/Blender/blender.exe'))
        # 白模工程目录别落到用户真机上的「白模项目」里去（shot_directory 从 workspace() 推）。
        self.space = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(self.space), True)
        self.stub(white_model_service, 'workspace', lambda: self.space)
        self.stub(previs_batch_service, 'prepare_batch', lambda project, snapshot, ids, call_config=None: '提示词')
        self.rendered = []
        self.stub(workflow_engines, 'run_background', lambda *a, **k: self.rendered.append(list(a)))
        self.verify_calls = []
        self.stub(self.automation, 'verify', self.verify)
        self.blender_windows = []
        self.stub(native_apps, 'open_blender', lambda *a, **k: self.blender_windows.append(a))

    def stub(self, module, name, value):
        original = getattr(module, name)
        setattr(module, name, value)
        self.addCleanup(setattr, module, name, original)

    def verify(self, project, sid, seconds, source=None):
        """第一次问是「这一镜已经就绪了吗」（没有），制作完再问就是「好了」。"""
        self.verify_calls.append(sid)
        return len(self.verify_calls) > 1

    def wait(self, state, deadline=30):
        end = time.time() + deadline
        while time.time() < end and state.get('busy'):
            time.sleep(0.05)
        return not state.get('busy')

    def test_a_manual_dispatch_opens_the_monitor_page(self):
        import previs_monitor as monitor
        calls = []
        def start(state, project, title=None, opener=None):
            calls.append(str(project))
            state['monitor'] = ('http://127.0.0.1:65535/', None)
            return state['monitor']
        self.stub(monitor, 'start', start)
        with tempfile.TemporaryDirectory() as td:
            project, source = make_episode(td)
            state = Watched(status={}, progress={})
            self.automation.start(project, source, ['SH001'], state, monitor=True)
            self.assertTrue(self.wait(state))
            self.assertEqual(calls, [str(project)])
            self.assertTrue(any('监视页' in text for text in state.summaries), state.summaries)
            self.assertTrue(any('65535' in text for text in state.summaries), state.summaries)

    def test_an_unattended_batch_does_not_open_the_browser(self):
        import previs_monitor as monitor
        calls = []
        self.stub(monitor, 'start', lambda *a, **k: calls.append(a))
        with tempfile.TemporaryDirectory() as td:
            project, source = make_episode(td)
            state = {'status': {}, 'progress': {}}
            self.automation.start(project, source, ['SH001'], state, monitor=False)
            self.assertTrue(self.wait(state))
            self.assertEqual(calls, [], '用户不在跟前时不弹浏览器')

    def test_the_batch_never_pops_a_desktop_blender(self):
        with tempfile.TemporaryDirectory() as td:
            project, source = make_episode(td)
            state = {'status': {}, 'progress': {}}
            self.automation.start(project, source, ['SH001'], state, monitor=False)
            self.assertTrue(self.wait(state), '这一批该跑完')
            self.assertEqual(self.blender_windows, [], '第 47 期第 2 条：不再弹桌面 Blender 窗口')
            self.assertEqual(state['status'][str(project) + '|SH001'], '已就绪')
            self.assertEqual(len(self.rendered), 1, '制作真的派出去了')


if __name__ == '__main__':
    unittest.main(verbosity=2)
