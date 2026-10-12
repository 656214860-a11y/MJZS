# -*- coding: utf-8 -*-
"""连贯性清单（第 61 期 v0.8 任务 7）：跨镜约束、锚点冻结与三元组校验的台账。

位置：资产管理之后、分镜定稿之前。附件里叫「连贯性清单」，要产出一份
continuity_ledger.json，含四样东西：

1. 每批次冻结锚点列表（frozen_anchors）——这一批必须逐字保住的东西；
2. 冲突参考图优先级裁决（conflicts）——多张参考图抢同一件事时谁说了算；
3. 跨批次连续性约束（cross_batch）——同一角色／场景在不同批次之间不许漂移；
4. 三元组一致性校验结果（triplets）——同批次内 scene_id＋character_ids＋costume_id 是否一致。

Agent 的定位（附件）：只做检查与裁决，不做内容生成；锚点字符串逐字复用，禁止重新描述。
第 62 期任务 11：它已是独立的一步（侧栏「04 连贯性清单」，资产管理之后、分镜定稿之前），
不再折在资产页底部；目录与契约照旧（03_continuity/），产物照旧落盘。
"""
import re
from copy import deepcopy
from pathlib import Path

from asset_contract import KIND_OF, merged_anchor, state_variants
from agent.core import restore_bytes, save, save_text
from file_cache import read_json
from shot_batches import TRIPLET, batches, normalize, triplet

# 附件里给的 Agent Prompt 模板（逐字照抄，程序直接复用这一句）。
PROMPT = (
    '你是一个连贯性检查Agent。输入是初步分镜JSON。任务：遍历所有镜头，识别跨镜约束。'
    '对每个镜头：1.检查character_refs中的参考图职责是否与character_anchor冲突。'
    '2.检查同一批次内所有镜头的scene_id+character_ids+costume_id是否一致。'
    '3.识别需要跨批次保持的锚点（如角色服装、场景光源方向）。'
    '输出：continuity_ledger JSON，包含每个批次的冻结锚点列表和冲突裁决记录。'
)
# 主观门禁那一条（G-09）的追加要求：只预筛两个方案 ＋ 推荐理由，人工点一下。
PRESCREEN_PROMPT = (
    '遇到并列候选时不要替用户定稿：给出 2 个候选方案与各自的推荐理由（一句一条），'
    '等用户点一下；被否掉的那一个要写进 conflict_decisions。'
)
# 「职责里混进了场景／动作／镜头」＝自相矛盾（一张参考图不可能既是身份又是运镜）。
IDENTITY_WORDS = ('面部', '发型', '服装', '瞳色', '骨相', '体型', '标志')
SCENE_WORDS = ('场景', '背景', '空间', '环境')
MOTION_WORDS = ('动作', '运镜', '镜头', '走位', '姿势')
LEDGER_NAME = 'continuity_ledger.json'
LEDGER_DOC = 'continuity_ledger.md'


def _words(text):
    return tuple(word for word in IDENTITY_WORDS + SCENE_WORDS + MOTION_WORDS if word in str(text or ''))


def anchors_of(shot, assets):
    """这一镜要冻结的锚点：出场角色的锚点（含状态覆盖）、场景的光源与空间锚点、道具的尺度。"""
    item = normalize(shot)
    known = assets if isinstance(assets, dict) else {}
    out = []
    for aid in item.get('character_ids') or []:
        asset = known.get(aid)
        if not isinstance(asset, dict):
            continue
        text = merged_anchor(asset, item.get('costume_id'))
        if text:
            out.append({'kind': 'character', 'id': aid, 'anchor': text,
                        'state': str(item.get('costume_id') or '')})
    scene = str(item.get('scene_id') or '')
    asset = known.get(scene)
    if isinstance(asset, dict):
        parts = []
        if str(asset.get('lighting_direction') or '').strip():
            parts.append('光源：' + str(asset['lighting_direction']).strip())
        for entry in asset.get('spatial_anchors') or []:
            if not isinstance(entry, dict):
                continue
            text = str(entry.get('object') or '').strip()
            if not text:
                continue
            where = str(entry.get('position') or '').strip()
            what = str(entry.get('material') or '').strip()
            parts.append('%s@%s%s' % (text, where, ('（%s）' % what) if what else ''))
        if str(asset.get('scale_reference') or '').strip():
            parts.append('尺度：' + str(asset['scale_reference']).strip())
        if parts:
            out.append({'kind': 'scene', 'id': scene, 'anchor': '；'.join(parts), 'state': ''})
    for aid in item.get('props') or []:
        asset = known.get(aid)
        if not isinstance(asset, dict):
            continue
        parts = [str(asset.get(key) or '').strip() for key in ('material', 'scale')]
        parts = [text for text in parts if text]
        if parts:
            out.append({'kind': 'prop', 'id': aid, 'anchor': '；'.join(parts), 'state': ''})
    return tuple(out)


