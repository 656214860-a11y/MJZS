from __future__ import annotations
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from tests.architecture import _layers, _scan
from tests.architecture._layers import LAYERS, LAYER_NAMES, TOOLS
from tests.architecture._scan import (ROOT, dynamic_import_rows, entity_file, import_rows, module_dynamic_import_rows,
                                      resolved_module_import_rows, module_name, module_scan_files, production_files)


LEDGER = ROOT / "维护记录" / "架构统一基数.json"


def _layer_ledger() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8"))["层级"]


def _dynamic_layer_ledger() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8"))["动态层级"]


def _module_classifications(paths: tuple[Path, ...]) -> dict[str, dict]:
    """扫描事实与登记事实分开；唯一旧键可绑定，歧义旧键绝不按目录猜层。"""
    stems: dict[str, list[str]] = {}
    for path in paths:
        if path.name != "__init__.py":
            stems.setdefault(path.stem, []).append(module_name(path, qualified=True))
    rows = {}
    for path in paths:
        name = module_name(path, qualified=True)
        key = name
        status = "unregistered"
        if name in LAYERS:
            status = "registered"
        elif path.name != "__init__.py" and path.stem in LAYERS:
            key = path.stem
            status = "legacy-unique" if len(stems[key]) == 1 else "ambiguous"
        elif name in TOOLS:
            status = "tool"
        layer = LAYERS.get(key) if status in ("registered", "legacy-unique") else None
        if status in ("registered", "legacy-unique") and (
                type(layer) not in (int, float) or layer not in LAYER_NAMES):
            status = "invalid-layer"
        rows[name] = {"file": path.relative_to(_scan.ROOT).as_posix(), "status": status,
                      "registration": key if status != "unregistered" else None, "layer": layer}
    return rows


def _qualified_upward_pairs() -> set[tuple[str, str, str]]:
    """严格影子入口；任何未分类源/本地目标都失败，不能被当作无越层。"""
    paths = module_scan_files(qualified=True)
    rows = _module_classifications(paths)
    rejected = {name: row["status"] for name, row in rows.items()
                if row["status"] not in ("registered", "legacy-unique", "tool")}
    if rejected:
        raise AssertionError(f"Unclassified local modules: {dict(sorted(rejected.items()))}")
    pairs = set()
    for path in paths:
        importer = module_name(path, qualified=True)
        source_layer = rows[importer]["layer"]
        if source_layer is None:  # 仅已有 TOOLS 显式分类；不代表其生产边界已验收。
            continue
        for line, imported in resolved_module_import_rows(path, qualified=True):
            if imported in rows:
                target_layer = rows[imported]["layer"]
            elif imported in LAYERS:
                # 扫描集中去掉的薄门面仍有精确顶层登记，不把它猜作同 stem 包实体。
                target_layer = LAYERS[imported]
                if type(target_layer) not in (int, float) or target_layer not in LAYER_NAMES:
                    raise AssertionError(f"Invalid target layer: {imported}")
            elif imported in TOOLS:
                continue
            else:
                local = _scan.ROOT.joinpath(*imported.split("."))
                if local.with_suffix(".py").is_file() or (local / "__init__.py").is_file():
                    raise AssertionError(f"Unclassified local import: {importer}:{line} -> {imported}")
                continue  # 外部依赖由既有白名单守卫负责。
            if target_layer is not None and source_layer < target_layer:
                pairs.add((path.relative_to(_scan.ROOT).as_posix(), importer, imported))
    return pairs


def _upward_pairs(*, qualified: bool = False) -> set[tuple[str, str, str]]:
    if qualified:
        return _qualified_upward_pairs()
    pairs = set()
    for path in module_scan_files():
        importer = module_name(path)
        source_layer = LAYERS.get(importer)
        if source_layer is None:
            continue
        for _line, imported in resolved_module_import_rows(path):
            target_layer = LAYERS.get(imported)
            if target_layer is not None and source_layer < target_layer:
                pairs.add((path.name, importer, imported))
    return pairs

# R1777 审计：常量字符串的 import_module／__import__ 绕开了上面的静态越层扫描。
# 存量动态越层豁免已并入 维护记录/架构统一基数.json 的「动态层级」段（K2 单源化），
# 只许减少、不许新增；消除一条就删台账行。


