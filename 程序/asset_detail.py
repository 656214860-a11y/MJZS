# -*- coding: utf-8 -*-
"""资产详情页（第 64 期任务 13；附件《资产详情页与正典板强制落地命令 v3.0》任务 2.2）。

资产管理主页面（03 资产管理）保持原来的表格布局不动，只多一个「进详情」的入口；正典板、锚点
字符串、参考职责声明、状态变体与原始 JSON 全部搬进这一页——它就是附件里要的「资产详情页」，
在桌面端以子路由的形式挂在资产管理页下面（desktop.asset_detail_id 有值就摆这一页）。

六个区域（附件任务 2.2，从上到下）：
1 顶部基础信息栏：编号、名称、类型、锁定徽章、返回按钮
2 正典板展示区：角色 7 格转盘图（上排 4 格全身、下排 3 格头部），点有图的格子放大；每格可绑定／清除；
  下面一颗「重新生成」把这一角色的正典板选择退回去，重走一遍 4 选 1
3 锚点字符串区：展示 ＋ 复制 ＋ 编辑（写完与资产 JSON 逐字核对）
4 参考职责声明区：负责什么 ＋ 不继承什么，可编辑
5 状态变体折叠区：折叠标题「状态变体（N 个）」，展开列每一条（缩略图／名称／override／编辑），
  另有「新增状态变体」
6 原始数据折叠区：这一项的完整 JSON

界面只读资产清单、只写资产清单（asset_plan.update_fields）；不自己拼 JSON，也不另开第二份数据源。
"""
import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

import asset_thumbs
from agent.core import read
from platform_tools import open_path
from responsive_ui import FlowBar
from ui_dialogs import FileDialog
from ui_widgets import BaseDialog, DescriptionBlock, PrimaryButton, SecondaryButton, TextArea, ask_confirmation, notify

CELL_SIZE = 48                       # 转盘图每一格的缩略图长边（第 65 期任务 4：96 → 48，缩小一倍）
ZOOM_SIZE = 900                      # 点一下放大后的长边（不放大原图，只按原分辨率显示）
TYPE_NAMES = {'CHAR': '角色', 'LOC': '场景', 'PROP': '道具'}
ANCHOR_LIMIT = 300


def _base(desktop):
    return desktop.asset_base()


def _open_zoom(desktop, path, title=''):
    """点一下放大：另开一个小窗摆原分辨率的图（读不出来就退回用系统看图打开）。"""
    image = asset_thumbs.thumbnail(desktop.win, path, ZOOM_SIZE)
    if image is None:
        open_path(path)
        return None
    source = desktop.win.focus_get()
    def restore_focus():
        if source is not None and source.winfo_exists():
            source.focus_set()
    win = BaseDialog(desktop.win, title or Path(path).name, modal=False, chrome=False,
                     on_close=restore_focus)
    tk.Label(win, image=image).pack(padx=8, pady=8)
    win.image = image                        # 图元必须留引用，否则画面上只剩空框
    close = SecondaryButton(win, text='关闭', command=win.close)
    close.pack(pady=(0, 8))
    # Windows 激活新窗口晚于 idle；仅接管窗口自身的焦点，不抢子控件焦点。
    win.bind('<FocusIn>', lambda event: close.focus_set() if event.widget is win else None,
             add='+')
    return win


def _reload(desktop, aid):
    """改完重新摆一遍这一页（页面重建会重置状态栏，所以由调用方最后写状态栏）。"""
    desktop.asset_detail_id = aid
    desktop.show(desktop.page_of('assets'))


def _fields(desktop, aid, values):
    from stage_execution_service import update_asset_plan_fields
    if not desktop.root:
        raise ValueError('还没有打开项目')
    return update_asset_plan_fields(desktop.root, _base(desktop), aid, values)


def bind_view(desktop, aid, view, title=''):
    """给正典板某一格绑定一张图（附件任务 2.2 的 TurnaroundGrid／HeadGrid）。"""
    base = _base(desktop)
    source = FileDialog(desktop.win).open_file(title=title or ('选择转盘图：' + view),
                                        initialdir=str(base / 'assets'),
                                        filetypes=[('图片', '*.png *.jpg *.jpeg *.webp')])
    if not source:
        return None
    from stage_execution_service import bind_asset_canonical_view
    dest = bind_asset_canonical_view(desktop.root, base, aid, view, source)
    desktop.status.set('已绑定正典板：' + view + ' · ' + dest.name)
    _reload(desktop, aid)
    return dest


