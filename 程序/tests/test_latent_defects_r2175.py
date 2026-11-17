"""R2175 全项目审查发现的潜伏缺陷：每条先复现，再验证修复。

1 读响应时超时／断线不经 URLError 包装，被当成程序缺陷（kind=bug）；
2 Qwen「测试连接」跟随重定向，把 API Key 转给跳转目标，且顶着 urllib 默认 User-Agent；
3 云朵确认派发遇实现内部的 TypeError，去掉 confirmed 又派发一遍；
4 分镜／首帧批次遇宿主内部的 TypeError，改按 manual 再派发一遍；
5 同批回收含重复路径或父子路径时，目录被套进自己的回收位置或整批撤回；
  写作页批量删除部分成功时，不刷新列表就报错。
"""
import io
import json
import socket
import tempfile
import threading
import unittest
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import urllib.request
import urllib.response

import infra.model_pool as model_pool
import infra.model_router as model_router
import storage_maintenance


def _read_request(conn):
    """读完整个请求（头＋Content-Length 正文）再动手：留着没读的数据，关连接会变成 RST。"""
    data = b''
    while b'\r\n\r\n' not in data:
        chunk = conn.recv(65536)
        if not chunk:
            return data
        data += chunk
    head, _, body = data.partition(b'\r\n\r\n')
    length = 0
    for line in head.split(b'\r\n')[1:]:
        name, _, value = line.partition(b':')
        if name.strip().lower() == b'content-length':
            length = int(value.strip() or b'0')
    while len(body) < length:
        chunk = conn.recv(65536)
        if not chunk:
            break
        body += chunk
    return data


class ResponseFailureKindTests(unittest.TestCase):
    """1 请求已发出、读响应时出的错同属网络问题；落到 kind=bug，创意聊天会说「系统内部错误」。"""

    def serve(self, behave):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(('127.0.0.1', 0))
        server.listen(1)
        release = threading.Event()

        def run():
            try:
                conn, _ = server.accept()
            except OSError:
                return
            with conn:
                _read_request(conn)
                behave(conn, release)

        thread = threading.Thread(target=run, daemon=True)
        self.addCleanup(server.close)
        self.addCleanup(thread.join, 5)
        self.addCleanup(release.set)          # 后登记的清理先执行：先放行，再 join
        thread.start()
        return 'http://127.0.0.1:%d/v1/chat/completions' % server.getsockname()[1]

    def send(self, url, timeout=0.5):
        # 系统代理不能把回环地址转走：只换掉代理表，其余仍是真实的 urllib 栈与真实套接字。
        with patch('urllib.request.getproxies', dict):
            return model_pool.http_transport(url, {'model': 'synthetic', 'messages': []},
                                             {'Authorization': 'Bearer SYNTHETIC'}, timeout)

    def test_a_read_timeout_is_a_network_failure(self):
        result = self.send(self.serve(lambda conn, release: release.wait(5)))
        self.assertFalse(result['ok'])
        self.assertEqual(result['kind'], 'network', result)
        self.assertEqual(model_router.error_class(result['error']), 'timeout', result)

    def test_a_dropped_connection_is_a_network_failure(self):
        result = self.send(self.serve(lambda conn, release: None))      # 读完请求就关，一个字节都不回
        self.assertFalse(result['ok'])
        self.assertEqual(result['kind'], 'network', result)

    def test_a_truncated_body_is_a_network_failure(self):
        def truncated(conn, release):
            conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n'
                         b'Content-Length: 100\r\n\r\n{"choices":')
        result = self.send(self.serve(truncated))
        self.assertFalse(result['ok'])
        self.assertEqual(result['kind'], 'network', result)

    def test_a_plain_program_error_is_still_a_bug(self):
        with patch.object(model_pool, '_http_opener', side_effect=RuntimeError('坏了')):
            result = self.send('http://127.0.0.1:9/v1/chat/completions')
        self.assertEqual(result['kind'], 'bug', result)


