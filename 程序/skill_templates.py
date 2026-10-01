# -*- coding: utf-8 -*-
"""阶段任务模板：仅解析本项目四步 YAML 模板，不依赖第三方 YAML 库。"""
from dataclasses import dataclass
from pathlib import Path

import pet_bus
from skill_registry import scalar, split_pair


@dataclass(frozen=True)
class TemplateStep:
    index: int
    name: str
    action: str
    needs_confirmation: bool = False
    question: str = ''


@dataclass(frozen=True)
class StageTemplate:
    name: str
    stage_id: str
    process_id: str
    steps: tuple
    path: Path


def template_root(program=None):
    return Path(program or Path(__file__).resolve().parent) / 'skills' / 'templates'


def parse_template(text, path='<memory>'):
    """解析模板允许的标量和 ``steps`` 列表，并对运行所需字段做严格校验。"""
    meta, rows, current = {}, [], None
    for raw in str(text).lstrip('\ufeff').replace('\r\n', '\n').split('\n'):
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        indent = len(raw) - len(raw.lstrip())
        pair = split_pair(raw)
        if indent == 0 and pair:
            key, value = pair
            if key == 'steps':
                current = None
            else:
                meta[key] = scalar(value)
            continue
        if indent == 2 and raw.strip().startswith('- ') and pair:
            key, value = pair
            current = {key: scalar(value)}
            rows.append(current)
            continue
        if indent >= 4 and current is not None and pair:
            key, value = pair
            current[key] = scalar(value)
    stage_id = str(meta.get('stage_id') or '')
    if stage_id not in pet_bus.STAGES:
        raise ValueError('%s：未知 stage_id %s' % (path, stage_id or '（空）'))
    steps = []
    for expected, row in enumerate(rows, 1):
        if int(row.get('index') or 0) != expected:
            raise ValueError('%s：步骤编号必须连续且从 1 开始' % path)
        if not all(str(row.get(key) or '').strip() for key in ('name', 'action')):
            raise ValueError('%s：步骤 %d 缺少 name 或 action' % (path, expected))
        if not isinstance(row.get('needs_confirmation'), bool):
            raise ValueError('%s：步骤 %d 的 needs_confirmation 必须是布尔值' % (path, expected))
        steps.append(TemplateStep(expected, str(row['name']), str(row['action']),
                                  row['needs_confirmation'], str(row.get('question') or '')))
    if not steps:
        raise ValueError('%s：模板没有步骤' % path)
    return StageTemplate(str(meta.get('name') or stage_id), stage_id, str(meta.get('process_id') or ''),
                         tuple(steps), Path(path))


def load_template(stage_id, program=None):
    """按规范阶段 ID 取得唯一模板；缺失或重复都显式报错，不猜测。"""
    wanted = str(stage_id or '').strip()
    found = []
    for path in sorted(template_root(program).glob('*_process_template.yaml')):
        template = parse_template(path.read_text(encoding='utf-8'), path)
        if template.stage_id == wanted:
            found.append(template)
    if len(found) != 1:
        raise ValueError('阶段 %s 的模板数量应为 1，实际为 %d' % (wanted or '（空）', len(found)))
    return found[0]