def conflicts(shots, assets=None):
    """参考图职责冲突（任务 7 第 1 条）：一张图既做身份又做运镜、或两张图抢同一件事。"""
    out = []
    for index, raw in enumerate(shots or []):
        item = normalize(raw, index)
        roles = item.get('reference_roles') or {}
        refs = list(item.get('character_refs') or [])
        for ref in refs:
            role = roles.get(ref) or {}
            body = str(role.get('responsibility') or '')
            exclude = str(role.get('exclude') or '')
            mixed = [word for word in _words(body) if word in SCENE_WORDS + MOTION_WORDS]
            if mixed and not any(word in exclude for word in mixed):
                out.append({'shot_id': item['shot_id'], 'batch_id': item.get('batch_id') or '',
                            'kind': '职责自相矛盾', 'refs': (ref,),
                            'detail': '%s 的职责里写了%s，但排除项没写它——一张参考图不能既管身份又管它'
                                      % (ref, '、'.join(mixed))})
        by_identity = {}
        for ref in refs:
            role = roles.get(ref) or {}
            key = tuple(word for word in _words(role.get('responsibility')) if word in IDENTITY_WORDS)
            if key:
                by_identity.setdefault(key, []).append(ref)
        for key, group in by_identity.items():
            if len(group) > 1:
                out.append({'shot_id': item['shot_id'], 'batch_id': item.get('batch_id') or '',
                            'kind': '多图抢同一件事', 'refs': tuple(group),
                            'detail': '%s 都声明负责%s，必须裁决谁为准' % ('、'.join(group), '、'.join(key))})
    return tuple(out)


def adjudicate(found):
    """冲突裁决（主观门禁 G-09 的机器那一半）：按「先出现的先负责身份」排序并写清结论。"""
    out = []
    for item in found:
        refs = list(item.get('refs') or ())
        if not refs:
            continue
        winner = refs[0]
        rest = refs[1:]
        detail = '%s 负责身份（面部、发型、服装）；%s 只补风格与光影，不继承场景、动作、镜头' % (
            winner, '、'.join(rest)) if rest else '%s 负责身份（面部、发型、服装），其余一律不继承' % winner
        out.append({'shot_id': item['shot_id'], 'batch_id': item.get('batch_id') or '',
                    'kind': item['kind'], 'priority': [winner] + rest, 'resolution': detail,
                    'reason': item['detail']})
    return tuple(out)


def triplets(shots):
    """三元组一致性（任务 7 第 2 条）：每个批次一行结论。"""
    out = []
    for name, items in batches(shots).items():
        kinds = {triplet(item) for item in items}
        scene, chars, costume = triplet(items[0])
        out.append({'batch_id': name, 'ok': len(kinds) == 1, 'scene_id': scene,
                    'character_ids': list(chars), 'costume_id': costume,
                    'detail': '一致' if len(kinds) == 1 else
                              '同一批次里出现 %d 种三元组，必须重切批次' % len(kinds)})
    return tuple(out)


