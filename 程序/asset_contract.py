# -*- coding: utf-8 -*-
"""资产 JSON 契约（第 61 期 v0.8 任务 8／5／3）：角色、场景、道具的新增字段、默认值与校验。

附件要补的三组字段（任务 8）：

- 角色：canonical_board（正典板转盘图）、character_anchor（逐字复用的锚点字符串）、
  base_anchor（基础锚点）、state_variants（状态变体，任务 5）；
- 场景：aspect_ratio／resolution／spatial_anchors／lighting_direction／scale_reference
  （宽幅描述解决多镜头拼接的空间错乱，尺度描述解决远近景的比例失真）；
- 道具：scale／material／holder。

硬约束 7「所有新增字段必须有默认值和校验规则」是这一份的规矩：normalize() 补默认值，
validate() 查规则，两者都在「不改老字段」的前提下工作——老资产 JSON 少这几个键照旧读得出来
（不重做已有功能，只做插入和约束）。

正典板是角色的**基础身份层**（面部骨相、发型基底、瞳色、体型比例、标志性特征，锁定不变）；
换状态面板／状态变体是**状态变体层**（服装、发型变化、受伤、脏污）。生成时把 base_anchor 与
state_variants 里那一条的 override 合并注入（merged_anchor）。
"""
import re
from pathlib import Path

import script_contract

# 正典板转盘图：上排 4 格全身，下排 3 格头部（任务 3）。
TURNAROUND = (('front', '正面 0°', '全身'), ('right', '右侧 90°', '全身'),
              ('left', '左侧 -90°', '全身'), ('back', '背面 180°', '全身'))
HEADS = (('head_3q_left', '3/4 左', '头部'), ('head_front', '正面', '头部'),
         ('head_3q_right', '3/4 右', '头部'))
VIEWS = TURNAROUND + HEADS

# 参考图职责的出厂说法（任务 12）：责任与排除都写死一句，下游逐字复用。
DEFAULT_RESPONSIBILITY = '面部、发型、服装'
DEFAULT_EXCLUDE = '场景、动作、镜头'
STATE_PREFIX = 'CST-'

KINDS = ('character', 'scene', 'prop')
PREFIX = {'character': 'CHAR', 'scene': 'LOC', 'prop': 'PROP'}
# 编号前缀 → 资产类别（分镜里写的是 CHAR_001 这样的编号）。
KIND_OF = {'CHAR': 'character', 'LOC': 'scene', 'PROP': 'prop'}


def resolve_aspect_ratio(workflow_lock=None, saved_preference=None, default='16:9'):
    """统一画幅优先级；纯契约函数，不读取项目文件也不改变校验语义。"""
    lock = workflow_lock if isinstance(workflow_lock, dict) else {}
    return str(lock.get('aspect_ratio') or saved_preference or default)


def resolve_resolution(workflow_lock=None, default='1920x1080'):
    """统一分辨率优先级（项目锁 > 默认）；纯契约函数，不读取项目文件也不改变校验语义。"""
    lock = workflow_lock if isinstance(workflow_lock, dict) else {}
    return str(lock.get('resolution') or default)


def legacy_asset_paths(project):
    """Read-only locations used by pre-stage-layout project archives."""
    root = Path(project)
    return (root / 'episode/assets/资产清单/assets.json', root / 'episode/assets.json')


def kind_of(aid):
    """资产编号 → 类别（认不出来返回空串）。"""
    match = re.match(r'^(CHAR|LOC|PROP)_', str(aid or '').strip())
    return KIND_OF.get(match[1], '') if match else ''


