# -*- coding: utf-8 -*-
"""第 63 期 BUG 回归：本地 ComfyUI 批量制图（native_assets.run）的批次记录目录。

用户报的原话是弹窗「制图未完成：name folder is not defined」——点「手动制作资产」还没提交就断。
原因：生成图第 48 期统一挪进 `生成资产` 时，批次记录目录那一半没跟着改，`folder` 只被用、没被定义。
这里用一个假的 ComfyUI 把整条路跑通，盯住三件事：

1. 批次记录落在 `workflows/Comfy资产批次`（用户盘上的老记录就在那儿，断点续跑指着它）；
2. 上次没跑完的批次能接着跑，不新开批次、不重复提交；
3. ComfyUI 中途退出（连不上）时给一句人话，而不是 WinError 原文。

运行：python test_native_run.py
"""
import io, json, os, sys, tempfile, threading, unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError, URLError

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import native_assets
from asset_context import generated_dir
from infra.pet_state import PAGE_OF

PNG_1PX = __import__('base64').b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')


def make_project(td):
    """够 run() 跑起来的最小项目：资产库一份资产清单，还没有已导入的图片。"""
    proj = Path(td) / 'p'
    base = proj / 'episode'
    (base / 'assets' / '资产清单').mkdir(parents=True)
    asset = {'name': '主角', 'description': '短发少年', 'image_prompt': '正面全身',
             'negative_prompt': '', 'positive_prompt': '正面全身', 'prompt': '正面全身',
             'reference_images': [], 'reference_roles': {}}
    (base / 'assets' / '资产清单' / 'assets.json').write_text(
        json.dumps({'CHAR_001': asset}, ensure_ascii=False), encoding='utf-8')
    return proj, base, asset


class FakeComfy:
    """只认 run() 用到的那几条接口的最小替身：健康检查、开批次、派发、取进度、取图。"""

    calls = []

    def __init__(self, url):
        self.url = url

    def request(self, path, data=None, raw=False, timeout=20):
        FakeComfy.calls.append(path)
        if path == '/drama/assets/health':
            return {'direct_submit': True, 'options': {'model': native_assets.LOCAL}}
        if path == '/drama/assets/start':
            return {'id': 'JOB1', 'state': 'pending'}
        if path == '/drama/assets/dispatch':
            return {'state': 'running', 'error': ''}
        if path == '/prompt':
            return {'prompt_id': 'P1'}
        if path == '/drama/assets/ack':
            return {'state': 'queued'}
        if path.startswith('/drama/assets/job/'):
            return {'state': 'completed', 'files': [{'id': 'CHAR_001', 'filename': 'x.png',
                                                     'subfolder': '', 'type': 'output'}]}
        if path.startswith('/view?'):
            return PNG_1PX
        raise AssertionError('没预料到的接口：' + path)


class FakeDownComfy(FakeComfy):
    """ComfyUI 已经退出的样子：连不上。"""

    def request(self, path, data=None, raw=False, timeout=20):
        FakeComfy.calls.append(path)
        raise URLError('[WinError 10061] 由于目标计算机积极拒绝，无法连接。')


class LegacyComfy(FakeComfy):
    """老节点：health 里没有 direct_submit，助手只能走 /drama/assets/dispatch。"""

    def request(self, path, data=None, raw=False, timeout=20):
        if path == '/drama/assets/health':
            FakeComfy.calls.append(path)
            return {'options': {'model': native_assets.LOCAL}}
        return FakeComfy.request(self, path, data, raw, timeout)


class BrokenDispatchComfy(LegacyComfy):
    """用户机上的样子：任务其实已经排进了 ComfyUI 队列，但 /dispatch 回一个英文的 500。"""

    def request(self, path, data=None, raw=False, timeout=20):
        if path == '/drama/assets/dispatch':
            FakeComfy.calls.append(path)
            error = HTTPError(path, 500, 'Internal Server Error', {}, io.BytesIO(b''))
            error.close()
            raise error
        return LegacyComfy.request(self, path, data, raw, timeout)


class BrokenAckComfy(FakeComfy):
    """任务已进入 ComfyUI，但节点认领回执暂时失败。"""

    def request(self, path, data=None, raw=False, timeout=20):
        if path == '/drama/assets/ack':
            FakeComfy.calls.append(path)
            raise URLError('节点认领接口暂不可用')
        return FakeComfy.request(self, path, data, raw, timeout)


class FakeUploader:
    """参考图上传：run() 只关心拿回一个文件名。"""

    def __init__(self, url):
        self.url = url

    def upload(self, path):
        return Path(path).name


