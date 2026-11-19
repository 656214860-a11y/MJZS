"""动态注册入口与工具运行边界的实际消费者门禁。"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from tests.architecture import _scan

import infra.ui_plugin_registry as ui_plugin_registry
from scripts.distribution_build import candidate_files, plan
from tests.architecture._layers import LAYERS, TOOLS
from tests.architecture._scan import ROOT, module_name, parse


class RuntimeToolClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.sources = {"app.py": "from helpers import serve\n"}
        self.files = {
            "helpers/serve.py": "def run(): pass\n",
            "worker/__init__.py": "",
            "worker/main.py": 'from . import settings\nif __name__ == "__main__":\n    settings.run()\n',
            "worker/settings.py": "import json\ndef run(): pass\n",
            "worker/requirements.txt": "",
        }
        self.components = {
            "helpers": _scan.RuntimeTool("runtime", {"helpers/serve.py": ("run",)}, layer=1),
            "worker": _scan.RuntimeTool(
                "process", {"worker/main.py": ("__main__",)}, ("worker/requirements.txt",),
            ),
        }
        self.legacy = {"helpers"}
        self.kept = {*self.sources, *self.files}

    def audit(self) -> dict:
        for relative, source in {**self.sources, **self.files}.items():
            file = self.root / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(source, encoding="utf-8")
        release = plan(self.root, {"keep": ["**"], "exclude": sorted(self.files.keys() - self.kept)})
        return _scan.tool_runtime_audit(
            self.root, self.sources, self.legacy, self.components, release["keep"],
            {"app.py": 4}, {"worker": {"worker/main.py": [("app.py", 2, "launch")]}},
        )

    def test_rejects_production_import_with_no_category(self) -> None:
        self.components.pop("helpers")
        self.legacy.clear()
        self.assertIn("unclassified-import", {row[0] for row in self.audit()["issues"]})

    def test_requires_legacy_registration_to_resolve_file_and_entry(self) -> None:
        self.legacy.add("ghost")
        self.components["ghost"] = _scan.RuntimeTool("runtime", {"ghost.py": ("main",)}, layer=1)
        self.files["helpers/serve.py"] = "def renamed(): pass\n"
        issues = self.audit()["issues"]
        self.assertIn(("missing-file", "ghost.py", "ghost"), issues)
        self.assertIn(("missing-entry", "helpers/serve.py", "run"), issues)

    def test_rejects_process_dependency_outside_isolation_or_requirements(self) -> None:
        self.files["worker/settings.py"] += "import app\nimport new_vendor\n"
        issues = self.audit()["issues"]
        self.assertIn(("process-import", "worker/settings.py:3", "app"), issues)
        self.assertIn(("process-dependency", "worker/settings.py:4", "new_vendor"), issues)

    def test_rejects_process_dependency_omitted_from_distribution(self) -> None:
        self.kept.remove("worker/settings.py")
        self.assertIn(("release-missing", "worker/settings.py", "worker"), self.audit()["issues"])

    def test_accepts_runtime_and_isolated_closure(self) -> None:
        audit = self.audit()
        _scan.require_tool_runtime_closure(audit)
        self.assertEqual(set(audit["closure"]["worker"]), {
            "worker/__init__.py", "worker/main.py", "worker/settings.py", "worker/requirements.txt",
        })

    def test_rejects_missing_isolated_module_and_dynamic_dependency(self) -> None:
        self.files["worker/settings.py"] += (
            "from . import absent\nfrom importlib import import_module as load\nload(dynamic_name)\n"
        )
        issues = self.audit()["issues"]
        self.assertIn(("process-missing-module", "worker/settings.py:3", "worker.absent"), issues)
        self.assertIn(("process-unresolved-import", "worker/settings.py:5", "worker"), issues)

    def test_rejects_runtime_layer_violation_without_legacy_exemption(self) -> None:
        self.files["helpers/serve.py"] += "import app\n"
        self.assertIn(("upward-import", "helpers/serve.py:2", "app.py"), self.audit()["issues"])

    def test_runtime_and_process_require_a_production_consumer(self) -> None:
        self.sources["app.py"] = ""
        self.assertIn(("no-production-consumer", "helpers", "runtime"), self.audit()["issues"])


def _production_tool_audit() -> dict:
    from tests.architecture.test_layers import _module_classifications

    tool = _scan.RuntimeTool
    components = {
        "codex_tasks": tool("runtime", {
            "codex_tasks.py": ("task_lock", "prepare_task", "task_file_reference"),
        }, layer=1),
        "codex_paste": tool("runtime", {
            "codex_paste.py": ("paste_existing", "paste_attachment"),
        }, ("codex_paste.ps1",), layer=1),
        "console_submit": tool("runtime", {"console_submit.py": ("send", "__main__")}, layer=1),
        "batch_frames_tool": tool("runtime", {
            "batch_frames_tool/batch_frames.py": ("run", "Client", "graph", "load_assets", "shot_inputs"),
            "batch_frames_tool/启动批量首帧.pyw": ("mainloop",),
        }, ("batch_frames_tool/config.json",), layer=2),
        "blender_previs_template": tool("generator", {"blender_previs_template.py": ("build", "__main__")}),
        "voice_engine": tool("process", {
            "voice_engine/offline_asr_server.py": ("main", "__main__"),
            "voice_engine/bootstrap.py": ("main", "__main__"),
            "voice_engine/download_models.py": ("main", "__main__"),
        }, ("voice_engine/requirements.txt", "voice_engine/requirements.lock",
            "voice_engine/models.lock.json")),
        "selftests": tool("development", {
            "smoke_test.py": ("main",), "run_selftests.py": ("main",),
        }, tuple(sorted(f"{name}.py" for name in _scan._EXCLUDED_STEMS - {"smoke_test", "run_selftests"}))),
        "distribution_builder": tool("development", {"scripts/distribution_build.py": ("main",)}),
    }

    def refs(source, token, kind, *, required_calls=(), names=()):
        nodes = tuple(ast.walk(parse(ROOT / source)))
        calls = {_dotted_name(node.func) for node in nodes if isinstance(node, ast.Call)}
        symbols = {node.id for node in nodes if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
        if not set(required_calls) <= calls or not set(names) <= symbols:
            return []
        return [(source, node.lineno, kind) for node in nodes
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
                and (token in node.value if kind == "generation-template" else node.value == token)]

    references = {
        "blender_previs_template": {"blender_previs_template.py": refs(
            "orchestrator/previs_batch_service.py", "blender_previs_template.py", "generation-template",
        )},
        "selftests": {"run_selftests.py": refs(
            "domain/pet_test_service.py", "run_selftests.py", "developer-test-mode",
            required_calls=("run_process", "launch_background"),
        )},
        "voice_engine": {
            "voice_engine/offline_asr_server.py": refs(
                "domain/offline_asr_client.py", "offline_asr_server.py", "stdio-script",
                required_calls=("platform_tools.launch_text_process",), names=("SERVER_SCRIPT",),
            ),
            "voice_engine/bootstrap.py": refs(
                "domain/offline_asr_setup.py", "bootstrap.py", "setup-script",
                required_calls=("self._phase", "self._launcher"), names=("BOOTSTRAP",),
            ),
            "voice_engine/download_models.py": refs(
                "domain/offline_asr_setup.py", "voice_engine.download_models", "setup-module",
                required_calls=("self._phase", "self._launcher", "venv_python"),
            ),
        },
    }
    scan = _scan.module_scan_files(qualified=True)
    sources = set(scan) | set(_scan.production_files())
    layers = {row["file"]: row["layer"] for row in _module_classifications(scan).values()}
    layers.update({path.name: LAYERS[path.stem] for path in sources - set(scan) if path.stem in LAYERS})
    app_sources = {path.relative_to(ROOT).as_posix() for path in sources}
    launcher = "../启动漫剧制作助手.pyw"
    app_sources.add(launcher)
    layers[launcher] = 5
    generated = {"data/voice_asr_venv/pyvenv.cfg", "data/voice_models/model.bin"}
    candidates = candidate_files(ROOT.parent)
    probes = {f"程序/{item}" for item in generated}
    # 用实际构建器的决策读取现存候选，并探测目标机器生成缓存以后的规则；不创建缓存。
    with patch("scripts.distribution_build.candidate_files", return_value=sorted(set(candidates) | probes)):
        release = plan(ROOT.parent)
    kept = {path.removeprefix("程序/") for path in release["keep"] if path.startswith("程序/")}
    audit = _scan.tool_runtime_audit(
        ROOT, app_sources, TOOLS, components,
        kept, layers, references, generated=generated,
    )
    audit["legacy"] = {"registered": sorted(TOOLS), "scan_hits": sorted({module_name(p) for p in scan} & TOOLS.keys())}
    audit["roles"] = {name: {"role": spec.role, "candidate_layer": spec.layer}
                      for name, spec in components.items()}
    relevant = probes | {f"程序/{item}" for files in audit["closure"].values() for item in files}
    audit["release"] = {bucket: sorted(relevant.intersection(rows))
                        for bucket, rows in release.items()}
    return audit


class ProductionToolClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit = _production_tool_audit()

    def test_legacy_scan_discrepancy_and_actual_entrypoints_are_accounted_for(self) -> None:
        audit = self.audit
        registered, scan_hits = (set(audit["legacy"][name]) for name in ("registered", "scan_hits"))
        self.assertEqual(registered - scan_hits, {"batch_frames_tool"})
        self.assertEqual(registered, {name for name, spec in audit["roles"].items()
                                      if spec["role"] in {"runtime", "generator"}})
        consumers = {name: {source for rows in entries.values() for source, _, _ in rows}
                     for name, entries in audit["callers"].items()}
        self.assertEqual(consumers["codex_tasks"], {
            "orchestrator/agent_dispatch.py", "orchestrator/workflow_engines.py",
            "ui/desktop_idea_chat.py", "ui/desktop_send_choice.py",
        })
        self.assertEqual(consumers["codex_paste"], {"ui/desktop_idea_chat.py", "ui/desktop_send_choice.py"})
        self.assertEqual(consumers["console_submit"], {"orchestrator/workflow_engines.py"})
        self.assertEqual(consumers["batch_frames_tool"], {
            "image_agent_runner.py",
            "ui/desktop_pet_bridge.py", "ui/keyframe_comfy.py", "ui/native_assets.py",
        })
        self.assertIn(
            ("batch_frames_tool/启动批量首帧.pyw", "batch_frames_tool/batch_frames.py"),
            {(source, target) for source, _, target in audit["tool_imports"]},
        )
        self.assertEqual(consumers["blender_previs_template"], {"orchestrator/previs_batch_service.py"})
        self.assertEqual(consumers["selftests"], {"domain/pet_test_service.py"})
        self.assertEqual(consumers["voice_engine"], {"domain/offline_asr_client.py", "domain/offline_asr_setup.py"})
        self.assertEqual(set(audit["closure"]["voice_engine"]), {
            "voice_engine/__init__.py", "voice_engine/bootstrap.py",
            "voice_engine/download_models.py", "voice_engine/funasr_config.py",
            "voice_engine/offline_asr_server.py", "voice_engine/requirements.txt",
            "voice_engine/requirements.lock", "voice_engine/models.lock.json",
        })

    def test_infra_does_not_import_batch_orchestration(self) -> None:
        self.assertFalse([
            issue for issue in self.audit['issues']
            if issue[0] == 'upward-import' and issue[1].startswith('infra/')
            and issue[2] == 'batch_frames_tool/batch_frames.py'
        ])

    def test_strict_production_guard_refuses_current_release_gaps(self) -> None:
        release = [
            ("release-development", f"{name}.py", "selftests") for name in _scan._EXCLUDED_STEMS
        ]
        generated = [
            ("release-generated-data", path, "local runtime data")
            for path in ("data/voice_asr_venv/pyvenv.cfg", "data/voice_models/model.bin")
        ]
        dev_launch = [
            ("development-launch", f"domain/pet_test_service.py:{line}", "run_selftests.py")
            for line in (78, 97)
        ]
        # 精确记录当前拒绝。任意新拒绝会使默认回归失败，严格调用始终检查全部问题。
        self.assertCountEqual(self.audit["issues"], [*release, *generated, *dev_launch])
        with self.assertRaisesRegex(AssertionError, "Tool runtime closure rejected"):
            _scan.require_tool_runtime_closure(self.audit)


_L4_MODULES = frozenset({
    'desktop', 'app', 'pet_ui', 'pet_cloud', 'pet_settings_ui', 'pet_models_ui',
    'responsive_ui', 'ui_theme', 'cell_hover', 'prompt_window', 'asset_detail',
    'skill_panel', 'storyboard_files', 'storyboard_table_ui', 'storyboard_previs_ui', 'asset_batch',
})
_DYNAMIC_IMPORTS = frozenset({'__import__', 'import_module', 'importlib.import_module'})


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f'{parent}.{node.attr}' if parent else None
    return None


class DynamicImportRegistryTests(unittest.TestCase):
    def test_l4_dynamic_imports_use_the_plugin_registry(self) -> None:
        """登记的 L4 页面不得直接调用动态 import。"""
        offenders = []
        for name in sorted(_L4_MODULES):
            path = ROOT / f'{name}.py'
            if not path.is_file():
                continue
            # 本轮列表是审计指定的 L4 扫描范围；LAYERS 仅用于保留
            # 当前登记信息，不能因登记滞后而跳过实际页面的动态导入扫描。
            _registered_layer = LAYERS.get(module_name(path))
            tree = parse(path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _dotted_name(node.func) in _DYNAMIC_IMPORTS:
                    offenders.append(f'{path.name}:{node.lineno} {_dotted_name(node.func)}')
        self.assertEqual(
            offenders, [],
            'L4 动态导入必须改用 ui_plugin_registry.module():\n' + '\n'.join(offenders),
        )

    def test_registry_rejects_unknown_plugin(self):
        with self.assertRaisesRegex(ValueError, '未登记'):
            ui_plugin_registry.module('unregistered_plugin')

    def test_registry_has_the_ui_plugins_used_by_callers(self):
        expected = {'skill_panel', 'stage_flow', 'pet_ui', 'agent.prompt_optimizer',
                    'workflow_settings'}
        self.assertTrue(expected <= ui_plugin_registry.UI_PLUGINS)


def _target_errors(path, plugins, layers, source_layer=4):
    errors = []
    # A4 preserves the top-level debug entry as L5 assembly; imported UI stays L4.
    entry_lines = {child.lineno for node in parse(path).body
                   if isinstance(node, ast.If) and _scan._is_main_guard(node.test)
                   for statement in node.body if isinstance(statement, ast.Expr)
                   for child in ast.walk(statement) if isinstance(child, ast.Call)}
    for line, target in _scan.ui_registry_targets(path):
        if target is None:
            errors.append((line, "unresolved"))
        elif target not in plugins:
            errors.append((line, "unknown-key"))
        elif target not in layers:
            errors.append((line, "unregistered-target"))
        elif layers[target] > (5 if source_layer == 4 and line in entry_lines else source_layer):
            errors.append((line, "upward-target"))
    return errors


class StageClosureTests(unittest.TestCase):
    def audit(self, source, *, registry=False, layers=None):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'caller.py'
            path.write_text(source, encoding='utf-8')
            target_layers = {'service': 3, 'view': 4} if layers is None else dict(layers)
            target_layers.update({'stage_handler_registry': 3, 'orchestrator.stage_handler_registry': 3})
            return _scan.stage_registry_audit(path, {'storyboard', 'animatic'},
                                             target_layers, registry=registry)

    def test_stage_unknown_and_variable_keys_fail_closed(self):
        for key in ("'missing'", 'stage', "'storyboard' if flag else unknown"):
            with self.subTest(key=key):
                self.assertTrue(self.audit('from stage_handler_registry import start\n'
                                           f'start(host, {key})')['errors'])

    def test_stage_dispatch_unregistered_upward_and_variable_targets(self):
        for target, reason in (('missing.run', 'unregistered-target'),
                               ('view.run', 'upward-target'), ('selected', 'unresolved-target')):
            with self.subTest(target=target):
                errors = self.audit(
                    'import missing, view\ndef start(host, stage):\n'
                    f" if stage == 'storyboard':\n  return {target}(host)\n",
                    registry=True)['errors']
                self.assertIn(reason, {row[1] for row in errors})

    def test_stage_callback_variable_is_rejected(self):
        self.assertTrue(self.audit('import stage_handler_registry as r\n'
                                  "r.start(host, 'storyboard', fallback=callback)")['errors'])

    def test_stage_literals_aliases_keywords_and_all_conditional_arms(self):
        for source in (
            "from orchestrator.stage_handler_registry import start as go\ngo(host, 'storyboard')",
            "from orchestrator import stage_handler_registry as r\nr.start(host, stage='animatic')",
            "import orchestrator.stage_handler_registry\n"
            "orchestrator.stage_handler_registry.start(host, 'storyboard' if flag else 'animatic')",
        ):
            self.assertEqual(self.audit(source)['errors'], [])

    def test_stage_registry_escapes_shadowing_and_star_arguments(self):
        for statement in ("go = r.start", "getattr(r, 'start')(host, 'storyboard')",
                          "r.start(*args)", "r.start(host, 'storyboard', **options)",
                          "r = other\nr.start(host, 'storyboard')"):
            self.assertTrue(self.audit('import stage_handler_registry as r\n' + statement)['errors'])
        self.assertTrue(self.audit('from stage_handler_registry import *')['errors'])
        self.assertTrue(self.audit('from stage_handler_registry import start\n'
                                  "def f(start):\n start(host, 'storyboard')")['errors'])
        self.assertTrue(self.audit('from stage_handler_registry import start\n'
                                  "def start(*args): pass\nstart(host, 'storyboard')")['errors'])

    def test_stage_callbacks_are_checked_at_the_injecting_layer(self):
        prefix = "import stage_handler_registry as r\nimport service, view\n"
        for expression in ('service.run', 'view.show', 'service.run if flag else view.show'):
            self.assertEqual(self.audit(prefix +
                f"r.start(host, 'storyboard', fallback={expression})")['errors'], [])
        for expression in ('missing', 'lambda *args: view.show(*args)',
                           'service.run if flag else missing'):
            self.assertTrue(self.audit(prefix +
                f"r.start(host, 'storyboard', fallback={expression})")['errors'])
        self.assertTrue(self.audit(prefix + "r.start(host, 'storyboard', fallback=view.show)",
                                   layers={'view': 5, 'service': 3})['errors'])

    def test_stage_action_targets_are_checked_at_the_injecting_layer(self):
        prefix = "import stage_handler_registry as r\nimport view\n"
        for parameter in ('skip_action', 'run_action'):
            for action, expected in (('view.act', set()),
                                     ('unknown', {'unresolved-target'}),
                                     ('view.act if flag else unknown', {'unresolved-target'})):
                with self.subTest(parameter=parameter, action=action):
                    errors = self.audit(
                        prefix + f"r.start(host, 'storyboard', {parameter}={action})")['errors']
                    self.assertEqual({reason for _, reason, _ in errors}, expected)
            errors = self.audit(prefix + f"r.start(host, 'storyboard', {parameter}=view.act)",
                                layers={'view': 5})['errors']
            self.assertIn('upward-target', {reason for _, reason, _ in errors})

    def test_stage_local_callback_body_is_not_a_name_only_exemption(self):
        prefix = "import stage_handler_registry as r\nimport service, view\n"
        good = prefix + "def callback(stage, trigger):\n return service.run(stage)\n"
        call = "r.start(host, 'storyboard', fallback=callback)"
        self.assertEqual(self.audit(good + call)['errors'], [])
        bad = good.replace('service.run(stage)', 'unknown(stage)')
        self.assertTrue(self.audit(bad + call)['errors'])
        self.assertTrue(self.audit(good.replace('def callback', '@service.decorate\ndef callback') + call)['errors'])
        method = prefix + ("class Host:\n def fallback(self, stage, trigger):\n"
                           "  return service.run(stage)\n def run(self):\n"
                           "  return r.start(self, 'storyboard', fallback=self.fallback)\n")
        self.assertEqual(self.audit(method)['errors'], [])

    def test_stage_declaration_closure_follows_helpers_and_dead_branches(self):
        source = ("raise RuntimeError('not executed')\nimport service, view\n"
                  "def handler(host):\n return service.run(host)\n"
                  "def start(host, stage):\n"
                  " if stage not in ('storyboard', 'animatic'): raise ValueError(stage)\n"
                  " if stage == 'storyboard': return handler(host)\n"
                  " if stage == 'animatic': return service.run(host)\n")
        report = self.audit(source, registry=True)
        self.assertEqual(report['errors'], [])
        self.assertEqual(len(report['branches']), 3)
        self.assertTrue(self.audit(source.replace('return handler(host)', 'return view.show(host)'),
                                   registry=True)['errors'])
        self.assertTrue(self.audit(source + " if False and stage == 'missing': return handler(host)\n",
                                   registry=True)['errors'])
        self.assertTrue(self.audit(source.replace("stage == 'animatic'", 'stage == selected'),
                                   registry=True)['errors'])
        for condition in ('stage.value', 'service.choose(stage)', "stage > 'animatic'"):
            report = self.audit(source.replace("stage == 'animatic'", condition), registry=True)
            self.assertIn('unresolved-condition', {e[1] for e in report['errors']})

    def test_unknown_stage_fallthrough_is_not_proof_of_registration(self):
        report = self.audit("def start(host, stage, fallback=None):\n"
                            " if callable(fallback): return fallback(stage)\n return ''",
                            registry=True)
        self.assertIn('unvalidated-stage-domain', {e[1] for e in report['errors']})
        with self.assertRaisesRegex(AssertionError, 'closure rejected'):
            _scan.require_stage_registry_closure({'registry': report})
        _scan.require_stage_registry_closure({'closed': {'errors': []}})

    def test_stage_keys_are_literal_unique_and_never_executed(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'keys.py'
            path.write_text("raise RuntimeError()\nSTAGES = ('a', 'b')", encoding='utf-8')
            self.assertEqual(_scan.literal_string_keys(path, 'STAGES'), {'a', 'b'})
            for value in ("('a', 'a')", 'load()', "('a', 3)"):
                path.write_text('STAGES = ' + value, encoding='utf-8')
                with self.assertRaises(ValueError):
                    _scan.literal_string_keys(path, 'STAGES')

    def test_source_layer_and_unknown_registry_members_are_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'caller.py'
            path.write_text("import stage_handler_registry as r\nr.start(host, 'storyboard')", encoding='utf-8')
            for layer in (2, -1):
                report = _scan.stage_registry_audit(path, {'storyboard'},
                            {'stage_handler_registry': 3}, source_layer=layer)
                self.assertIn('upward-target', {e[1] for e in report['errors']})
        self.assertTrue(self.audit('import stage_handler_registry as r\nr.missing()')['errors'])

    def test_l3_ui_dynamic_edge_uses_source_layer(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'stage.py'
            path.write_text("from infra.ui_plugin_registry import module\nmodule('panel')", encoding='utf-8')
            self.assertEqual(_target_errors(path, {'panel'}, {'panel': 4}, 3), [(2, 'upward-target')])
            self.assertEqual(_target_errors(path, {'panel'}, {'panel': 3}, 3), [])

    def test_guarded_stage_parameter_proves_the_domain(self):
        source = (
            "from stage_handler_registry import start\n"
            "def entry(host, stage):\n"
            " if stage not in ('storyboard', 'animatic'):\n"
            "  raise ValueError(stage)\n"
            " return start(host, stage)\n"
        )
        self.assertEqual(self.audit(source)['errors'], [])
        for invalid in (
            source.replace("'animatic'", "'missing'"),
            source.replace("('storyboard', 'animatic')", "'storyboard'"),
            source.replace('raise ValueError(stage)', 'pass'),
            source.replace(' return start', " stage = 'missing'\n return start"),
            source.replace(' return start', ' import missing as stage\n return start'),
            source.replace(' return start', ' def nested(stage):\n  return start'),
            source.replace('host, stage):', 'host, stage=start(host, stage)):'),
            source.replace('return start(host, stage)', 'return [start(host, stage) for stage in items]'),
            source.replace('def entry', 'from contract.pet_bus import STAGES\ndef entry')
            .replace("('storyboard', 'animatic')", 'STAGES'),
        ):
            self.assertTrue(self.audit(invalid)['errors'], invalid)

    def test_production_strict_closure_accepts_all_entries(self):
        audits = _production_stage_audits()
        bridge = 'ui/desktop_pet_bridge.py'
        self.assertIn('orchestrator/stage_handler_registry.py', audits)
        self.assertEqual(len(audits[bridge]['calls']), 2)
        _scan.require_stage_registry_closure(audits)


def _production_stage_audits():
    keys = _scan.literal_string_keys(ROOT / 'contract/pet_bus.py', 'STAGES')
    # Existing non-workflow commands in start(); these are commands, not stages.
    keys |= {'pet_performance', 'pet_test'}
    paths = _scan.module_scan_files(qualified=True)
    layers = dict(LAYERS)
    for path in paths:
        layer = LAYERS.get(_scan.module_name(path))
        if layer is not None:
            layers[_scan.module_name(path, qualified=True)] = layer
    plugins = _scan.ui_registry_declaration(ROOT / 'infra/ui_plugin_registry.py')
    plugin_layers = {key: layers.get(key, layers.get(key.rsplit('.', 1)[-1])) for key in plugins}
    plugin_layers = {key: value for key, value in plugin_layers.items() if value is not None}
    audits = {}
    for path in paths:
        name = path.relative_to(ROOT).as_posix()
        layer = layers.get(_scan.module_name(path, qualified=True))
        report = _scan.stage_registry_audit(path, keys, layers,
                    registry=name == 'orchestrator/stage_handler_registry.py',
                    source_layer=layer if layer is not None else -1)
        if layer is not None and layer < 4:
            report['errors'].extend(_target_errors(path, plugins, plugin_layers, layer))
        if report['calls'] or report['targets'] or report['errors']:
            audits[name] = report
    return audits


class RegistryClosureTests(unittest.TestCase):
    def check_source(self, source, plugins, layers):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "caller.py"
            path.write_text(source, encoding="utf-8")
            return _target_errors(path, plugins, layers)

    def test_unknown_key_is_rejected(self):
        self.assertEqual(self.check_source(
            "import infra.ui_plugin_registry as r\nr.module('missing')",
            {"known"}, {"known": 4}), [(2, "unknown-key")])

    def test_unregistered_and_upward_targets_are_rejected(self):
        for layers, reason in (({}, "unregistered-target"), ({"known": 5}, "upward-target")):
            with self.subTest(reason=reason):
                self.assertEqual(self.check_source(
                    "from infra.ui_plugin_registry import module as load\nload('known')",
                    {"known"}, layers), [(2, reason)])

    def test_variable_is_not_silently_accepted(self):
        self.assertEqual(self.check_source(
            "from infra import ui_plugin_registry as r\nr.module(name)",
            {"known"}, {"known": 4}), [(2, "unresolved")])


    def test_literals_aliases_keywords_and_conditionals(self):
        for source in (
            "import infra.ui_plugin_registry as r\nr.module('known')",
            "import infra.ui_plugin_registry\ninfra.ui_plugin_registry.module(name='known')",
            "from ui_plugin_registry import module as load\nload('known' if flag else 'other')",
        ):
            self.assertEqual(self.check_source(source, {"known", "other"}, {"known": 4, "other": 3}), [])
        self.assertEqual(self.check_source(
            "import ui_plugin_registry as r\nr.module('known' if flag else variable)",
            {"known"}, {"known": 4}), [(2, "unresolved")])

    def test_loader_escape_is_rejected(self):
        self.assertEqual(self.check_source(
            "from infra.ui_plugin_registry import module as load\nother = load",
            {"known"}, {"known": 4}), [(2, "unresolved")])

    def test_declaration_is_parsed_without_execution(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "registry.py"
            path.write_text("raise RuntimeError('never execute')\nUI_PLUGINS = frozenset({'known'})", encoding="utf-8")
            self.assertEqual(_scan.ui_registry_declaration(path), {"known"})
            path.write_text("UI_PLUGINS = get_plugins()", encoding="utf-8")
            with self.assertRaises(ValueError):
                _scan.ui_registry_declaration(path)

    def test_l4_production_target_closure(self):
        plugins = _scan.ui_registry_declaration(ROOT / "infra/ui_plugin_registry.py")
        # Preserve current flat identity policy; strict identity remains a separate gate.
        layers = {key: LAYERS[key] if key in LAYERS else LAYERS.get(key.rsplit(".", 1)[-1])
                  for key in plugins}
        layers = {key: value for key, value in layers.items() if value is not None}
        self.assertEqual(sorted(plugins - layers.keys()), [])
        self.assertTrue(all(type(layer) in (int, float) and layer in range(6) for layer in layers.values()))
        errors = []
        count = 0
        for path in _scan.module_scan_files(qualified=True):
            if LAYERS.get(_scan.module_name(path)) != 4:
                continue
            count += len(list(_scan.ui_registry_targets(path)))
            errors.extend((path.relative_to(ROOT).as_posix(), *row)
                          for row in _target_errors(path, plugins, layers))
        self.assertGreater(count, 0)
        self.assertEqual(errors, [])

    def test_unknown_runtime_key_never_imports(self):
        with patch.object(ui_plugin_registry, 'import_module') as load:
            with self.assertRaises(ValueError):
                ui_plugin_registry.module('unregistered_plugin')
            load.assert_not_called()
            load.return_value = object()
            self.assertIs(ui_plugin_registry.module(' skill_panel '), load.return_value)
            load.assert_called_once_with('skill_panel')


    def test_debug_entry_does_not_exempt_ui_functions(self):
        prefix = "import infra.ui_plugin_registry as r\n"
        self.assertEqual(self.check_source(prefix + "if __name__ == '__main__':\n r.module('launch')",
                                           {"launch"}, {"launch": 5}), [])
        self.assertEqual(self.check_source(prefix + "def open_page():\n r.module('launch')",
                                           {"launch"}, {"launch": 5}), [(3, "upward-target")])


    def test_registry_escape_and_conditional_unknown_are_rejected(self):
        for expression in ("other = r", "getattr(r, 'module')('known')"):
            self.assertEqual(self.check_source("import ui_plugin_registry as r\n" + expression,
                                               {"known"}, {"known": 4}), [(2, "unresolved")])
        self.assertEqual(self.check_source(
            "from ui_plugin_registry import module\nmodule('known' if flag else 'missing')",
            {"known"}, {"known": 4}), [(2, "unknown-key")])
