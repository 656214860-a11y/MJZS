"""覆盖率审计的固定谓词、三源同源与双向棘轮。

扫描范围＝产品运行时生产模块（R1393 起）：根目录生产 .py 加上 `agent/`／`batch_frames_tool/`
等被产品实际导入的运行时子包，排除 `skills/`／`scripts/`／`reference/`／`outputs/`／`附加工具/`
非产品目录。台账键为相对 `程序/` 的 posix 路径（根目录文件即文件名）。
"""
from __future__ import annotations
import ast
import hashlib
import unittest
import json
import re
from pathlib import Path
from pet_bus import CONTRACT
from tests.architecture._scan import parse, production_runtime_files
ROOT=Path(__file__).resolve().parents[2]
CANARY=Path(__file__).with_name('_canary')
# 21 白名单：明确的平台适配器／外部工具；其余 OS 进程调用须报告。
P21={'platform_tools','native_apps','app_shortcut','codex_paste','codex_tasks','console_submit','engine_probe','previs_automation','qwen_adapter','workflow_engines','aigc_lint','bootstrap'}
# 26 白名单：唯一模型池、路由与供应商适配器。
# 23 白名单：阶段完成核验的唯一权威；其余完成事件必须与同函数内的核验证据同现。
P23={'stage_completion_service','pet_bus'}
# 23 目标事件：正式完成事件（script.completed 是自动链唯一启动信号，stage.completed 是阶段收尾）。
P23_EVENTS={'stage.completed','script.completed'}
P26={'model_pool','model_router','qwen_adapter','comfy_service','cloud_assets','cloud_video','platform_tools'}
# 24 白名单：两份注册表是产品插件入口；clipboard_lock 仅在非 Windows 条件分支加载 Unix
# 标准库 fcntl，属于跨平台锁实现而非产品动态插件，不能把它记作未登记业务动态导入。
P24={'ui_plugin_registry','stage_handler_registry','clipboard_lock'}
LEDGER=ROOT/'维护记录'/'架构统一基数.json'
CRITERIA=ROOT/'维护记录'/'覆盖率审计判据_20261001.md'
AUDIT_SECTIONS={'20':'覆盖率审计20','21':'覆盖率审计21','22':'覆盖率审计22','23':'覆盖率审计23','24':'覆盖率审计24','25':'覆盖率审计25','26':'覆盖率审计26'}
def _key(path):
    """台账用的文件标识：相对 程序/ 的 posix 路径（根目录文件即文件名）。"""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def _scope_ranges(tree):
    """预计算作用域区间，避免对每个命中节点重复 ast.walk（O(n²)→O(n)）。"""
    return sorted((candidate.lineno,
                   getattr(candidate, 'end_lineno', candidate.lineno),
                   candidate.name)
                  for candidate in ast.walk(tree)
                  if isinstance(candidate, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)))


def _scope(scopes, node):
    line = node.lineno
    return '.'.join(name for start, end, name in scopes if start <= line <= end) or '<module>'


def _anchor(path, tree, node, kind, duplicates):
    """生成可随无关行平移的审计登记键；作用域区间只在本文件首次命中时才算。"""
    if '<scopes>' not in duplicates:
        duplicates['<scopes>'] = _scope_ranges(tree)
    base = f'{_scope(duplicates["<scopes>"], node)}:{kind}:' + hashlib.sha256(
        ast.dump(node, include_attributes=False).encode('utf-8')).hexdigest()[:16]
    duplicates[base] = duplicates.get(base, 0) + 1
    return f'{_key(path)}:{base}:{duplicates[base]}'
def dot(n):
    if isinstance(n,ast.Name): return n.id
    if isinstance(n,ast.Attribute):
        p=dot(n.value); return f'{p}.{n.attr}' if p else None
    if (isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name)
            and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str)):
        return f'{n.value.id}.{n.slice.value}'

def _dynamic_target(node):
    """只把非字面量或插件／阶段处理器目标视作注册路径动态加载。"""
    if not node.args or not isinstance(node.args[0],ast.Constant) or not isinstance(node.args[0].value,str):
        return None
    return node.args[0].value

def _event_kind(node, name):
    """取得统一事件入口的字面量 kind；包装器转发的变量不在静态候选内。"""
    index = 2 if name == 'pet_bus.emit_safe' else 0
    if len(node.args) <= index or not isinstance(node.args[index], ast.Constant):
        return None
    return node.args[index].value if isinstance(node.args[index].value, str) else None