def defaults(kind, workflow_lock=None, saved_preference=None):
    """这一类资产的新增字段默认值（老资产缺键时补这些，不改动别的键）。"""
    if kind == 'character':
        return {'character_id': '', 'canonical_board': '', 'canon_board_views': {},
                'character_anchor': '', 'base_anchor': '', 'reference_role': DEFAULT_RESPONSIBILITY,
                'reference_exclude': DEFAULT_EXCLUDE, 'locked': False, 'state_variants': [],
                'physical_features': dict((key, '') for key in script_contract.PHYSICAL_KEYS)}
    if kind == 'scene':
        return {'scene_id': '', 'reference_image': '',
                'aspect_ratio': resolve_aspect_ratio(workflow_lock, saved_preference, '16:9'),
                'resolution': resolve_resolution(workflow_lock, '1920x1080'),
                'spatial_anchors': [], 'lighting_direction': '',
                'scale_reference': ''}
    if kind == 'prop':
        return {'prop_id': '', 'reference_image': '', 'scale': '', 'material': '', 'holder': ''}
    return {}


def normalize(asset, aid=''):
    """补默认值（就地返回一份新 dict）：只补缺的键，已有的值一个都不动。"""
    out = dict(asset) if isinstance(asset, dict) else {}
    kind = kind_of(aid) or ('character' if 'state_variants' in out else '')
    if not kind:
        return out
    for key, value in defaults(kind).items():
        if key not in out:
            out[key] = dict(value) if isinstance(value, dict) else (
                list(value) if isinstance(value, list) else value)
    key = {'character': 'character_id', 'scene': 'scene_id', 'prop': 'prop_id'}[kind]
    if not out.get(key):
        out[key] = str(aid or '')
    if kind == 'character':
        out['state_variants'] = [item for item in
                                 (normalize_variant(v, i) for i, v in
                                  enumerate(out.get('state_variants') or [], 1))
                                 if item]
        out['physical_features'] = script_contract.field_features(out.get('physical_features'))
    return out


def normalize_variant(item, index=1):
    """状态变体的一条：state_id／name／override／reference_image 四个键补齐。"""
    if not isinstance(item, dict):
        return None
    out = dict(item)
    out.setdefault('state_id', '')
    out.setdefault('name', '')
    out.setdefault('override', '')
    out.setdefault('reference_image', '')
    if not out['state_id']:
        out['state_id'] = '%s%02d' % (STATE_PREFIX, index)
    return out


def state_variants(asset):
    """这一项资产的换状态面板（任务 5）：state_variants 数组，缺了就是空。"""
    values = (asset or {}).get('state_variants')
    if not isinstance(values, list):
        return ()
    return tuple(item for item in (normalize_variant(v, i) for i, v in enumerate(values, 1)) if item)


def variant(asset, costume_id):
    """按 costume_id 找那一条状态变体（找不到返回 None）。"""
    text = str(costume_id or '').strip()
    if not text:
        return None
    for item in state_variants(asset):
        if item['state_id'] == text:
            return item
    return None


def merged_anchor(asset, costume_id=''):
    """生成时注入的锚点＝基础锚点 ＋ 状态覆盖（任务 5）。

    没有 costume_id、或这一条变体没有 override 时只给基础锚点；两段都空时返回空串
    （调用方据此判「这一项还没定稿锚点」）。character_anchor 给了就优先用它——它是人工定稿过
    的那一句，逐字复用（硬约束 4）。
    """
    base = str((asset or {}).get('character_anchor') or (asset or {}).get('base_anchor') or '').strip()
    item = variant(asset, costume_id)
    override = str(item.get('override') or '').strip() if item else ''
    if base and override:
        return '%s；状态覆盖：%s' % (base, override)
    return base or override


IMAGE_SUFFIX = ('.png', '.jpg', '.jpeg', '.webp', '.gif')


def looks_like_image(value):
    """这一串是不是一张图的路径（第 64 期任务 13）。

    canonical_board 按契约定是「转盘图路径」，但 Agent 预筛出来的正典板方案（4 选 1 里的那一句）
    也记在同一个字段上；认不出图后缀就不当成图，转盘图那 7 格照旧显示「（缺图）」。
    """
    return str(value or '').strip().lower().endswith(IMAGE_SUFFIX)


def view_image(asset, view):
    """正典板某一个视角的图：先看 canon_board_views，再退回 canonical_board 只有一张的情形。"""
    views = (asset or {}).get('canon_board_views')
    value = ''
    if isinstance(views, dict):
        value = str(views.get(view) or '').strip()
    if value:
        return value
    if view == 'front':
        fallback = str((asset or {}).get('canonical_board') or '').strip()
        return fallback if looks_like_image(fallback) else ''
    return ''


