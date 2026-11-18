# -*- coding: utf-8 -*-
"""T8 变异测试抽样：对 L0 契约层纯函数注入机械变异，跑对应测试看是否被杀死。

开发期工具，不进发布包；不作为硬门禁，只产报告。
用法：python -B scripts/mutation_sample.py [--json]
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable

# 每个位点：(模块, 测试文件, 标签, 原文, 变异文)。原文必须在模块源里唯一出现。
SITES = [
    ("contract.artifact_schema", "test_artifact_schema.py",
     "validate 版本不一致翻转", "elif found != item['version']:", "elif found == item['version']:"),
    ("contract.artifact_schema", "test_artifact_schema.py",
     "migrate 阶梯循环边界偏一", "while current < target:", "while current <= target:"),
    ("contract.artifact_schema", "test_artifact_schema.py",
     "stamp 默认版本归零", "int(version if version is not None else item['version'])",
     "int(version if version is not None else 0)"),
    ("contract.shot_batches", "test_shot_batches.py",
     "duration 空串回退漏判", "if value in (None, ''):", "if value is None:"),
    ("contract.shot_batches", "test_shot_batches.py",
     "批次满员边界偏一", "len(current) >= cap_shots", "len(current) > cap_shots"),
    ("contract.shot_batches", "test_shot_batches.py",
     "批次秒数上限放宽", "seconds + duration(item) > cap", "seconds + duration(item) >= cap"),
    ("contract.shot_batches", "test_shot_batches.py",
     "三元组一致性翻转", "triplet(item) != triplet(current[-1])",
     "triplet(item) == triplet(current[-1])"),
    ("contract.shot_batches", "test_shot_batches.py",
     "normalize 非 dict 输入漏挡", "out = dict(shot) if isinstance(shot, dict) else {}",
     "out = dict(shot)"),
]

_RUNNER = r'''
import sys, unittest
import importlib.util
spec = importlib.util.spec_from_file_location(%(mod)r, %(mut)r)
module = importlib.util.module_from_spec(spec)
sys.modules[%(mod)r] = module
spec.loader.exec_module(module)
sys.path.insert(0, %(tests)r)
sys.path.insert(0, %(root)r)
import importlib
test_mod = importlib.import_module(%(test)r[:-3])
suite = unittest.TestLoader().loadTestsFromModule(test_mod)
result = unittest.TextTestRunner(verbosity=0, stream=open(%(nul)r, "w", encoding="utf-8")).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
'''


def _apply(module: str, old: str, new: str) -> Path:
    rel = module.replace(".", "/") + ".py"
    source = (ROOT / rel).read_text(encoding="utf-8")
    if source.count(old) != 1:
        raise RuntimeError("位点不唯一或不存在：%s / %r" % (module, old))
    tmp = Path(tempfile.mkdtemp(prefix="mut_"))
    target = tmp / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.replace(old, new), encoding="utf-8")
    return target


def run_sites(sites=SITES, timeout=120):
    """逐位点跑变异体；返回结果列表。"""
    rows = []
    for module, test_file, label, old, new in sites:
        mutant = _apply(module, old, new)
        code = _RUNNER % {
            "mod": module, "mut": str(mutant), "test": test_file,
            "tests": str(ROOT / "tests"), "root": str(ROOT), "nul": "nul" if sys.platform == "win32" else "/dev/null",
        }
        try:
            proc = subprocess.run([PYTHON, "-B", "-c", code], cwd=str(ROOT),
                                  capture_output=True, text=True, timeout=timeout,
                                  encoding='utf-8', errors='replace')
        except subprocess.TimeoutExpired:
            rows.append({"module": module, "test": test_file, "site": label,
                         "verdict": "错误", "stderr_tail": "运行超过 %d 秒被回收" % timeout})
            continue
        if proc.returncode == 0:
            verdict = "存活"
        elif proc.returncode == 1:
            verdict = "杀死"
        else:
            verdict = "错误"
        rows.append({"module": module, "test": test_file, "site": label,
                     "verdict": verdict, "stderr_tail": (proc.stderr or "")[-200:]})
    return rows


def render_report(rows):
    killed = sum(1 for r in rows if r["verdict"] == "杀死")
    lines = ["# 变异测试抽样报告（T8）", "",
             "对 L0 契约层纯函数注入 %d 个机械变异位点，跑对应测试文件判定。" % len(rows),
             "杀死 %d / 存活 %d / 错误 %d。" % (
                 killed,
                 sum(1 for r in rows if r["verdict"] == "存活"),
                 sum(1 for r in rows if r["verdict"] == "错误")), "",
             "| 模块 | 位点 | 判定 |", "| --- | --- | --- |"]
    lines += ["| %s | %s | %s |" % (r["module"], r["site"], r["verdict"]) for r in rows]
    survivors = [r for r in rows if r["verdict"] != "杀死"]
    if survivors:
        lines += ["", "## 存活/错误位点（弱断言候选）", ""]
        lines += ["- %s / %s：%s" % (r["module"], r["test"], r["site"]) for r in survivors]
    return "\n".join(lines) + "\n"


def main(argv=None):
    rows = run_sites()
    if argv and "--json" in (argv or sys.argv[1:]):
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        print(render_report(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
