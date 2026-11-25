# -*- coding: utf-8 -*-
"""设置页技能包的发现、筛选与树形展示。"""
import os
from pathlib import Path

import pet_bus
import orchestrator.skill_project_layer as skill_project_layer
import skill_registry
from ui_tokens import COLORS

STATUS_LABELS = {'ok': '正常', 'warning': '警告', 'problem': '问题', 'error': '预演失败'}
_KIND_LABELS = {'package': '技能包', 'skill': '独立 SKILL', 'child': '包内子技能',
                'legacy': '旧包', 'stage-entry': '阶段入口'}
_SOURCE_FILTER_LABELS = {'全部来源': '', '项目': 'project', '用户': 'user',
                         '内置': 'builtin', '旧包': 'legacy'}
_SOURCE_LABELS = {'project': '项目版', 'user': '用户版', 'builtin': '内置版',
                  'legacy': '旧包（未挂载）'}
_CHILD_SCAN_SKIP_DIRS = {'.git', '.hg', '.svn', '__pycache__', 'node_modules', '.venv', 'venv'}


class ManageItem:
    """管理页一行：注册表 Skill 本体＋行的真实类型/父子关系/作用域。"""

    def __init__(self, skill, row):
        self.skill = skill
        self.row = row

    def __getattr__(self, name):
        return getattr(self.skill, name)


def _linked(path):
    """os.walk 剪枝用：符号链接／junction 一律不进包内扫描。"""
    try:
        junction = getattr(path, 'is_junction', lambda: False)
        return bool(path.is_symlink() or junction())
    except OSError:
        return True


def _is_stage_root_directory(path):
    """只认 SKILL 根目录直系阶段目录；不用 ``stage_from_path`` 的祖先回溯，免得误判真包。"""
    path = Path(path)
    prefix = path.name[:2]
    return (path.parent.name.casefold() == 'skills' and prefix.isdigit()
            and prefix in skill_project_layer.STAGE_DIRECTORY_IDS)


def _real_package_root(skill):
    """注册入口背后的真实包目录；阶段目录本身的总入口绝不是包。"""
    if not bool(skill.get(skill_registry.IMPORTED_PACKAGE_FLAG, False)):
        return None
    path = getattr(skill, 'path', None)
    if path is None:
        return None
    root = Path(path).parent
    # Registry 也允许阶段目录根部直接放 SKILL.md。那只是阶段总入口；
    # 不能把阶段目录或它的阶段名冒充成「技能包」父节点。
    if _is_stage_root_directory(root):
        return None
    return root


def _child_skill_from_file(path, layer=''):
    """包内子 SKILL 的轻量解析：外部包多为轻格式，缺字段不当作硬错误。"""
    path = Path(path)
    try:
        meta, body = skill_registry.parse(path.read_text(encoding='utf-8-sig'),
                                          source=str(path))
    except (OSError, UnicodeError, ValueError):
        meta, body = {}, ''
    if path.name.casefold() == skill_registry.PACKAGE_SKILL_FILENAME.casefold():
        fallback = path.parent.name
    elif path.name.endswith(skill_registry.SKILL_SUFFIX):
        fallback = path.name[:-len(skill_registry.SKILL_SUFFIX)]
    else:
        fallback = path.stem
    meta = dict(meta)
    name = str(meta.get('name') or '').strip() or fallback
    meta['name'] = name
    meta['displayName'] = (str(meta.get('displayName') or '').strip()
                           or skill_registry.markdown_heading(body) or name)
    meta['description'] = (str(meta.get('description') or '').strip()
                           or skill_registry.markdown_summary(body))
    return skill_registry.Skill(meta, body, path, layer=layer)