class RunTests(unittest.TestCase):
    """整条本地制图链路：记录目录、断点续跑、连不上时的人话。"""

    def setUp(self):
        from batch_frames_tool import batch_frames
        import native_apps
        FakeComfy.calls = []
        self.addCleanup(setattr, native_assets, 'Comfy', native_assets.Comfy)
        self.addCleanup(setattr, batch_frames, 'Client', batch_frames.Client)
        self.addCleanup(setattr, native_apps, 'wait_comfy', native_apps.wait_comfy)
        native_assets.Comfy = FakeComfy
        batch_frames.Client = FakeUploader
        native_apps.wait_comfy = lambda url, report=None, timeout=90, cancelled=None: None
        self.options = {'model': native_assets.LOCAL, 'aspect_ratio': '1:1'}

    def records(self, proj):
        return sorted((proj / 'workflows' / 'Comfy资产批次').glob('*.json'))

    def test_a_fresh_batch_writes_its_record_where_the_app_says_it_does(self):
        with tempfile.TemporaryDirectory() as td:
            proj, base, asset = make_project(td)
            message = native_assets.run(proj, base, [('CHAR_001', asset)],
                                        'http://127.0.0.1:8189', lambda text: None,
                                        options=self.options, stop=threading.Event())
            self.assertIn('已自动导入 1/1', message)
            files = self.records(proj)
            self.assertEqual(len(files), 1, '一个批次一份记录，落在「制作记录」那颗按钮打开的地方')
            record = json.loads(files[0].read_text(encoding='utf-8'))
            self.assertEqual(record['state'], 'completed')
            self.assertEqual(record['imported'], ['CHAR_001'])
            self.assertTrue((base / 'assets.json').is_file(), '图片进了资产库')
            self.assertTrue(list(generated_dir(base).glob('*.png')), '生成图统一进生成资产目录')

    def test_an_unfinished_batch_is_resumed_not_resubmitted(self):
        from asset_reference_images import snapshot
        with tempfile.TemporaryDirectory() as td:
            proj, base, asset = make_project(td)
            folder = proj / 'workflows' / 'Comfy资产批次'
            folder.mkdir(parents=True)
            saved = {'id': 'JOBX', 'state': 'pending', 'signature': '老签名',
                     'assets': {'CHAR_001': snapshot(base, asset)}, 'imported': [],
                     'request': {'request_id': 'JOBX', 'project': str(proj), 'items': [],
                                 'delivery': 'direct', 'options': self.options}}
            (folder / 'JOBX.json').write_text(json.dumps(saved, ensure_ascii=False), encoding='utf-8')
            message = native_assets.run(proj, base, [('CHAR_001', asset)],
                                        'http://127.0.0.1:8189', lambda text: None,
                                        options=self.options, stop=threading.Event())
            self.assertIn('已自动导入 1/1', message)
            self.assertEqual(len(self.records(proj)), 1, '接着上次那一条跑，不新开批次')
            self.assertIn('/drama/assets/job/JOBX', FakeComfy.calls, '认的是上次那个任务号')
            self.assertNotIn('/drama/assets/start', FakeComfy.calls, '不重新提交')

    def test_the_assistant_submits_the_prompt_itself(self):
        """节点声明 direct_submit 时，批次由助手自己 POST /prompt 排进队列，并把任务号认领给节点。"""
        with tempfile.TemporaryDirectory() as td:
            proj, base, asset = make_project(td)
            message = native_assets.run(proj, base, [('CHAR_001', asset)],
                                        'http://127.0.0.1:8189', lambda text: None,
                                        options=self.options, stop=threading.Event())
            self.assertIn('已自动导入 1/1', message)
            self.assertIn('/prompt', FakeComfy.calls, '助手自己把批次排进 ComfyUI 队列')
            self.assertIn('/drama/assets/ack', FakeComfy.calls, '排上队后把任务号告诉节点，进度才跟得上')
            self.assertNotIn('/drama/assets/dispatch', FakeComfy.calls, '不再碰那个会抛 500 的老接口')

    def test_a_broken_dispatch_no_longer_aborts_the_batch(self):
        """老节点：/dispatch 回 500（任务其实已排队）。不许整批中断，也不许把英文栈甩给用户。"""
        with tempfile.TemporaryDirectory() as td:
            proj, base, asset = make_project(td)
            native_assets.Comfy = BrokenDispatchComfy
            reports = []
            message = native_assets.run(proj, base, [('CHAR_001', asset)],
                                        'http://127.0.0.1:8189', reports.append,
                                        options=self.options, stop=threading.Event())
            self.assertIn('已自动导入 1/1', message)
            self.assertNotIn('HTTP Error', message)
            self.assertTrue(any('可能已排队' in text and '不会重复提交' in text for text in reports))

    def test_a_failed_ack_is_visible_without_resubmitting_the_prompt(self):
        """/prompt 已排队后回执失败，必须说明会以输出目录对账，且不再发第二次 prompt。"""
        with tempfile.TemporaryDirectory() as td:
            proj, base, asset = make_project(td)
            native_assets.Comfy = BrokenAckComfy
            reports = []
            message = native_assets.run(proj, base, [('CHAR_001', asset)],
                                        'http://127.0.0.1:8189', reports.append,
                                        options=self.options, stop=threading.Event())
            self.assertIn('已自动导入 1/1', message)
            self.assertTrue(any('进度认领未确认' in text and '不会重复提交' in text for text in reports))
            self.assertEqual(FakeComfy.calls.count('/prompt'), 1, '认领失败不许重复提交已排队的任务')
            record = json.loads(self.records(proj)[0].read_text(encoding='utf-8'))
            self.assertIn('进度认领未确认', record['ack_warning'])

    def test_a_dead_comfyui_says_what_to_do(self):
        with tempfile.TemporaryDirectory() as td:
            proj, base, asset = make_project(td)
            native_assets.Comfy = FakeDownComfy
            with self.assertRaises(ValueError) as caught:
                native_assets.run(proj, base, [('CHAR_001', asset)],
                                  'http://127.0.0.1:8189', lambda text: None,
                                  options=self.options, stop=threading.Event())
            text = str(caught.exception)
            self.assertIn('本地 ComfyUI 没在运行', text)
            self.assertIn('不会重复提交', text)
            self.assertEqual(self.records(proj), [], '连不上就不该留下半截批次')


