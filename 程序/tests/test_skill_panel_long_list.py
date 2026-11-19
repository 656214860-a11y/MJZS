"""Long-list layout must be one bounded pass, not cumulative rebuilds."""
import types
import unittest

from ui import skill_panel


class _Widget:
    def __init__(self):
        self.grid_calls = 0

    def grid_forget(self):
        pass

    def grid(self, **_kwargs):
        self.grid_calls += 1


class _NoIndexList(list):
    def index(self, *_args, **_kwargs):
        raise AssertionError('长列表布局不得逐项反查 index')


class SkillPanelLongListTests(unittest.TestCase):
    def test_adding_1000_controls_defers_layout_until_batch_is_complete(self):
        panel = types.SimpleNamespace(
            skill_controls=[], skill_canvas=object(), skill_action_row=None,
            schedule_calls=0)
        panel.schedule_skill_layout = lambda: setattr(
            panel, 'schedule_calls', panel.schedule_calls + 1)
        for _ in range(1000):
            skill_panel.Panel.add_skill_control(panel, _Widget())
        self.assertEqual(panel.schedule_calls, 0)
        self.assertEqual(len(panel.skill_controls), 1000)

    def test_layout_1000_controls_is_a_single_linear_pass(self):
        widgets = _NoIndexList(_Widget() for _ in range(1000))
        row = types.SimpleNamespace(grid_columnconfigure=lambda *_args, **_kwargs: None)
        panel = types.SimpleNamespace(
            _skill_layout_job='pending', flow_skill_row=row,
            skill_canvas=object(), skill_controls=widgets)
        skill_panel.Panel.layout_skill_controls(panel)
        self.assertIsNone(panel._skill_layout_job)
        self.assertTrue(all(widget.grid_calls == 1 for widget in widgets))


if __name__ == '__main__':
    unittest.main()