def _scan_package_children(package, entry=None, layer='', parent='', stage=''):
    """真实包目录里的子 SKILL 清单；只读、后台调用，不注册、不改变执行语义。"""
    package = Path(package)
    if not package.is_dir() or _linked(package):
        return []
    try:
        entry_resolved = Path(entry).resolve() if entry else None
    except OSError:
        entry_resolved = None
    rows = []
    for folder, directories, files in os.walk(package, followlinks=False):
        base = Path(folder)
        directories[:] = sorted(
            name for name in directories
            if name not in _CHILD_SCAN_SKIP_DIRS and not _linked(base / name))
        for filename in sorted(files):
            lower = filename.casefold()
            if (lower != skill_registry.PACKAGE_SKILL_FILENAME.casefold()
                    and not filename.endswith(skill_registry.SKILL_SUFFIX)):
                continue
            path = base / filename
            if _linked(path):
                continue
            try:
                if entry_resolved is not None and path.resolve() == entry_resolved:
                    continue
            except OSError:
                continue
            skill = _child_skill_from_file(path, layer=layer)
            if stage:
                skill.meta['stage'] = stage
            elif layer == 'legacy':
                skill.meta['stage'] = ''
            try:
                relative = path.relative_to(package).as_posix()
            except ValueError:
                relative = str(path)
            rows.append(ManageItem(skill, {
                'kind': 'child', 'parent': parent, 'package_root': str(package),
                'relative': relative, 'disabled': False, 'source': layer,
                'scope': '随父包 · 不单独执行',
                'action_note': '子技能是包内资料；安装、启停与删除都作用于父包。'}))
    return sorted(rows, key=lambda item: (str(item.row.get('relative') or '').casefold()))


def _scope_text(kind, layer):
    if kind == 'child':
        return '随父包 · 不单独执行'
    if kind == 'legacy':
        return '未挂载 · 不参与执行'
    if kind == 'stage-entry':
        return '所在阶段 · 阶段总入口'
    if layer == 'project':
        return '当前项目 · 注册入口'
    if layer == 'user':
        return '全部项目 · 注册入口'
    if layer == 'builtin':
        return '内置只读 · 注册入口'
    return '注册入口'


def _active_manage_item(skill, disabled=False):
    """注册表条目 → 管理行；只有真实包目录才生成可展开的子技能节点。"""
    package = _real_package_root(skill)
    if package is not None:
        kind = 'package'
    elif bool(skill.get(skill_registry.IMPORTED_PACKAGE_FLAG, False)):
        kind = 'stage-entry'
    else:
        kind = 'skill'
    row = {'kind': kind, 'disabled': bool(disabled),
           'package_root': str(package) if package is not None else '',
           'source': getattr(skill, 'layer', ''),
           'scope': _scope_text(kind, getattr(skill, 'layer', '')),
           'action_note': ('安装、启停、删除与重命名都作用于整包。' if kind == 'package'
                           else '阶段目录总入口；不能按包删除或改名。' if kind == 'stage-entry'
                           else '')}
    item = ManageItem(skill, row)
    if kind == 'package':
        children = _scan_package_children(package, entry=getattr(skill, 'path', None),
                                          layer=getattr(skill, 'layer', ''),
                                          parent=getattr(skill, 'name', ''),
                                          stage=getattr(skill, 'stage', ''))
        row['children'] = children
        row['child_count'] = len(children)
    else:
        row['children'] = []
        row['child_count'] = 0
    return item


def _legacy_manage_items(program):
    """根部旧包（未挂载到阶段的整包）→ 管理行；来源仍只是真实文件位置。"""
    rows = []
    try:
        found = skill_project_layer.scan_residue(
            program, package_source=skill_registry.Registry._package_source)
    except OSError:
        return []
    for entry in found:
        package = Path(entry.get('path') or '')
        source = skill_registry.Registry._package_source(package)
        if source is not None:
            try:
                meta, body = skill_registry.parse(
                    source.read_text(encoding='utf-8-sig'), source=str(source))
                meta = skill_registry.imported_package_meta(meta, body, package, source)
            except (OSError, UnicodeError, ValueError):
                meta, body = {'name': package.name}, ''
        else:
            meta, body = {'name': package.name, 'displayName': package.name,
                          'description': '旧包目录，没有可读取的包说明。'}, ''
        skill = skill_registry.Skill(meta, body, source or package, layer='builtin')
        row = {'kind': 'legacy', 'disabled': False, 'package_root': str(package),
               'relative_path': str(entry.get('relative_path') or package.name),
               'source': 'legacy', 'scope': _scope_text('legacy', 'builtin'),
               'action_note': '旧包没有挂载到阶段；不参与执行，可经残留包回收。'}
        item = ManageItem(skill, row)
        children = _scan_package_children(package, entry=source, layer='legacy',
                                          parent=getattr(skill, 'name', ''))
        row['children'] = children
        row['child_count'] = len(children)
        rows.append(item)
    return rows


