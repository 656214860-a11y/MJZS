# -*- coding: utf-8 -*-
"""用户确认门禁（第 61 期 v0.8 任务 1）：客观门禁 Agent 全自动，主观门禁预筛 2 个候选 ＋ 人工点一下。

附件任务 1 要的是「Agent 预审 ＋ 人工一键确认」：

- **客观门禁**（字段完整性、三元组一致性、参考图职责冲突、资产齐全、批次合规、跨批次漂移）
  由 Agent 全自动判断，通过就自动放行，不打扰用户；
- **主观门禁**（锚点定稿、正典板 4 选 1、连贯性台账裁决）由 Agent 预筛到 **2 个候选 ＋ 推荐理由**，
  人工只做最后一次点击；其中 G-08 连贯性台账裁决是**可选、建议**项，不是 SG-02 的放行条件；
- 人工点击量因此从「每镜审核」降到「**每角色一次**」：待确认项按 key 去重（同一个角色／同一批次
  只问一次），点过的记进 03_continuity/output/gate_confirmations.json，重跑不再重复问。

判定者只有两种：Agent（自动）与人工（点确认）。门禁清单表就是 table_rows()（交付物 9）。

三条定位（附件硬约束 3）：三虎 agent 只编排与门禁，不生成内容；门禁只判「能不能进下一阶段」，
不改内容；不通过就把话说短，打回上一阶段或让用户点一下。
"""
import hashlib
from pathlib import Path

from file_cache import read_json
from asset_contract import missing_ids
from asset_contract import normalize as normalize_asset
from shot_batches import check_batches, validate as validate_shot
from legacy_compat import canonical_stage_name
from project_context import ProjectContext

OBJECTIVE = '客观'
SUBJECTIVE = '主观'
AUTO = 'Agent'
HUMAN = '人工'
PENDING = 'pending'
APPLIED = 'applied'
FAILED = 'failed'
CONFIRM_NAME = 'gate_confirmations.json'
FOLDER = '03_continuity'

# 门禁清单（交付物 9）。字段含义：
#   id       门禁编号
#   type     客观（Agent 自动放行）／主观（Agent 预筛 ＋ 人工点击）
#   judge    判定者
#   title    一句话名字
#   condition 通过条件（短、能一眼看懂）
#   reject   不通过动作
#   check    客观门禁的判据函数名
#   ask      主观门禁的候选构造函数名
GATES = (
    {'id': 'G-01', 'type': OBJECTIVE, 'judge': AUTO, 'title': '字段完整性',
     'condition': '资产与分镜的新增字段齐全、取值合法',
     'reject': '打回上一阶段补齐，不打扰您', 'check': 'fields', 'ask': ''},
    {'id': 'G-02', 'type': OBJECTIVE, 'judge': AUTO, 'title': '三元组一致性',
     'condition': '同一批次内 scene_id＋character_ids＋costume_id 完全一致',
     'reject': '重切批次，不打扰您', 'check': 'triplets', 'ask': ''},
    {'id': 'G-03', 'type': OBJECTIVE, 'judge': AUTO, 'title': '参考图职责冲突',
     'condition': '每张参考图的职责不与 anchor 自相矛盾',
     'reject': '改职责声明或移到连贯性清单裁决', 'check': 'roles', 'ask': ''},
    {'id': 'G-04', 'type': OBJECTIVE, 'judge': AUTO, 'title': '资产齐全',
     'condition': '分镜引用的资产都有名字与生图提示词',
     'reject': '列出缺的编号，打回资产管理', 'check': 'assets', 'ask': ''},
    {'id': 'G-05', 'type': SUBJECTIVE, 'judge': HUMAN, 'title': '锚点定稿',
     'condition': '每个角色选定一句锚点字符串并锁定',
     'reject': '预筛 2 候选，等您点一下', 'check': '', 'ask': 'anchors'},
    {'id': 'G-06', 'type': SUBJECTIVE, 'judge': HUMAN, 'title': '正典板 4 选 1',
     'condition': '每个角色选定一套正典板（四视角同背景同光照）',
     'reject': '预筛 2 候选，等您点一下', 'check': '', 'ask': 'canon'},
    {'id': 'G-07', 'type': OBJECTIVE, 'judge': AUTO, 'title': '批次合规',
     'condition': '每批 ≤4 镜、累计 ≤18 秒、三元组一致',
     'reject': '重切批次，不打扰您', 'check': 'batch', 'ask': ''},
    {'id': 'G-08', 'type': SUBJECTIVE, 'judge': HUMAN, 'title': '连贯性台账裁决',
     'condition': '多图抢同一件事的优先级裁决（可选、建议，不是 SG-02 放行条件）',
     'reject': '可跳过，不影响 SG-02 放行；需要时预筛 2 候选', 'check': '', 'ask': 'conflicts'},
    {'id': 'G-09', 'type': OBJECTIVE, 'judge': AUTO, 'title': '跨批次锚点漂移',
     'condition': '同一角色／场景的锚点在批次之间一模一样',
     'reject': '以首次冻结的锚点为准，回改漂移的那一批', 'check': 'drift', 'ask': ''},
)