def clear_view(desktop, aid, view):
    """清掉正典板某一格绑的图（只动这一格，别的视角不动）。"""
    asset = desktop.asset_requirements().get(aid) or {}
    views = asset.get('canon_board_views')
    views = dict(views) if isinstance(views, dict) else {}
    if view not in views:
        desktop.status.set('正典板这一格本来就没有图')
        return None
    views.pop(view)
    values = {'canon_board_views': views}
    if view == 'front' and not views:
        values['canonical_board'] = ''
    _fields(desktop, aid, values)
    desktop.status.set('已清掉正典板：' + view)
    _reload(desktop, aid)
    return True


def regenerate(desktop, aid):
    """「重新生成」：把这一角色的正典板／锚点选择退回待办，两个候选重新摆在详情页上（4 选 1 重走）。

    第 64 期任务 13：原来这两条主观门禁（G-05 锚点定稿、G-06 正典板 4 选 1）在界面上根本没有
    入口，选择也无从落盘——这就是「正典板和换状态面板两次新增都失败」的一半原因。
    """
    from confirm_gates import forget
    dropped = []
    for key in ('canon:' + aid, 'anchor:' + aid):
        try:
            forget(desktop.root, key)
            dropped.append(key)
        except OSError:
            continue
    desktop.status.set('已重新摆出候选：' + aid + ' 的正典板与锚点各 2 个候选（点一下采用）')
    _reload(desktop, aid)
    return dropped


def edit_anchor(desktop, aid):
    """编辑锚点：写完立刻按资产 JSON 核对一遍（附件任务 2.2 区域 3 的「编辑后校验」）。"""
    asset = desktop.asset_requirements().get(aid) or {}
    current = str(asset.get('character_anchor') or asset.get('base_anchor') or '')
    value = simpledialog.askstring('编辑锚点字符串',
                                   '锚点字符串（逐字复用，下游不许改写）：',
                                   initialvalue=current, parent=desktop.win)
    if value is None:
        return None
    value = value.strip()
    if not value:
        notify(desktop.win, '锚点字符串不能为空。', level='error', title='无法保存', status=desktop.status)
        return None
    if '\n' in value or '\r' in value or len(value) > ANCHOR_LIMIT:
        notify(desktop.win, '锚点字符串必须是一行、且不超过 ' + str(ANCHOR_LIMIT) + ' 个字。',
               level='error', title='无法保存', status=desktop.status)
        return None
    _fields(desktop, aid, {'character_anchor': value, 'base_anchor': value})
    saved = str((desktop.asset_requirements().get(aid) or {}).get('character_anchor') or '')
    if saved != value:
        notify(desktop.win, '资产 JSON 里读回来的锚点与刚写的对不上：' + saved,
               level='error', title='保存没生效', status=desktop.status)
        return None
    desktop.status.set('锚点已保存并与资产 JSON 核对一致')
    _reload(desktop, aid)
    return value


def edit_role(desktop, aid):
    """编辑参考职责声明：负责什么 ＋ 不继承什么（附件任务 2.2 区域 4）。"""
    from asset_contract import DEFAULT_EXCLUDE, DEFAULT_RESPONSIBILITY
    asset = desktop.asset_requirements().get(aid) or {}
    role = simpledialog.askstring('参考职责 · 负责',
                                  '这一项参考图负责什么：',
                                  initialvalue=str(asset.get('reference_role') or DEFAULT_RESPONSIBILITY),
                                  parent=desktop.win)
    if role is None:
        return None
    exclude = simpledialog.askstring('参考职责 · 不继承',
                                     '这一项参考图不继承什么：',
                                     initialvalue=str(asset.get('reference_exclude') or DEFAULT_EXCLUDE),
                                     parent=desktop.win)
    if exclude is None:
        return None
    _fields(desktop, aid, {'reference_role': role.strip(), 'reference_exclude': exclude.strip()})
    desktop.status.set('参考职责声明已保存')
    _reload(desktop, aid)
    return role


