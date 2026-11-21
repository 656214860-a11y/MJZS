"""阶段文件「接口」「交互」两节的结构守卫。

写法全文见 ``docs/process/阶段文档写法.md``，本守卫检查六条规则：

- R1 ``## 接口`` 与 ``## 交互`` 两个二级标题都要在，都在 ``## 设计`` 之后，
  ``## 接口`` 在 ``## 交互`` 之前。
- R2 ``## 接口`` 下依次有三级标题：读入、写出、完成判定与交接、对外调用；
  ``## 交互`` 下依次有：页面区域、控件与操作、页面状态、键盘、右键与拖放。
- R3 表格行第一格形如 ``IF-Sxx-nn``／``UX-Sxx-nn``：Sxx 必须等于本文件的阶段号；
  同一文件内编号不重复；IF 编号只出现在「接口」节，UX 编号只出现在「交互」节。
- R4 这些行的最后一格必须以 ✅、🟡、⬜、❓ 之一开头。
- R5 最后一格以 ⬜ 或 🟡 开头的，这一格里必须有「来源：」或「建议，待确认」。
- R6 最后一格以 ✅ 开头的，整行至少有一处反引号包住的内容。

两节一个都没有时 ``problems`` 返回空清单；``REQUIRE_ALL = True`` 时缺节即报
（DOC-Z1 收口轮再把常量改成 True）。
"""
from __future__ import annotations

import re
import sys
import unittest
from unittest.mock import patch

from tests.architecture.test_requirement_traceability import stage_files

REQUIRE_ALL = False

_IFACE_SECTIONS = ('读入', '写出', '完成判定与交接', '对外调用')
_UX_SECTIONS = ('页面区域', '控件与操作', '页面状态', '键盘、右键与拖放')
_ID = re.compile(r'(IF|UX)-S(\d{2})-(\d{2})')
_STATUS_MARKS = ('✅', '🟡', '⬜', '❓')
_CODE_SPAN = re.compile(r'`[^`\n]+`')


def _active_lines(text: str) -> list[tuple[int, str]]:
    """返回 ``(行起始偏移, 行文本)``，跳过 ``` 围栏内的行（样例代码不参与检查）。"""
    lines = []
    in_fence = False
    offset = 0
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip('\r\n')
        if line.strip().startswith('```'):
            in_fence = not in_fence
        elif not in_fence:
            lines.append((offset, line))
        offset += len(raw)
    return lines


def _cells(line: str) -> list[str]:
    cells = [cell.strip() for cell in line.strip().split('|')]
    if cells and cells[0] == '':
        cells = cells[1:]
    if cells and cells[-1] == '':
        cells = cells[:-1]
    return cells