class QwenProbeTests(unittest.TestCase):
    """2 「测试连接」带着 API Key：跳转不能跟，请求也不能顶着 urllib 的默认签名。"""
    BASE = 'https://dashscope.invalid/compatible-mode/v1'

    def probe(self, status, location=None, body=b'{"data":[{"id":"qwen-x"}]}', model='qwen-x'):
        import qwen_setup
        seen = []

        def respond(handler, request):
            seen.append(request)
            headers = Message()
            first = len(seen) == 1
            if first and location:
                headers['Location'] = location
            response = urllib.response.addinfourl(io.BytesIO(body), headers, request.full_url,
                                                 status if first else 200)
            response.msg = 'Synthetic response'
            self.addCleanup(response.close)
            return response

        # 只换掉面向套接字的两个处理器，重定向走真实的 urllib 机制。
        with patch('urllib.request._opener', None), patch('urllib.request.getproxies', dict), \
                patch.object(urllib.request.HTTPHandler, 'http_open', respond), \
                patch.object(urllib.request.HTTPSHandler, 'https_open', respond):
            text = qwen_setup.probe({'base_url': self.BASE, 'api_key': 'SYNTHETIC-KEY', 'model': model})
        return text, seen

    def test_a_redirect_is_not_followed_with_the_key(self):
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status):
                text, seen = self.probe(status, 'https://collector.invalid/models')
                self.assertEqual([request.full_url for request in seen], [self.BASE + '/models'])
                self.assertEqual(text, '连接失败（HTTP %d），请检查网络、根地址和 API Key。' % status)

    def test_the_probe_carries_the_key_and_a_non_urllib_user_agent(self):
        text, seen = self.probe(200)
        self.assertEqual(text, 'API 已连接；模型在返回列表中。')
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].get_method(), 'GET')
        self.assertEqual(seen[0].get_header('Authorization'), 'Bearer SYNTHETIC-KEY')
        self.assertEqual(seen[0].get_header('User-agent'), model_pool.HTTP_USER_AGENT)

    def test_messages_for_other_answers_are_unchanged(self):
        self.assertEqual(self.probe(200, model='qwen-other')[0], 'API 已连接；请确认填写的模型已开通权限。')
        self.assertEqual(self.probe(401)[0], '连接失败（HTTP 401），请检查网络、根地址和 API Key。')
        self.assertEqual(self.probe(200, body=b'not json')[0], '连接失败，请检查网络、根地址和 API Key。')
        self.assertEqual(self.probe(200, body=b'[]')[0], '连接失败，请检查网络、根地址和 API Key。')


class DispatchOnceTests(unittest.TestCase):
    """3／4 先认签名再决定带不带关键字参数：实现内部抛 TypeError 时，同一件事只派发一次。"""

    def test_the_cloud_does_not_send_the_same_sentence_twice(self):
        from ui import pet_cloud
        calls = []

        def dispatch(text, at=None, confirmed=False):
            calls.append((text, confirmed))
            raise TypeError('编排器内部出错')

        cloud = SimpleNamespace(pet=SimpleNamespace(agent=SimpleNamespace(dispatch=dispatch)))
        with self.assertRaises(TypeError):
            pet_cloud.Cloud.dispatch(cloud, '执行选中')
        self.assertEqual(calls, [('执行选中', True)])

    def test_the_cloud_still_serves_an_older_dispatch(self):
        from ui import pet_cloud
        calls = []
        agent = SimpleNamespace(dispatch=lambda text: calls.append(text) or 'ok')
        self.assertEqual(pet_cloud.Cloud.dispatch(SimpleNamespace(pet=SimpleNamespace(agent=agent)), '查一下进度'), 'ok')
        self.assertEqual(calls, ['查一下进度'])

    def host(self, name, batch):
        return SimpleNamespace(desktop=SimpleNamespace(**{name: batch}), errors=[])

    def test_batches_are_not_redispatched_as_manual(self):
        import pet_ui_stages
        stages = pet_ui_stages.PetStagesMixin
        cases = (('pet_storyboard_batch', '分镜批次未派发', 'storyboard', stages.storyboard_batch),
                 ('pet_frame_batch', '首帧批次未派发', 'firstframe',
                  lambda host: stages.firstframe_batch(host, trigger='auto')))
        for name, notice, key, run in cases:
            with self.subTest(name=name):
                triggers = []

                def batch(trigger='manual'):
                    triggers.append(trigger)
                    raise TypeError('宿主内部出错')

                host = self.host(name, batch)
                self.assertIn(notice, run(host))
                self.assertEqual(triggers, ['auto'])
                self.assertEqual([item[0] for item in host.errors], [key])

    def test_batches_still_serve_a_host_without_the_trigger(self):
        import pet_ui_stages
        stages = pet_ui_stages.PetStagesMixin
        host = self.host('pet_storyboard_batch', lambda: '已经在准备分镜任务')
        self.assertEqual(stages.storyboard_batch(host), '已经在准备分镜任务')
        host = self.host('pet_frame_batch', lambda: '已按分镜顺序派发 1 镜首帧')
        self.assertEqual(stages.firstframe_batch(host, trigger='auto'), '已按分镜顺序派发 1 镜首帧')

    def test_the_signature_check(self):
        from pet_ui_support import accepts_keyword
        self.assertTrue(accepts_keyword(lambda text, confirmed=False: None, 'confirmed'))
        self.assertTrue(accepts_keyword(lambda text, *, confirmed: None, 'confirmed'))
        self.assertTrue(accepts_keyword(lambda text, **options: None, 'confirmed'))
        self.assertFalse(accepts_keyword(lambda text: None, 'confirmed'))
        self.assertFalse(accepts_keyword(lambda confirmed, /: None, 'confirmed'))