def cross_batch(shots, assets=None):
    """跨批次连续性约束（任务 7 第 3 条）：同一个锚点在两批之间必须一模一样。"""
    frozen = {}
    order = []
    for name, items in batches(shots).items():
        for item in items:
            for entry in anchors_of(item, assets):
                key = (entry['kind'], entry['id'], entry['state'])
                if key not in frozen:
                    frozen[key] = []
                    order.append(key)
                frozen[key].append((name, entry['anchor']))
    out = []
    for key in order:
        kind, aid, state = key
        seen = []
        for name, anchor in frozen[key]:
            if anchor not in [text for _batch, text in seen]:
                seen.append((name, anchor))
        if len(seen) > 1:
            out.append({'kind': kind, 'id': aid, 'state': state, 'ok': False,
                        'detail': '%s 的锚点在批次之间不一致：%s'
                                  % (aid, ' ／ '.join('%s：%s' % pair for pair in seen))})
        else:
            out.append({'kind': kind, 'id': aid, 'state': state, 'ok': True,
                        'detail': '%s 在全部批次里锚点一致' % aid})
    flags = []
    for name, items in batches(shots).items():
        for item in items:
            for flag in item.get('continuity_flags') or []:
                text = str(flag).strip()
                if text and text not in flags:
                    flags.append(text)
    for text in flags:
        out.append({'kind': 'flag', 'id': '', 'state': '', 'ok': True,
                    'detail': '全程必须保住：' + text})
    return tuple(out)


def drift(ledger, assets):
    """跨批次锚点漂移（门禁 G-09）：台账冻结的锚点与现在资产里的锚点对不上，就报警。

    台账是「冻结」的那一份；资产被人改过、或某一批偷偷重写了锚点，就会出现两份字符串。
    这里只比字符串，不重新描述（硬约束 4）。
    """
    known = assets if isinstance(assets, dict) else {}
    out = []
    seen = set()
    for block in ledger.get('batches') or []:
        for entry in block.get('frozen_anchors') or []:
            if entry.get('kind') != 'character':
                continue
            key = (entry.get('id'), entry.get('state') or '')
            if key in seen:
                continue
            seen.add(key)
            asset = known.get(entry.get('id'))
            if not isinstance(asset, dict):
                continue
            now = merged_anchor(asset, entry.get('state'))
            if now and now != entry.get('anchor'):
                out.append({'kind': 'character', 'id': entry.get('id'),
                            'state': entry.get('state') or '', 'ok': False,
                            'detail': '%s 的锚点已漂移：台账冻结的是「%s」，资产里现在是「%s」'
                                      % (entry.get('id'), entry.get('anchor'), now)})
    return tuple(out)


def build(shots, assets=None):
    """整份台账：批次冻结锚点 ＋ 冲突裁决 ＋ 跨批次约束 ＋ 三元组校验。"""
    grouped = batches(shots)
    blocks = []
    for name, items in grouped.items():
        frozen = []
        for item in items:
            for entry in anchors_of(item, assets):
                if entry not in frozen:
                    frozen.append(entry)
        blocks.append({'batch_id': name,
                       'shot_ids': [item['shot_id'] for item in items],
                       'seconds': sum(int(item.get('estimated_duration') or 0) for item in items),
                       'frozen_anchors': frozen})
    found = conflicts(shots, assets)
    ledger = {'version': 1, 'stage': '03_continuity', 'prompt': PROMPT,
              'prescreen_prompt': PRESCREEN_PROMPT,
              'batches': blocks, 'conflicts': list(adjudicate(found)),
              'cross_batch': list(cross_batch(shots, assets)),
              'triplets': list(triplets(shots))}
    ledger['drift'] = list(drift(ledger, assets))   # 第 61 期 v0.8 任务 7：门禁 G-09
    problems = list(resolve_problems(ledger))
    ledger['summary'] = {'batches': len(blocks), 'shots': sum(len(item['shot_ids']) for item in blocks),
                         'ok': not problems, 'problems': problems}
    return ledger