class _Host:
    """制图结束回调用到的主窗口那几样：当前项目、当前页、状态栏、翻页。"""

    def __init__(self, root, page_index):
        self.root = root
        self.page_index = page_index
        self.worker = None
        self.settings = {}
        self.status = mock.Mock()
        self.shown = []
        self.finishers = []

    def show(self, index):
        self.shown.append(index)

    def launch_comfy(self, silent=False):
        return True

    def async_(self, work, done=None, **kw):
        self.finishers.append(done)


class FinishedStaysOnPageTests(unittest.TestCase):
    """REQ-S05-24：制图结束不把人从别的页拉回资产管理页（UX-B6B）。

    不开窗口：拿替身当制图窗的控件组，走到 start() 把结束回调交给后台任务那一步，再直接调这个回调。
    """

    RESULT = '已自动导入 1/1'

    def _finish(self, page_index, *, project='项目甲', root='项目甲', window_open=False):
        controls = mock.MagicMock()
        controls.app = _Host(root, page_index)
        controls.project = project
        controls.context_matches.return_value = True
        controls.selection.return_value = [('CHAR_001', {})]
        controls.model.get.return_value = native_assets.LOCAL
        controls.win.winfo_exists.return_value = window_open
        controls.events.empty.return_value = True
        native_assets._AssetControls.start(controls)
        self.assertEqual(len(controls.app.finishers), 1, 'start() 应把结束回调交给后台任务一次')
        with mock.patch('domain.asset_batch_service.batch_complete', return_value=True):
            controls.app.finishers[0](self.RESULT)
        return controls

    def test_finished_redraws_assets_page_when_user_is_on_it(self):
        controls = self._finish(PAGE_OF['assets'])
        self.assertEqual(controls.app.shown, [PAGE_OF['assets']])
        controls.app.status.set.assert_called_with(self.RESULT)

    def test_finished_leaves_other_pages_alone(self):
        controls = self._finish(PAGE_OF['storyboard'])
        self.assertEqual(controls.app.shown, [], '人在别的页时不许翻回资产管理页')
        controls.app.status.set.assert_called_with(self.RESULT)

    def test_finished_on_another_page_still_reports_in_the_drawing_window(self):
        controls = self._finish(PAGE_OF['storyboard'], window_open=True)
        self.assertEqual(controls.app.shown, [], '制图窗还开着也不许翻回资产管理页')
        controls.progress_text.set.assert_called_with(self.RESULT)
        controls.notify.assert_called_once()
        self.assertEqual(controls.notify.call_args.kwargs.get('title'), '制作完成')
        controls.win.destroy.assert_called_once_with()

    def test_finished_after_project_switch_does_not_redraw(self):
        controls = self._finish(PAGE_OF['assets'], root='项目乙')
        self.assertEqual(controls.app.shown, [])
        controls.app.status.set.assert_called_with(self.RESULT)


if __name__ == '__main__':
    unittest.main(verbosity=2)
