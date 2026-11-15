"""阶段契约的展示聚合。

目录事实属于 ``stage_layout``；门禁归属属于 ``confirm_gates``。
本模块只把两者组装给 UI／报告使用，避免路径层反向导入门禁层。
"""
from __future__ import annotations

import confirm_gates
import contract.stage_layout as stage_layout


def contract_rows():
    """返回阶段、输入、输出、文档和适用门禁的展示行。"""
    rows = []
    for folder, stage, title, _duty, inputs, outputs in stage_layout.STAGES:
        rows.append({'folder': folder, 'stage': stage, 'title': title,
                     'input': tuple(inputs), 'output': tuple(outputs),
                     'docs': tuple(name for name, _text in stage_layout.DOCS.get(folder, ())),
                     'gates': tuple(confirm_gates.stage_gates(folder))})
    return tuple(rows)