def problems(text: str, stage: str) -> list[str]:
    """检查一个阶段文件全文的「接口」「交互」两节，返回问题清单。

    ``stage`` 形如 ``'S05'``。函数不读文件，便于用样例测试。
    """
    issues: list[str] = []
    lines = _active_lines(text)
    h2 = [(pos, line[3:].strip()) for pos, line in lines if line.startswith('## ')]
    titles = [title for _, title in h2]
    has_iface = '接口' in titles
    has_ux = '交互' in titles
    if not has_iface and not has_ux:
        if REQUIRE_ALL:
            issues.append('缺少「## 接口」「## 交互」两节')
        return issues

    # R1：两个二级标题都要有，都在「## 设计」之后，「接口」在「交互」之前。
    pos_of = {}
    end_of = {}
    for index, (pos, title) in enumerate(h2):
        pos_of.setdefault(title, pos)
        end_of.setdefault(title, h2[index + 1][0] if index + 1 < len(h2) else len(text))
    if not has_iface:
        issues.append('缺少「## 接口」节')
    if not has_ux:
        issues.append('缺少「## 交互」节')
    if '设计' not in pos_of:
        issues.append('缺少「## 设计」节，无法确认两节在文末的位置')
    else:
        for title in ('接口', '交互'):
            if title in pos_of and pos_of[title] < pos_of['设计']:
                issues.append('「## %s」必须出现在「## 设计」之后' % title)
    if '接口' in pos_of and '交互' in pos_of and pos_of['接口'] > pos_of['交互']:
        issues.append('「## 接口」必须在「## 交互」之前')

    # R2：两节下的三级标题固定四个、顺序不变。
    h3 = [(pos, line[4:].strip()) for pos, line in lines if line.startswith('### ')]
    for title, required in (('接口', _IFACE_SECTIONS), ('交互', _UX_SECTIONS)):
        if title not in pos_of:
            continue
        found = tuple(name for pos, name in h3
                      if pos_of[title] <= pos < end_of[title])
        if found != required:
            issues.append('「## %s」下的三级标题应依次为 %s，实际为 %s'
                          % (title, '、'.join(required), '、'.join(found) or '（无）'))

    # R3–R6：编号行的阶段号、唯一性、所在节，以及最后一格的状态记号。
    iface_range = (pos_of.get('接口'), end_of.get('接口'))
    ux_range = (pos_of.get('交互'), end_of.get('交互'))
    seen: dict[str, int] = {}
    for pos, line in lines:
        if not line.lstrip().startswith('|'):
            continue
        cells = _cells(line)
        if not cells:
            continue
        matched = _ID.fullmatch(cells[0])
        if not matched:
            continue
        kind, number = matched.group(1), 'S' + matched.group(2)
        rid = matched.group(0)
        if number != stage:
            issues.append('%s 的阶段号应为 %s' % (rid, stage))
        if rid in seen:
            issues.append('编号 %s 在同一文件内重复' % rid)
        else:
            seen[rid] = pos
        in_iface = iface_range[0] is not None and iface_range[0] <= pos < iface_range[1]
        in_ux = ux_range[0] is not None and ux_range[0] <= pos < ux_range[1]
        if kind == 'IF' and not in_iface:
            issues.append('IF 编号 %s 只许出现在「接口」节' % rid)
        if kind == 'UX' and not in_ux:
            issues.append('UX 编号 %s 只许出现在「交互」节' % rid)
        status = cells[-1]
        if not status.startswith(_STATUS_MARKS):
            issues.append('%s 最后一格必须以 ✅🟡⬜❓ 之一开头' % rid)
            continue
        if status.startswith(('⬜', '🟡')) and '来源：' not in status and '建议，待确认' not in status:
            issues.append('%s 标 ⬜／🟡 时必须写「来源：」或「建议，待确认」' % rid)
        if status.startswith('✅') and not _CODE_SPAN.search(line):
            issues.append('%s 标 ✅ 时整行至少一处反引号包住的代码位置' % rid)
    return issues


def _stage_of(path) -> str:
    return path.stem.split('_', 1)[0]


class StageDocSectionsTests(unittest.TestCase):
    """T1–T4：样例自检、真实文件、跨文件编号、REQUIRE_ALL。"""

    def test_t1_r1_violation(self):
        text = ('## 需求\n\n## 设计\n\n## 交互\n\n## 接口\n\n'
                '### 读入\n')
        self.assertTrue(problems(text, 'S01'))

    def test_t1_r2_violation(self):
        text = ('## 设计\n\n## 接口\n\n### 读入\n\n### 写出\n\n### 完成判定与交接\n\n'
                '## 交互\n\n### 页面区域\n\n### 控件与操作\n\n### 页面状态\n\n### 键盘、右键与拖放\n')
        self.assertTrue(problems(text, 'S01'))

    def test_t1_r3_violation(self):
        text = (_COMPLIANT
                .replace('| UX-S01-01 |', '| UX-S02-01 |'))
        self.assertTrue(problems(text, 'S01'))

    def test_t1_r4_violation(self):
        text = _COMPLIANT.replace('| ✅ |', '| 已上线 |', 1)
        self.assertTrue(problems(text, 'S01'))

    def test_t1_r5_violation(self):
        text = _COMPLIANT.replace('| ⬜ 来源：用户决定 2026-11-21 |', '| ⬜ |')
        self.assertTrue(problems(text, 'S01'))

    def test_t1_r6_violation(self):
        text = _COMPLIANT.replace('`asset_plan._sync_plan`', 'asset_plan._sync_plan')
        self.assertTrue(problems(text, 'S01'))

    def test_t1_compliant_sample_is_clean(self):
        self.assertEqual(problems(_COMPLIANT, 'S01'), [])

    def test_t2_real_stage_files_are_clean(self):
        for path in stage_files():
            self.assertEqual(problems(path.read_text(encoding='utf-8'), _stage_of(path)), [],
                             path.name)

    def test_t3_ids_do_not_repeat_across_stage_files(self):
        seen = {}
        duplicates = []
        for path in stage_files():
            for line in path.read_text(encoding='utf-8').splitlines():
                matched = _ID.match(_first_cell(line) or '')
                if matched:
                    rid = matched.group(0)
                    if rid in seen:
                        duplicates.append('%s 同时出现在 %s 与 %s' % (rid, seen[rid], path.name))
                    else:
                        seen[rid] = path.name
        self.assertEqual(duplicates, [])

    def test_t4_require_all_flags_missing_sections(self):
        sample = '## 需求\n\n- **REQ-S01-01** ✅\n\n## 设计\n\n设计条目。\n'
        self.assertEqual(problems(sample, 'S01'), [])
        with patch.object(sys.modules[__name__], 'REQUIRE_ALL', True):
            self.assertTrue(problems(sample, 'S01'))