def resolve_problems(ledger):
    """台账里没通过的那几条（门禁 G-02／G-03 与跨批次漂移）。"""
    out = []
    for row in ledger.get('triplets') or []:
        if not row.get('ok'):
            out.append('%s：%s' % (row.get('batch_id'), row.get('detail')))
    for row in ledger.get('cross_batch') or []:
        if not row.get('ok'):
            out.append(row.get('detail'))
    for row in ledger.get('conflicts') or []:
        if row.get('kind') == '职责自相矛盾':
            out.append('%s：%s' % (row.get('shot_id'), row.get('detail')))
    for row in ledger.get('drift') or []:
        if not row.get('ok'):
            out.append(row.get('detail'))
    return tuple(out)


def ask(ledger):
    """要用户点一下的那几条（主观门禁）：每条两个候选 ＋ 推荐理由。"""
    out = []
    for index, row in enumerate(ledger.get('conflicts') or [], 1):
        if row.get('kind') != '多图抢同一件事':
            continue
        priority = list(row.get('priority') or [])
        if len(priority) < 2:
            continue
        name = row.get('batch_id') or row.get('shot_id') or ''
        out.append({'id': 'G-08-%02d' % index, 'key': 'conflict:%s' % name,
                    'title': '%s 的参考图优先级' % name,
                    'candidates': ['%s 为准（%s 退为风格补充）' % (priority[0], priority[1]),
                                   '%s 为准（%s 退为风格补充）' % (priority[1], priority[0])],
                    'reason': row.get('reason') or '',
                    'recommended': 0})
    return tuple(out)


def _anchor_library(ledger):
    """从台账提取机器复用的锚点库，不在这里落盘。"""
    library = {}
    for block in ledger.get('batches') or []:
        for entry in block.get('frozen_anchors') or []:
            if entry.get('kind') != 'character':
                continue
            record = library.setdefault(entry['id'], {'anchor': entry['anchor'], 'states': {}})
            record['anchor'] = entry['anchor']
            if entry.get('state'):
                record['states'][entry['state']] = entry['anchor']
    return library


def _triplet_rows(ledger):
    """从台账提取跨阶段复用的合法三元组，不在这里落盘。"""
    rows = {}
    for row in ledger.get('triplets') or []:
        if row.get('ok'):
            rows[row['batch_id']] = [row['scene_id'], list(row['character_ids']), row['costume_id']]
    return rows


def publish_bundle(project, ledger):
    """原子发布连贯性成果及共享索引；任一失败则恢复本轮之前的全部文件。"""
    import stage_layout
    paths = stage_layout.paths(project, '03_continuity')
    file = paths['output'] / LEDGER_NAME
    targets = (
        (file, save, ledger),
        (paths['docs'] / LEDGER_DOC, save_text, markdown(ledger)),
        (stage_layout.anchors_path(project), save, _anchor_library(ledger)),
        (stage_layout.triplets_path(project), save, _triplet_rows(ledger)),
    )
    previous = tuple((path, path.read_bytes() if path.is_file() else None) for path, _, _ in targets)
    try:
        for path, writer, content in targets:
            writer(path, content)
        normalized_ledger = deepcopy(ledger)
        if (read_json(file) != normalized_ledger or (paths['docs'] / LEDGER_DOC).read_text(encoding='utf-8') != markdown(ledger)
                or read_json(stage_layout.anchors_path(project)) != _anchor_library(ledger)
                or read_json(stage_layout.triplets_path(project)) != _triplet_rows(ledger)):
            raise ValueError('连贯性清单发布后复核失败')
    except Exception:
        for path, raw in previous:
            restore_bytes(path, raw)
        raise
    return file


def write(project, ledger):
    """兼容入口：台账、人读版与共享索引统一经发布包落盘。"""
    return publish_bundle(project, ledger)