def _dynamic_upward_pairs() -> set[tuple[str, str, str]]:
    pairs = set()
    for path in module_scan_files():
        importer = module_name(path)
        source_layer = LAYERS.get(importer)
        if source_layer is None:
            continue
        for _line, imported in module_dynamic_import_rows(path):
            target_layer = LAYERS.get(imported)
            if target_layer is not None and source_layer < target_layer:
                pairs.add((path.name, importer, imported))
    return pairs


class AuthoritativeIdentityTests(unittest.TestCase):
    """A9-4a 只登记有职责/消费者依据的精确身份，不扩展旧 stem 绑定。"""

    selected = {"contract": 0, "infra": 1, "orchestrator": 3,
                "ui": 4, "ui.ui_part_renderers": 4}

    def test_selected_identities_have_exact_authoritative_layers(self) -> None:
        rows = _module_classifications(module_scan_files(qualified=True))
        for name, layer in self.selected.items():
            with self.subTest(name=name):
                self.assertEqual((rows[name]["status"], rows[name]["registration"],
                                  rows[name]["layer"]), ("registered", name, layer))

    def test_removing_exact_entries_restores_only_selected_refusals(self) -> None:
        paths = module_scan_files(qualified=True)
        after = _module_classifications(paths)
        legacy = {name: layer for name, layer in LAYERS.items() if name not in self.selected}
        with patch.dict(LAYERS, legacy, clear=True):
            before = _module_classifications(paths)
            with self.assertRaisesRegex(AssertionError, "Unclassified local modules"):
                _upward_pairs(qualified=True)
        changed = {name for name in before if before[name] != after[name]}
        self.assertEqual(changed, set(self.selected))
        for name in self.selected:
            self.assertEqual(before[name]["status"], "unregistered")
        remaining = {name: row["status"] for name, row in after.items()
                     if row["status"] not in ("registered", "legacy-unique", "tool")}
        if remaining:
            with self.assertRaises(AssertionError) as refusal:
                _upward_pairs(qualified=True)
            self.assertEqual(str(refusal.exception),
                             f"Unclassified local modules: {dict(sorted(remaining.items()))}")

    def test_exact_entries_preserve_legacy_dependency_semantics(self) -> None:
        current = (_upward_pairs(), _dynamic_upward_pairs())
        legacy = {name: layer for name, layer in LAYERS.items() if name not in self.selected}
        with patch.dict(LAYERS, legacy, clear=True):
            self.assertEqual(current, (_upward_pairs(), _dynamic_upward_pairs()))


