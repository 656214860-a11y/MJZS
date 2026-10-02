"""R743 报告模式：固定范围与白名单，不读取台账。"""
from __future__ import annotations
import ast
import unittest
import json
from pathlib import Path
from tests.architecture._scan import parse, production_files
ROOT=Path(__file__).resolve().parents[2]
CANARY=Path(__file__).with_name('_canary')
# 21 白名单：明确的平台适配器／外部工具；其余 OS 进程调用须报告。
P21={'platform_tools','native_apps','app_shortcut','codex_paste','codex_tasks','console_submit','engine_probe','previs_automation','qwen_adapter','workflow_engines'}
# 25 白名单：pet_bus 已登记事件；自定义字面量须报告。
E25={'stage.executing','stage.failed','stage.retrying','stage.paused','script.completed','budget.warning','budget.exceeded','notify.aggregate','intent.command'}
# 26 白名单：唯一模型池、路由与供应商适配器。
P26={'model_pool','model_router','qwen_adapter','comfy_service','cloud_assets','cloud_video'}
# 24 白名单：两份注册表是产品插件入口；clipboard_lock 仅在非 Windows 条件分支加载 Unix
# 标准库 fcntl，属于跨平台锁实现而非产品动态插件，不能把它记作未登记业务动态导入。
P24={'ui_plugin_registry','stage_handler_registry','clipboard_lock'}
def dot(n):
    if isinstance(n,ast.Name): return n.id
    if isinstance(n,ast.Attribute):
        p=dot(n.value); return f'{p}.{n.attr}' if p else None
def scan(kind, paths=None):
    out=set()
    for p in (production_files() if paths is None else paths):
        tree=parse(p) if paths is None else ast.parse(p.read_text(encoding='utf-8'))
        for n in ast.walk(tree):
            if not isinstance(n,ast.Call): continue
            name,mod=dot(n.func),p.stem
            hit=(kind=='21' and name in {'subprocess.run','subprocess.Popen','os.startfile'} and mod not in P21) or (kind=='22' and name in {'os.remove','os.unlink','shutil.rmtree'} and mod not in {'storage_maintenance','file_cache','asset_batch_lifecycle','storyboard_lifecycle'}) or (kind=='24' and name in {'__import__','import_module','importlib.import_module'} and mod not in P24) or (kind=='25' and name in {'pet_bus.emit_safe','self._emit','pet._emit'} and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value not in E25) or (kind=='26' and name in {'requests.get','requests.post','urllib.request.urlopen'} and mod not in P26)
            if hit: out.add(f'{p.name}:{n.lineno}')
    return out
class CoverageAuditCanaryTests(unittest.TestCase):
    def test_each_predicate_hits_canary(self):
        names={'21':'audit21_platform_violation.py','22':'audit22_violation.py','24':'audit24_violation.py','25':'audit25_event_violation.py','26':'audit26_violation.py'}
        for kind,name in names.items():
            self.assertTrue(scan(kind,[CANARY/name]),f'{kind} 金丝雀漏报')
    def test_24_26_real_hits_are_ledgered(self):
        ledger=json.loads((ROOT/'维护记录'/'架构统一基数.json').read_text(encoding='utf-8'))
        for kind,section in (('24','覆盖率审计24'),('26','覆盖率审计26')):
            known={f"{x['file']}:{x['point']}" for x in ledger[section]['items']}
            self.assertTrue(scan(kind)<=known, f'{section} 新增未入账命中')