# 门禁挂在哪几个当前用户可见阶段目录。旧内部标识由 stage_gates() 兼容解析。
GATE_STAGES = {
    'G-01': ('05资产管理', '07分镜定稿'),
    'G-02': ('06连贯性清单',),
    'G-03': ('05资产管理', '06连贯性清单'),
    'G-04': ('05资产管理', '08首帧管理'),
    'G-05': ('05资产管理',),
    'G-06': ('05资产管理',),
    'G-07': ('07分镜定稿',),
    'G-08': ('06连贯性清单',),
    'G-09': ('06连贯性清单',),
}

ANCHOR_REASON = '候选一改动最小、直接沿用现有描述；候选二把可变属性摘出去，锚点更稳。'
CANON_REASON = '推荐候选一：更贴现有资产提示词。生成转盘图时手上不持道具，七格同背景色同光照方向。'
CONFLICT_REASON = '先出现的参考图优先负责身份，后来那张只补风格与光影。'


def by_id(gate_id):
    """门禁编号 → 那一行（认不出来返回 None）。"""
    text = str(gate_id or '').strip().upper()
    for row in GATES:
        if row['id'] == text:
            return row
    return None


def gate_ids():
    """全部门禁编号（按编号先后）。"""
    return tuple(row['id'] for row in GATES)


def objective_ids():
    """客观门禁（Agent 自动放行）的编号。"""
    return tuple(row['id'] for row in GATES if row['type'] == OBJECTIVE)


def subjective_ids():
    """主观门禁（要人工点一下）的编号。"""
    return tuple(row['id'] for row in GATES if row['type'] == SUBJECTIVE)


def stage_gates(folder):
    """某个阶段目录适用的门禁编号（stage_layout.contract_rows 用它填契约表）。"""
    # 兼容读取统一由门面处理；传入旧标识时仍落到当前阶段名，从而门禁表、目录与实际
    # 存储共用一套口径。
    text = canonical_stage_name(folder)
    return tuple(row['id'] for row in GATES if text in GATE_STAGES.get(row['id'], ()))


def table_rows():
    """门禁清单表（交付物 9）：门禁ID、类型、判定者、通过条件、不通过动作。"""
    return tuple((row['id'], row['type'], row['judge'], row['condition'], row['reject'])
                 for row in GATES)


def detail_rows():
    """门禁清单的加长版：多一列名字与它挂的阶段，给人看。"""
    return tuple((row['id'], row['title'], row['type'], row['judge'], row['condition'],
                  '、'.join(GATE_STAGES.get(row['id'], ())) or '—') for row in GATES)


# ── 客观门禁的判据（都收口在已有模块上，不另写一套规则） ──────────────────────
def check_fields(shots=None, assets=None, ledger=None):
    """G-01：资产与分镜的新增字段齐不齐、值合不合法。"""
    problems = []
    known = assets if isinstance(assets, dict) else {}
    for aid, asset in sorted(known.items()):
        problems += ['%s：%s' % (aid, text) for text in _validate_asset(asset, aid)]
    for index, shot in enumerate(shots or []):
        problems += validate_shot(shot, index)
    return problems


