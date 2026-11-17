# -*- coding: utf-8 -*-
"""L2 领域服务层优化任务书轮 4（功能轮）：domain_events 旁路事件实现与三事件接入。

覆盖 ``domain.domain_events`` 的 bind／emit 契约（未绑定安全 no-op、总线异常与
契约校验失败一律吞掉不抛）、``pet_bus.CONTRACT`` 三个新事件登记，以及
``keyframe.replaced``／``video.generated``／``paid.invoked`` 三个接入点的真实
触发路径；并用「绑定总线 vs 未绑定」同输入对照证明旁路事件不改变状态结果
（L2-D10：事件只做旁路提示，不作为状态唯一来源）。
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import contract.pet_bus as pet_bus
from agent.core import read, save
from domain import domain_events, recon_service
from tests.image_fixtures import png


class RecordingBus:
    """录制型总线替身：emit 走真实 ``pet_bus.event`` 契约校验，事件才算数。"""

    def __init__(self):
        self.events = []

    def emit(self, kind, **payload):
        item = pet_bus.event(kind, **payload)
        self.events.append(item)
        return item


class ExplodingBus:
    """emit 必抛异常的总线替身：模拟总线侧任何意外。"""

    def emit(self, kind, **payload):
        raise RuntimeError('bus exploded')


class FailingContractBus:
    """emit 内部契约校验失败的总线替身（等价 pet_bus.event 拒绝）。"""

    def emit(self, kind, **payload):
        raise ValueError('未登记的事件：' + str(kind))


def kinds(bus):
    return [item['kind'] for item in bus.events]


class DomainEventsEmitTests(unittest.TestCase):
    """emit 薄封装契约：未绑定 no-op；绑定后经 emit_safe；任何异常返回 None 不抛。"""

    def setUp(self):
        domain_events.bind(None)

    def tearDown(self):
        domain_events.bind(None)

    def test_unbound_emit_is_safe_noop(self):
        self.assertIsNone(domain_events.emit(domain_events.KEYFRAME_REPLACED,
                                             stage='keyframe', shot='SH001', nonce='n'))
        self.assertIsNone(domain_events.emit(domain_events.PAID_INVOKED,
                                             stage='script', op='search', nonce='n'))

    def test_bound_emit_returns_event_and_reaches_bus(self):
        bus = RecordingBus()
        errors = []
        domain_events.bind(bus, errors)
        item = domain_events.emit(domain_events.KEYFRAME_REPLACED,
                                  stage='keyframe', shot='SH001', nonce='n1')
        self.assertIsInstance(item, dict)
        self.assertEqual(item['kind'], 'keyframe.replaced')
        self.assertEqual(kinds(bus), ['keyframe.replaced'])
        got = bus.events[0]
        self.assertEqual((got['stage'], got['shot'], got['nonce']),
                         ('keyframe', 'SH001', 'n1'))
        self.assertFalse(errors)

    def test_emit_swallows_bus_explosion(self):
        domain_events.bind(ExplodingBus(), [])
        self.assertIsNone(domain_events.emit(domain_events.VIDEO_GENERATED,
                                             stage='video', shot='SH001', nonce='n'))

    def test_emit_swallows_contract_violation(self):
        errors = []
        domain_events.bind(RecordingBus(), errors)
        # 缺必填字段 shot／nonce → pet_bus.event 拒绝 → emit_safe 记一笔返回 None。
        self.assertIsNone(domain_events.emit(domain_events.KEYFRAME_REPLACED,
                                             stage='keyframe'))
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0][0], 'keyframe.replaced')

    def test_emit_swallows_contract_bus_error(self):
        domain_events.bind(FailingContractBus(), [])
        self.assertIsNone(domain_events.emit(domain_events.PAID_INVOKED,
                                             stage='script', op='search', nonce='n'))


class ContractRegistrationTests(unittest.TestCase):
    """CONTRACT 登记本身：三个 kind 可构造事件，缺字段与未登记 kind 仍被拒。"""

    def test_three_kinds_registered(self):
        for kind, fields in (
                ('keyframe.replaced', {'stage': 'keyframe', 'shot': 'SH001', 'nonce': 'a'}),
                ('video.generated', {'stage': 'video', 'shot': 'SH001', 'nonce': 'b'}),
                ('paid.invoked', {'stage': 'script', 'op': 'search', 'nonce': 'c'})):
            item = pet_bus.event(kind, **fields)
            self.assertEqual(item['kind'], kind)
            self.assertTrue(item['id'])

    def test_missing_required_field_still_rejected(self):
        with self.assertRaises(ValueError):
            pet_bus.event('keyframe.replaced', stage='keyframe', shot='SH001')
        with self.assertRaises(ValueError):
            pet_bus.event('paid.invoked', stage='script', op='search')

    def test_unregistered_kind_still_rejected(self):
        with self.assertRaises(ValueError):
            pet_bus.event('no.such.event', stage='script', nonce='x')


class KeyframeReplacedEventTests(unittest.TestCase):
    """``replace_keyframe`` 成功路径发 ``keyframe.replaced``；总线爆炸不影响主流程。"""

    def setUp(self):
        domain_events.bind(None)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(domain_events.bind, None)
        self.base = Path(self.tmp.name)
        (self.base / 'frames').mkdir()
        self.source = self.base / 'episode.json'
        self.episode = {'shots': [{'id': 'SH001'}]}
        save(self.source, self.episode)

    def _replace(self):
        from stage_execution_service import replace_stage_keyframe
        return replace_stage_keyframe(
            self.base, self.source, self.episode, self.episode['shots'][0], png())

    def test_replace_emits_keyframe_replaced(self):
        bus = RecordingBus()
        domain_events.bind(bus, [])
        result = self._replace()
        self.assertTrue(result.ok)
        self.assertEqual(kinds(bus), ['keyframe.replaced'])
        item = bus.events[0]
        self.assertEqual(item['stage'], 'keyframe')
        self.assertEqual(item['shot'], 'SH001')
        self.assertTrue(item['nonce'])
        # 旁路事件不改变状态真源：镜头状态仍以 episode.json 落盘内容为准。
        self.assertEqual(read(self.source)['shots'][0]['frame'], 'frames/SH001.png')

    def test_replace_with_exploding_bus_still_succeeds(self):
        domain_events.bind(ExplodingBus(), [])
        result = self._replace()
        self.assertTrue(result.ok)
        self.assertTrue((self.base / 'frames' / 'SH001.png').is_file())
        self.assertEqual(self.episode['shots'][0]['frame'], 'frames/SH001.png')


class VideoGeneratedEventTests(unittest.TestCase):
    """``Studio.publish_downloaded_video`` 落盘发布成功发 ``video.generated``。"""

    def setUp(self):
        domain_events.bind(None)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(domain_events.bind, None)
        self.root = Path(self.tmp.name)
        self.folder = self.root / 'data' / 'SH001' / 'v001'
        self.folder.mkdir(parents=True)
        self.dest = self.folder / 'SH001.mp4'
        self.dest.write_bytes(b'complete-video')
        self.db = self.root / 'data' / 'state.json'
        self.state = {'shots': {'SH001': [{'version': 1, 'state': 'succeeded'}]}}
        self.version = self.state['shots']['SH001'][0]

    def _fake_studio(self):
        root, db, folder = self.root, self.db, self.folder

        class FakeStudio:
            def __init__(self):
                self.root, self.db = root, db

            def task_folder(self, sid, version):
                return folder

            def record_video_usage(self, sid, version):
                pass

            def publish_manifest(self, state=None):
                pass
        return FakeStudio()

    def _publish(self):
        import engine
        return engine.Studio.publish_downloaded_video(
            self._fake_studio(), self.state, 'SH001', self.version, self.dest,
            {'errors': []})

    def test_publish_emits_video_generated(self):
        bus = RecordingBus()
        domain_events.bind(bus, [])
        version = self._publish()
        self.assertEqual(version['state'], 'downloaded')
        self.assertEqual(kinds(bus), ['video.generated'])
        item = bus.events[0]
        self.assertEqual(item['stage'], 'video')
        self.assertEqual(item['shot'], 'SH001')
        self.assertTrue(item['nonce'])

    def test_publish_with_exploding_bus_still_succeeds(self):
        domain_events.bind(ExplodingBus(), [])
        version = self._publish()
        self.assertEqual(version['state'], 'downloaded')
        self.assertTrue(self.db.is_file())


class PaidInvokedEventTests(unittest.TestCase):
    """``recon_service`` 每个实际发起的付费调用发一条 ``paid.invoked``。"""

    def setUp(self):
        domain_events.bind(None)
        self.addCleanup(domain_events.bind, None)

    def _collect(self):
        calls = []

        def send(kind, value, count=5):
            calls.append((kind, value))
            if kind == 'search':
                return {'ok': True, 'status': 200, 'data': {},
                        'results': [{'title': 't', 'url': 'https://a.example/1',
                                     'rerank_score': 2.4},
                                    {'title': 't', 'url': 'https://b.example/2',
                                     'rerank_score': 2.4}]}
            return {'ok': True, 'status': 200, 'data': {'title': 'x'},
                    'title': 'x', 'content': '正文'}

        ports = recon_service.ReconPorts(sender=send, pause=lambda _s: None)
        card = recon_service.collect({'name': '某剧', 'question': '怎么成的'},
                                     '对标爆款', ports=ports)
        return card, calls

    @staticmethod
    def _normalize(card):
        """剔除墙钟时间字段：同一输入两次 collect 的结果应逐字段一致。"""
        card = dict(card)
        card.pop('collected_at', None)
        budget = dict(card.get('budget') or {})
        budget['seconds'] = 0
        card['budget'] = budget
        return card

    def test_collect_emits_paid_invoked_per_operation(self):
        bus = RecordingBus()
        domain_events.bind(bus, [])
        card, calls = self._collect()
        self.assertEqual(card['kind'], 'recon_card')
        # 每个实际发起的付费调用一条：4 条检索词 search ＋ 2 个来源 fetch；
        # _attempt 内部重试不重复计（本用例发送器一次成功，无重试）。
        self.assertEqual(len(calls), 6)
        paid = [item for item in bus.events if item['kind'] == 'paid.invoked']
        self.assertEqual(len(paid), 6)
        self.assertEqual([item['op'] for item in paid],
                         ['search'] * 4 + ['fetch'] * 2)
        for item in paid:
            self.assertEqual(item['stage'], 'script')
            self.assertTrue(item['nonce'])
        # nonce 让每次发生都是独立幂等键：同 op 的多次发起互不合并。
        self.assertEqual(len({item['nonce'] for item in paid}), 6)

    def test_collect_with_exploding_bus_returns_card(self):
        domain_events.bind(ExplodingBus(), [])
        card, calls = self._collect()
        self.assertEqual(card['kind'], 'recon_card')
        self.assertEqual(len(card['sources']), 2)
        self.assertEqual(len(calls), 6)

    def test_events_do_not_change_collect_result(self):
        """L2-D10：绑定总线发出事件后，collect 结果与未绑定逐字段一致。"""
        unbound_card, _ = self._collect()
        bus = RecordingBus()
        domain_events.bind(bus, [])
        bound_card, _ = self._collect()
        self.assertTrue(bus.events)
        self.assertEqual(self._normalize(bound_card), self._normalize(unbound_card))


if __name__ == '__main__':
    unittest.main()
