"""阶段步骤模板的结构契约测试。"""
import re
import unittest
from pathlib import Path

from pet_bus import STAGES


TEMPLATE_ROOT = Path(__file__).parent.parent / "skills" / "templates"


class StageTemplateTests(unittest.TestCase):
    def test_each_canonical_stage_has_a_valid_sequential_step_template(self):
        templates = sorted(TEMPLATE_ROOT.glob("*_process_template.yaml"))
        self.assertEqual(len(templates), len(STAGES))

        found_stages = []
        for template in templates:
            text = template.read_text(encoding="utf-8")
            stage = re.search(r'^stage_id: "([^"\n]+)"$', text, re.MULTILINE)
            self.assertIsNotNone(stage, template.name)
            found_stages.append(stage.group(1))
            self.assertRegex(text, re.compile(r'^process_id: "\d{2}_[^"]+"$', re.MULTILINE), template.name)
            indexes = [int(value) for value in re.findall(r"^  - index: (\d+)$", text, re.MULTILINE)]
            self.assertGreaterEqual(len(indexes), 4, template.name)
            self.assertEqual(indexes, list(range(1, len(indexes) + 1)), template.name)
            self.assertEqual(len(re.findall(r"^    action: \S+$", text, re.MULTILINE)), len(indexes), template.name)
            self.assertEqual(
                len(re.findall(r"^    needs_confirmation: (?:true|false)$", text, re.MULTILINE)),
                len(indexes),
                template.name,
            )

        self.assertEqual(set(found_stages), set(STAGES))