def check_triplets(shots=None, assets=None, ledger=None):
    """G-02：同一批次内三元组一致（读连贯性台账，没有台账就现切一次）。"""
    rows = (ledger or {}).get('triplets')
    if rows is None:
        from continuity_ledger import triplets
        rows = triplets(shots or [])
    return ['%s：%s' % (row.get('batch_id'), row.get('detail'))
            for row in rows if not row.get('ok')]


def check_roles(shots=None, assets=None, ledger=None):
    """G-03：参考图职责不自相矛盾（一张图不能既管身份又管运镜）。"""
    rows = (ledger or {}).get('conflicts')
    if rows is None:
        from continuity_ledger import conflicts
        rows = conflicts(shots or [], assets)
    return ['%s：%s' % (row.get('shot_id'), row.get('detail'))
            for row in rows if row.get('kind') == '职责自相矛盾']


def check_assets(shots=None, assets=None, ledger=None):
    """G-04：分镜引用的资产都有名字与生图提示词。"""
    return list(missing_ids(shots or [], assets))


def check_batch(shots=None, assets=None, ledger=None):
    """G-07：批次本身合规。"""
    return list(check_batches(shots or []))


def check_drift(shots=None, assets=None, ledger=None):
    """G-09：同一锚点在批次之间、以及跟台账比，都不能漂移。"""
    data = ledger if isinstance(ledger, dict) else {}
    out = [row.get('detail') for row in data.get('cross_batch') or [] if not row.get('ok')]
    blocks = {'batches': data.get('batches') or []}
    if blocks['batches'] and isinstance(assets, dict) and assets:
        # 台账冻结的那一份与现在的资产比：资产被人改过、或哪一批偷偷重写了锚点，就是漂移。
        from continuity_ledger import drift
        rows = list(drift(blocks, assets))
    else:
        rows = list(data.get('drift') or [])
    out += [row.get('detail') for row in rows if not row.get('ok')]
    return out


_CHECKS = {'fields': check_fields, 'triplets': check_triplets, 'roles': check_roles,
           'assets': check_assets, 'batch': check_batch, 'drift': check_drift}


def _validate_asset(asset, aid):
    from asset_contract import validate
    return validate(asset, aid)


# ── 主观门禁的候选（Agent 预筛 2 个 ＋ 推荐理由，人工点一下） ────────────────────
def content_digest(*parts):
    """候选内容摘要（O11）：同一件事怎么摆都是同一个串，用来判断确认有没有过期。

    只喂「决定这条候选长什么样」的字段，别把确认结果本身也喂进去——否则一确认就把自己作废。
    """
    text = '\x1f'.join(str(part) for part in parts)
    return hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]


def _characters(assets):
    """资产清单里的角色，按编号排序：[(编号, 资产), …]。"""
    known = assets if isinstance(assets, dict) else {}
    return [(aid, known[aid]) for aid in sorted(known) if str(aid).startswith('CHAR_')]


def anchor_candidates(shots=None, assets=None, ledger=None):
    """G-05：还没定稿锚点的角色，每个给 2 个候选 ＋ 推荐理由（每角色只问一次）。"""
    out = []
    for aid, asset in _characters(assets):
        data = normalize_asset(asset, aid)
        if str(data.get('character_anchor') or '').strip() and data.get('locked'):
            continue
        name = str(data.get('name') or '').strip() or aid
        brief = '、'.join(text for text in (str(data.get('description') or '').strip(),
                                          str(data.get('appearance') or '').strip()) if text)
        first = (brief + '；面部骨相、发型基底、瞳色、体型比例固定') if brief else \
            (name + '：面部骨相、发型基底、瞳色、体型比例固定，服装走状态变体')
        second = name + '：只锁不变属性（面部骨相、发型基底、瞳色、体型比例），' \
                        '服装与发型变化一律走状态变体'
        out.append({'gate_id': 'G-05', 'key': 'anchor:%s' % aid, 'title': '%s 的锚点字符串' % name,
                    'candidates': (first[:160], second[:160]), 'reason': ANCHOR_REASON,
                    'recommended': 0, 'digest': content_digest('G-05', aid, name, brief)})
    return tuple(out)