def _json_replace_calls(function):
    """只把替换正式 JSON 的外部覆写归为 file_cache 审计目标。"""
    assignments={node.targets[0].id: node.value for node in ast.walk(function)
                 if isinstance(node, ast.Assign) and len(node.targets)==1
                 and isinstance(node.targets[0], ast.Name)}
    for node in ast.walk(function):
        if not isinstance(node, ast.Call) or dot(node.func) != 'gateway.replace_file' or len(node.args)<2:
            continue
        target=node.args[1]
        value=assignments.get(target.id) if isinstance(target, ast.Name) else target
        if value and any(isinstance(part, ast.Constant) and isinstance(part.value, str)
                         and part.value.lower().endswith('.json') for part in ast.walk(value)):
            yield node

def _completion_verification(tree):
    """同一函数内的核验证据：emit_verified_completion／_completion_evidence／verified_stage_output。"""
    verified=set()
    for function in (node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef)):
        for call in (node for node in ast.walk(function) if isinstance(node,ast.Call)):
            name=(dot(call.func) or '').lower()
            if 'verif' in name or name == 'self._completion_evidence':
                verified.add(id(function))
                break
    return verified

def _scan23(paths=None):
    """第 23 项：发出正式完成事件，但同一函数内没有任何核验证据（未核验就宣布完成）。"""
    out=set()
    for p in (production_runtime_files() if paths is None else paths):
        tree=parse(p) if paths is None else ast.parse(p.read_text(encoding='utf-8'))
        if p.stem in P23:
            continue
        verified=_completion_verification(tree)
        duplicates = {}
        owners={}
        for function in (node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef)):
            for node in ast.walk(function):
                owners[id(node)]=function
        for node in ast.walk(tree):
            if not isinstance(node,ast.Call):
                continue
            name=dot(node.func)
            if not (name == 'pet_bus.emit_safe' or (name or '').endswith('._emit')):
                continue
            if _event_kind(node, name) not in P23_EVENTS:
                continue
            owner=owners.get(id(node))
            if owner is None or id(owner) not in verified:
                out.add(_anchor(p, tree, node, '23', duplicates))
    return out

def _audit19_config_writes():
    """第 19 项（归并第 3 项）：L2 里可能落到项目／阶段 config.json 的写入点。"""
    from tests.architecture._layers import LAYERS
    write_names={'save','save_bytes','save_text','write_text','write_bytes','dump'}
    found=set()
    for name,layer in LAYERS.items():
        if layer != 2:
            continue
        path=ROOT/f'{name}.py'
        if not path.is_file():
            continue
        tree=ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
        for function in (node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef)):
            literals={node.value for node in ast.walk(function)
                      if isinstance(node,ast.Constant) and isinstance(node.value,str)}
            if 'config.json' not in literals:
                continue
            if any(isinstance(node,ast.Call) and (
                    (isinstance(node.func,ast.Name) and node.func.id in write_names) or
                    (isinstance(node.func,ast.Attribute) and node.func.attr in write_names))
                   for node in ast.walk(function)):
                found.add(f'{path.name}:{function.name}')
    return found

