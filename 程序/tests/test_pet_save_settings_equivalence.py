"""pet_agent.save_settings 重构前后等价：旧实现（elif 链）原样留作基准，边界输入逐一对比（R1785）。"""
import json
import tempfile
import unittest
from pathlib import Path

import pet_agent
from pet_agent import SETTING_KEYS, _int, normalize_kind


def legacy_merge(data, values):
    """重构前 save_settings 里的合并循环，仅作对照基准；不要改它。"""
    data = dict(data) if isinstance(data, dict) else {}
    for key, value in dict(values or {}).items():
        if key not in SETTING_KEYS or value is None:
            continue
        if key == 'dnd':
            window = tuple(value) if isinstance(value, (list, tuple)) else ()
            if len(window) != 2:
                continue
            data[key] = [int(window[0]), int(window[1])]
        elif key == 'retry_delays':
            if isinstance(value, (list, tuple)) and value:
                data[key] = [int(item) for item in value]
        elif key == 'budget_limits':
            limits = {}
            for kind, amount in dict(value or {}).items():
                try:
                    name = normalize_kind(kind)
                except ValueError:
                    continue
                number = _int(amount)
                if number and number > 0:
                    limits[name] = number
            data[key] = limits
        elif key == 'anim':
            data[key] = bool(value)
        elif key == 'max_attempts':
            number = _int(value)
            if number and number > 0:
                data[key] = number
        else:
            data[key] = value
    return data


EXISTING = {'level': 'semi', 'model_pool': {'keep': 'me'}, 'dnd': [1, 2], 'anim': True}
CASES = {
    'empty': {},
    'none': None,
    'unknown-key-ignored': {'model_pool': 'x', 'secret_name': 'y'},
    'none-value-skipped': {'level': None, 'dnd': None},
    'level': {'level': 'auto'},
    'dnd-list': {'dnd': [22, 7]},
    'dnd-tuple-str-ints': {'dnd': ('23', '6')},
    'dnd-wrong-length': {'dnd': [1, 2, 3]},
    'dnd-not-sequence': {'dnd': 5},
    'retry-ok': {'retry_delays': [1, '2', 3.0]},
    'retry-empty': {'retry_delays': []},
    'retry-not-list': {'retry_delays': 'abc'},
    'budget-mixed': {'budget_limits': {'image': 3, 'tokens': '500000', 'bogus': 9, 'video': 0, 'tts': -1}},
    'budget-empty': {'budget_limits': {}},
    'anim-false': {'anim': False},
    'anim-truthy': {'anim': 'yes'},
    'attempts-ok': {'max_attempts': '4'},
    'attempts-zero': {'max_attempts': 0},
    'attempts-garbage': {'max_attempts': 'x'},
    'token-table': {'token': {'a': 1, 'b': [2]}},
    'many-at-once': {'level': 'hint', 'dnd': [0, 8], 'anim': 0, 'max_attempts': 2, 'token': {'k': 1}},
}
RAISES = {
    'dnd-non-int': {'dnd': ['a', 'b']},
    'retry-non-int': {'retry_delays': ['x']},
    'budget-not-mapping': {'budget_limits': 5},
}


class SaveSettingsEquivalenceTests(unittest.TestCase):
    def run_new(self, existing, values):
        with tempfile.TemporaryDirectory() as td:
            path = pet_agent.config_file(td)
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            if existing is not None:
                Path(path).write_text(json.dumps(existing, ensure_ascii=False), encoding='utf-8')
            pet_agent.save_settings(values, program=td)
            return json.loads(Path(path).read_text(encoding='utf-8'))

    def test_new_matches_legacy_on_edge_inputs(self):
        for existing in (None, {}, EXISTING):
            for name, values in CASES.items():
                with self.subTest(existing=bool(existing), case=name):
                    self.assertEqual(self.run_new(existing, values), legacy_merge(existing, values))

    def test_same_exceptions_as_legacy(self):
        for name, values in RAISES.items():
            with self.subTest(case=name):
                with self.assertRaises((ValueError, TypeError)):
                    legacy_merge(EXISTING, values)
                with self.assertRaises((ValueError, TypeError)):
                    self.run_new(EXISTING, values)

    def test_broken_disk_value_is_replaced(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(pet_agent.config_file(td))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('[1, 2', encoding='utf-8')
            pet_agent.save_settings({'level': 'auto'}, program=td)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'level': 'auto'})


if __name__ == '__main__':
    unittest.main()