def canon_candidates(shots=None, assets=None, ledger=None):
    """G-06：还没有正典板的角色，每个给 2 套方案 ＋ 推荐理由（每角色只问一次）。"""
    out = []
    for aid, asset in _characters(assets):
        data = normalize_asset(asset, aid)
        if str(data.get('canonical_board') or '').strip():
            continue
        views = data.get('canon_board_views')
        if isinstance(views, dict) and any(str(value or '').strip() for value in views.values()):
            continue
        name = str(data.get('name') or '').strip() or aid
        out.append({'gate_id': 'G-06', 'key': 'canon:%s' % aid, 'title': '%s 的正典板' % name,
                    'candidates': ('方案一：写实骨相＋冷调布光（四视角同背景色、同光照方向）',
                                   '方案二：风格化骨相＋暖调布光（四视角同背景色、同光照方向）'),
                    'reason': CANON_REASON, 'recommended': 0,
                    'digest': content_digest('G-06', aid, name)})
    return tuple(out)


def conflict_candidates(shots=None, assets=None, ledger=None):
    """G-08：连贯性台账里多图抢同一件事的那几条，逐条给 2 个候选（每批次只问一次）。"""
    rows = []
    if isinstance(ledger, dict):
        rows = ledger.get('conflicts') or []
    elif shots:
        from continuity_ledger import adjudicate, conflicts
        rows = list(adjudicate(conflicts(shots, assets)))
    out = []
    for index, row in enumerate(rows, 1):
        if row.get('kind') != '多图抢同一件事':
            continue
        priority = list(row.get('priority') or [])
        if len(priority) < 2:
            continue
        name = row.get('batch_id') or row.get('shot_id') or ''
        out.append({'gate_id': 'G-08', 'key': 'conflict:%s' % name,
                    'title': '%s 的参考图优先级' % name,
                    'candidates': ('%s 为准（%s 退为风格补充）' % (priority[0], priority[1]),
                                   '%s 为准（%s 退为风格补充）' % (priority[1], priority[0])),
                    'reason': row.get('reason') or CONFLICT_REASON, 'recommended': 0,
                    'digest': content_digest('G-08', name, *priority)})
    return tuple(out)


_ASKS = {'anchors': anchor_candidates, 'canon': canon_candidates, 'conflicts': conflict_candidates}


# ── 确认记忆：同一角色／同一批次只问一次（人工点击量降到「每角色一次」） ──────────
def confirm_path(project=None, *, context=None):
    """确认记录落在哪：03_continuity/output/gate_confirmations.json。"""
    if context is not None:
        if not isinstance(context, ProjectContext):
            raise TypeError('确认门禁需要由 L3 注入 ProjectContext。')
        root = context.root.resolve()
        if project is not None and Path(project).resolve() != root:
            raise ValueError('项目路径与注入的 ProjectContext 不一致。')
        return context.stage_resolver('continuity') / 'output' / CONFIRM_NAME
    import stage_layout
    return stage_layout.paths(project, FOLDER)['output'] / CONFIRM_NAME


def confirmations(project=None, *, context=None):
    """已经点过的确认（key → {choice, by}）。"""
    if not project and context is None:
        return {}
    path = confirm_path(project, context=context)
    if not path.is_file():
        from stage_path_service import read_file
        path = read_file(context.root if context is not None else project,
                         'continuity', 'output', CONFIRM_NAME)
    if not path.is_file():
        return {}
    try:
        data = read_json(path)
    except (OSError, ValueError):
        return {}
    out = data.get('confirmed') if isinstance(data, dict) else None
    return out if isinstance(out, dict) else {}


