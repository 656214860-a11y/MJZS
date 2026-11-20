"""只读 DORA 类指标报告：数据全部来自 git 历史与 common-dir 里的全量记录，不改仓库里的任何文件。

用法（程序目录下）::

    python -B scripts/dora_report.py [--days 30] [--repo <路径>] [--no-write]

报告同时写到 ``程序/logs/dora_最近.md``（logs 已被忽略）。口径：

- 前置时间：每个「合入 X 到 master」合并提交，从被合入分支第一个独有提交到合并时刻；
- 失败检查点：标题以 ``R<n>-FAIL:`` 开头的提交占 R 轮提交的比例（确切口径，来自提交约定）；
- 7 天内被修复：某轮改动的 ``程序/`` 顶层模块，在其后 7 天内又被标题含「修复」的提交改动，该轮计一次
  （**启发式**，只是返工信号，不是严格的变更失败率）；
- 红灯停留：读 ``full-safe-history.jsonl``（后台全量每次结束追加一行）里首个红到下一个绿的间隔；没有数据写「数据不足」；
- 全量红灯归因：同一份历史，只认 ``head`` 是完整提交号的行（早期自检往真实历史里写过样例行，红灯停留同样剔除），
  统计窗与 ``--days`` 相同。没有失败文件名的红（中断、超时）单列，不参与下面的判断；其余的红和绿都算「完整全量」。
  测试文件——「偶发」＝同一个提交上，有一次全量红了它、另一次完整全量没红它（代码没变，结果变了）；
  「持续红」＝没有这种证据，且连续 3 次及以上完整全量都红；「疑似偶发」＝以上都不是，但分成两段及以上、每段红一两次就恢复；
  其余「未定」。某次红的全量——有文件正处在连续 3 次及以上的红里记「含持续红」；否则失败文件全是偶发、疑似偶发的记
  「只有偶发」；剩下的记「未定」。历史里只有文件名，分不出「真缺陷」和「环境一直有问题」，两者都落在持续红里；
  偶发文件碰巧连红 3 次及以上时，那几次也记在「含持续红」里，所以「只有偶发」是下限；
- 按来源：提交信息末尾的 ``Agent: <名称>`` 行；未标注归「未标注」。
这些是结果侧信号，不设阈值，也不作为目标。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
REPORT = PROGRAM / 'logs' / 'dora_最近.md'
ROUND_RE = re.compile(r'^R(\d+)(-FAIL)?:')
MERGE_RE = re.compile(r'^R\d+: 合入 (\S+) 到 master')
AGENT_RE = re.compile(r'^Agent: (.+)$', re.M)
HEAD_RE = re.compile(r'[0-9a-f]{40}')
WEEK = 7 * 86400
PERSISTENT = 3  # 同一个测试文件连续这么多次完整全量都红，才算持续红
TOP_FILES = 20
RECENT = 10
FLAKY, SUSPECT, STEADY, UNKNOWN, NAMELESS = '偶发', '疑似偶发', '持续红', '未定', '没有失败文件名'


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


def history_rows(history_path, since=None):
    """``full-safe-history.jsonl`` 里统计窗内的有效记录（按文件顺序，各带 ``stamp``）与被剔除的行数。

    文件读不到返回 ``(None, 0)``。``head`` 不是完整提交号、时间读不出、不是 JSON 的行算无效；
    时间早于 ``since`` 的行在统计窗外，不保留也不计数。
    """
    try:
        lines = Path(history_path).read_text(encoding='utf-8').splitlines()
    except (OSError, ValueError):
        return None, 0
    rows, dropped, decoder = [], 0, json.JSONDecoder()
    for line in lines:
        if not line.strip():
            continue
        try:
            row = decoder.decode(line)
        except ValueError:
            row = None
        stamp = _stamp(row.get('at')) if isinstance(row, dict) else None
        if stamp is not None and since is not None and stamp < since:
            continue
        if stamp is None or not HEAD_RE.fullmatch(str(row.get('head') or '')):
            dropped += 1
        else:
            rows.append(dict(row, stamp=stamp))
    return rows, dropped


def red_dwell(history_path, since=None):
    """有效记录里每段「首个红 → 下一个绿」的秒数；文件读不到返回 None。"""
    rows, _dropped = history_rows(history_path, since)
    if rows is None:
        return None
    spans, red_at = [], None
    for row in rows:
        if row.get('ok') is False and red_at is None:
            red_at = row['stamp']
        elif row.get('ok') is True and red_at is not None:
            spans.append(row['stamp'] - red_at)
            red_at = None
    return spans


def _tally(slot, row):
    slot[0] += 1
    slot[1] += row.get('seconds') or 0


def red_breakdown(rows):
    """把红的全量拆成偶发与持续（口径见模块说明），``rows`` 来自 ``history_rows``。

    返回 ``(各类红的全量 {类别: [次数, 秒数]}, 各测试文件 {名称: {kind, reds, streaks, flips, last}})``；
    ``streaks`` 是每段连续红的次数，``flips`` 是红绿不一的提交数。
    """
    runs = {kind: [0, 0] for kind in (FLAKY, STEADY, UNKNOWN, NAMELESS)}
    files, complete, heads, previous = {}, [], {}, set()
    for row in rows:
        failed = set() if row.get('ok') is True else {str(name) for name in row.get('failed_files') or []}
        if row.get('ok') is not True and not failed:
            _tally(runs[NAMELESS], row)  # 中断或超时：说明不了任何单个文件，也不打断连续段
            continue
        spots = {}
        for name in failed:
            info = files.setdefault(name, {'reds': 0, 'streaks': [], 'flips': 0, 'last': ''})
            info['reds'] += 1
            info['last'] = str(row.get('at'))
            if name in previous:
                info['streaks'][-1] += 1
            else:
                info['streaks'].append(1)
            spots[name] = len(info['streaks']) - 1
        complete.append((row, spots))
        heads.setdefault(row.get('head'), []).append(failed)
        previous = failed
    for outcomes in heads.values():
        for name in set().union(*outcomes):
            if any(name not in failed for failed in outcomes):
                files[name]['flips'] += 1
    for info in files.values():
        info['kind'] = (FLAKY if info['flips'] else STEADY if max(info['streaks']) >= PERSISTENT
                        else SUSPECT if len(info['streaks']) > 1 else UNKNOWN)
    for row, spots in complete:
        if not spots:
            continue
        if any(files[name]['streaks'][spot] >= PERSISTENT for name, spot in spots.items()):
            kind = STEADY
        elif all(files[name]['kind'] in (FLAKY, SUSPECT) for name in spots):
            kind = FLAKY
        else:
            kind = UNKNOWN
        _tally(runs[kind], row)
    return runs, files


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


def render_reds(rows, dropped):
    """「全量红灯归因」一节的各行；``rows``、``dropped`` 来自 ``history_rows``。"""
    lines = ['', '## 全量红灯归因（偶发与持续分开）', '']
    skipped = '；另有 %d 行无效记录未计入（head 不是完整提交号，或时间读不出）' % dropped if dropped else ''
    if not rows:
        return lines + ['- 数据不足：统计窗内没有有效的全量记录' + skipped]
    runs, files = red_breakdown(rows)
    green = sum(1 for row in rows if row.get('ok') is True)
    red = len(rows) - green
    recent = rows[-RECENT:]
    lines += ['有效全量 %d 次（绿 %d／红 %d），%s → %s%s。最近 %d 次（从旧到新）：%s。' % (
        len(rows), green, red, rows[0].get('at'), rows[-1].get('at'), skipped, len(recent),
        ''.join('绿' if row.get('ok') is True else '红' for row in recent)), '',
              '| 这次红的原因 | 次数 | 占红的比例 | 耗时 |', '| --- | --- | --- | --- |']
    for kind, label in ((FLAKY, '只有偶发、疑似偶发的文件'), (STEADY, '含持续红的文件（连续 %d 次及以上）' % PERSISTENT),
                        (UNKNOWN, '未定（文件只红过一小段）'), (NAMELESS, '没有失败文件名（中断或超时）')):
        count, seconds = runs[kind]
        lines.append('| %s | %d | %s | %s |' % (label, count, '%.1f%%' % (100 * count / red) if red else '—', _hours(seconds)))
    ranked = sorted(files, key=lambda name: (-files[name]['reds'], name))
    flaky = [name for name in ranked if files[name]['kind'] in (FLAKY, SUSPECT)]
    steady = [name for name in ranked if files[name]['kind'] == STEADY]
    lines += ['', '### 偶发与疑似偶发的测试文件（共 %d 个，按红的次数列前 %d）' % (len(flaky), TOP_FILES), '',
              '| 测试文件 | 判定 | 红的次数 | 分成几段 | 最长连续 | 红绿不一的提交 | 最近一次红 |', '| --- | --- | --- | --- | --- | --- | --- |']
    for name in flaky[:TOP_FILES]:
        info = files[name]
        lines.append('| %s | %s | %d | %d | %d | %d | %s |' % (
            name, info['kind'], info['reds'], len(info['streaks']), max(info['streaks']), info['flips'], info['last']))
    lines += ['', '### 持续红的测试文件（共 %d 个，按红的次数列前 %d）' % (len(steady), TOP_FILES), '',
              '| 测试文件 | 红的次数 | 分成几段 | 最长连续 | 最近一次红 |', '| --- | --- | --- | --- | --- |']
    for name in steady[:TOP_FILES]:
        info = files[name]
        lines.append('| %s | %d | %d | %d | %s |' % (name, info['reds'], len(info['streaks']), max(info['streaks']), info['last']))
    lines += ['', '另有 %d 个文件未定（只红过一小段，看不出是哪一种）。「只有偶发」是下限：偶发文件连红 %d 次及以上时，'
              '那几次记在「含持续红」里。判定口径见脚本开头。' % (len(files) - len(flaky) - len(steady), PERSISTENT)]
    return lines


def render(repo, days, history_path=None):
    commits = collect(repo, days)
    rounds = round_commits(commits)
    fails = [commit for commit in rounds if ROUND_RE.match(commit.subject).group(2)]
    leads = lead_times(repo, commits)
    count, considered, hot = reworked(commits)
    since = time.time() - days * 86400 if days else None
    spans = red_dwell(history_path, since) if history_path else None
    rows, dropped = history_rows(history_path, since) if history_path else (None, 0)
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
    lines += render_reds(rows, dropped)
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
