"""规则→守卫测试对照：AGENTS §2.3、§2.5 的每条规则登记它的守卫测试，没有守卫的规则一目了然。

用法（程序目录下）::

    python -B scripts/rule_guard_map.py            # 打印对照表
    python -B scripts/rule_guard_map.py --write    # 刷新 维护记录/规则守卫对照.md（生成物，不手工编辑）

登记在 ``维护记录/规则守卫基线.json`` 的 ``guards``（编号→测试文件，须真实存在）。没有登记的规则列为“暂无”，
其上限固定在 ``tests/architecture/test_rule_guard_map.py`` 的 ``UNGUARDED_CEILING``，只许减少；
补了测试就登记并同步收紧上限，改为“降为建议”须经用户确认。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))
import infra.file_cache as file_cache  # noqa: E402

AGENTS = PROGRAM / 'AGENTS.md'
ARCHITECTURE = PROGRAM / 'architecture.md'
BASELINE = PROGRAM / '维护记录' / '规则守卫基线.json'
REPORT = PROGRAM / '维护记录' / '规则守卫对照.md'
SECTIONS = ('### 2.3 ', '## 2.5 ')
LR_SECTION = '### 层间关系规范'
RULE_LINE = re.compile(r'^(\d+[a-z]?)\. (?:\*\*([^*]+)\*\*)?(.*)$')
LR_ROW = re.compile(r'^\|\s*(LR-\d+)\s*\|\s*([^|]+?)\s*\|')


def parse_rules(text):
    """``[(编号, 标题)]``：只取 §2.3 与 §2.5 里行首为「编号. 」的规则。"""
    rules, active = [], False
    for line in text.splitlines():
        if line.startswith('#'):
            active = line.startswith(SECTIONS)
            continue
        matched = RULE_LINE.match(line) if active else None
        if matched:
            title = (matched.group(2) or matched.group(3)).strip()
            rules.append((matched.group(1), title[:24] + ('…' if len(title) > 24 else '')))
    return rules


def parse_arch_rules(text):
    """``[(编号, 标题)]``：architecture.md「层间关系规范」表的 LR-01~LR-10。"""
    rules, active = [], False
    for line in text.splitlines():
        if line.startswith('### '):
            active = line.startswith(LR_SECTION)
            continue
        matched = LR_ROW.match(line) if active else None
        if matched:
            title = matched.group(2).strip().split('：')[0].split(':')[0].strip()
            rules.append((matched.group(1), title[:24] + ('…' if len(title) > 24 else '')))
    return rules


def load_guards(path=BASELINE):
    return file_cache.read_json(Path(path)).get('guards', {})


def build(agents=AGENTS, baseline=BASELINE, architecture=ARCHITECTURE):
    guards = load_guards(baseline)
    rows = [(number, title, guards.get(number, []))
            for number, title in parse_rules(Path(agents).read_text(encoding='utf-8'))]
    rows += [(number, title, guards.get(number, []))
             for number, title in parse_arch_rules(Path(architecture).read_text(encoding='utf-8'))]
    return rows


def render(rows):
    lines = ['# 规则守卫对照（生成物，运行 `python -B scripts/rule_guard_map.py --write` 刷新，不手工编辑）', '',
             '| 规则 | 标题 | 守卫测试 |', '| --- | --- | --- |']
    for number, title, files in rows:
        lines.append('| %s | %s | %s |' % (number, title.replace('|', '/'), '、'.join(Path(f).name for f in files) if files else '**暂无**'))
    return '\n'.join(lines) + '\n'


def unguarded(rows):
    return sorted(number for number, _, files in rows if not files)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--write', action='store_true', help='写 维护记录/规则守卫对照.md')
    args = parser.parse_args(argv)
    text = render(build())
    if args.write:
        REPORT.write_text(text, encoding='utf-8', newline='\n')
    sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
