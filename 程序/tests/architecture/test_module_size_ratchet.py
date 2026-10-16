"""单个生产模块行数上限：新模块 ≤ 1500 行；超限的老模块登记上限，只许下降。

超限文件只能随拆分变小。登记上限比实际高出 100 行以上时必须下调（让下降固化），
低于等于 1500 行的文件必须从登记表删除。新增功能应放进新模块或已拆出的 *_service /
*_controller，不要继续堆进下列大文件。
"""
import unittest

from tests.architecture._scan import ROOT, production_files

LIMIT = 1500
SLACK = 100
OVERSIZE_CAPS = {
    'desktop.py': 2300,
    'pet_cloud.py': 2150,
    'skill_panel.py': 1900,
    'stage_execution_service.py': 1700,
}


def _lines():
    return {p.name: len(p.read_text(encoding='utf-8', errors='replace').splitlines())
            for p in production_files()}


class ModuleSizeRatchet(unittest.TestCase):
    def test_no_module_exceeds_its_cap(self):
        over = [f'{name}: {n} 行 > 上限 {OVERSIZE_CAPS.get(name, LIMIT)}'
                for name, n in sorted(_lines().items()) if n > OVERSIZE_CAPS.get(name, LIMIT)]
        self.assertEqual(over, [], '请拆分或把新增代码放进新模块，不要抬高上限')

    def test_registry_tracks_real_sizes(self):
        sizes = _lines()
        stale = []
        for name, cap in OVERSIZE_CAPS.items():
            actual = sizes.get(name)
            if actual is None or actual <= LIMIT:
                stale.append(f'{name}: 已不超限或不存在，请从登记表删除')
            elif cap - actual > SLACK:
                stale.append(f'{name}: 实际 {actual} 行，登记 {cap}，请下调到 {actual + SLACK} 以内')
        self.assertEqual(stale, [])


if __name__ == '__main__':
    unittest.main()
