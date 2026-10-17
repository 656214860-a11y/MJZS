from __future__ import annotations
import json
import unittest
from tests.architecture._layers import LAYERS, LAYER_NAMES, TOOLS
from tests.architecture._scan import ROOT, import_rows, module_name, production_files


LEDGER = ROOT / "维护记录" / "架构统一基数.json"


def _layer_ledger() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8"))["层级"]


def _upward_pairs() -> set[tuple[str, str, str]]:
    pairs = set()
    for path in production_files():
        importer = module_name(path)
        source_layer = LAYERS.get(importer)
        if source_layer is None:
            continue
        for _line, imported in import_rows(path):
            target_layer = LAYERS.get(imported)
            if target_layer is not None and source_layer < target_layer:
                pairs.add((path.name, importer, imported))
    return pairs

class LayerDirectionTests(unittest.TestCase):
    def test_idea_attachments_is_registered_as_l2_and_has_no_upward_dependency(self) -> None:
        """附件文本编排是领域服务，必须受分层扫描保护。"""
        source = "idea_attachments"
        self.assertEqual(LAYERS.get(source), 2)
        for path in production_files():
            if module_name(path) != source:
                continue
            for _line, target in import_rows(path):
                target_layer = LAYERS.get(target)
                self.assertFalse(
                    target_layer is not None and LAYERS[source] < target_layer,
                    f"{source} 不能依赖更高层模块 {target}",
                )

    def test_higher_layers_may_depend_only_on_same_or_lower_layers(self) -> None:
        exempt = {(item["file"], item["importer"], item["imported"])
                  for item in _layer_ledger()["items"]}
        violations = _upward_pairs() - exempt
        if violations:
            self.fail("发现未登记越层依赖：\n" + "\n".join(map(str, sorted(violations))))

    def test_every_top_level_runtime_module_is_registered_or_an_explicit_tool(self) -> None:
        missing = [module_name(path) for path in production_files()
                   if module_name(path) not in LAYERS and module_name(path) not in TOOLS]
        self.assertEqual(missing, [], f"顶层运行期模块不得绕过层级门禁：{missing}")

    def test_layer_exemptions_are_a_locatable_nonincreasing_baseline(self) -> None:
        record = _layer_ledger()
        items = record["items"]
        ledger_pairs = {(item["file"], item["importer"], item["imported"]) for item in items}
        self.assertEqual(len(items), len(ledger_pairs), "层级豁免不得重复登记")
        self.assertEqual(_upward_pairs(), ledger_pairs,
                         "台账项必须仍可在固定扫描范围中定位；新增越层必须显式登记")
        self.assertLessEqual(len(items), record["baseline_exempt"],
                             "既存越层豁免数不得高于本轮定稿基数")
        for item in items:
            self.assertEqual(item["disposition"], "exempt")
            self.assertEqual(item["reason"], "既存越层，待专项收口")

    def test_registered_names_resolve_to_a_file_tool_or_historical_entry(self) -> None:
        """登记表每一名须有实体文件、或声明为工具、或是已登记的历史名称（R1649）。"""
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        historical = set(ledger["historical_name_audit"]["entrypoints"])
        unresolved = sorted(
            name for name in LAYERS
            if not (ROOT / f"{name}.py").is_file()
            and not (ROOT / name / "__init__.py").is_file()
            and name not in TOOLS
            and name not in historical
        )
        self.assertEqual(unresolved, [],
                         "僵尸登记名（无实体文件、非工具、未登记历史）：" + ", ".join(unresolved))