def toggle_lock(desktop, aid):
    """锁定／解锁（附件任务 5.1 的「锁定/解锁」）。"""
    asset = desktop.asset_requirements().get(aid) or {}
    locked = not bool(asset.get('locked'))
    _fields(desktop, aid, {'locked': locked})
    desktop.status.set('已锁定：本角色外观不再变（换状态走状态变体）' if locked
                       else '已解锁：可以继续改这一项的外观')
    _reload(desktop, aid)
    return locked


def add_variant(desktop, aid):
    """新增状态变体（附件任务 2.2 区域 5 的「新增状态变体」）。"""
    from asset_contract import STATE_PREFIX, normalize_variant, state_variants
    asset = desktop.asset_requirements().get(aid) or {}
    rows = [dict(item) for item in state_variants(asset)]
    name = simpledialog.askstring('新增状态变体', '状态名称（例如「日常装」）：', parent=desktop.win)
    if not name:
        return None
    override = simpledialog.askstring('新增状态变体', '换状态时改什么（服装／发型／受伤／脏污）：',
                                      parent=desktop.win)
    if override is None:
        return None
    rows.append(normalize_variant({'name': name.strip(), 'override': override.strip()}, len(rows) + 1))
    _fields(desktop, aid, {'state_variants': rows})
    desktop.status.set('已新增状态变体：' + name.strip())
    _reload(desktop, aid)
    return rows


def edit_variant(desktop, aid, state_id):
    """编辑一条状态变体的名称与覆盖描述（编号不变）。"""
    from asset_contract import state_variants
    asset = desktop.asset_requirements().get(aid) or {}
    rows = [dict(item) for item in state_variants(asset)]
    target = next((item for item in rows if item.get('state_id') == state_id), None)
    if target is None:
        raise ValueError('这一条状态变体已经不在了，请刷新')
    name = simpledialog.askstring('编辑状态变体', '状态名称：', initialvalue=str(target.get('name') or ''),
                                  parent=desktop.win)
    if name is None:
        return None
    override = simpledialog.askstring('编辑状态变体', '换状态时改什么：',
                                      initialvalue=str(target.get('override') or ''), parent=desktop.win)
    if override is None:
        return None
    if not name.strip() or not override.strip():
        notify(desktop.win, '状态名称与覆盖描述都要写。', level='error', title='无法保存', status=desktop.status)
        return None
    target['name'] = name.strip()
    target['override'] = override.strip()
    _fields(desktop, aid, {'state_variants': rows})
    desktop.status.set('已保存状态变体：' + target['name'])
    _reload(desktop, aid)
    return rows


def delete_variant(desktop, aid, state_id):
    """删掉一条状态变体（问一句再动手）。"""
    from asset_contract import state_variants
    asset = desktop.asset_requirements().get(aid) or {}
    rows = [dict(item) for item in state_variants(asset)]
    target = next((item for item in rows if item.get('state_id') == state_id), None)
    if target is None:
        raise ValueError('这一条状态变体已经不在了，请刷新')
    if not ask_confirmation(desktop.win, '删除状态变体',
                            '删掉「' + str(target.get('name') or state_id) + '」这一条状态变体？',
                            dangerous=True):
        return None
    rows = [item for item in rows if item.get('state_id') != state_id]
    _fields(desktop, aid, {'state_variants': rows})
    desktop.status.set('已删除状态变体：' + str(target.get('name') or state_id))
    _reload(desktop, aid)
    return rows


def _pick(desktop, key, choice, aid):
    """采用一个候选：记一次确认 ＋ 把选择真正写进资产清单，然后重建这一页。"""
    from stage_execution_service import apply_asset_plan_gate_choice
    from confirm_gates import record
    record(desktop.root, key, choice)
    apply_asset_plan_gate_choice(desktop.root, key, choice)
    desktop.status.set('已采用：' + str(choice)[:60] + '（已写进资产 JSON）')
    _reload(desktop, aid)