def cells(asset=None):
    """正典板转盘图的 7 格（上排 4 格全身 ＋ 下排 3 格头部），给资产详情栏画横条。

    每一格：{'view','label','row','image','ready'}。ready=False ＝这一格还没有图（界面上画占位）。
    """
    out = []
    for row, group in ((0, TURNAROUND), (1, HEADS)):
        for view, label, shape in group:
            image = view_image(asset, view)
            out.append({'view': view, 'label': label, 'row': row, 'shape': shape,
                        'image': image, 'ready': bool(image)})
    return tuple(out)


def lock_label(asset):
    """锁定状态那一行的字（任务 3 要在转盘图下面显示）。"""
    asset = asset or {}
    if asset.get('locked'):
        return '已锁定：本角色外观不再变（换状态走状态变体）'
    return '未锁定：定稿锚点后请锁定，禁止下游重新描述'


def card_lines(asset):
    """转盘图下面那三行：锚点字符串（可复制）、参考职责声明、锁定状态。"""
    asset = asset or {}
    anchor = str(asset.get('character_anchor') or asset.get('base_anchor') or '').strip()
    role = str(asset.get('reference_role') or DEFAULT_RESPONSIBILITY).strip()
    exclude = str(asset.get('reference_exclude') or DEFAULT_EXCLUDE).strip()
    board = str(asset.get('canonical_board') or '').strip()
    return (('锚点字符串（逐字复用，可复制）', anchor or '（还没定稿，Agent 会预筛 2 个候选给您点一下）'),
            ('正典板', board if board and not looks_like_image(board) else (
                '已绑定转盘图' if board else '（还没选定，可在资产详情页的「正典板」里选）')),
            ('参考职责声明', '%s；不继承：%s' % (role, exclude)),
            ('锁定状态', lock_label(asset)))


def panel_text():
    """资产管理页面改造后的组件结构图（第 64 期任务 13；附件 v3.0 交付物 2）。

    主页面（02_assets）保持原来的表格布局不动，只在「资产编号」那一格加了进详情的入口；
    正典板、锚点字符串、参考职责声明、状态变体与原始 JSON 全部搬进资产管理页的子路由
    「资产详情页」（附件任务 2.1 的 /assets/:assetId，桌面端是 desktop.asset_detail_id）。
    连贯性清单从第 62 期任务 11 起是独立的一页。
    """
    return (
        '资产管理页（02_assets）\n'
        '├── 顶部：资产 全部／角色／场景／道具　检查提示词　识别背景人物\n'
        '├── 参考图行：导入参考图　候选图墙　参考图目录\n'
        '├── 资产图片行：导入资产图片　批量删除资产　资产目录\n'
        '├── 资产表：资产编号／名称／资产图片／参考图（类目）／外观要求／资产提示词\n'
        '│      · 点「资产编号」那一格 ＝ 进资产详情页（子路由，主页面布局一个像素都不动）\n'
        '├── 制作行：手动制作资产　开始生成　阶段配置　自动补资产\n'
        '├── 【第 62 期任务 11】连贯性清单已挪到侧栏独立成页（06 连贯性清单），不再折在这一页\n'
        '│      · 批次冻结锚点　· 参考图优先级裁决（每条 2 候选＋理由，点一下）\n'
        '│      · 跨批次连续性约束　· 三元组校验　· 锚点漂移\n'
        '└── 资产详情页（子路由；左上角「← 返回资产管理」回主页面）\n'
        '    ├── 区域 1 顶部基础信息栏：资产编号／名称／类别／锁定徽章／锁定按钮／返回\n'
        '    ├── 区域 2 正典板：转盘图 7 格（上排全身 正面 0°／右侧 90°／左侧 -90°／背面 180°，\n'
        '    │              下排头部 3/4 左／正面／3/4 右）＋ 点有图的格子放大 ＋ 重新生成\n'
        '    ├── 区域 3 锚点字符串：展示／复制／编辑（写完与资产 JSON 逐字核对）\n'
        '    ├── 区域 4 参考职责声明：负责什么／不继承什么，可编辑\n'
        '    ├── 区域 5 状态变体（折叠）：CST-## 缩略图／名称／覆盖描述／编辑 ＋ 新增状态变体\n'
        '    └── 区域 6 原始数据（折叠）：这一项的完整资产 JSON\n'
    )


