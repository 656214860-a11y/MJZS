"""三虎的重试退避、参数修正与贴片动画开关：补既有用例没压到的边界（越界次数、自定义档位、比例打平、
坏输入、读写配置失败）。纯函数直接调；动画开关用最小宿主对象驱动 PetSettingsMixin，不起 Tk、不写盘。"""
import unittest
from types import SimpleNamespace
from unittest import mock

import pet_agent
import pet_ui_settings


class BackoffEdges(unittest.TestCase):
    def test_attempt_below_one_waits_the_first_step(self):
        for attempt in (0, -3, '1'):
            self.assertEqual(pet_agent.backoff(attempt), 30.0)

    def test_table_end_is_a_ceiling_not_a_doubling(self):
        self.assertEqual([pet_agent.backoff(n) for n in range(1, 7)], [30.0, 60.0, 120.0, 120.0, 120.0, 120.0])

    def test_custom_table_and_float_result(self):
        self.assertEqual(pet_agent.backoff(9, delays=(5,)), 5.0)
        self.assertIsInstance(pet_agent.backoff(1, delays=(2,)), float)


class RetryPlanEdges(unittest.TestCase):
    def test_custom_cap_hands_over_with_attempt_count(self):
        plan = pet_agent.retry_plan(1, '请求超时', max_attempts=1)
        self.assertFalse(plan['allow'])
        self.assertIsNone(plan['delay'])
        self.assertEqual(plan['next_attempt'], 1)
        self.assertIn('已重试 1 次', plan['hint'])

    def test_odd_attempt_values_are_normalised(self):
        self.assertEqual(pet_agent.retry_plan('2', '请求超时')['next_attempt'], 3)
        self.assertEqual(pet_agent.retry_plan(None, '请求超时')['next_attempt'], 1)
        self.assertEqual(pet_agent.retry_plan(-5, '请求超时')['attempt'], 0)

    def test_custom_delays_follow_the_same_ceiling(self):
        self.assertEqual(pet_agent.retry_plan(0, '请求超时', delays=(1, 2))['delay'], 1.0)
        self.assertEqual(pet_agent.retry_plan(5, '请求超时', max_attempts=10, delays=(1, 2))['delay'], 2.0)

    def test_param_error_no_longer_retries(self):
        """轮 5B 对照表：params → E-NET-CLIENT（retryable=False），不再立即重试。"""
        plan = pet_agent.retry_plan(2, '参数不合法', status=400, params={'duration': 99})
        self.assertFalse(plan['allow'])
        self.assertIsNone(plan['delay'])
        self.assertEqual(plan['next_attempt'], 2)
        self.assertEqual(plan['action'], 'fix_params')

    def test_param_error_without_params_still_stops(self):
        plan = pet_agent.retry_plan(0, '参数不合法', status=400)
        self.assertFalse(plan['allow'])
        self.assertNotIn('params', plan)

    def test_non_retryable_never_gets_a_delay(self):
        plan = pet_agent.retry_plan(0, '命中内容审核')
        self.assertFalse(plan['allow'])
        self.assertIsNone(plan['delay'])
        self.assertEqual(plan['next_attempt'], 0)


class SnapSizeEdges(unittest.TestCase):
    def test_same_ratio_ties_break_on_pixel_count(self):
        self.assertEqual(pet_agent.snap_size(1500, 1500), (1024, 1024))
        self.assertEqual(pet_agent.snap_size(1900, 1900), (2048, 2048))

    def test_extreme_portrait_keeps_portrait(self):
        self.assertEqual(pet_agent.snap_size(1000, 4000), (720, 1280))
        self.assertEqual(pet_agent.snap_size(4000, 1000), (1280, 720))

    def test_exact_legal_size_is_itself(self):
        for size in pet_agent.SIZES:
            self.assertEqual(pet_agent.snap_size(*size), size)

    def test_custom_sizes(self):
        # 比例按「宽/高」量：3/4 离 1 差 0.25，4/3 差 0.33
        self.assertEqual(pet_agent.snap_size(10, 10, sizes=((4, 3), (3, 4))), (3, 4))


