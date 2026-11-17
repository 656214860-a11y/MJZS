# -*- coding: utf-8 -*-
"""死代码扫描 B0-3：给 refs.json 的每条命中打上下文标签，产出分类结论。

上下文类别：
  IMPORT   —— 真实 import/from 语句（区分生产还是测试消费者）
  PATCH    —— mock.patch / import_module / __import__ / .module( 字符串目标
  PATH_REF —— '<name>.py' 文件路径引用（架构门禁、清单、发布脚本）
  REGISTRY —— _layers/_scan/棘轮登记表里的名字登记
  DOC      —— .md/.txt 文档提及
  MENTION  —— 其余（注释、docstring、日志名、巧合词）
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROG = HERE.parents[2]
REFS = json.loads((HERE / "refs.json").read_text(encoding="utf-8"))
SCAN = json.loads((HERE / "scan1.json").read_text(encoding="utf-8"))
OUT = HERE / "classified.json"

IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+")
PATCH_RE = re.compile(r"patch\(|import_module|__import__|\.module\(|importorskip|patch\.object")
REGISTRY_FILES = ("_layers.py", "_scan.py", "ratchet", "基准", "registry")


def classify_file(rel: str, lines: list[str], needles: dict[str, str]) -> dict[str, set[str]]:
    """needles: {needle_key: literal}；返回 {类别: {文件}}。"""
    out: dict[str, set[str]] = defaultdict(set)
    for key, lit in needles.items():
        kind = key.split(":", 1)[0]
        if kind == "fname":
            rx = re.compile(re.escape(lit))
        elif kind == "dotted":
            rx = re.compile(r"(?<![\w.])" + re.escape(lit) + r"(?![\w])")
        else:
            rx = re.compile(r"(?<![\w.])" + re.escape(lit) + r"(?![\w])")
        for i, ln in enumerate(lines):
            if not rx.search(ln):
                continue
            s = ln.strip()
            if IMPORT_RE.match(s):
                out["IMPORT"].add(rel)
            elif PATCH_RE.search(s):
                out["PATCH"].add(rel)
            elif s.endswith(".py") or ".py'" in s or '.py"' in s:
                out["PATH_REF"].add(rel)
            elif any(t in rel for t in REGISTRY_FILES):
                out["REGISTRY"].add(rel)
            elif rel.endswith((".md", ".txt")):
                out["DOC"].add(rel)
            else:
                out["MENTION"].add(rel)
            break  # 每文件每针只记一次最强类别? 不——改为记全部类别，见下
    return out


def main() -> None:
    # 重新扫描命中行（refs.json 只有文件级，需回到文件取行）
    result = {}
    for r, s in REFS.items():
        needles = {}
        for k in s["hits"]:
            needles[k] = k.split(":", 1)[1]
        cats: dict[str, set[str]] = defaultdict(set)
        examples: dict[str, list[str]] = defaultdict(list)
        all_hit_files = sorted({f for v in s["hits"].values() for f in v})
        for f in all_hit_files:
            fp = PROG / f if not f.startswith("<root>") else PROG.parent / f[7:]
            if not fp.is_file():
                continue
            try:
                lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            is_doc = f.endswith((".md", ".txt"))
            priority = {"IMPORT": 5, "PATCH": 4, "PATH_REF": 3, "REGISTRY": 2, "DOC": 1, "MENTION": 0}
            for key, lit in needles.items():
                kind = key.split(":", 1)[0]
                if kind == "fname":
                    rx = re.compile(re.escape(lit))
                else:
                    rx = re.compile(r"(?<![\w.])" + re.escape(lit) + r"(?![\w])")
                best_cat, best_rank, best_line = None, -1, ""
                for ln in lines:
                    if not rx.search(ln):
                        continue
                    st = ln.strip()
                    # IMPORT 只认真平铺模块引用：'import <lit>'/'from <lit> import'/'import <lit> as'
                    # 'import pkg.<lit> as <lit>' 的别名命中不算（实体模块经包路径导入）。
                    if re.match(r"\s*(?:import|from)\s+" + re.escape(lit) + r"(?=[\s,]|$)", ln):
                        cat = "IMPORT"
                    elif PATCH_RE.search(st):
                        cat = "PATCH"
                    elif ".py" in st:
                        cat = "PATH_REF"
                    elif any(t in f for t in REGISTRY_FILES):
                        cat = "REGISTRY"
                    elif is_doc:
                        cat = "DOC"
                    else:
                        cat = "MENTION"
                    if priority[cat] > best_rank:
                        best_cat, best_rank, best_line = cat, priority[cat], st[:110]
                        if best_rank == 5:
                            break
                if best_cat:
                    cats[best_cat].add(f)
                    if len(examples[best_cat]) < 3:
                        examples[best_cat].append(f"{f}: {best_line}")
        prod_import = sorted(f for f in cats.get("IMPORT", set()) if not f.startswith(("tests/", "scripts/", "skills/", "附加工具/", "维护记录/")) and "/" not in f or f.startswith(("agent/", "orchestrator/", "domain/", "infra/", "contract/", "ui/", "voice_engine/", "batch_frames_tool/")))
        test_import = sorted(f for f in cats.get("IMPORT", set()) if f not in prod_import)
        result[r] = {
            "tier": s["tier"], "lines": s["lines"], "dotted": s["dotted"],
            "cats": {k: sorted(v) for k, v in cats.items()},
            "prod_import_files": prod_import,
            "examples": dict(examples),
        }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    # 打印非 LIVE 节点的分类摘要
    for r, s in sorted(result.items(), key=lambda kv: -kv[1]["lines"]):
        cats = {k: len(v) for k, v in s["cats"].items() if v}
        if not cats:
            continue
        print(f"{s['lines']:>5} {r:55s} [{s['tier']:11s}] {cats}")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