def validate(asset, aid=''):
    """这一项资产的校验问题（空列表＝通过）。规则就是「新增字段的值域」，老字段不查。"""
    problems = []
    if not isinstance(asset, dict):
        return ['资产条目必须是对象']
    kind = kind_of(aid) or kind_of(asset.get('character_id') or asset.get('scene_id')
                                  or asset.get('prop_id') or '')
    if not kind:
        return problems
    data = normalize(asset, aid)
    if kind == 'character':
        anchor = str(data.get('character_anchor') or '')
        if data.get('locked') and not anchor.strip():
            problems.append('锁定前必须定稿 character_anchor（锚点字符串不能为空）')
        views = data.get('canon_board_views')
        if isinstance(views, dict):
            known = {view for view, _label, _shape in VIEWS}
            for view in views:
                if view not in known:
                    problems.append('正典板视角名不认识：' + str(view))
        seen = set()
        for item in state_variants(data):
            sid = item['state_id']
            if not re.fullmatch(re.escape(STATE_PREFIX) + r'\d{2,}', sid):
                problems.append('状态编号须为 %s01 格式：%s' % (STATE_PREFIX, sid))
            if sid in seen:
                problems.append('状态编号重复：' + sid)
            seen.add(sid)
            if not str(item.get('override') or '').strip():
                problems.append('状态变体缺少 override（服装覆盖描述）：' + sid)
        raw = asset.get('physical_features')
        if isinstance(raw, str) and raw.strip():
            problems.append('物理特征要字段化（skin_tone／hair／eyes／distinctive_marks／'
                            'body_type），别写成整句自然语言')
        elif raw is not None and not isinstance(raw, (dict, str)):
            problems.append('physical_features 必须是对象或字符串')
        if not str(data.get('canonical_board') or '').strip() and not isinstance(views, dict):
            problems.append('缺少 canonical_board（正典板转盘图）')
    elif kind == 'scene':
        ratio = str(data.get('aspect_ratio') or '')
        if not re.fullmatch(r'\d{1,2}:\d{1,2}', ratio):
            problems.append('aspect_ratio 须为 16:9 这样的宽高比：' + ratio)
        size = str(data.get('resolution') or '')
        if not re.fullmatch(r'\d{3,5}x\d{3,5}', size):
            problems.append('resolution 须为 1920x1080 这样的分辨率：' + size)
        anchors = data.get('spatial_anchors')
        if not isinstance(anchors, list):
            problems.append('spatial_anchors 必须是数组')
        else:
            for index, item in enumerate(anchors, 1):
                if not isinstance(item, dict) or not str(item.get('object') or '').strip() \
                        or not str(item.get('position') or '').strip():
                    problems.append('第 %d 条空间锚点缺少 object 或 position' % index)
    elif kind == 'prop':
        holder = str(data.get('holder') or '')
        if holder and not re.fullmatch(r'CHAR_\d{3,}', holder):
            problems.append('holder 须为角色编号（CHAR_###）或留空：' + holder)
    return problems


def missing_ids(shots, assets):
    """分镜引用的编号里，资产清单中缺 name 或 image_prompt 的那些（门禁 G-04 用）。"""
    known = assets if isinstance(assets, dict) else {}
    out = []
    seen = set()
    for shot in shots or []:
        if not isinstance(shot, dict):
            continue
        values = []
        for key in ('character_ids', 'characters'):
            value = shot.get(key)
            if isinstance(value, list):
                values += [item for item in value if isinstance(item, str)]
        for key in ('scene_id', 'location', 'costume_id'):
            value = shot.get(key)
            if isinstance(value, str) and value.strip():
                values.append(value.strip())
        for aid in values:
            if not re.fullmatch(r'(CHAR|LOC|PROP)_\d{3,}', aid) or aid in seen:
                continue
            seen.add(aid)
            item = known.get(aid)
            if not isinstance(item, dict) or not str(item.get('name') or '').strip():
                out.append('%s：资产清单里没有这一项' % aid)
            elif not str(item.get('image_prompt') or item.get('positive_prompt')
                        or item.get('prompt') or '').strip():
                out.append('%s：缺少生图提示词' % aid)
    return out