def _build_manage_rows(skills, disabled, program):
    """管理页根行：真实技能包/旧包在前，独立 SKILL 在后；不造阶段或来源分组节点。"""
    rows = [_active_manage_item(skill, disabled=False) for skill in skills]
    rows.extend(_active_manage_item(skill, disabled=True) for skill in disabled)
    rows.extend(_legacy_manage_items(program))
    stage_order = {sid: index for index, sid in enumerate(pet_bus.STAGES)}

    def key(item):
        row = item.row
        package_first = 0 if row.get('kind') in ('package', 'legacy') else 1
        return (package_first,
                stage_order.get(getattr(item, 'stage', ''), len(pet_bus.STAGES)),
                skill_project_layer.LAYER_ORDER.get(getattr(item, 'layer', ''), 9),
                str(getattr(item, 'name', '') or '').casefold())

    return sorted(rows, key=key)


def _status_of(item, health):
    row = item.row
    if row.get('kind') == 'legacy':
        return '未挂载'
    if row.get('kind') == 'child':
        return '随父包'
    if row.get('disabled'):
        return '已禁用'
    status = health.get(getattr(item, 'name', ''), '')
    return STATUS_LABELS.get(status, status or '—')


def _filter_values(state):
    source_label = str(state['source_filter'].get() or '全部来源')
    stage_label = str(state['stage_filter'].get() or '全部阶段')
    return (str(state['filter_text'].get() or '').strip().casefold(),
            _SOURCE_FILTER_LABELS.get(source_label, ''),
            state.get('stage_ids', {}).get(stage_label, ''))


def _passes_filters(item, state):
    query, source, stage = _filter_values(state)
    if source and str(item.row.get('source') or getattr(item, 'layer', '')) != source:
        return False
    if stage and getattr(item, 'stage', '') != stage:
        return False
    if not query:
        return True
    row = item.row
    haystack = ' '.join(str(value or '') for value in (
        getattr(item, 'name', ''), getattr(item, 'displayName', ''),
        getattr(item, 'description', ''), row.get('relative', ''),
        row.get('package_root', ''), _KIND_LABELS.get(row.get('kind'), ''))).casefold()
    return query in haystack


def _filters_active(state):
    query, source, stage = _filter_values(state)
    return bool(query or source or stage)


def _visible_manage_rows(state):
    """按过滤条件给出 ``(根行, 可见子行, 根行自身是否命中)``。"""
    out = []
    for item in state.get('rows', []):
        children = list(item.row.get('children') or [])
        own = _passes_filters(item, state)
        matched_children = [child for child in children if _passes_filters(child, state)]
        if own:
            # 父包本身命中时保留整棵子树；子行仍只是包内容，不提升为独立安装项。
            out.append((item, children, True))
        elif matched_children:
            out.append((item, matched_children, False))
    return out


def _row_iid(item):
    row = item.row
    name = str(getattr(item, 'name', '') or '')
    if row.get('kind') == 'legacy':
        return 'legacy|' + str(row.get('relative_path') or name)
    if row.get('disabled'):
        return 'disabled|' + name
    return name or 'row|%s' % id(item)


def _child_iid(child, parent_iid):
    return 'child|%s|%s' % (parent_iid, child.row.get('relative') or getattr(child, 'name', ''))


def _row_values(item, health):
    name = str(getattr(item, 'name', '') or '')
    row = item.row
    stage = pet_bus.stage_label(getattr(item, 'stage', '') or '') or '—'
    source = str(row.get('source') or getattr(item, 'layer', ''))
    return (name, getattr(item, 'displayName', '') or '—', stage,
            _SOURCE_LABELS.get(source, skill_project_layer.LAYER_LABELS.get(
                getattr(item, 'layer', ''), '—')),
            _status_of(item, health), _KIND_LABELS.get(row.get('kind'), '—'),
            str(row.get('scope') or '—'))