class FacadeIdentityTests(unittest.TestCase):
    """A9-4f：精确包实体与兼容门面并存，不把同 stem 当作同一身份。"""

    selected = {"infra.file_index": 1, "contract.file_index_contract": 0,
                "contract.file_naming": 0, "domain.global_library_service": 1,
                "orchestrator.legacy_migration": 3, "infra.storage_maintenance": 1}

    def test_entities_and_compatibility_facades_keep_separate_exact_layers(self) -> None:
        rows = _module_classifications(module_scan_files(qualified=True))
        for entity, layer in self.selected.items():
            facade = entity.rsplit(".", 1)[-1]
            with self.subTest(entity=entity):
                for name in (entity, facade):
                    self.assertEqual((rows[name]["status"], rows[name]["registration"],
                                      rows[name]["layer"]), ("registered", name, layer))
                self.assertNotEqual(rows[entity]["file"], rows[facade]["file"])
        self.assertNotEqual(LAYERS.get("domain.global_library_service"), LAYERS["domain"])

    def test_removing_exact_entries_restores_only_six_ambiguous_entities(self) -> None:
        paths = module_scan_files(qualified=True)
        after = _module_classifications(paths)
        legacy = {name: layer for name, layer in LAYERS.items() if name not in self.selected}
        guard = LayerDirectionTests("test_higher_layers_may_depend_only_on_same_or_lower_layers")
        with patch.dict(LAYERS, legacy, clear=True):
            before = _module_classifications(paths)
            with self.assertRaisesRegex(AssertionError, "Unclassified local modules") as refusal:
                guard.test_higher_layers_may_depend_only_on_same_or_lower_layers(qualified=True)
            for name in self.selected:
                self.assertEqual(before[name]["status"], "ambiguous")
                self.assertIn(repr(name) + ": 'ambiguous'", str(refusal.exception))
        self.assertEqual({name for name in before if before[name] != after[name]},
                         set(self.selected))
        remaining = {name: row["status"] for name, row in after.items()
                     if row["status"] not in ("registered", "legacy-unique", "tool")}
        if remaining:
            with self.assertRaises(AssertionError) as refusal:
                guard.test_higher_layers_may_depend_only_on_same_or_lower_layers(qualified=True)
            self.assertEqual(str(refusal.exception),
                             f"Unclassified local modules: {dict(sorted(remaining.items()))}")

    def test_exact_entries_preserve_default_static_and_dynamic_dependencies(self) -> None:
        current = (_upward_pairs(), _dynamic_upward_pairs())
        legacy = {name: layer for name, layer in LAYERS.items() if name not in self.selected}
        with patch.dict(LAYERS, legacy, clear=True):
            self.assertEqual(current, (_upward_pairs(), _dynamic_upward_pairs()))
        LayerDirectionTests().test_higher_layers_may_depend_only_on_same_or_lower_layers()

    def test_reexports_and_storage_alias_cli_preserve_compatibility(self) -> None:
        import importlib
        import runpy
        import sys

        for name in self.selected:
            entity = importlib.import_module(name)
            facade = importlib.import_module(name.rsplit(".", 1)[-1])
            with self.subTest(entity=name):
                if name == "infra.storage_maintenance":
                    self.assertIs(facade, entity)
                else:
                    self.assertTrue(facade.__all__)
                    for symbol in facade.__all__:
                        self.assertIs(getattr(facade, symbol), getattr(entity, symbol))
        entity = importlib.import_module("infra.storage_maintenance")
        for args, calls in (([], 0), (["--cleanup"], 1)):
            with self.subTest(args=args), patch.object(entity, "main") as main:
                with patch.object(sys, "argv", ["storage_maintenance.py", *args]):
                    runpy.run_path(str(ROOT / "storage_maintenance.py"), run_name="__main__")
                self.assertEqual(main.call_count, calls)
        with patch("storage_maintenance.recycle_paths") as recycle:
            self.assertIs(entity.recycle_paths, recycle)



class PackageImportCanaryTests(unittest.TestCase):
    """临时包中的坏依赖必须触发真实越层守卫，不执行包代码。"""

    def setUp(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for package in ("contract", "contract/nested", "ui"):
            directory = self.root / package
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "__init__.py").write_text("TOKEN = 1\n", encoding="utf-8")
        for relative in ("contract/high.py", "ui/high.py", "contract/low.py"):
            (self.root / relative).write_text("raise RuntimeError('must not import')\n", encoding="utf-8")
        self.enterContext(patch.object(_scan, "ROOT", self.root))
        self.enterContext(patch(__name__ + ".LAYERS", {"client": 0, "high": 4, "low": 0}))
        self.enterContext(patch(__name__ + "._layer_ledger", return_value={"items": []}))

    def _source(self, relative: str, source: str) -> Path:
        path = self.root / relative
        path.write_text(source, encoding="utf-8")
        return path

    def test_package_submodule_imports_trip_the_actual_layer_guard(self) -> None:
        cases = (
            ("contract/client.py", "from ui import high as view\n"),
            ("contract/client.py", "from . import high\n"),
            ("contract/client.py", "from .high import Marker\n"),
            ("contract/nested/client.py", "from .. import high\n"),
            ("contract/nested/client.py", "from ..high import Marker\n"),
            ("contract/client.py", "def load():\n    from ui import high\n"),
            ("contract/client.py", "try:\n    from ui import high\nexcept ImportError:\n    pass\n"),
        )
        guard = LayerDirectionTests("test_higher_layers_may_depend_only_on_same_or_lower_layers")
        for relative, source in cases:
            with self.subTest(relative=relative, source=source):
                path = self._source(relative, source)
                with patch(__name__ + ".module_scan_files", return_value=(path,)):
                    with self.assertRaisesRegex(AssertionError, "client.*high"):
                        guard.test_higher_layers_may_depend_only_on_same_or_lower_layers()
                    self.assertEqual(_upward_pairs(), {("client.py", "client", "high")})

    def test_same_layer_and_downward_package_imports_remain_allowed(self) -> None:
        guard = LayerDirectionTests("test_higher_layers_may_depend_only_on_same_or_lower_layers")
        for source_layer in (0, 4):
            for source in ("from contract import low", "from . import low", "from .low import Marker"):
                with self.subTest(layer=source_layer, source=source):
                    path = self._source("contract/client.py", source)
                    with patch(__name__ + ".LAYERS", {"client": source_layer, "low": 0}), patch(
                            __name__ + ".module_scan_files", return_value=(path,)):
                        guard.test_higher_layers_may_depend_only_on_same_or_lower_layers()
                        self.assertIn("low", {name for _, name in _scan.resolved_module_import_rows(path)})

    def test_symbols_are_not_invented_modules_and_line_numbers_survive(self) -> None:
        path = self._source("contract/client.py", "from contract import TOKEN\nfrom ui import high as view\nfrom .high import Marker\n")
        rows = list(_scan.resolved_module_import_rows(path))
        self.assertIn((2, "high"), rows)
        self.assertIn((3, "high"), rows)
        self.assertFalse({"TOKEN", "Marker", "view"}.intersection(name for _, name in rows))