def read(project):
    """读回台账（没有就是空 dict）。"""
    from stage_path_service import read_file
    file = read_file(project, 'continuity', 'output', LEDGER_NAME)
    if not file.is_file():
        return {}
    try:
        data = read_json(file)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_anchors(project, ledger):
    """锚点库（_shared/anchors）：角色锚点逐字复用，机器只读它，不许重新描述。"""
    import stage_layout
    return save_json(stage_layout.anchors_path(project), _anchor_library(ledger))


def write_triplets(project, ledger):
    """三元组字典（_shared/triplets）：批次编号 → 元组，跨阶段对齐用。"""
    import stage_layout
    return save_json(stage_layout.triplets_path(project), _triplet_rows(ledger))


def save_json(path, data):
    """原子写 JSON（目录缺了就补）。"""
    save(path, data)
    return Path(path)


def markdown(ledger):
    """人读版（只给人看，机器不读）。"""
    lines = ['# 连贯性清单', '',
             '镜头 %d 个，批次 %d 组；结论：%s' % (
                 (ledger.get('summary') or {}).get('shots', 0),
                 (ledger.get('summary') or {}).get('batches', 0),
                 '通过' if (ledger.get('summary') or {}).get('ok') else '有待办'), '']
    for block in ledger.get('batches') or []:
        lines.append('## %s（%s 秒）' % (block.get('batch_id'), block.get('seconds')))
        lines.append('镜头：' + '、'.join(block.get('shot_ids') or []))
        for entry in block.get('frozen_anchors') or []:
            lines.append('- 冻结锚点 %s %s：%s' % (entry.get('kind'), entry.get('id'), entry.get('anchor')))
        lines.append('')
    lines.append('## 参考图裁决')
    lines += ['- %s：%s' % (row.get('shot_id'), row.get('resolution'))
              for row in ledger.get('conflicts') or []] or ['- 没有冲突']
    lines.append('')
    lines.append('## 跨批次连续性')
    lines += ['- %s' % row.get('detail') for row in ledger.get('cross_batch') or []] or ['- 没有跨批次约束']
    lines.append('')
    lines.append('## 锚点漂移')
    lines += ['- %s' % row.get('detail') for row in ledger.get('drift') or []] or ['- 没有漂移']
    lines.append('')
    lines.append('## 三元组校验')
    lines += ['- %s：%s' % (row.get('batch_id'), row.get('detail')) for row in ledger.get('triplets') or []]
    problems = (ledger.get('summary') or {}).get('problems') or []
    if problems:
        lines += ['', '## 待办']
        lines += ['- %s' % text for text in problems]
    return '\n'.join(lines) + '\n'


def gate(ledger):
    """门禁结论：(通过吗, 待办列表)。"""
    problems = tuple((ledger.get('summary') or {}).get('problems') or [])
    return (not problems), problems


# ── 问题闭环（O23）：发现 → 处理决定 → 解除／重开，登记在 03_continuity/output/continuity_issues.json ──
ISSUE_NAME = 'continuity_issues.json'
OPEN, IGNORED, RESOLVED = 'open', 'ignored', 'resolved'
ISSUE_STATES = (OPEN, IGNORED, RESOLVED)
HUMAN = '人工'
SEVERITIES = {'conflict': '高', 'triplet': '高', 'drift': '中', 'cross_batch': '中'}
ISSUE_KINDS = {'conflict': '职责自相矛盾', 'triplet': '三元组不一致',
               'drift': '锚点漂移', 'cross_batch': '跨批次不一致'}
STATE_LABELS = {OPEN: '待处理', IGNORED: '已忽略', RESOLVED: '已解除'}


def _issue_digest(kind, scope, detail, shots, assets):
    import hashlib
    text = '\x1f'.join([str(kind), str(scope), str(detail), '|'.join(shots), '|'.join(assets)])
    return hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]