def _first_cell(line: str):
    line = line.strip()
    if not line.startswith('|'):
        return None
    cells = [cell.strip() for cell in line.split('|')]
    cells = cells[1:] if cells and cells[0] == '' else cells
    cells = cells[:-1] if cells and cells[-1] == '' else cells
    return cells[0] if cells else None


_COMPLIANT = """## 需求

- **REQ-S01-01** ✅

## 设计

设计条目。

## 接口

### 读入

| 编号 | 读什么 | 来源 | 读取入口 | 缺失或损坏时 | 状态 |
|---|---|---|---|---|---|
| IF-S01-01 | 已采用的分镜 | S03 初步分镜的产出 | `asset_plan._sync_plan` | 提示后退回 | ✅ |

### 写出

| 编号 | 写什么 | 位置 | 写入入口 | 写入方式 | 下游谁用 | 状态 |
|---|---|---|---|---|---|---|
| IF-S01-20 | 资产清单 | `05资产管理/` | `asset_plan._publish_plan_bundle` | 原子写 | S06 | ✅ |

### 完成判定与交接

| 编号 | 判定或交接项 | 依据 | 对应需求 | 状态 |
|---|---|---|---|---|
| IF-S01-40 | 清单非空 | `stage_completion_service` | REQ-S01-01 | ✅ |

### 对外调用

| 编号 | 调用对象 | 入口 | 是否计费 | 失败时 | 状态 |
|---|---|---|---|---|---|
| IF-S01-60 | 无对外调用 | 无 | 否 | 无 | ✅ `no_call` |

## 交互

### 页面区域

1. 顶部导航：页签，`desktop_page_nav`。
2. 中部列表：条目，`ui_table`。

### 控件与操作

| 编号 | 控件 | 所在区域 | 操作 | 程序做什么 | 用户看到的反馈 | 可用条件 | 状态 |
|---|---|---|---|---|---|---|---|
| UX-S01-01 | 「生成」 | 中部列表 | 点击 | `desktop.start` | 进度条动 | 项目已打开 | ✅ `desktop.start` |
| UX-S01-02 | 「演变记录」 | 详情区 | 点击 | 待定 | 待定 | 待定 | ⬜ 来源：用户决定 2026-11-21 |

### 页面状态

| 编号 | 情形 | 页面显示什么 | 依据 | 状态 |
|---|---|---|---|---|
| UX-S01-60 | 没有打开项目 | 提示先打开项目 | `desktop.project` | ✅ |
| UX-S01-61 | 刚新建的空项目 | 空列表 | `desktop.project` | ✅ |
| UX-S01-62 | 前置阶段没完成 | 提示先完成前置 | `stage_completion_service` | ✅ |
| UX-S01-63 | 正在制作 | 进度条 | `pet_bus` | ✅ |
| UX-S01-64 | 已经完成 | 结果列表 | `stage_completion_service` | ✅ |
| UX-S01-65 | 出错 | 错误提示 | `broadcaster` | ✅ |

### 键盘、右键与拖放

| 编号 | 操作 | 作用在哪 | 程序做什么 | 状态 |
|---|---|---|---|---|
| UX-S01-80 | 无 | 无 | 本页没有专门的键盘、右键、拖放操作，见 `desktop_shared_send`。 | ✅ |
"""


if __name__ == '__main__':
    unittest.main()
