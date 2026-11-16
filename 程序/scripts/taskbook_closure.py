# -*- coding: utf-8 -*-
"""任务书闭环校验器（规则 35，R3039 决策 13）：守卫测试与提交闸共用单一实现。

五项机器检查（诚实边界：机器不核验证据内容真假，真伪靠用户抽检＋处置确认闸）：
a. 完成文件与 ``tasks_round/<主题>任务书.md`` 同名对应、只存 ``任务完成/``、无孤儿文件；
b. 任务书每条验收勾选项在完成文件中有对应条目（逐条覆盖，禁止挑做）；
c. 每条任务给完成证据（轮次号／commit hash）或给处置（转欠账／请求授权／放弃），禁止只写「完成」；
   机器口径：证据/处置标记总数 ≥ 任务条数；
d. 处置条目必须带用户确认凭据（轮次号或「用户确认/对话留痕」字样）；
e. ``任务完成/README.md`` 建档存在。

豁免白名单（只许减少）：``docs/review/`` 下的历史任务书不进扫描面。
"""
from __future__ import annotations

import re
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
TASKS_ROUND = PROGRAM / 'tasks_round'
COMPLETION_DIR = TASKS_ROUND / '任务完成'
README_NAME = 'README.md'
EXEMPT_TASKBOOKS = frozenset({'docs/review/优化任务书_SWE2_20261115.md'})

CHECKBOX_RE = re.compile(r'^\s*-\s*\[[ xX]\]\s*(.*)$', re.MULTILINE)
EVIDENCE_MARK = re.compile(r'R\d{3,}|[0-9a-f]{7,40}|转欠账|请求授权|放弃|不实施|范围外')
DISPOSITION_RE = re.compile(r'转欠账|请求授权|放弃|不实施|范围外')
CONFIRM_RE = re.compile(r'R\d{3,}|用户确认|对话留痕')
CLOSE_DECLARATION_RE = re.compile(r'任务书.*(收尾|完成)|任务完成文件')


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''


def stem_of(taskbook: Path) -> str:
    return taskbook.name[:-len('任务书.md')]


def taskbooks(tasks_round: Path = TASKS_ROUND) -> list[Path]:
    return sorted(p for p in tasks_round.glob('*任务书.md') if p.is_file())


def completion_files(completion_dir: Path = COMPLETION_DIR) -> list[Path]:
    return sorted(p for p in completion_dir.glob('*.md') if p.name != README_NAME)


def checkboxes(taskbook: Path) -> list[str]:
    return [m.group(1).strip() for m in CHECKBOX_RE.finditer(_text(taskbook)) if m.group(1).strip()]


def validate(tasks_round: Path = TASKS_ROUND, completion_dir: Path = COMPLETION_DIR,
             problems: list[str] | None = None) -> list[str]:
    """校验完成文件目录；返回问题清单（空列表＝通过）。未写完成文件的任务书不强制（由提交闸在声明收尾时拦截）。"""
    problems = [] if problems is None else problems
    books = taskbooks(tasks_round)
    completions = completion_files(completion_dir)
    known_stems = {stem_of(b) for b in books}
    # e
    if not (completion_dir / README_NAME).is_file():
        problems.append('任务完成/README.md 建档缺失')
    # a：无孤儿、命名对应
    for done in completions:
        if not any(done.name == stem + '·任务完成.md' for stem in known_stems):
            problems.append('孤儿完成文件（无同名任务书）：%s' % done.name)
    # b/c/d：每个已有完成文件逐条覆盖其任务书
    for book in books:
        done = completion_dir / (stem_of(book) + '·任务完成.md')
        if not done.is_file():
            continue
        tasks = checkboxes(book)
        if not tasks:
            continue
        text = _text(done)
        for task in tasks:
            if task not in text:
                problems.append('%s 缺少条目覆盖：%s' % (done.name, task))
        markers = len(EVIDENCE_MARK.findall(text))
        if markers < len(tasks):
            problems.append('%s 证据/处置标记不足：任务 %d 条、标记 %d 处' % (done.name, len(tasks), markers))
        for line in text.splitlines():
            if DISPOSITION_RE.search(line) and not CONFIRM_RE.search(line):
                problems.append('%s 处置条目缺用户确认凭据：%s' % (done.name, line.strip()[:60]))
    return problems


def declares_closure(message: str, staged_paths: list[str]) -> bool:
    """本轮是否声明任务书收尾/完成：提交信息带收尾字样，或暂存区新增/修改了任务完成文件。"""
    if CLOSE_DECLARATION_RE.search(message):
        return True
    return any('任务完成' in path and path.endswith('.md') for path in staged_paths)
