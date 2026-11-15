"""只读 DORA 类指标报告：数据全部来自 git 历史与 common-dir 里的全量记录，不改仓库里的任何文件。

用法（程序目录下）::

    python -B scripts/dora_report.py [--days 30] [--repo <路径>] [--no-write]

报告同时写到 ``程序/logs/dora_最近.md``（logs 已被忽略）。口径：

- 前置时间：每个「合入 X 到 master」合并提交，从被合入分支第一个独有提交到合并时刻；
- 失败检查点：标题以 ``R<n>-FAIL:`` 开头的提交占 R 轮提交的比例（确切口径，来自提交约定）；
- 7 天内被修复：某轮改动的 ``程序/`` 顶层模块，在其后 7 天内又被标题含「修复」的提交改动，该轮计一次
  （**启发式**，只是返工信号，不是严格的变更失败率）；
- 红灯停留：读 ``full-safe-history.jsonl``（后台全量每次结束追加一行）里首个红到下一个绿的间隔；没有数据写「数据不足」；
- 按来源：提交信息末尾的 ``Agent: <名称>`` 行；未标注归「未标注」。
这些是结果侧信号，不设阈值，也不作为目标。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
REPORT = PROGRAM / 'logs' / 'dora_最近.md'
ROUND_RE = re.compile(r'^R(\d+)(-FAIL)?:')
MERGE_RE = re.compile(r'^R\d+: 合入 (\S+) 到 master')
AGENT_RE = re.compile(r'^Agent: (.+)$', re.M)
WEEK = 7 * 86400


@dataclass
class Commit:
    sha: str
    parents: list
    ts: int
    subject: str
    body: str = ''
    files: set = field(default_factory=set)


def _git(repo, *args):
    return subprocess.run(['git', '-c', 'core.quotepath=false', '-C', str(repo), *args], capture_output=True,
                          text=True, encoding='utf-8', errors='replace').stdout


def collect(repo, days=None, rev='HEAD'):
    """按时间正序返回 ``[Commit]``；``days`` 为 None 取全部历史。"""
    since = ['--since=%d.days' % days] if days else []
    raw = _git(repo, 'log', rev, *since, '--format=%x1e%H%x1f%P%x1f%ct%x1f%s%x1f%b')
    commits = {}
    for record in raw.split('\x1e'):
        parts = record.split('\x1f')
        if len(parts) >= 5 and parts[0].strip():
            sha = parts[0].strip()
            commits[sha] = Commit(sha, parts[1].split(), int(parts[2]), parts[3], parts[4].strip())
    names = _git(repo, 'log', rev, *since, '--name-only', '--format=%x1e%H')
    for record in names.split('\x1e'):
        lines = [line for line in record.splitlines() if line.strip()]
        if lines and lines[0].strip() in commits:
            commits[lines[0].strip()].files = set(lines[1:])
    return sorted(commits.values(), key=lambda commit: commit.ts)


def modules_of(files):
    """``程序/`` 下顶层 .py 与子包的模块名；测试、文档、维护记录不算。"""
    found = set()
    for name in files:
        parts = name.replace('\\', '/').split('/')
        if len(parts) >= 2 and parts[0] == '程序' and parts[1] not in ('tests', 'tasks_round', '维护记录', 'docs', 'logs'):
            if len(parts) == 2 and parts[1].endswith('.py'):
                found.add(parts[1][:-3])
            elif len(parts) > 2 and parts[1] != 'skills':
                found.add(parts[1])
    return found


def lead_times(repo, commits):
    """合并提交的前置时间（秒）：被合入分支第一个独有提交 → 合并时刻。"""
    result = []
    for commit in commits:
        if len(commit.parents) == 2 and MERGE_RE.match(commit.subject):
            stamps = _git(repo, 'log', '--format=%ct', '%s..%s' % tuple(commit.parents)).split()
            if stamps:
                result.append(commit.ts - min(int(stamp) for stamp in stamps))
    return result


def round_commits(commits):
    return [commit for commit in commits if ROUND_RE.match(commit.subject) and len(commit.parents) < 2]


def reworked(commits):
    """启发式：返回 ``(被返工的轮次提交数, 参与统计数, 返工热点 Counter)``。"""
    rounds = [commit for commit in round_commits(commits) if not ROUND_RE.match(commit.subject).group(2)
              and '修复' not in commit.subject and modules_of(commit.files)]
    fixes = [commit for commit in commits if '修复' in commit.subject and len(commit.parents) < 2]
    hot, count = Counter(), 0
    for commit in rounds:
        mine = modules_of(commit.files)
        if any(commit.ts < fix.ts <= commit.ts + WEEK and fix.sha != commit.sha and mine & modules_of(fix.files)
               for fix in fixes):
            count += 1
    for fix in fixes:
        hot.update(modules_of(fix.files))
    return count, len(rounds), hot


def _stamp(text):
    try:
        return int(datetime.fromisoformat(str(text)).timestamp())
    except ValueError:
        return None


def red_dwell(history_path):
    """``full-safe-history.jsonl`` 里每段「首个红 → 下一个绿」的秒数；文件不存在返回 None。"""
    decoder = json.JSONDecoder()
    try:
        rows = [decoder.decode(line) for line in Path(history_path).read_text(encoding='utf-8').splitlines() if line.strip()]
    except (OSError, ValueError):
        return None
    spans, red_at = [], None
    for row in rows:
        stamp = _stamp(row.get('at'))
        if stamp is None:
            continue
        if row.get('ok') is False and red_at is None:
            red_at = stamp
        elif row.get('ok') is True and red_at is not None:
            spans.append(stamp - red_at)
            red_at = None
    return spans


def by_agent(commits):
    """按 ``Agent:`` 行分组：``{名称: (轮次提交数, FAIL 数)}``。"""
    groups = {}
    for commit in round_commits(commits):
        matched = AGENT_RE.search(commit.body)
        name = matched.group(1).strip() if matched else '未标注'
        total, failed = groups.get(name, (0, 0))
        groups[name] = (total + 1, failed + (1 if ROUND_RE.match(commit.subject).group(2) else 0))
    return groups


def _hours(seconds):
    return '%.1f 小时' % (seconds / 3600)


def _median(values):
    ordered = sorted(values)
    return ordered[len(ordered) // 2] if ordered else None


def render(repo, days, history_path=None):
    commits = collect(repo, days)
    rounds = round_commits(commits)
    fails = [commit for commit in rounds if ROUND_RE.match(commit.subject).group(2)]
    leads = lead_times(repo, commits)
    count, considered, hot = reworked(commits)
    spans = red_dwell(history_path) if history_path else None
    lines = ['# DORA 类指标报告（只读，近 %s 天，提交 %d 个，轮次提交 %d 个）' % (days or '全部', len(commits), len(rounds)), '',
             '| 指标 | 数值 | 口径 |', '| --- | --- | --- |']
    lines.append('| 前置时间（中位／最长） | %s | 分支首个独有提交 → 合入 master，共 %d 次合并 |' % (
        '%s ／ %s' % (_hours(_median(leads)), _hours(max(leads))) if leads else '数据不足', len(leads)))
    lines.append('| 失败检查点占比 | %s | `R<n>-FAIL:` 提交 %d／轮次提交 %d |' % (
        '%.1f%%' % (100 * len(fails) / len(rounds)) if rounds else '数据不足', len(fails), len(rounds)))
    lines.append('| 7 天内被修复的轮次比例 | %s | **启发式**：同模块 7 天内又有「修复」提交；%d／%d |' % (
        '%.1f%%' % (100 * count / considered) if considered else '数据不足', count, considered))
    lines.append('| 红灯停留（中位／最长） | %s | 后台全量首个红 → 下一个绿，%s |' % (
        '%s ／ %s' % (_hours(_median(spans)), _hours(max(spans))) if spans else '数据不足',
        '%d 段' % len(spans) if spans else '尚无 full-safe-history.jsonl 记录或没有红过'))
    lines += ['', '## 返工热点（被「修复」提交改动最多的模块，前 15）', '']
    lines += ['- %s：%d 次' % item for item in hot.most_common(15)] or ['- 数据不足']
    lines += ['', '## 按来源（`Agent:` 行）', '', '| 来源 | 轮次提交 | FAIL | FAIL 占比 |', '| --- | --- | --- | --- |']
    for name, (total, failed) in sorted(by_agent(commits).items()):
        lines.append('| %s | %d | %d | %.1f%% |' % (name, total, failed, 100 * failed / total))
    lines += ['', '> 冒烟 8/8、架构门禁数量是健康检查，不是目标；以上结果侧信号才用来判断治理是否有效。']
    return '\n'.join(lines) + '\n'


def common_history(repo):
    common = _git(repo, 'rev-parse', '--git-common-dir').strip()
    path = Path(common)
    return (path if path.is_absolute() else Path(repo) / path) / 'full-safe-history.jsonl'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--days', type=int, default=30, help='统计最近多少天；0 表示全部历史')
    parser.add_argument('--repo', default=str(PROGRAM.parent))
    parser.add_argument('--no-write', action='store_true', help='只打印，不写 logs/dora_最近.md')
    args = parser.parse_args(argv)
    text = render(args.repo, args.days or None, common_history(args.repo))
    if not args.no_write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(text, encoding='utf-8', newline='\n')
    sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
