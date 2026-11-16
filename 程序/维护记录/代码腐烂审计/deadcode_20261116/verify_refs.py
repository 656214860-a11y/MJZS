# -*- coding: utf-8 -*-
"""死代码扫描 B0-2：非存活节点的全仓字符串引用核验（只读，不改文件）。

对 scan1.json 里非 LIVE 节点，逐一构造引用针（dotted 名／顶层裸名／子目录 stem／文件名），
在 程序/ 语料（.py/.pyw/.json/.md/.txt/.yaml，排除数据与记录目录）中做词边界匹配，
产出 refs.json：每个节点被哪些文件以何种形式提及。
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROG = HERE.parents[2]
SCAN = json.loads((HERE / "scan1.json").read_text(encoding="utf-8"))
OUT = HERE / "refs.json"

EXCLUDE_DIRS = {"data", "logs", "private", "tasks_round", "维护记录", ".git", ".wt",
                ".selftmp", "__pycache__", "outputs", "episode", "assets", "reference",
                "voice_asr_venv"}
CORPUS_SUFFIXES = {".py", ".pyw", ".json", ".md", ".txt", ".yaml", ".yml"}


def corpus_files() -> list[Path]:
    files = []
    for p in PROG.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(PROG)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if p.suffix.lower() in CORPUS_SUFFIXES:
            files.append(p)
    pyw = PROG.parent / "启动漫剧制作助手.pyw"
    if pyw.is_file():
        files.append(pyw)
    return files


def needles_for(rel_path: str, dotted: str, is_top: bool) -> dict[str, re.Pattern]:
    needles = {}
    stem = Path(rel_path).stem
    if dotted:
        needles["dotted:" + dotted] = re.compile(r"(?<![\w.])" + re.escape(dotted) + r"(?![\w])")
    if is_top:
        needles["flat:" + stem] = re.compile(r"(?<![\w.])" + re.escape(stem) + r"(?![\w])")
    else:
        needles["stem:" + stem] = re.compile(r"(?<![\w.])" + re.escape(stem) + r"(?![\w])")
        needles["fname:" + Path(rel_path).name] = re.compile(re.escape(Path(rel_path).name))
    return needles


def main() -> None:
    nodes = SCAN["nodes"]
    nonlive = {r: n for r, n in nodes.items() if n["tier"] != "LIVE"}

    # needle_key -> 节点集合；literal = key 冒号后原文（正则断言两侧，字面量即针名本体）
    needle_nodes: dict[str, set[str]] = defaultdict(set)
    needle_rx: dict[str, re.Pattern] = {}
    for r, n in nonlive.items():
        for key, rx in needles_for(r, n.get("dotted", ""), "/" not in r).items():
            needle_nodes[key].add(r)
            needle_rx[key] = rx
    needle_list = [(k, sorted(needle_nodes[k]), needle_rx[k], k.split(":", 1)[1])
                   for k in needle_nodes]

    hits: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    files = corpus_files()
    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel_f = p.relative_to(PROG).as_posix() if p.is_relative_to(PROG) else "<root>/" + p.name
        for key, node_set, rx, literal in needle_list:
            if literal not in text:
                continue
            if rx.search(text):
                for n in node_set:
                    hits[n][key].add(rel_f)

    summary = {}
    for r, n in nonlive.items():
        h = {k: sorted(v) for k, v in hits.get(r, {}).items()}
        all_files = sorted({f for v in h.values() for f in v})
        summary[r] = {
            "tier": n["tier"], "lines": n["lines"], "dotted": n.get("dotted", ""),
            "hits": h, "ref_files": all_files[:40], "ref_file_count": len(all_files),
        }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print("nonlive:", len(nonlive), "corpus files:", len(files), "needles:", len(needle_list))
    zero = [r for r, s in summary.items() if s["ref_file_count"] == 0]
    print("ZERO-REF nodes:", len(zero))
    for r in sorted(zero, key=lambda x: -summary[x]["lines"]):
        s = summary[r]
        print(f"  {s['lines']:>5} {r} [{s['tier']}]")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
