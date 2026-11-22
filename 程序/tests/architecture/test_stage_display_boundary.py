# -*- coding: utf-8 -*-
"""阶段名称展示必须服从 pet_bus 的单一权威表。"""
import ast
import re
import unittest
from pathlib import Path

import pet_bus
from tests.architecture._scan import entity_file, module_scan_files


ROOT = Path(__file__).resolve().parents[2]


def _stage_numbers():
    """权威显示名 → 两位步号（与 pet_bus.STAGES 顺序同源）。"""
    return {pet_bus.stage_name(stage): index for index, stage in enumerate(pet_bus.STAGES, start=1)}


def _stage_pattern(numbers):
    names = '|'.join(re.escape(name) for name in numbers)
    # 前面不能是字母数字（排除 L2／L3 这类层级前缀），紧随其后的是权威显示名。
    return re.compile(r'(?<![A-Za-z0-9_])(\d{1,2})\s*(%s)' % names)


def _page_number(node):
    """非 0 的整数字面量才算写死的阶段页码：0 是「回到第一页」的既有写法，布尔值不算。"""
    return isinstance(node, ast.Constant) and type(node.value) is int and node.value != 0


def _reads_page_index(node):
    """``x.page_index`` 或 ``getattr(x, 'page_index', …)``。"""
    if isinstance(node, ast.Attribute):
        return node.attr == 'page_index'
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'getattr'
            and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == 'page_index')


def _literal_page_use(node):
    """写死阶段页码的两种写法：``x.show(3)``／``x.go_page(3)``，以及拿 ``page_index`` 和数字比。"""
    if isinstance(node, ast.Call):
        return (isinstance(node.func, ast.Attribute) and node.func.attr in ('show', 'go_page')
                and bool(node.args) and _page_number(node.args[0]))
    if not isinstance(node, ast.Compare):
        return False
    sides = [node.left, *node.comparators]
    if not any(_reads_page_index(side) for side in sides):
        return False
    for side in sides:
        members = side.elts if isinstance(side, (ast.Tuple, ast.List, ast.Set)) else [side]
        if any(_page_number(member) for member in members):
            return True
    return False


class StageDisplayBoundaryTests(unittest.TestCase):

    # 展示位点：阶段名称与步号都必须由 pet_bus 权威表现算，不得退回写死。
    STAGE_LABEL_SITES = {
        'keyframe_batch.py': "pet_bus.stage_label('keyframe')",
        'stage_parallel.py': "pet_bus.stage_label('assets')",
        'pet_ui_voice.py': "pet_bus.stage_label('storyboard')",  # R1506：该播报已迁到 PetVoiceMixin
        'desktop_media_pages.py': "pet_bus.stage_label('video')",  # R1505：视频页构建已迁到 MediaPagesMixin
        'skill_tools.py': "stage_label('edit')",
        # 面板拆分后阶段展示的权威推导在 support 模块（stage_label() → _bus_stage_label）；
        # 组合文件 skill_panel.py 只做 mixin 装配，不再重复持有该绑定。
        'skill_panel_support.py': '_bus_stage_label',
    }

    def test_desktop_pages_are_generated_from_canonical_stage_table(self):
        source = entity_file('desktop_page_registry').read_text(encoding='utf-8')
        self.assertIn('for index, stage in enumerate(pet_bus.STAGES, start=1)', source)
        self.assertIn('pet_bus.stage_name(stage)', source)

        tree = ast.parse(source)
        pages_assignment = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == 'PAGES' for target in node.targets)
        )
        literals = [node.value for node in ast.walk(pages_assignment.value)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)]
        self.assertFalse(set(literals) & set(pet_bus.STAGE_NAMES.values()))
        self.assertIn('14  参考网站', literals)

    def test_stage_name_has_a_stable_unknown_stage_fallback(self):
        self.assertEqual(pet_bus.stage_name('script'), pet_bus.STAGE_NAMES['script'])
        self.assertEqual(pet_bus.stage_name('unknown'), 'unknown')
        self.assertEqual(pet_bus.stage_name('unknown', '当前阶段'), '当前阶段')

    def test_stage_label_matches_navigation_order(self):
        """pet_bus.stage_label 的步号必须与 STAGES 顺序一致，未知阶段原样退回。"""
        self.assertEqual(pet_bus.stage_label('script'), '01 剧本准备')
        self.assertEqual(pet_bus.stage_label('assets'), '05 资产管理')
        self.assertEqual(pet_bus.stage_label('delivery'), '13 质检与交付')
        self.assertEqual(pet_bus.stage_label('nope'), 'nope')

    def test_production_stage_numbers_match_authority(self):
        """生产文案里写死的「NN 阶段名」，编号必须等于 pet_bus.STAGES 的步号。"""
        legacy = {'stage_path_service.py'}  # R1124 前旧编号目录名，只读兼容，编号本就有意不同
        numbers = _stage_numbers()
        pattern = _stage_pattern(numbers)
        offenders = {}
        for path in module_scan_files():
            if path.name in legacy:
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                    continue
                for match in pattern.finditer(node.value):
                    want = numbers[match.group(2)]
                    if int(match.group(1)) != want:
                        offenders.setdefault(path.name, set()).add('%s（应为 %02d）' % (match.group(0), want))
        self.assertFalse(offenders, '阶段编号与 pet_bus.STAGES 不一致：' + repr({k: sorted(v) for k, v in sorted(offenders.items())}))

    def test_page_switches_do_not_hardcode_stage_page_numbers(self):
        """换页和页码比较不得写死阶段页的数字：阶段顺序一调，数字就指到别的页去了（UX-B6）。

        阶段页一律按阶段名取页码（``pet_state.PAGE_OF['assets']`` 这类）；``show(0)`` 不在此列。
        """
        offenders = []
        for path in module_scan_files():
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            offenders.extend('%s:%d' % (path.name, node.lineno) for node in ast.walk(tree) if _literal_page_use(node))
        self.assertEqual(sorted(offenders), [], '换页或页码比较写死了阶段页的数字，请改用 pet_state.PAGE_OF')

    def test_literal_page_use_recognises_each_form(self):
        """守卫自身的识别范围：该报的报，首页、按名取页码、不相干的比较不报。"""
        def hits(source):
            return [node for node in ast.walk(ast.parse(source)) if _literal_page_use(node)]
        for source in ('app.show(2)', 'self.go_page(4)', 'ok = self.page_index == 2',
                       "ok = getattr(app, 'page_index', None) != 3", 'ok = self.page_index in (2, 5)'):
            self.assertEqual(len(hits(source)), 1, source)
        for source in ('app.show(0)', "app.show(PAGE['assets'])", "ok = self.page_index == PAGE['assets']",
                       'ok = self.page_index == 0', 'ok = count == 2', 'app.show(True)', 'app.show()'):
            self.assertEqual(hits(source), [], source)

    def test_display_sites_derive_stage_labels_from_authority(self):
        """已迁移的展示位点必须继续由权威标签现算，不得退回写死。"""
        for name, token in sorted(self.STAGE_LABEL_SITES.items()):
            source = entity_file(Path(name).stem).read_text(encoding='utf-8')
            self.assertIn(token, source, '阶段展示必须由权威表现算：' + name)


if __name__ == '__main__':
    unittest.main()