class FixParamsEdges(unittest.TestCase):
    def test_legal_size_is_left_untouched(self):
        result = pet_agent.fix_params({'width': 1024, 'height': 768, 'size': '1024x768'})
        self.assertEqual(result, {'params': {'width': 1024, 'height': 768, 'size': '1024x768'}, 'fixed': []})

    def test_bad_sizes_are_left_alone(self):
        for params in ({'width': -5, 'height': 10}, {'size': 'abcxdef'}, {'size': '1024'}, {'width': 0, 'height': 0}):
            self.assertEqual(pet_agent.fix_params(params), {'params': params, 'fixed': []}, params)

    def test_size_string_is_replaced_by_width_height(self):
        result = pet_agent.fix_params({'size': '1000X4000'})
        self.assertEqual(result, {'params': {'width': 720, 'height': 1280}, 'fixed': ['尺寸']})

    def test_unreadable_duration_becomes_minimum(self):
        self.assertEqual(pet_agent.fix_params({'duration': 'abc'}), {'params': {'duration': 1}, 'fixed': ['时长']})
        self.assertEqual(pet_agent.fix_params({'length': 5}), {'params': {'length': 5}, 'fixed': []})

    def test_every_duration_key_is_clamped(self):
        result = pet_agent.fix_params({'duration': 0, 'seconds': 11, 'length': 3})
        self.assertEqual(result['params'], {'duration': 1, 'seconds': 10, 'length': 3})
        self.assertEqual(result['fixed'], ['时长', '时长'])

    def test_model_name_is_trimmed_case_folded_and_dropped_when_empty(self):
        self.assertEqual(pet_agent.fix_params({'model': '  DeepSeek '}),
                         {'params': {'model': 'deepseek-v4-flash'}, 'fixed': ['模型名']})
        self.assertEqual(pet_agent.fix_params({'model': None}), {'params': {}, 'fixed': ['模型名']})
        self.assertEqual(pet_agent.fix_params({'model': 'x'}, aliases={'x': 'y'})['params'], {'model': 'y'})

    def test_fixes_are_reported_in_a_fixed_order(self):
        result = pet_agent.fix_params({'model': 'wan', 'duration': 50, 'width': 3000, 'height': 900})
        self.assertEqual(result['fixed'], ['尺寸', '时长', '模型名'])
        self.assertEqual(result['params'], {'model': 'wan2.2', 'duration': 10, 'width': 1280, 'height': 720})


class _Host(pet_ui_settings.PetSettingsMixin):
    def __init__(self, settings):
        self.agent = SimpleNamespace(settings=settings)
        self.program = 'program-dir'
        self.errors = []
        self.notice = ''


class _Broken(dict):
    def get(self, *args):
        raise OSError('read failed')


class AnimationSwitchEdges(unittest.TestCase):
    def test_default_and_stored_values(self):
        self.assertTrue(_Host({}).animation_enabled())
        self.assertFalse(_Host({'anim': 0}).animation_enabled())
        self.assertTrue(_Host({'anim': 'yes'}).animation_enabled())

    def test_unreadable_settings_keep_animating_and_record_the_error(self):
        host = _Host(_Broken())
        self.assertTrue(host.animation_enabled())
        self.assertEqual(host.errors, [('settings.anim', 'read failed')])

    def test_set_anim_saves_applies_and_announces(self):
        host = _Host({})
        with mock.patch.object(pet_agent, 'save_settings') as save:
            self.assertFalse(host.set_anim(0))
        save.assert_called_once_with({'anim': False}, 'program-dir')
        self.assertEqual(host.agent.settings['anim'], False)
        self.assertEqual(host.notice, '贴片动画已关掉')
        self.assertEqual(host.errors, [])

    def test_save_failure_still_takes_effect_now(self):
        host = _Host({'anim': False})
        with mock.patch.object(pet_agent, 'save_settings', side_effect=OSError('disk full')):
            self.assertTrue(host.set_anim('on'))
        self.assertTrue(host.agent.settings['anim'])
        self.assertTrue(host.animation_enabled())
        self.assertEqual(host.notice, '贴片动画已打开')
        self.assertEqual(host.errors, [('settings.anim', 'disk full')])

    def test_unwritable_live_settings_are_recorded_not_raised(self):
        host = _Host(None)
        with mock.patch.object(pet_agent, 'save_settings'):
            self.assertTrue(host.set_anim(True))
        self.assertEqual([key for key, _ in host.errors], ['settings.anim'])
        self.assertEqual(host.notice, '贴片动画已打开')


if __name__ == '__main__':
    unittest.main()