class RecycleBatchTests(unittest.TestCase):
    """5 同批回收：重复路径只算一次，目录已在批内时不再单列其中的文件。"""

    def project(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        root = Path(holder.name)
        folder = root / '剧本准备' / 'a'
        folder.mkdir(parents=True)
        (folder / 'x.txt').write_text('x', encoding='utf-8')
        (folder / 'y.txt').write_text('y', encoding='utf-8')
        return root, folder

    def test_a_folder_and_its_files_in_one_batch(self):
        for label in ('文件在前', '目录在前', '同一目录两次'):
            with self.subTest(label=label):
                root, folder = self.project()
                paths = {'文件在前': [folder / 'x.txt', folder], '目录在前': [folder, folder / 'x.txt'],
                         '同一目录两次': [folder, folder]}[label]
                records = storage_maintenance.recycle_paths(root, paths, '自检')
                self.assertEqual([record['source'] for record in records], ['剧本准备/a'])
                moved = root / records[0]['recycle_path']
                self.assertEqual(sorted(path.name for path in moved.iterdir()), ['x.txt', 'y.txt'])
                batch = moved.parents[1]
                manifest = json.loads((batch / storage_maintenance.MANIFEST_NAME).read_text(encoding='utf-8-sig'))
                self.assertEqual(manifest['state'], storage_maintenance.BATCH_COMMITTED)
                storage_maintenance.restore_recycle_batch(root, batch)
                self.assertEqual(sorted(path.name for path in folder.iterdir()), ['x.txt', 'y.txt'])

    def test_a_partial_batch_delete_refreshes_the_list_first(self):
        import desktop_files_panel
        root, folder = self.project()
        events = []
        page = SimpleNamespace(root=root, win=None,
                               status=SimpleNamespace(set=lambda text: events.append(('status', text))),
                               writing_page_services=SimpleNamespace(confirm=lambda *args, **kwargs: True))
        selection = SimpleNamespace(paths=(folder / 'x.txt', folder / '已不在.txt'), deletes_all=False)
        writing = SimpleNamespace(page=page, selected_scripts=lambda: selection,
                                  confirmed_note=lambda paths: '',
                                  fill_script_list=lambda: events.append('refresh'))
        with self.assertRaises(OSError):
            desktop_files_panel.ProjectFilesPanel.delete_script(writing)
        self.assertFalse((folder / 'x.txt').exists(), '还在的那份已进回收站')
        self.assertEqual(events, ['refresh'], '报错前先刷新列表，别再列着已进回收站的文件')


if __name__ == '__main__':
    unittest.main()
