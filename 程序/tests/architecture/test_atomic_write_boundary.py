"""正式成果写入必须经统一原子服务或已登记的受控边界。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import (ROOT, module_name, module_scan_files, parse,
                                      production_runtime_files, registry_key)


_DIRECT_WRITE_METHODS = frozenset({"write_text", "write_bytes"})
# R3246 轮 2：agent/ 并入分层包后 registry_key 归一为扁平名（core.py／publication.py），
# 与 T10 包实体同一口径；agent.core 本身是原子写权威，登记为受控边界。
_ATOMIC_BOUNDARIES = frozenset({"model_secrets", "qwen_adapter", "workflow_engines", "core"})
# skill_archive 的 open(target,'wb') 只写 ZIP 解压暂存区（用后经回收站收走），
# 包内文件是任意字节不是正式成果，不走 agent.core 文本保存口径；
# skill_remote_service 的 open(dest,'wb') 只写下载缓存（data/skills/下载缓存/，
# 同为暂存语义，失败即删半截文件），同理不算正式成果。
# app_logging 的 perf_metrics.json 是可丢弃诊断日志，不是项目正式成果；进程退出时尽力写入。
# optimizer_mcp_bridge 的 open(os.devnull,'w') 只是给 MCP 子进程重定向 stderr，
# 不产生任何文件（R3246 轮 2 agent/ 入包扫描后登记）。
_TEMPORARY_BOUNDARIES = frozenset({"app_logging", "app_shortcut", "skill_archive", "skill_remote_service",
                                   "optimizer_mcp_bridge"})

# R1854：直接 os.replace／Path.replace 会绕过 agent.core.replace 的 Windows 共享冲突重试与发布记录
# （R1853 的 asset_detail_service 就是这样一次“拒绝访问”整次失败）。agent/core.py 是权威实现；
# 其余为登记时的现状（发布日志自身、日志轮转、导入暂存切换、注入的 replace_file 默认值等），只许减少。
_REPLACE_AUTHORITY = "core.py"
_REPLACE_REGISTERED = {
    "core.py": 1,
    "publication.py": 2,
    # R3292：faulthandler.log 超 5MiB 时的日志轮转（FAULT_LOG → FAULT_LOG.1），与 log_maintenance 同类。
    "app_logging.py": 1,
    "image_agent_runner.py": 1,
    "log_maintenance.py": 2,
    "skill_registry.py": 1,
    "stage_handoff_gateways.py": 1,
    "stage_write_preparation_service.py": 3,
    # white_model_service 的两处 temporary.replace(target) 属 L2 边界内既有形态
    # （该模块被 test_white_model_service_json_boundary 禁止 import agent.core），
    # 保持登记原值；R3310 只收敛了 orchestrator/stage_execution_service 的网关 lambda。
    "white_model_service.py": 2,
}

# REL-06 原子写审计：「项目配置、台账、产物清单」三类关键文件的属主模块。
# 它们的写盘只能经统一入口——agent.core.save/save_text 或调用方注入的发布器
# （如 domain/projects 的 publish_json=agent.core.save、artifact_schema.migrate_file
# 的 publish 参数）。这些模块永远不得进上面两个登记表：登记等于把绕过合法化，
# 发现直接写盘必须修产品代码，不许扩表。
_CRITICAL_FILE_OWNERS = {
    "engine": "项目 config.json 写回、视频产物清单（save/save_text）",
    "stage_config": "项目 skill_config.json（save）",
    "project_settings": "项目 ui_settings.json（save）；配置 .bak 快照经 shutil.copyfile（备份机制，同 artifact_schema.migrate_file 口径）",
    "projects": "项目 config.json／projects.json 登记与资产清单（注入 publish_json=agent.core.save）",
    "request_ledger": "项目 请求台账.json（save）",
    "continuity_ledger": "项目连续性台账（save/save_text）",
    "desktop_send_ledger": "项目续发台账（save）",
    "artifact_lineage": "产物来源关系.json（save）",
    "artifact_schema": "迁移写盘（.bak 快照→注入原子发布→读回断言）",
}


def _is_direct_replace(call: ast.Call) -> bool:
    """os.replace(a, b) 与 Path.replace(target)；str.replace 恒为两个参数，不会误报。"""
    func = call.func
    if not isinstance(func, ast.Attribute) or func.attr != "replace":
        return False
    if isinstance(func.value, ast.Name) and func.value.id == "os":
        return True
    return len(call.args) == 1 and not call.keywords and not isinstance(func.value, ast.Constant)


def _replace_counts() -> dict:
    counts = {}
    for path in production_runtime_files():
        found = sum(1 for node in ast.walk(parse(path))
                    if isinstance(node, ast.Call) and _is_direct_replace(node))
        if found:
            counts[registry_key(path)] = found
    return counts


def _is_direct_write(call: ast.Call) -> bool:
    """识别绕开服务的文件写入调用，不把 read/open 或目录操作误报为写入。"""
    if isinstance(call.func, ast.Attribute) and call.func.attr in _DIRECT_WRITE_METHODS:
        if isinstance(call.func.value, ast.Name) and call.func.value.id == 'line_endings':
            return False
        return True
    if not isinstance(call.func, ast.Name) or call.func.id != "open":
        return False
    for keyword in call.keywords:
        if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
            return any(flag in str(keyword.value.value) for flag in "wx")
    return len(call.args) > 1 and isinstance(call.args[1], ast.Constant) and any(
        flag in str(call.args[1].value) for flag in "wx")


def _write_lines(path):
    return tuple(node.lineno for node in ast.walk(parse(path))
                 if isinstance(node, ast.Call) and _is_direct_write(node))


class AtomicWriteBoundaryTests(unittest.TestCase):
    def test_direct_production_writes_are_limited_to_registered_boundaries(self):
        offenders = []
        for path in module_scan_files():
            name = module_name(path)
            lines = _write_lines(path)
            if lines and name not in _ATOMIC_BOUNDARIES | _TEMPORARY_BOUNDARIES:
                offenders.extend('%s:%d' % (path.name, line) for line in lines)
        self.assertEqual(offenders, [], '正式成果请改走 agent.core / line_endings；未登记直接写入：'
                         + ', '.join(offenders))

    def test_direct_replace_is_limited_to_registered_writers(self):
        counts = _replace_counts()
        bad = []
        for name, actual in sorted(counts.items()):
            allowed = _REPLACE_REGISTERED.get(name, 0)
            if actual > allowed:
                bad.append('%s: %d 处直接 replace > 登记 %d 处' % (name, actual, allowed))
        for name in sorted(set(_REPLACE_REGISTERED) - set(counts) - {_REPLACE_AUTHORITY}):
            bad.append('%s: 已无直接 replace，请从登记表删除' % name)
        self.assertEqual(bad, [], '文件切换请改走 agent.core.replace()／save()：' + '; '.join(bad))

    def test_direct_replace_detector_catches_both_spellings(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            sample = Path(folder) / 'sample.py'
            sample.write_text('import os\nos.replace(a, b)\nPath(a).replace(b)\n'
                              "text.replace('x', 'y')\n", encoding='utf-8')
            calls = [node for node in ast.walk(parse(sample)) if isinstance(node, ast.Call)]
            self.assertEqual(sum(_is_direct_replace(node) for node in calls), 2)

    def test_registered_atomic_boundaries_prove_temporary_then_replace(self):
        for path in module_scan_files():
            name = module_name(path)
            if name not in _ATOMIC_BOUNDARIES:
                continue
            source = path.read_text(encoding='utf-8')
            with self.subTest(module=name):
                self.assertIn('temporary_path(', source)
                self.assertIn('replace(', source)

    def test_background_adapters_validate_report_body_before_publication(self):
        for name in ('qwen_adapter', 'workflow_engines'):
            path = next(path for path in module_scan_files() if module_name(path) == name)
            source = path.read_text(encoding='utf-8')
            with self.subTest(module=name):
                self.assertIn('未返回制作报告正文', source)
                self.assertLess(source.index('未返回制作报告正文'),
                                source.index('save_text(Path(report)'))

    def test_critical_file_owners_stay_on_the_unified_write_entry(self):
        # 项目配置／台账／产物清单的属主模块：不许登记为直接写盘边界，
        # 也不许出现绕开统一入口的直接写盘调用——发现先修产品，不扩表。
        overlap = sorted(set(_CRITICAL_FILE_OWNERS) & (_ATOMIC_BOUNDARIES | _TEMPORARY_BOUNDARIES))
        self.assertEqual(overlap, [], '关键文件属主不得登记为直接写盘边界：' + ', '.join(overlap))
        scanned = {module_name(path) for path in module_scan_files()}
        missing = sorted(set(_CRITICAL_FILE_OWNERS) - scanned)
        self.assertEqual(missing, [], '属主模块不在扫描范围，清单需修正：' + ', '.join(missing))
        offenders = []
        for path in module_scan_files():
            if module_name(path) in _CRITICAL_FILE_OWNERS:
                offenders.extend('%s:%d' % (path.name, line) for line in _write_lines(path))
        self.assertEqual(offenders, [],
                         '项目配置／台账／产物清单必须经统一入口写入，发现直接写盘：'
                         + ', '.join(offenders))

    def test_shortcut_script_is_temporary_and_is_reclaimed(self):
        path = next(path for path in module_scan_files() if module_name(path) == 'app_shortcut')
        source = path.read_text(encoding='utf-8')
        self.assertIn('tempfile.mkstemp(', source)
        self.assertIn('remove_temporary_file(script_path)', source)