def _gates_block(desktop, aid):
    """这一项还没处理的门禁待办：G-05 锚点定稿、G-06 正典板 4 选 1。

    附件要的是「Agent 预筛 2 个候选 ＋ 推荐理由，人工一键确认」；第 64 期任务 13 之前这两条
    主观门禁在界面上根本没有入口，点了也无处落盘——这是「两次新增都失败」的核心原因。
    """
    from confirm_gates import run
    registry = desktop.asset_requirements()
    box = ttk.LabelFrame(desktop.content, text='待确认（Agent 已预筛，点一下采用）', padding=6)
    rows = []
    for gate_id in ('G-05', 'G-06'):
        try:
            result = run(gate_id, project=desktop.root, assets=registry)
        except (ValueError, OSError, KeyError):
            continue
        for item in result.get('ask') or ():
            if item.get('key', '').split(':')[-1] != aid:
                continue
            rows.append(item)
    if not rows:
        box.destroy()
        return None
    box.pack(fill='x', pady=(4, 0))
    for item in rows:
        line = ttk.Frame(box)
        line.pack(fill='x', anchor='w', pady=2)
        ttk.Label(line, text=item['title'] + '：', foreground='#b54708').pack(anchor='w')
        for index, candidate in enumerate(item['candidates']):
            row = ttk.Frame(box)
            row.pack(fill='x', anchor='w', padx=(10, 0))
            ttk.Label(row, text='候选' + str(index + 1) + ' ' + str(candidate),
                      wraplength=760, justify='left').pack(side='left')
            SecondaryButton(row, text='采用',
                       command=lambda key=item['key'], value=candidate:
                       desktop.safe(lambda: _pick(desktop, key, value, aid))).pack(side='left', padx=6)
        DescriptionBlock(box, text='理由：' + str(item.get('reason') or '')).pack(anchor='w', padx=(10, 0))
        recommended = item['candidates'][item.get('recommended', 0)]
        PrimaryButton(box, text='采用推荐（候选' + str(int(item.get('recommended', 0)) + 1) + '）',
                   command=lambda key=item['key'], value=recommended:
                   desktop.safe(lambda: _pick(desktop, key, value, aid))).pack(anchor='w', pady=(2, 6))
    return box


def _header(desktop, aid, asset):
    head = FlowBar(desktop.content)
    head.pack(fill='x', pady=(0, 4))
    back = SecondaryButton(head, text='← 返回资产管理',
                           command=lambda: desktop.safe(desktop.close_asset_detail))
    back.pack(side='left', padx=(0, 12), pady=2)
    back.focus_set()
    ttk.Label(head, text=aid + ' · ' + str(asset.get('name', aid)),
              font=('Microsoft YaHei UI', 13, 'bold')).pack(side='left')
    ttk.Label(head, text='　' + TYPE_NAMES.get(aid.split('_')[0], '资产')).pack(side='left')
    locked = bool(asset.get('locked'))
    ttk.Label(head, text='　' + ('已锁定' if locked else '未锁定'),
              foreground='#1a7f37' if locked else '#b54708').pack(side='left')
    SecondaryButton(head, text='解锁' if locked else '锁定',
               command=lambda: desktop.safe(lambda: toggle_lock(desktop, aid))).pack(side='left', padx=8, pady=2)
    return head