def scan(kind, paths=None):
    if kind == '23':
        return _scan23(paths)
    out=set()
    for p in (production_runtime_files() if paths is None else paths):
        tree=parse(p) if paths is None else ast.parse(p.read_text(encoding='utf-8'))
        functions={node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        duplicates = {}
        if kind == '20':
            for name, function in functions.items():
                calls=[dot(node.func) for node in ast.walk(function) if isinstance(node, ast.Call)]
                publishes=sum(call == 'gateway.published' for call in calls)
                replaces=sum(1 for _ in _json_replace_calls(function))
                # agent.core 的原子发布由签名变化自动换代缓存；只有绕过该入口的
                # replace_file 是“外部覆写”，必须显式广播失效事件。
                if replaces and publishes < replaces:
                    out.add(_anchor(p, tree, function, '20', duplicates))
            continue
        for n in ast.walk(tree):
            if not isinstance(n,ast.Call): continue
            name,mod=dot(n.func),p.stem
            dynamic_target=_dynamic_target(n)
            event_kind = _event_kind(n, name)
            hit=(kind=='21' and name in {'subprocess.run','subprocess.Popen','os.startfile'} and mod not in P21) or (kind=='22' and name in {'os.remove','os.unlink','shutil.rmtree'} and mod not in {'storage_maintenance','file_cache','asset_batch_lifecycle','storyboard_lifecycle'}) or (kind=='24' and name in {'__import__','import_module','importlib.import_module'} and mod not in P24 and (dynamic_target is None or 'plugin' in dynamic_target.lower() or 'handler' in dynamic_target.lower())) or (kind=='25' and (name == 'pet_bus.emit_safe' or (name or '').endswith('._emit')) and event_kind is not None and event_kind not in CONTRACT) or (kind=='26' and name in {'requests.get','requests.post','urllib.request.urlopen'} and mod not in P26)
            if hit: out.add(_anchor(p, tree, n, kind, duplicates))
    return out
class CoverageAuditCanaryTests(unittest.TestCase):
    def test_each_predicate_hits_canary(self):
        names={'20':'audit20_cache_violation.py','21':'audit21_platform_violation.py','22':'audit22_violation.py','23':'audit23_violation.py','24':'audit24_violation.py','25':'audit25_event_violation.py','26':'audit26_violation.py'}
        for kind,name in names.items():
            self.assertTrue(scan(kind,[CANARY/name]),f'{kind} 金丝雀漏报')
    def test_pending_and_predicate_hits_are_exactly_equal(self):
        """双向棘轮：既禁止漏账，也禁止待办死账。"""
        ledger=json.loads(LEDGER.read_text(encoding='utf-8'))
        for kind,section in AUDIT_SECTIONS.items():
            pending={f"{x['file']}:{x['point']}" for x in ledger[section]['items']
                     if x['disposition']=='pending'}
            actual=scan(kind)
            self.assertEqual(actual,pending,
                             f'{section} 台账 pending 与冻结谓词实际命中不相等')

    def test_audit_pending_sets_do_not_overlap(self):
        """同一待办位置只能归属一个审计段落。"""
        ledger=json.loads(LEDGER.read_text(encoding='utf-8'))
        pending={section:{f"{x['file']}:{x['point']}" for x in ledger[section]['items']
                          if x['disposition']=='pending'}
                 for section in AUDIT_SECTIONS.values()}
        for left_name,left in pending.items():
            for right_name,right in pending.items():
                if left_name < right_name:
                    self.assertEqual(left & right,set(),
                                     f'{left_name} 与 {right_name} 存在重复待办')

    def test_criteria_true_candidate_counts_match_scan_and_pending(self):
        """判据表由同一冻结扫描器生成，不能手写另一套数字。"""
        ledger=json.loads(LEDGER.read_text(encoding='utf-8'))
        criteria=CRITERIA.read_text(encoding='utf-8')
        for kind,section in AUDIT_SECTIONS.items():
            matched=re.search(rf'^\|{kind} .*?\|.*?\|.*?\|(\d+)(?:（.*?）)?\|$',criteria,re.MULTILINE)
            self.assertIsNotNone(matched,f'判据文档缺少第 {kind} 项真候选数')
            documented=int(matched.group(1))
            actual=scan(kind)
            pending=sum(item['disposition']=='pending' for item in ledger[section]['items'])
            self.assertEqual(documented,len(actual),f'第 {kind} 项文档与扫描器不一致')
            self.assertEqual(documented,pending,f'第 {kind} 项文档与台账 pending 不一致')

    def test_audit19_is_merged_into_the_third_item_scope(self):
        """第 19 项不另建扫描器：它的 config.json 写入点必须已被第 3 项登记覆盖。"""
        ledger=json.loads(LEDGER.read_text(encoding='utf-8'))
        recorded={f"{x['file']}:{x['point']}" for x in ledger['第三项']['items']}
        self.assertTrue(_audit19_config_writes() <= recorded,
                        f'第 19 项候选未被第 3 项登记：{sorted(_audit19_config_writes() - recorded)}')
        self.assertEqual(ledger['覆盖率审计19']['items'],[])

    def test_audit19_to_23_each_record_a_disposition_and_reason(self):
        """19–23 每段都必须有处置与理由（19 归并、22 复用既有门禁、23 冻结窄谓词）。"""
        ledger=json.loads(LEDGER.read_text(encoding='utf-8'))
        for kind in ('19','20','21','22','23'):
            section=f'覆盖率审计{kind}'
            self.assertIn(section,ledger,f'缺少 {section}')
            self.assertTrue(str(ledger[section].get('disposition','')).strip(),f'{section} 缺 disposition')
            self.assertTrue(str(ledger[section].get('reason','')).strip(),f'{section} 缺理由')