def schema():
    """资产 JSON Schema（含新增字段，交付物 5）。"""
    view_names = [view for view, _label, _shape in VIEWS]
    variant = {'type': 'object', 'required': ['state_id', 'name', 'override', 'reference_image'],
               'properties': {'state_id': {'type': 'string', 'pattern': '^CST-[0-9]{2,}$'},
                              'name': {'type': 'string', 'minLength': 1},
                              'override': {'type': 'string', 'minLength': 1},
                              'reference_image': {'type': 'string'}},
               'additionalProperties': True}
    def box(props, required):
        return {'type': 'object', 'required': list(required), 'properties': props,
                'additionalProperties': True}
    common = {'name': {'type': 'string', 'minLength': 1},
              'description': {'type': 'string'},
              'image_prompt': {'type': 'string'},
              'negative_prompt': {'type': 'string'},
              'reference_images': {'type': 'array', 'items': {'type': 'string'}}}
    character = dict(common, **{
        'character_id': {'type': 'string', 'pattern': '^CHAR_[0-9]{3,}$'},
        'canonical_board': {'type': 'string', 'description': '正典板转盘图（相对路径）'},
        'canon_board_views': {'type': 'object',
                              'properties': {view: {'type': 'string'} for view in view_names},
                              'additionalProperties': False},
        'character_anchor': {'type': 'string', 'description': '逐字复用的锚点字符串'},
        'base_anchor': {'type': 'string'},
        'reference_role': {'type': 'string', 'default': DEFAULT_RESPONSIBILITY},
        'reference_exclude': {'type': 'string', 'default': DEFAULT_EXCLUDE},
        'locked': {'type': 'boolean', 'default': False},
        'state_variants': {'type': 'array', 'items': variant,
                           'description': '换状态面板：基础锚点＋状态覆盖'},
        'physical_features': {'type': 'object', 'description': '物理特征（五件字段化，第 70 期任务 6）',
                              'properties': dict((key, {'type': 'string'})
                                                 for key in script_contract.PHYSICAL_KEYS),
                              'additionalProperties': True}})
    scene = dict(common, **{
        'scene_id': {'type': 'string', 'pattern': '^LOC_[0-9]{3,}$'},
        'reference_image': {'type': 'string'},
        'aspect_ratio': {'type': 'string', 'default': '16:9'},
        'resolution': {'type': 'string', 'default': '1920x1080'},
        'spatial_anchors': {'type': 'array', 'items': box(
            {'object': {'type': 'string'}, 'position': {'type': 'string'},
             'material': {'type': 'string'}}, ('object', 'position'))},
        'lighting_direction': {'type': 'string'},
        'scale_reference': {'type': 'string'}})
    prop = dict(common, **{
        'prop_id': {'type': 'string', 'pattern': '^PROP_[0-9]{3,}$'},
        'reference_image': {'type': 'string'},
        'scale': {'type': 'string'},
        'material': {'type': 'string'},
        'holder': {'type': 'string', 'description': '持有者角色编号，没有就留空'}})
    return {'$schema': 'https://json-schema.org/draft/2020-12/schema',
            'title': '漫剧助手结构化资产清单（v0.8 含正典板／状态变体）',
            'type': 'object',
            'patternProperties': {'^CHAR_[0-9]{3,}$': box(character, ('character_id', 'name')),
                                  '^LOC_[0-9]{3,}$': box(scene, ('scene_id', 'name')),
                                  '^PROP_[0-9]{3,}$': box(prop, ('prop_id', 'name'))},
            'additionalProperties': True}