def _board_block(desktop, aid, asset):
    """区域 2：正典板展示区（角色 7 格，场景／道具各一格宽幅参考图）。"""
    from asset_contract import cells
    box = ttk.LabelFrame(desktop.content, text='正典板', padding=6)
    box.pack(fill='x', pady=(4, 0))
    grid = ttk.Frame(box)
    grid.pack(fill='x')
    base = _base(desktop)
    for index, cell in enumerate(cells(asset)):
        row, column = divmod(index, 4)
        holder = ttk.Frame(grid)
        holder.grid(row=row, column=column, padx=4, pady=4, sticky='nw')
        ttk.Label(holder, text=cell['label'],
                  foreground='#1a7f37' if cell['ready'] else '#8a8a8a').pack(anchor='w')
        image = None
        thumbnail_unavailable = False
        if cell['ready']:
            path = (base / cell['image']).resolve()
            if path.is_file() and path.is_relative_to(base):
                thumbnail_unavailable = True
                image = asset_thumbs.thumbnail(holder, path, CELL_SIZE)
        if image is not None:
            title = aid + ' · ' + cell['label']
            label = SecondaryButton(holder, image=image, text='放大：' + title,
                                    takefocus=True, cursor='hand2',
                                    command=lambda value=cell['image'], name=title:
                                    desktop.safe(lambda: _open_zoom(desktop, (base / value).resolve(), name)))
            label.image = image
            label.pack(anchor='w')
            label.bind('<Return>', lambda _e, button=label: (button.invoke(), 'break')[1])
            text = Path(cell['image']).name
        elif thumbnail_unavailable:
            # 文件已绑定但缩略图服务暂时没有可用图，不能误导用户以为绑定丢了。
            ttk.Label(holder, text='（缩略图暂不可用）', foreground='#8a8a8a').pack(anchor='w')
            text = Path(cell['image']).name + '（可重新选择图片）'
        else:
            ttk.Label(holder, text='（缺图）', foreground='#8a8a8a').pack(anchor='w')
            text = '还没绑定'
        ttk.Label(holder, text=text, foreground='#555555', wraplength=CELL_SIZE + 40,
                  justify='left').pack(anchor='w')
        buttons = ttk.Frame(holder)
        buttons.pack(anchor='w')
        SecondaryButton(buttons, text='绑定图片',
                   command=lambda view=cell['view'], name=cell['label']:
                   desktop.safe(lambda: bind_view(desktop, aid, view, aid + ' · ' + name))).pack(side='left')
        if cell['ready']:
            SecondaryButton(buttons, text='清除',
                       command=lambda view=cell['view']:
                       desktop.safe(lambda: clear_view(desktop, aid, view))).pack(side='left', padx=4)
    foot = ttk.Frame(box)
    foot.pack(fill='x', pady=(4, 0))
    PrimaryButton(foot, text='重新生成',
               command=lambda: desktop.safe(lambda: regenerate(desktop, aid))).pack(side='left')
    board = str(asset.get('canonical_board') or '').strip()
    note = '当前方案：' + board if board else '还没选定：点「重新生成」把 Agent 预筛的候选摆出来'
    DescriptionBlock(foot, text=note).pack(side='left', padx=8)
    return box


def _anchor_block(desktop, aid, asset):
    from asset_contract import card_lines
    box = ttk.LabelFrame(desktop.content, text='锚点字符串', padding=6)
    box.pack(fill='x', pady=(4, 0))
    anchor = str(asset.get('character_anchor') or asset.get('base_anchor') or '').strip()
    ttk.Label(box, text=anchor or '（还没定稿：用下面的候选点一下，或点「编辑」自己写）',
              wraplength=760, justify='left', foreground='#1a7f37' if anchor else '#8a8a8a').pack(anchor='w')
    row = ttk.Frame(box)
    row.pack(fill='x', pady=(4, 0))
    SecondaryButton(row, text='复制',
               command=lambda: desktop.safe(lambda: (desktop.copy_text(anchor),
                                                     desktop.status.set('锚点字符串已复制')))).pack(side='left')
    SecondaryButton(row, text='编辑',
               command=lambda: desktop.safe(lambda: edit_anchor(desktop, aid))).pack(side='left', padx=6)
    for title, text in card_lines(asset):
        if title in ('锚点字符串（逐字复用，可复制）', '正典板'):
            continue
        DescriptionBlock(box, text=title + '：' + text).pack(anchor='w', pady=(2, 0))
    return box


def _role_block(desktop, aid, asset):
    from asset_contract import DEFAULT_EXCLUDE, DEFAULT_RESPONSIBILITY
    box = ttk.LabelFrame(desktop.content, text='参考职责声明', padding=6)
    box.pack(fill='x', pady=(4, 0))
    role = str(asset.get('reference_role') or DEFAULT_RESPONSIBILITY)
    exclude = str(asset.get('reference_exclude') or DEFAULT_EXCLUDE)
    DescriptionBlock(box, text='负责：' + role).pack(anchor='w')
    DescriptionBlock(box, text='不继承：' + exclude).pack(anchor='w')
    SecondaryButton(box, text='编辑',
               command=lambda: desktop.safe(lambda: edit_role(desktop, aid))).pack(anchor='w', pady=(4, 0))
    return box