def _issue(kind, scope, shots, assets, detail):
    """一条结构化问题：稳定编号 ＋ 涉及镜头/资产 ＋ 证据 ＋ 严重程度。"""
    shots = [str(item).strip() for item in (shots or []) if str(item or '').strip()]
    assets = [str(item).strip() for item in (assets or []) if str(item or '').strip()]
    detail = str(detail or '')
    evidence = '；'.join(text for text in (
        ('涉及镜头：' + '、'.join(shots)) if shots else '',
        ('涉及资产：' + '、'.join(assets)) if assets else '',
        detail) if text)
    return {'id': 'CI-%s-%s' % (kind, scope or 'NA'), 'kind': kind,
            'kind_label': ISSUE_KINDS.get(kind, kind), 'severity': SEVERITIES.get(kind, '中'),
            'shots': shots, 'assets': assets, 'detail': detail, 'evidence': evidence,
            'digest': _issue_digest(kind, scope, detail, shots, assets)}


def issues(ledger):
    """台账里没过的那几条变成结构化问题：编号稳定（含批次），同一份台账算出来总是一样。"""
    out = []
    blocks = {str(block.get('batch_id') or ''): block for block in ledger.get('batches') or []}
    for row in ledger.get('triplets') or []:
        if row.get('ok'):
            continue
        batch = str(row.get('batch_id') or '')
        block = blocks.get(batch) or {}
        out.append(_issue('triplet', batch, block.get('shot_ids'),
                          [row.get('scene_id')] + list(row.get('character_ids') or []),
                          row.get('detail')))
    for row in ledger.get('cross_batch') or []:
        if row.get('ok'):
            continue
        out.append(_issue('cross_batch', '%s-%s' % (row.get('id') or 'NA', row.get('state') or ''),
                          [], [row.get('id')], row.get('detail')))
    seen = {}
    for row in ledger.get('conflicts') or []:
        if row.get('kind') != '职责自相矛盾':
            continue
        shot = str(row.get('shot_id') or '')
        seen[shot] = seen.get(shot, 0) + 1
        scope = shot if seen[shot] == 1 else '%s-%d' % (shot, seen[shot])
        out.append(_issue('conflict', scope, [row.get('shot_id')], [], row.get('detail')))
    for row in ledger.get('drift') or []:
        if row.get('ok'):
            continue
        out.append(_issue('drift', '%s-%s' % (row.get('id') or 'NA', row.get('state') or ''),
                          [], [row.get('id')], row.get('detail')))
    return tuple(out)


def issues_path(project):
    """问题闭环登记表落在 03_continuity/output/continuity_issues.json。"""
    import stage_layout
    return stage_layout.paths(project, '03_continuity')['output'] / ISSUE_NAME


def read_issues(project):
    """已经登记过的问题（编号 → 记录）；没有或读不动就给空表。"""
    path = issues_path(project)
    if not path.is_file():
        from stage_path_service import read_file
        path = read_file(project, 'continuity', 'output', ISSUE_NAME)
    if not path.is_file():
        return {}
    try:
        data = read_json(path)
    except (OSError, ValueError):
        return {}
    rows = data.get('issues') if isinstance(data, dict) else None
    return dict(rows) if isinstance(rows, dict) else {}


def _report_rows(register):
    """登记表 → 报告行：待处理在前（严重度高的再前），然后已忽略、已解除。"""
    order = {OPEN: 0, IGNORED: 1, RESOLVED: 2}
    rows = []
    for value in (register or {}).values():
        if not isinstance(value, dict):
            continue
        item = dict(value)
        item['state_label'] = STATE_LABELS.get(str(item.get('state')), str(item.get('state') or ''))
        decision = item.get('decision') if isinstance(item.get('decision'), dict) else {}
        item['reason'] = str(decision.get('reason') or '')
        rows.append(item)
    rows.sort(key=lambda row: (order.get(str(row.get('state')), 9),
                               row.get('severity') != '高', str(row.get('id') or '')))
    return rows


