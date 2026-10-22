"""Pet.click 重构前后等价：旧实现（elif 链）原样留作基准，用桩对象记录调用顺序与参数逐一对比（R1785）。
不起 Tk：Pet.click 是普通函数，桩对象提供它要用的方法即可。"""
import unittest

import pet_agent
from pet_ui import Pet, SNOOZE_SECONDS


def legacy_click(self, intent, at=None):
    """重构前的 click（elif 链），仅作对照基准；不要改它。"""
    self.note_work(at=at)
    agent = self.agent
    if intent == 'pause':
        agent.pause('您在气泡里按了暂停')
        self.auto.pause()
        self.pause_running_stage()
        self.announce('已暂停自动执行：宠物只报告进度，不再自动推进', at=at)
    elif intent == 'resume':
        agent.resume()
        self.auto.resume()
        self.announce('已继续自动执行：按当前自动化等级推进，会花钱的步骤仍需您确认', at=at)
    elif intent == 'retry':
        self.retry_failures()
    elif intent == 'oneclick':
        return self.one_click(at=at)
    elif intent == 'level':
        order = list(pet_agent.LEVELS)
        self.set_paw_level(order[(order.index(agent.level) + 1) % len(order)], at=at)
    elif intent == 'chat':
        return self.open_chat()
    elif intent == 'skip':
        self.skip_failure()
    elif intent == 'model':
        self.switch_model()
    elif intent == 'snooze':
        self.snooze()
        self.notice = '好，安静 %d 分钟：这段时间只记账，出安静期再报一次' % (SNOOZE_SECONDS // 60)
    elif intent == 'details':
        self.show_details()
    self._emit('intent.command', text=str(intent), source='bubble')
    self.refresh(at=at)
    return intent


class _Recorder:
    def __init__(self, calls, prefix):
        self._calls, self._prefix = calls, prefix

    def __getattr__(self, name):
        def method(*args, **kwargs):
            self._calls.append((self._prefix + name, args, tuple(sorted(kwargs.items()))))
            return (self._prefix + name, 'ret')
        return method


class _Stub(_Recorder):
    def __init__(self, level):
        self.calls = []
        super().__init__(self.calls, '')
        self.notice = ''
        self.agent = _Recorder(self.calls, 'agent.')
        self.agent.level = level
        self.auto = _Recorder(self.calls, 'auto.')


def run(func, intent, level, at):
    stub = _Stub(level)
    result = func(stub, intent, at=at)
    return result, stub.calls, stub.notice


INTENTS = ('pause', 'resume', 'retry', 'oneclick', 'level', 'chat', 'skip', 'model', 'snooze',
           'details', 'unknown', '', None)


class PetClickEquivalenceTests(unittest.TestCase):
    def test_every_intent_matches_legacy(self):
        for intent in INTENTS:
            for level in pet_agent.LEVELS:
                for at in (None, 12.5):
                    with self.subTest(intent=intent, level=level, at=at):
                        self.assertEqual(run(Pet.click, intent, level, at),
                                         run(legacy_click, intent, level, at))

    def test_oneclick_and_chat_skip_the_intent_event(self):
        for intent in ('oneclick', 'chat'):
            _, calls, _ = run(Pet.click, intent, pet_agent.LEVELS[0], None)
            self.assertNotIn('_emit', [name for name, _args, _kw in calls])

    def test_other_intents_emit_then_refresh(self):
        _, calls, _ = run(Pet.click, 'retry', pet_agent.LEVELS[0], 3.0)
        self.assertEqual([name for name, _a, _k in calls][-2:], ['_emit', 'refresh'])


if __name__ == '__main__':
    unittest.main()