def _variants_block(desktop, aid, asset):
    """区域 5：状态变体折叠区（折叠标题「状态变体（N 个）」）。"""
    from asset_contract import state_variants
    rows = state_variants(asset)
    box = ttk.Frame(desktop.content)
    box.pack(fill='x', pady=(4, 0))
    body = ttk.LabelFrame(desktop.content, text='状态变体', padding=6)
    state = {'open': False}
    def toggle():
        state['open'] = not state['open']
        if state['open']:
            body.pack(fill='x', pady=(2, 0))
        else:
            body.pack_forget()
        button.configure(text=title_text() + ('（收起）' if state['open'] else '（展开）'))
    def title_text():
        return '状态变体（' + str(len(rows)) + ' 个）'
    button = SecondaryButton(box, text=title_text() + '（展开）', command=toggle)
    button.pack(anchor='w')
    base = _base(desktop)
    if not rows:
        ttk.Label(body, text='还没有：剧本有换装需求时再新增（编号自动排 CST-01、CST-02…）',
                  foreground='#8a8a8a').pack(anchor='w')
    for item in rows:
        line = ttk.Frame(body)
        line.pack(fill='x', anchor='w', pady=2)
        image = None
        thumbnail_unavailable = False
        value = str(item.get('reference_image') or '').strip()
        if value:
            path = (base / value).resolve()
            if path.is_file() and path.is_relative_to(base):
                thumbnail_unavailable = True
                image = asset_thumbs.thumbnail(line, path, CELL_SIZE)
        if image is not None:
            title = aid + ' · ' + item['state_id']
            label = SecondaryButton(line, image=image, text='放大：' + title,
                                    takefocus=True, cursor='hand2',
                                    command=lambda value=value, name=title: desktop.safe(
                                        lambda: _open_zoom(desktop, (base / value).resolve(), name)))
            label.image = image
            label.pack(side='left', padx=(0, 8))
            label.bind('<Return>', lambda _e, button=label: (button.invoke(), 'break')[1])
        else:
            label = '（缩略图暂不可用）' if thumbnail_unavailable else '（缺缩略图）'
            ttk.Label(line, text=label, foreground='#8a8a8a', width=12).pack(side='left', padx=(0, 8))
        ttk.Label(line, text=item['state_id'] + ' · ' + (item['name'] or '未命名') + '：'
                           + (item['override'] or '缺覆盖描述'), wraplength=520,
                  justify='left').pack(side='left')
        SecondaryButton(line, text='缩略图',
                   command=lambda sid=item['state_id']:
                   desktop.safe(lambda: _bind_variant_image(desktop, aid, sid))).pack(side='left', padx=4)
        SecondaryButton(line, text='编辑',
                   command=lambda sid=item['state_id']:
                   desktop.safe(lambda: edit_variant(desktop, aid, sid))).pack(side='left')
        SecondaryButton(line, text='删除',
                   command=lambda sid=item['state_id']:
                   desktop.safe(lambda: delete_variant(desktop, aid, sid))).pack(side='left', padx=4)
    SecondaryButton(body, text='新增状态变体',
               command=lambda: desktop.safe(lambda: add_variant(desktop, aid))).pack(anchor='w', pady=(6, 0))
    return box


def _bind_variant_image(desktop, aid, state_id):
    """给一条状态变体绑一张缩略图。"""
    base = _base(desktop)
    source = FileDialog(desktop.win).open_file(title='选择状态变体缩略图',
                                        initialdir=str(base / 'assets'),
                                        filetypes=[('图片', '*.png *.jpg *.jpeg *.webp')])
    if not source:
        return None
    from stage_execution_service import bind_asset_variant_thumbnail
    dest = bind_asset_variant_thumbnail(desktop.root, base, aid, state_id, source)
    desktop.status.set('已绑定状态变体缩略图：' + state_id)
    _reload(desktop, aid)
    return dest