def merge_issues(register, current, *, now=''):
    """把本轮算出的问题并进登记表（纯函数）。返回 (新登记表, 报告行)。

    同一编号不会重复新增；本轮没有、原来待处理／已忽略的置为已解除（修好解除）；
    已解除的重新出现 → 重开；已忽略的证据变了 → 重开（原忽略只对当时那一版证据有效）。
    """
    existing = dict(register) if isinstance(register, dict) else {}
    stamp = str(now or '')
    seen = set()
    for raw in current or []:
        item = dict(raw) if isinstance(raw, dict) else {}
        iid = str(item.get('id') or '')
        if not iid:
            continue
        seen.add(iid)
        previous = existing.get(iid) if isinstance(existing.get(iid), dict) else {}
        state = str(previous.get('state') or OPEN)
        digest = str(previous.get('digest') or '')
        history = list(previous.get('history') or [])
        decision = dict(previous.get('decision') or {}) if isinstance(previous.get('decision'), dict) else {}
        note = ''
        if not previous:
            item['state'] = OPEN
            note = '首次发现'
        elif state == RESOLVED:
            item['state'] = OPEN
            note = '曾经解除，这次检查又出现'
        elif state == IGNORED and digest and digest != str(item.get('digest') or ''):
            item['state'] = OPEN
            note = '忽略时依据的那一版证据已变化，需要重新决定'
            decision = {}
        elif state == IGNORED:
            item['state'] = IGNORED
        else:
            item['state'] = OPEN
        item['decision'] = decision
        item['first_seen'] = str(previous.get('first_seen') or stamp)
        item['last_seen'] = stamp or str(previous.get('last_seen') or '')
        if note:
            history.append({'at': item['last_seen'], 'state': item['state'], 'note': note})
        item['history'] = history[-20:]
        existing[iid] = item
    for iid, value in list(existing.items()):
        if iid in seen or not isinstance(value, dict):
            continue
        if str(value.get('state') or OPEN) in (OPEN, IGNORED):
            row = dict(value)
            row['state'] = RESOLVED
            row['last_seen'] = stamp or str(row.get('last_seen') or '')
            history = list(row.get('history') or [])
            history.append({'at': row['last_seen'], 'state': RESOLVED, 'note': '这次检查里已不再出现'})
            row['history'] = history[-20:]
            existing[iid] = row
    return existing, _report_rows(existing)


def sync_issues(project, ledger, *, publish=None, now=''):
    """读台账 → 算问题 → 并入登记表；只有 L3 注入 publish 才落盘，不注入就只读预览。"""
    register, rows = merge_issues(read_issues(project), issues(ledger), now=now)
    if publish is not None:
        publish(issues_path(project), {'version': 1, 'issues': register})
    return rows


def decide_issue(project, issue_id, decision, reason='', by=HUMAN, *, publish, now=''):
    """记一条人工处理决定。忽略必须写明理由，并记下作用的证据版本（当时那一版摘要）。"""
    decision = str(decision or '').strip().lower()
    if decision not in (OPEN, IGNORED):
        raise ValueError('处理决定只能是 open／ignored：' + str(decision or '（空）'))
    reason = str(reason or '').strip()
    if decision == IGNORED and not reason:
        raise ValueError('忽略一条问题必须写明理由（为什么可以不管）。')
    register = read_issues(project)
    row = register.get(str(issue_id))
    if not isinstance(row, dict):
        raise ValueError('没有这条问题：' + str(issue_id or '（空）'))
    row = dict(row)
    row['state'] = decision
    row['decision'] = {'value': decision, 'reason': reason, 'by': str(by or HUMAN),
                       'digest': str(row.get('digest') or ''), 'at': str(now or '')}
    history = list(row.get('history') or [])
    history.append({'at': str(now or ''), 'state': decision,
                    'note': reason or ('人工重新打开' if decision == OPEN else '人工关闭')})
    row['history'] = history[-20:]
    register[str(issue_id)] = row
    publish(issues_path(project), {'version': 1, 'issues': register})
    return _report_rows(register)


def issue_gate(project, ledger, *, now=''):
    """闭环之后还拦不拦：只有「待处理」算没解决；已忽略与已解除都放行。"""
    rows = sync_issues(project, ledger, now=now)
    blocking = [row for row in rows if str(row.get('state')) == OPEN]
    return (not blocking), tuple(blocking)
