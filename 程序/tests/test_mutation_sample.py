# -*- coding: utf-8 -*-
"""mutation_sample 位点表防腐：每个变异位点必须在源文件里唯一命中。"""
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import mutation_sample


class SiteTableTests(unittest.TestCase):
    def test_every_site_matches_its_source_exactly_once(self):
        for module, _test, label, old, _new in mutation_sample.SITES:
            source = (mutation_sample.ROOT / (module.replace(".", "/") + ".py")).read_text(encoding="utf-8")
            self.assertEqual(source.count(old), 1, "位点失配：%s / %s" % (module, label))

    def test_apply_produces_the_mutant(self):
        module, _t, _l, old, new = mutation_sample.SITES[0]
        mutant = mutation_sample._apply(module, old, new)
        text = mutant.read_text(encoding="utf-8")
        self.assertIn(new, text)
        self.assertNotIn(old, text)


if __name__ == "__main__":
    unittest.main()