def _raw_block(desktop, aid):
    """区域 6：原始 JSON（折叠；只读，便于核对）。"""
    holder = ttk.Frame(desktop.content)
    holder.pack(fill='x', pady=(4, 8))
    body = ttk.LabelFrame(desktop.content, text='原始数据', padding=6)
    state = {'open': False}
    def toggle():
        state['open'] = not state['open']
        if state['open']:
            body.pack(fill='both', pady=(2, 8))
        else:
            body.pack_forget()
        button.configure(text='资产 JSON 原文' + ('（收起）' if state['open'] else '（展开）'))
    button = SecondaryButton(holder, text='资产 JSON 原文（展开）', command=toggle)
    button.pack(anchor='w')
    from asset_plan import plan_file
    text = '{}'
    try:
        data = read(plan_file(desktop.root, _base(desktop)))
        row = data.get(aid) if isinstance(data, dict) else None
        text = json.dumps(row if row is not None else {}, ensure_ascii=False, indent=2)
    except (OSError, ValueError):
        text = '（读不出来）'
    view = TextArea(body, wrap='none', height=12, bg='#ffffff', fg='#243247', padx=10, pady=10)
    view.insert('1.0', text)
    view.configure(state='disabled')
    view.pack(fill='both', expand=True)
    return holder


def show(desktop, aid):
    """把资产详情页摆进 desktop.content（资产管理页的子路由）。"""
    aid = str(aid or '').strip()
    registry = desktop.asset_requirements()
    asset = registry.get(aid) if isinstance(registry, dict) else None
    if not isinstance(asset, dict):
        message='资产不存在：' + (aid or '（没选）') + '。请回资产管理页点一行再看。'
        # 状态栏会在页面重排时被覆盖；错误必须同时留在当前页面，用户和自动化测试
        # 都能看到这次打开失败的原因。
        desktop.note(message)
        ttk.Label(desktop.content,text=message,style='Muted.TLabel',wraplength=640).pack(anchor='w',padx=8,pady=(8,4))
        SecondaryButton(desktop.content, text='← 返回资产管理',
                   command=lambda: desktop.safe(desktop.close_asset_detail)).pack(anchor='w',padx=8)
        return None
    _header(desktop, aid, asset)
    desktop.note('这一页只摆这一项资产：正典板、锚点、参考职责与状态变体都在这里改；'
                 '改完立刻写进资产清单 assets.json，主页面同步刷新。')
    _gates_block(desktop, aid)
    _board_block(desktop, aid, asset)
    if aid.startswith('CHAR_'):
        _anchor_block(desktop, aid, asset)
        _role_block(desktop, aid, asset)
        _variants_block(desktop, aid, asset)
    else:
        _role_block(desktop, aid, asset)
    _raw_block(desktop, aid)
    return aid


# ── 资产清单（第 71 期任务 2）────────────────────────────────────────────────
# 侧栏「03 资产管理」下面那一级缩进的「资产清单」摆的就是这一页：一页看完每个角色的
# 正典板（7 格转盘图）与换状态面板（状态变体 CST-01…）。只读展示＋点图放大；要改内容点
# 每一项下面的「编辑这一项」进资产详情页——两页写的是同一份资产清单 assets.json。
ROSTER_KINDS = ('CHAR', 'LOC', 'PROP')
ROSTER_PANEL_WIDTH = 6               # 「正典板」「换状态」那两个行首标签的宽度（字符数）


def roster_rows(registry):
    """清单页的排序：角色 → 场景 → 道具，同一类按编号先后（认不出的类目排在最后）。"""
    rows = [(str(aid), asset) for aid, asset in (registry or {}).items() if isinstance(asset, dict)]
    def key(item):
        kind = item[0].split('_')[0]
        return (ROSTER_KINDS.index(kind) if kind in ROSTER_KINDS else len(ROSTER_KINDS), item[0])
    return sorted(rows, key=key)


def _roster_thumb(desktop, parent, base, value, title, side='left'):
    """清单页的一张小图：有图才摆，点一下放大；读不出来返回 None（调用方自己写「缺图」）。"""
    value = str(value or '').strip()
    if not value:
        return None
    path = (base / value).resolve()
    if not path.is_file() or not path.is_relative_to(base):
        return None
    image = asset_thumbs.thumbnail(parent, path, CELL_SIZE)
    if image is None:
        return None
    label = tk.Label(parent, image=image, cursor='hand2')
    label.image = image                       # 图元必须留引用，否则画面上只剩空框
    label.pack(side=side, padx=(0, 8), pady=1)
    label.bind('<Button-1>', lambda _e, path=path, name=title:
               desktop.safe(lambda: _open_zoom(desktop, path, name)))
    return label