def record(project, key, choice='', by=HUMAN, *, publish, context=None, state=APPLIED, digest=''):
    """记一次人工确认；正式发布器必须由 L3 注入。

    ``state`` 记这一步走到哪：pending（已记待办、还没落盘）／applied（落盘成功，才算确认完成）／
    failed（落盘失败）。只有 applied 会被 ``pending()`` 当成已点过，pending／failed 会重新摆出候选，
    这样「未采用却已审核通过」不会发生（O10）。
    """
    path = confirm_path(project, context=context)
    data = {'version': 1, 'confirmed': dict(confirmations(project, context=context))}
    data['confirmed'][str(key)] = {'choice': str(choice), 'by': str(by), 'state': str(state),
                                   'digest': str(digest)}
    publish(path, data)
    return path


def forget(project, key, *, publish, context=None):
    """忘掉一次确认；正式发布器必须由 L3 注入。"""
    path = confirm_path(project, context=context)
    data = {'version': 1, 'confirmed': dict(confirmations(project, context=context))}
    data['confirmed'].pop(str(key), None)
    publish(path, data)
    return path


def _is_done(row):
    """一条确认是否算「已点过」：只有 applied 算；pending／failed 与缺记录一样视同未确认。

    旧记录没有 state（升级前的格式）按已采用处理，避免把人已点过的门禁重新问一遍。
    """
    if not isinstance(row, dict):
        return False
    return str(row.get('state') or APPLIED) not in (PENDING, FAILED)


def _digest_ok(row, item):
    """确认绑的内容摘要还对得上吗：两头都有摘要才比，缺一边按旧口径放行。"""
    stored = str(row.get('digest') or '')
    current = str((item or {}).get('digest') or '')
    return True if not stored or not current else stored == current


def state_of(project, key, *, context=None):
    """一条确认当前走到哪一步：applied／pending／failed；没有记录返回空串。"""
    row = confirmations(project, context=context).get(str(key))
    if not isinstance(row, dict):
        return ''
    return str(row.get('state') or APPLIED)


def pending(project, items, *, context=None):
    """还没点过的候选（同 key 只留一条——这就是「每角色一次」）。"""
    done = confirmations(project, context=context) if project or context is not None else {}
    out, seen = [], set()
    for item in items or ():
        key = str((item or {}).get('key') or '')
        if key and ((_is_done(done.get(key)) and _digest_ok(done.get(key), item)) or key in seen):
            continue
        seen.add(key)
        out.append(item)
    return tuple(out)


def run(gate_id, project='', shots=None, assets=None, ledger=None, *, context=None):
    """跑一条门禁。返回 {'gate_id','type','judge','title','passed','problems','ask'}。

    客观门禁：problems 空＝通过，自动放行。
    主观门禁：ask＝还没点过的候选（空＝已确认，放行）。
    """
    row = by_id(gate_id)
    if row is None:
        raise ValueError('未知门禁：' + str(gate_id))
    result = {'gate_id': row['id'], 'type': row['type'], 'judge': row['judge'],
              'title': row['title'], 'problems': (), 'ask': ()}
    if row['type'] == OBJECTIVE:
        result['problems'] = tuple(_CHECKS[row['check']](shots=shots, assets=assets, ledger=ledger))
        result['passed'] = not result['problems']
    else:
        items = tuple(_ASKS[row['ask']](shots=shots, assets=assets, ledger=ledger))
        result['ask'] = pending(project, items, context=context) if project or context is not None else items
        result['passed'] = not result['ask']
    # 诊断只保留最后一次结果，不写项目目录，也不参与门禁判定。
    import diagnostic_capture
    diagnostic_capture.record_gate_result(row['id'], 'passed' if result['passed'] else 'blocked')
    return result


def summary(project='', shots=None, assets=None, ledger=None, *, context=None):
    """一次跑完全部门禁：一行一条，给门禁面板与自检看。"""
    rows = []
    for row in GATES:
        result = run(row['id'], project=project, shots=shots, assets=assets, ledger=ledger, context=context)
        rows.append((row['id'], row['title'], row['type'], result['passed'],
                     len(result['problems']), len(result['ask'])))
    return tuple(rows)


def passed(project='', shots=None, assets=None, ledger=None, *, context=None):
    """全部门禁都过吗（客观没问题＋主观没有待点）。"""
    return all(row[3] for row in summary(project, shots=shots, assets=assets, ledger=ledger, context=context))