class LayerRegistrationCanaryTests(unittest.TestCase):
    """登记失败必须保留旧图，不能把未知层或覆盖当成合格依赖。"""

    def setUp(self) -> None:
        self.enterContext(patch.object(_layers, "LAYERS", {}))
        self.enterContext(patch(__name__ + ".LAYERS", _layers.LAYERS))

    def test_unknown_layers_reject_the_whole_registration(self) -> None:
        _layers._register(4, "ui.shared")
        before = dict(_layers.LAYERS)
        for layer in (None, -1, 0.25, 6, float("nan"), True, "0"):
            with self.subTest(layer=layer):
                with self.assertRaisesRegex(ValueError, "Unknown architecture layer"):
                    _layers._register(layer, "contract.shared", "contract.__init__")
                self.assertEqual(_layers.LAYERS, before)

    def test_conflicting_exact_identities_reject_without_partial_writes(self) -> None:
        for name in ("shared", "ui.shared", "contract.__init__"):
            with self.subTest(name=name):
                _layers.LAYERS.clear()
                _layers._register(4, name)
                before = dict(_layers.LAYERS)
                with self.assertRaisesRegex(ValueError, "Conflicting architecture layer"):
                    _layers._register(0, "new_module", name)
                self.assertEqual(_layers.LAYERS, before)

    def test_distinct_names_and_idempotent_known_layers_remain_valid(self) -> None:
        expected = {"contract.shared": 0, "ui.shared": 4,
                    "contract": 0, "contract.__init__": 0, "ui.__init__": 4}
        for name, layer in expected.items():
            _layers._register(layer, name, name)
            _layers._register(layer, name)
        for layer in _layers.LAYER_NAMES:
            name = f"known_{layer}"
            _layers._register(layer, name)
            expected[name] = layer
        self.assertEqual(_layers.LAYERS, expected)

    def test_invalid_registration_cannot_erase_actual_upward_dependency(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "client.py"
            source.write_text("import high\n", encoding="utf-8")
            _layers._register(0, "client")
            _layers._register(4, "high")
            guard = LayerDirectionTests("test_higher_layers_may_depend_only_on_same_or_lower_layers")
            with patch.object(_scan, "ROOT", root), patch(
                    __name__ + ".module_scan_files", return_value=(source,)), patch(
                    __name__ + "._layer_ledger", return_value={"items": []}):
                for layer, name in ((None, "client"), (None, "high"), (0, "high")):
                    with self.subTest(layer=layer, name=name):
                        with self.assertRaises(ValueError):
                            _layers._register(layer, name)
                        self.assertEqual(_upward_pairs(), {("client.py", "client", "high")})
                        with self.assertRaisesRegex(AssertionError, "client.*high"):
                            guard.test_higher_layers_may_depend_only_on_same_or_lower_layers()


class PackageIdentityCanaryTests(unittest.TestCase):
    """严格模式调用原分层消费者；扫描源码中的 raise 绝不能被执行。"""

    def setUp(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for package in ("contract", "ui"):
            self._write(f"{package}/__init__.py", "TOKEN = 1\n")
        self.enterContext(patch.object(_scan, "ROOT", self.root))
        self.layers = {"contract": 0, "ui": 0}
        self.enterContext(patch(__name__ + ".LAYERS", self.layers))
        self.enterContext(patch(__name__ + ".TOOLS", {}))
        self.enterContext(patch(__name__ + "._layer_ledger", return_value={"items": []}))
        self.guard = LayerDirectionTests("test_higher_layers_may_depend_only_on_same_or_lower_layers")

    def _write(self, relative: str, text: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_cross_package_same_stem_uses_exact_layers_in_actual_guard(self) -> None:
        self.layers.update({"contract.shared": 0, "ui.shared": 4})
        low = self._write("contract/shared.py", "from ui import shared as view\n")
        self._write("ui/shared.py", "raise RuntimeError('must not execute')\n")
        with self.assertRaisesRegex(AssertionError, "contract.shared.*ui.shared"):
            self.guard.test_higher_layers_may_depend_only_on_same_or_lower_layers(qualified=True)
        self.assertEqual(_upward_pairs(qualified=True),
                         {("contract/shared.py", "contract.shared", "ui.shared")})
        low.write_text("from contract import TOKEN\n", encoding="utf-8")
        self._write("ui/shared.py", "from contract import shared\n")
        self.guard.test_higher_layers_may_depend_only_on_same_or_lower_layers(qualified=True)

    def test_initializer_and_relative_nested_imports_trip_actual_guard(self) -> None:
        self.layers.update({"ui.high": 4, "contract.nested": 0, "contract.nested.client": 0})
        self._write("ui/high.py", "raise RuntimeError('must not execute')\n")
        initializer = self._write("contract/__init__.py", "from ui import high\n")
        self._write("contract/nested/__init__.py", "")
        nested = self._write("contract/nested/client.py", "")
        self.assertIn(initializer, module_scan_files(qualified=True))
        self.assertEqual(module_name(initializer, qualified=True), "contract")
        with self.assertRaisesRegex(AssertionError, "contract.*ui.high"):
            self.guard.test_higher_layers_may_depend_only_on_same_or_lower_layers(qualified=True)
        initializer.write_text("", encoding="utf-8")
        self.layers["contract.high"] = 4
        self._write("contract/high.py", "")
        for source in ("from .. import high", "from ..high import Marker",
                       "def load():\n    from .. import high",
                       "try:\n    from .. import high\nexcept ImportError:\n    pass"):
            with self.subTest(source=source):
                nested.write_text(source + "\n", encoding="utf-8")
                with self.assertRaisesRegex(AssertionError, "contract.nested.client.*contract.high"):
                    self.guard.test_higher_layers_may_depend_only_on_same_or_lower_layers(qualified=True)

    def test_scanned_unknown_module_and_initializer_are_rejected(self) -> None:
        self._write("ui/unregistered.py", "import json\n")
        with self.assertRaisesRegex(AssertionError, "ui.unregistered.*unregistered"):
            self.guard.test_higher_layers_may_depend_only_on_same_or_lower_layers(qualified=True)
        self.layers["ui.unregistered"] = 4
        self.guard.test_higher_layers_may_depend_only_on_same_or_lower_layers(qualified=True)
        del self.layers["ui"]
        with self.assertRaisesRegex(AssertionError, "'ui': 'unregistered'"):
            self.guard.test_higher_layers_may_depend_only_on_same_or_lower_layers(qualified=True)

    def test_ambiguous_legacy_key_is_rejected_instead_of_guessed(self) -> None:
        self._write("shared.py", "")
        self._write("contract/shared.py", "")
        self.layers["shared"] = 0
        with self.assertRaisesRegex(AssertionError, "contract.shared.*ambiguous"):
            self.guard.test_higher_layers_may_depend_only_on_same_or_lower_layers(qualified=True)
        self.layers["contract.shared"] = 0
        self.guard.test_higher_layers_may_depend_only_on_same_or_lower_layers(qualified=True)

    def test_unscanned_local_target_cannot_masquerade_as_external(self) -> None:
        self.layers["contract.client"] = 0
        self._write("contract/client.py", "import extra.hidden\n")
        self._write("extra/__init__.py", "")
        self._write("extra/hidden.py", "")
        with self.assertRaisesRegex(AssertionError, "Unclassified local import.*extra"):
            self.guard.test_higher_layers_may_depend_only_on_same_or_lower_layers(qualified=True)

    def test_direct_dotted_import_checks_parent_initialization_dependency(self) -> None:
        self.layers.update({"contract.client": 0, "ui": 4, "ui.low": 0})
        path = self._write("contract/client.py", "import ui.low as view\n")
        self._write("ui/low.py", "")
        self.assertEqual(list(resolved_module_import_rows(path, qualified=True)),
                         [(1, "ui"), (1, "ui.low")])
        with self.assertRaisesRegex(AssertionError, "contract.client.*ui"):
            self.guard.test_higher_layers_may_depend_only_on_same_or_lower_layers(qualified=True)

    def test_unique_legacy_registration_and_external_symbols_remain_valid(self) -> None:
        self.layers["client"] = 0
        path = self._write("contract/client.py", "import json.decoder\nfrom contract import TOKEN\n")
        rows = _module_classifications(module_scan_files(qualified=True))
        self.assertEqual(rows["contract.client"]["status"], "legacy-unique")
        self.guard.test_higher_layers_may_depend_only_on_same_or_lower_layers(qualified=True)
        self.assertNotIn("TOKEN", {name for _, name in resolved_module_import_rows(path, qualified=True)})
        self.layers["client"] = None
        with self.assertRaisesRegex(AssertionError, "contract.client.*invalid-layer"):
            self.guard.test_higher_layers_may_depend_only_on_same_or_lower_layers(qualified=True)


class LayerDirectionTests(unittest.TestCase):
    def test_dynamic_imports_do_not_add_upward_dependencies(self) -> None:
        record = _dynamic_layer_ledger()
        items = record["items"]
        ledger_pairs = {(item["file"], item["importer"], item["imported"]) for item in items}
        self.assertEqual(len(items), len(ledger_pairs), "动态层级豁免不得重复登记")
        found = _dynamic_upward_pairs() - _upward_pairs()  # 静态口径已登记的不重复算
        self.assertEqual(found, ledger_pairs,
                         "动态越层台账必须与实测一致：新增请改依赖方向，消除请删台账行")
        self.assertLessEqual(len(items), record["baseline_exempt"],
                             "既存动态越层豁免数不得高于本轮定稿基数")
        for item in items:
            self.assertEqual(item["disposition"], "exempt")
            self.assertEqual(item["reason"], "既存动态越层，待专项收口")

    def test_idea_attachments_is_registered_as_l2_and_has_no_upward_dependency(self) -> None:
        """附件文本编排是领域服务，必须受分层扫描保护。"""
        source = "idea_attachments"
        self.assertEqual(LAYERS.get(source), 2)
        for path in module_scan_files():
            if module_name(path) != source:
                continue
            for _line, target in resolved_module_import_rows(path):
                target_layer = LAYERS.get(target)
                self.assertFalse(
                    target_layer is not None and LAYERS[source] < target_layer,
                    f"{source} 不能依赖更高层模块 {target}",
                )

    def test_higher_layers_may_depend_only_on_same_or_lower_layers(self, *, qualified: bool = False) -> None:
        exempt = {(item["file"], item["importer"], item["imported"])
                  for item in _layer_ledger()["items"]}
        violations = _upward_pairs(qualified=qualified) - exempt
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
            if not entity_file(name).is_file()
            and not ROOT.joinpath(*name.split(".")).with_suffix(".py").is_file()
            and not (ROOT / name / "__init__.py").is_file()
            and name not in TOOLS
            and name not in historical
        )
        self.assertEqual(unresolved, [],
                         "僵尸登记名（无实体文件、非工具、未登记历史）：" + ", ".join(unresolved))
