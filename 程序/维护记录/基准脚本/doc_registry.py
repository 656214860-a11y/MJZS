"""工程文档登记表快照与双向核对。

解析 ``程序/docs/records/工程文档登记表.md`` 的登记表，与文件系统双向比对：

- 已登记但不存在 → 报错；
- 存在（在登记范围内）但未登记 → 报错；
- 层级 / 性质 取值越出任务书定义域 → 报错。

全部一致时把每份文档的字节数、REQ/DES 条数、路径存在性写入
``程序/维护记录/文档登记快照.json``，供 ② 门禁与 ③ 生成器复用。

用法::

    python -B 维护记录/基准脚本/doc_registry.py            # 核对并写快照
    python -B 维护记录/基准脚本/doc_registry.py --check    # 只核对，不写快照
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[2]
REGISTRY = PROGRAM / "docs" / "records" / "工程文档登记表.md"
SNAPSHOT = PROGRAM / "维护记录" / "文档登记快照.json"

# 登记范围（任务书轮 0）：程序根 *.md ＋ docs/**/*.md（含 docs/adr）＋ governance/**/*.md。
SCOPES = ("*.md", "docs/**/*.md", "governance/**/*.md")

LAYERS = {"L0", "L0P", "L1", "L2", "L3", "L4", "L5", "全局"}
NATURES = {"权威", "派生"}
STAGES = {"全局", "—"} | {f"S{n:02d}" for n in range(1, 14)}

ROW = re.compile(r"^\|(.+)\|\s*$")
REQ_RE = re.compile(r"REQ-S\d+-\d+")
DES_RE = re.compile(r"DES-S\d+-\d+")


def safe_document(path: Path, program: Path | None = None) -> bool:
    """Only read owned regular files; never traverse symlinks or junctions."""
    program = PROGRAM if program is None else program
    try:
        relative = path.relative_to(program)
    except ValueError:
        return False
    current = program
    for part in relative.parts:
        current = current / part
        if current.is_symlink() or (hasattr(current, 'is_junction') and current.is_junction()):
            return False
    return path.is_file() and path.resolve().is_relative_to(program.resolve())


def disk_paths() -> set[str]:
    found: set[str] = set()
    for pattern in SCOPES:
        for path in PROGRAM.glob(pattern):
            if path.is_file():
                if not safe_document(path):
                    raise ValueError('文档路径越界或含链接：' + path.relative_to(PROGRAM).as_posix())
                found.add(path.relative_to(PROGRAM).as_posix())
    return found


def registry_rows() -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    if not safe_document(REGISTRY):
        raise ValueError('登记表不是受控普通文件')
    for line in REGISTRY.read_text(encoding="utf-8").splitlines():
        match = ROW.match(line.strip())
        if not match:
            continue
        cells = [cell.strip().strip("`").strip() for cell in match.group(1).split("|")]
        if len(cells) != 6 or cells[0] in {"文档路径", ""} or set(cells[0]) <= {"-", " "}:
            continue
        if cells[0] in rows:
            raise ValueError('文档路径重复登记：' + cells[0])
        rows[cells[0]] = {
            "层级": cells[1],
            "阶段": cells[2],
            "性质": cells[3],
            "最后核验轮次": cells[4],
            "消费者": cells[5],
        }
    return rows


def layer_tokens(value: str) -> list[str]:
    return [token.strip() for token in value.split(",") if token.strip()]


def duplicate_topics(rows: dict[str, dict[str, str]]) -> list[str]:
    """同名现行权威不能同时散落 docs 子目录；迁移台账与历史证据不参与。"""
    owners: dict[str, list[str]] = {}
    for path, meta in rows.items():
        if not path.startswith('docs/') or meta['性质'] != '权威':
            continue
        title = Path(path).stem
        owners.setdefault(title, []).append(path)
    return ['重复现行权威主题：%s → %s' % (title, ', '.join(sorted(paths)))
            for title, paths in sorted(owners.items()) if len(paths) > 1]


def collect_errors(rows: dict[str, dict[str, str]], on_disk: set[str]) -> list[str]:
    errors: list[str] = []
    for path, meta in sorted(rows.items()):
        if path not in on_disk:
            errors.append(f"已登记但不存在：{path}")
            continue
        for token in layer_tokens(meta["层级"]):
            if token not in LAYERS:
                errors.append(f"层级取值越界：{path} → {token}")
        if meta["阶段"] not in STAGES:
            errors.append(f"阶段取值越界：{path} → {meta['阶段']}")
        if meta["性质"] not in NATURES:
            errors.append(f"性质取值越界：{path} → {meta['性质']}")
    for path in sorted(on_disk - set(rows)):
        errors.append(f"存在但未登记：{path}")
    errors.extend(duplicate_topics(rows))
    return errors


def doc_stats(path: Path) -> dict:
    if not safe_document(path):
        raise ValueError('拒绝读取仓库外或链接文档')
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "bytes": len(path.read_bytes()),
        "req_count": len(set(REQ_RE.findall(text))),
        "des_count": len(set(DES_RE.findall(text))),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="工程文档登记表核对与快照")
    parser.add_argument("--check", action="store_true", help="只核对，不写快照")
    args = parser.parse_args()

    if not REGISTRY.is_file():
        print(f"登记表不存在：{REGISTRY}", file=sys.stderr)
        return 2

    try:
        rows = registry_rows()
        on_disk = disk_paths()
    except (OSError, ValueError) as exc:
        print('登记输入无效：' + str(exc), file=sys.stderr)
        return 2
    errors = collect_errors(rows, on_disk)
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        print(f"登记表核对失败：{len(errors)} 处不一致", file=sys.stderr)
        return 1

    docs = {}
    for path in sorted(rows):
        full = PROGRAM / path
        entry = {"exists": full.is_file(), **rows[path]}
        if full.is_file():
            entry.update(doc_stats(full))
        docs[path] = entry

    if not args.check:
        snapshot = {
            "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "registry": "docs/records/工程文档登记表.md",
            "scopes": list(SCOPES),
            "count": len(docs),
            "docs": docs,
        }
        SNAPSHOT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    print(f"登记表核对通过：{len(docs)} 份文档" + ("" if args.check else f"，快照已写 {SNAPSHOT.name}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