def _insert_manage_item(tree, state, item, children, own_hit):
    iid = _row_iid(item)
    kind = item.row.get('kind')
    tags = []
    if item.row.get('disabled'):
        tags.append('disabled')
    if kind == 'legacy':
        tags.append('legacy')
    tree.insert('', 'end', iid=iid, text=item.name or item.displayName,
                values=_row_values(item, state['health']), tags=tuple(tags),
                open=bool(iid in state['expanded'] or (children and not own_hit)))
    state['rowmap'][iid] = item
    for child in children:
        child_iid = _child_iid(child, iid)
        tree.insert(iid, 'end', iid=child_iid,
                    text=child.name or child.displayName,
                    values=_row_values(child, state['health']), tags=('child',))
        state['rowmap'][child_iid] = child
    return iid


def render_manage_rows(tree, state):
    """按当前过滤条件重画树；只有真实包行有子节点，阶段与来源永远只是列/筛选器。"""
    existing = tree.get_children()
    if existing:
        tree.delete(*existing)
    state['rowmap'] = {}
    count = 0
    for item, children, own_hit in _visible_manage_rows(state):
        _insert_manage_item(tree, state, item, children, own_hit)
        count += 1 + len(children)
    tree.tag_configure('disabled', foreground=COLORS['text_muted'])
    tree.tag_configure('legacy', foreground=COLORS['warning'])
    tree.tag_configure('child', foreground=COLORS['text_muted'])
    table = getattr(tree, '_data_table', None)
    if table is not None:
        empty = ('没有符合当前筛选的 SKILL；点「清空」恢复。' if _filters_active(state)
                 else '暂无 SKILL，点「导入 SKILL…」添加。')
        table.empty_label.configure(text=empty)
        table.refresh_empty_state()
    return count


def _detail_text(item, state):
    if item is None:
        return '选中一行后，在这里看类型、来源、作用范围、位置与说明。'
    row = item.row
    kind = row.get('kind')
    source = str(row.get('source') or getattr(item, 'layer', ''))
    lines = ['名称：%s' % (getattr(item, 'name', '') or '—'),
             '显示名：%s' % (getattr(item, 'displayName', '') or '—'),
             '类型：%s' % _KIND_LABELS.get(kind, '—'),
             '来源：%s' % _SOURCE_LABELS.get(source, skill_project_layer.LAYER_LABELS.get(
                 getattr(item, 'layer', ''), '—')),
             '阶段：%s' % (pet_bus.stage_label(getattr(item, 'stage', '') or '') or '未挂载'),
             '状态：%s' % _status_of(item, state.get('health', {})),
             '作用域：%s' % (row.get('scope') or '—')]
    if kind == 'child':
        lines.append('所属包：%s' % (row.get('parent') or '—'))
        lines.append('包内位置：%s' % (row.get('relative') or '—'))
    elif row.get('package_root'):
        lines.append('包目录：%s' % row.get('package_root'))
        lines.append('子技能：%d 个（展开列表查看；随包启停）' % int(row.get('child_count') or 0))
    path = getattr(item, 'path', None)
    if path:
        lines.append('入口文件：%s' % path)
    if row.get('action_note'):
        lines.append('操作口径：%s' % row.get('action_note'))
    description = str(getattr(item, 'description', '') or '').strip()
    if description:
        lines.extend(['', '说明：' + description])
    return '\n'.join(lines)


def update_detail(tree, state):
    detail = state.get('detail')
    if detail is None:
        return
    text = _detail_text(_selected(tree, state), state)
    detail.configure(state='normal')
    detail.delete('1.0', 'end')
    detail.insert('1.0', text)
    detail.configure(state='disabled')


def _remember_expansion(tree, state, opened):
    def remember(_event=None):
        item = tree.focus()
        if not item:
            return
        if opened:
            state['expanded'].add(item)
        else:
            state['expanded'].discard(item)
    return remember


def _selected(tree, state):
    pick = tree.selection()
    if not pick:
        return None
    iid = pick[0]
    rowmap = state.get('rowmap') or {}
    if iid in rowmap:
        return rowmap[iid]
    # 兼容自检或旧调用方直接塞进来的平铺 iid：注册行仍可按名字找回。
    disabled = iid.startswith('disabled|')
    name = iid.split('|', 1)[-1] if disabled else iid
    pool = state.get('disabled', []) if disabled else state['skills']
    skill = next((s for s in pool if getattr(s, 'name', '') == name), None)
    return _active_manage_item(skill, disabled=disabled) if skill is not None else None