def _roster_role(desktop, aid, asset):
    """一个角色一块：正典板那几格 ＋ 换状态那几条（场景／道具只有正典板）。"""
    from asset_contract import cells, state_variants
    base = _base(desktop)
    box = ttk.LabelFrame(desktop.content, padding=6,
                         text=aid + ' · ' + str(asset.get('name') or aid) + '　'
                              + TYPE_NAMES.get(aid.split('_')[0], '资产'))
    box.pack(fill='x', pady=(4, 0))
    grid = cells(asset)
    board = ttk.Frame(box)
    board.pack(fill='x')
    ttk.Label(board, text='正典板', width=ROSTER_PANEL_WIDTH,
              foreground='#344d6b').pack(side='left', anchor='n')
    bound = 0
    for cell in grid:
        holder = ttk.Frame(board)
        holder.pack(side='left', padx=(0, 10), anchor='n')
        ttk.Label(holder, text=cell['label'],
                  foreground='#1a7f37' if cell['ready'] else '#8a8a8a').pack(anchor='w')
        if _roster_thumb(desktop, holder, base, cell['image'] if cell['ready'] else '',
                         aid + ' · ' + cell['label'], side='top') is None:
            ttk.Label(holder, text='（缺图）', foreground='#8a8a8a').pack(anchor='w')
        else:
            bound += 1
    states = state_variants(asset) if aid.startswith('CHAR_') else []
    if aid.startswith('CHAR_'):
        panel = ttk.Frame(box)
        panel.pack(fill='x', pady=(6, 0))
        ttk.Label(panel, text='换状态', width=ROSTER_PANEL_WIDTH,
                  foreground='#344d6b').pack(side='left', anchor='n')
        if not states:
            ttk.Label(panel, text='还没有状态变体：剧本有换装需求时，在详情页新增（编号自动排 CST-01…）',
                      foreground='#8a8a8a').pack(side='left')
        for item in states:
            line = ttk.Frame(panel)
            line.pack(side='left', padx=(0, 12), anchor='n')
            _roster_thumb(desktop, line, base, item.get('reference_image'),
                          aid + ' · ' + str(item.get('state_id') or ''))
            ttk.Label(line, text=str(item.get('state_id') or '') + ' · '
                               + str(item.get('name') or '未命名') + '：'
                               + str(item.get('override') or '缺覆盖描述'),
                      wraplength=230, justify='left').pack(side='left')
    foot = ttk.Frame(box)
    foot.pack(fill='x', pady=(6, 0))
    SecondaryButton(foot, text='编辑这一项',
               command=lambda: desktop.safe(lambda: desktop.open_asset_detail(aid))).pack(side='left')
    ttk.Label(foot, text='正典板 ' + str(bound) + '/' + str(len(grid)) + ' 格已绑定 · 状态变体 '
                         + str(len(states)) + ' 个', foreground='#555555').pack(side='left', padx=(10, 0))
    return box


def show_roster(desktop):
    """把资产清单页摆进 desktop.content（侧栏「资产清单」那一格）。"""
    registry = desktop.asset_requirements()
    rows = roster_rows(registry)
    head = FlowBar(desktop.content)
    head.pack(fill='x', pady=(0, 4))
    SecondaryButton(head, text='← 返回资产管理',
               command=lambda: desktop.safe(desktop.close_asset_detail)).pack(side='left', padx=(0, 12), pady=2)
    ttk.Label(head, text='资产清单', font=('Microsoft YaHei UI', 13, 'bold')).pack(side='left')
    ttk.Label(head, text='　共 ' + str(len(rows)) + ' 项').pack(side='left')
    if not rows:
        desktop.note('这个项目还没有资产清单：先到第2步采用一份分镜，回来点「手动制作资产」。')
        return []
    desktop.note('正典板与换状态面板都取自资产清单 assets.json；点小图放大，要改内容点每一项下面的「编辑这一项」。')
    for aid, asset in rows:
        _roster_role(desktop, aid, asset)
    return [aid for aid, _asset in rows]
