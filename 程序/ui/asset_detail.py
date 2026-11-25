# -*- coding: utf-8 -*-
"""资产详情页（第 64 期任务 13；附件《资产详情页与正典板强制落地命令 v3.0》任务 2.2）。

资产管理主页面（05 资产管理）保持原来的表格布局不动，只多一个「进详情」的入口；正典板、锚点
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
import difflib
import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import ui.asset_thumbs as asset_thumbs
from agent.core import read
from contract import error_codes
from contract.platform_tools import open_path
from responsive_ui import FlowBar
from ui.ui_dialogs import FileDialog
from ui_widgets import BaseDialog, Card, DescriptionBlock, HintLabel, PrimaryButton, SecondaryButton, TextArea, ask_confirmation, ask_string, notify
import contract.pet_bus as pet_bus
from ui_tokens import CHAR_WIDTH, TEXT_ROWS, COLORS, FONTS, SPACING, TEXT_DESC, TEXT_HINT

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
    tk.Label(win, image=image).pack(padx=SPACING['sm'], pady=SPACING['sm'])
    win.image = image                        # 图元必须留引用，否则画面上只剩空框
    close = SecondaryButton(win, text='关闭', command=win.close)
    close.pack(pady=(SPACING['none'], SPACING['sm']))
    # Windows 激活新窗口晚于 idle；仅接管窗口自身的焦点，不抢子控件焦点。
    win.bind('<FocusIn>', lambda event: close.focus_set() if event.widget is win else None,
             add='+')
    return win


def _reload(desktop, aid):
    """重建详情页；操作成功反馈统一由 _complete 在重建后发布。"""
    desktop.asset_detail_id = aid
    desktop.show(desktop.page_of('assets'))


def _complete(desktop, aid, message):
    """提交及核对成功后完成交互；刷新失败时不得发布成功反馈。"""
    _reload(desktop, aid)
    desktop.status.set(message)


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
    _complete(desktop, aid, '已绑定正典板：' + view + ' · ' + dest.name)
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
    _complete(desktop, aid, '已清掉正典板：' + view)
    return True


def regenerate(desktop, aid):
    """「重新生成」：把这一角色的正典板／锚点选择退回待办，两个候选重新摆在详情页上（4 选 1 重走）。

    第 64 期任务 13：原来这两条主观门禁（G-05 锚点定稿、G-06 正典板 4 选 1）在界面上根本没有
    入口，选择也无从落盘——这就是「正典板和换状态面板两次新增都失败」的一半原因。
    """
    from stage_execution_service import reopen_asset_plan_choices
    dropped = reopen_asset_plan_choices(desktop.root, aid)
    _complete(desktop, aid, '已重新摆出候选：' + aid + ' 的正典板与锚点各 2 个候选（点一下采用）')
    return dropped


def edit_anchor(desktop, aid):
    """编辑锚点：写完立刻按资产 JSON 核对一遍（附件任务 2.2 区域 3 的「编辑后校验」）。"""
    asset = desktop.asset_requirements().get(aid) or {}
    current = str(asset.get('character_anchor') or asset.get('base_anchor') or '')
    value = ask_string(desktop.win, '编辑锚点字符串',
                       '锚点字符串（逐字复用，下游不许改写）：',
                       initialvalue=current)
    if value is None:
        return None
    value = value.strip()
    if not value:
        notify(desktop.win, '锚点字符串不能为空。', level='error', title='无法保存', status=desktop.status, modal=False)
        return None
    if '\n' in value or '\r' in value or len(value) > ANCHOR_LIMIT:
        notify(desktop.win, '锚点字符串必须是一行、且不超过 ' + str(ANCHOR_LIMIT) + ' 个字。',
               level='error', title='无法保存', status=desktop.status, modal=False)
        return None
    _fields(desktop, aid, {'character_anchor': value, 'base_anchor': value})
    saved = str((desktop.asset_requirements().get(aid) or {}).get('character_anchor') or '')
    if saved != value:
        notify(desktop.win, '资产 JSON 里读回来的锚点与刚写的对不上：' + saved,
               level='error', title='保存没生效', status=desktop.status, modal=False)
        return None
    _complete(desktop, aid, '锚点已保存并与资产 JSON 核对一致')
    return value


def edit_role(desktop, aid):
    """编辑参考职责声明：负责什么 ＋ 不继承什么（附件任务 2.2 区域 4）。"""
    from contract.asset_contract import DEFAULT_EXCLUDE, DEFAULT_RESPONSIBILITY
    asset = desktop.asset_requirements().get(aid) or {}
    role = ask_string(desktop.win, '参考职责 · 负责',
                      '这一项参考图负责什么：',
                      initialvalue=str(asset.get('reference_role') or DEFAULT_RESPONSIBILITY))
    if role is None:
        return None
    exclude = ask_string(desktop.win, '参考职责 · 不继承',
                         '这一项参考图不继承什么：',
                         initialvalue=str(asset.get('reference_exclude') or DEFAULT_EXCLUDE))
    if exclude is None:
        return None
    _fields(desktop, aid, {'reference_role': role.strip(), 'reference_exclude': exclude.strip()})
    _complete(desktop, aid, '参考职责声明已保存')
    return role


def toggle_lock(desktop, aid):
    """锁定／解锁（附件任务 5.1 的「锁定/解锁」）。"""
    asset = desktop.asset_requirements().get(aid) or {}
    locked = not bool(asset.get('locked'))
    _fields(desktop, aid, {'locked': locked})
    _complete(desktop, aid, '已锁定：本角色外观不再变（换状态走状态变体）' if locked
              else '已解锁：可以继续改这一项的外观')
    return locked


def add_variant(desktop, aid):
    """新增状态变体（附件任务 2.2 区域 5 的「新增状态变体」）。"""
    from contract.asset_contract import STATE_PREFIX, normalize_variant, state_variants
    asset = desktop.asset_requirements().get(aid) or {}
    rows = [dict(item) for item in state_variants(asset)]
    name = ask_string(desktop.win, '新增状态变体', '状态名称（例如「日常装」）：')
    if not name:
        return None
    override = ask_string(desktop.win, '新增状态变体', '换状态时改什么（服装／发型／受伤／脏污）：')
    if override is None:
        return None
    rows.append(normalize_variant({'name': name.strip(), 'override': override.strip()}, len(rows) + 1))
    _fields(desktop, aid, {'state_variants': rows})
    _complete(desktop, aid, '已新增状态变体：' + name.strip())
    return rows


def edit_variant(desktop, aid, state_id):
    """编辑一条状态变体的名称与覆盖描述（编号不变）。"""
    from contract.asset_contract import state_variants
    asset = desktop.asset_requirements().get(aid) or {}
    rows = [dict(item) for item in state_variants(asset)]
    target = next((item for item in rows if item.get('state_id') == state_id), None)
    if target is None:
        raise ValueError('这一条状态变体已经不在了，请刷新')
    name = ask_string(desktop.win, '编辑状态变体', '状态名称：',
                      initialvalue=str(target.get('name') or ''))
    if name is None:
        return None
    override = ask_string(desktop.win, '编辑状态变体', '换状态时改什么：',
                          initialvalue=str(target.get('override') or ''))
    if override is None:
        return None
    if not name.strip() or not override.strip():
        notify(desktop.win, '状态名称与覆盖描述都要写。', level='error', title='无法保存', status=desktop.status, modal=False)
        return None
    target['name'] = name.strip()
    target['override'] = override.strip()
    _fields(desktop, aid, {'state_variants': rows})
    _complete(desktop, aid, '已保存状态变体：' + target['name'])
    return rows


def delete_variant(desktop, aid, state_id):
    """删掉一条状态变体（问一句再动手）。"""
    from contract.asset_contract import state_variants
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
    _complete(desktop, aid, '已删除状态变体：' + str(target.get('name') or state_id))
    return rows


def _pick(desktop, key, choice, aid, digest=''):
    """采用一个候选：准备→落盘→确认一条路走完（O10）；只有落盘成功才报已采用。"""
    from stage_execution_service import adopt_asset_plan_choice
    try:
        adopt_asset_plan_choice(desktop.root, key, choice, digest)
    except Exception as error:
        raise RuntimeError('采用没有完成：确认没有生效，候选还留着，可再点一次（'
                           + str(error) + '）') from error
    _complete(desktop, aid, '已采用：' + str(choice)[:60] + '（已写进资产 JSON）')


def _gates_block(desktop, aid):
    """这一项还没处理的门禁待办：G-05 锚点定稿、G-06 正典板 4 选 1。

    附件要的是「Agent 预筛 2 个候选 ＋ 推荐理由，人工一键确认」；第 64 期任务 13 之前这两条
    主观门禁在界面上根本没有入口，点了也无处落盘——这是「两次新增都失败」的核心原因。
    """
    from domain.confirm_gates import run
    registry = desktop.asset_requirements()
    box = Card(desktop.content)
    ttk.Label(box, text='待确认（Agent 已预筛，点一下采用）').pack(anchor='w')
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
    box.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))
    for item in rows:
        line = ttk.Frame(box)
        line.pack(fill='x', anchor='w', pady=SPACING['xs'])
        ttk.Label(line, text=item['title'] + '：', foreground=COLORS['warning_text']).pack(anchor='w')
        for index, candidate in enumerate(item['candidates']):
            row = ttk.Frame(box)
            row.pack(fill='x', anchor='w', padx=(SPACING['md'], SPACING['none']))
            ttk.Label(row, text='候选' + str(index + 1) + ' ' + str(candidate),
                      wraplength=TEXT_DESC['wraplength'], justify='left').pack(side='left')
            SecondaryButton(row, text='采用',
                       command=lambda key=item['key'], value=candidate, digest=item.get('digest', ''):
                       desktop.safe(lambda: _pick(desktop, key, value, aid, digest))).pack(side='left', padx=SPACING['sm'])
        DescriptionBlock(box, text='理由：' + str(item.get('reason') or '')).pack(anchor='w', padx=(SPACING['md'], SPACING['none']))
        recommended = item['candidates'][item.get('recommended', 0)]
        PrimaryButton(box, text='采用推荐（候选' + str(int(item.get('recommended', 0)) + 1) + '）',
                   command=lambda key=item['key'], value=recommended, digest=item.get('digest', ''):
                   desktop.safe(lambda: _pick(desktop, key, value, aid, digest))).pack(anchor='w', pady=(SPACING['xs'], SPACING['sm']))
    return box


def _header(desktop, aid, asset):
    head = FlowBar(desktop.content)
    head.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
    back = SecondaryButton(head, text='← 返回资产管理',
                           command=lambda: desktop.safe(desktop.close_asset_detail))
    back.pack(side='left', padx=(SPACING['none'], SPACING['md']), pady=SPACING['xs'])
    back.focus_set()
    ttk.Label(head, text=aid + ' · ' + str(asset.get('name', aid)),
              font=FONTS['heading_3']).pack(side='left')
    ttk.Label(head, text='　' + TYPE_NAMES.get(aid.split('_')[0], '资产')).pack(side='left')
    locked = bool(asset.get('locked'))
    ttk.Label(head, text='　' + ('已锁定' if locked else '未锁定'),
              foreground=COLORS['success_text'] if locked else COLORS['warning_text']).pack(side='left')
    SecondaryButton(head, text='解锁' if locked else '锁定',
               command=lambda: desktop.safe(lambda: toggle_lock(desktop, aid))).pack(side='left', padx=SPACING['sm'], pady=SPACING['xs'])
    return head


def _board_block(desktop, aid, asset):
    """区域 2：正典板展示区（角色 7 格，场景／道具各一格宽幅参考图）。"""
    from contract.asset_contract import cells
    box = Card(desktop.content)
    ttk.Label(box, text='正典板').pack(anchor='w')
    box.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))
    grid = ttk.Frame(box)
    grid.pack(fill='x')
    base = _base(desktop)
    for index, cell in enumerate(cells(asset)):
        row, column = divmod(index, 4)
        holder = ttk.Frame(grid)
        holder.grid(row=row, column=column, padx=SPACING['xs'], pady=SPACING['xs'], sticky='nw')
        ttk.Label(holder, text=cell['label'],
                  foreground=COLORS['success_text'] if cell['ready'] else COLORS['text_muted']).pack(anchor='w')
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
            HintLabel(holder, text='（缩略图暂不可用）').pack(anchor='w')
            text = Path(cell['image']).name + '（可重新选择图片）'
        else:
            HintLabel(holder, text='（缺图）').pack(anchor='w')
            text = '还没绑定'
        ttk.Label(holder, text=text, foreground=COLORS['text_secondary'], wraplength=CELL_SIZE + SPACING['2xl'] + SPACING['sm'],
                  justify='left').pack(anchor='w')
        buttons = ttk.Frame(holder)
        buttons.pack(anchor='w')
        SecondaryButton(buttons, text='绑定图片',
                   command=lambda view=cell['view'], name=cell['label']:
                   desktop.safe(lambda: bind_view(desktop, aid, view, aid + ' · ' + name))).pack(side='left')
        if cell['ready']:
            SecondaryButton(buttons, text='清除',
                       command=lambda view=cell['view']:
                       desktop.safe(lambda: clear_view(desktop, aid, view))).pack(side='left', padx=SPACING['xs'])
    foot = ttk.Frame(box)
    foot.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))
    PrimaryButton(foot, text='重新生成',
               command=lambda: desktop.safe(lambda: regenerate(desktop, aid))).pack(side='left')
    board = str(asset.get('canonical_board') or '').strip()
    note = '当前方案：' + board if board else '还没选定：点「重新生成」把 Agent 预筛的候选摆出来'
    DescriptionBlock(foot, text=note).pack(side='left', padx=SPACING['sm'])
    return box


def _anchor_block(desktop, aid, asset):
    from contract.asset_contract import card_lines
    box = Card(desktop.content)
    ttk.Label(box, text='锚点字符串').pack(anchor='w')
    box.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))
    anchor = str(asset.get('character_anchor') or asset.get('base_anchor') or '').strip()
    ttk.Label(box, text=anchor or '（还没定稿：用下面的候选点一下，或点「编辑」自己写）',
              wraplength=TEXT_DESC['wraplength'], justify='left',
              foreground=COLORS['success_text'] if anchor else COLORS['text_muted']).pack(anchor='w')
    row = ttk.Frame(box)
    row.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))
    def copy_anchor():
        reason = desktop.copy_text(anchor)
        desktop.status.set('复制失败：' + reason if reason else '锚点字符串已复制')
    SecondaryButton(row, text='复制',
               command=lambda: desktop.safe(copy_anchor)).pack(side='left')
    SecondaryButton(row, text='编辑',
               command=lambda: desktop.safe(lambda: edit_anchor(desktop, aid))).pack(side='left', padx=SPACING['sm'])
    for title, text in card_lines(asset):
        if title in ('锚点字符串（逐字复用，可复制）', '正典板'):
            continue
        DescriptionBlock(box, text=title + '：' + text).pack(anchor='w', pady=(SPACING['xs'], SPACING['none']))
    return box


def _role_block(desktop, aid, asset):
    from contract.asset_contract import DEFAULT_EXCLUDE, DEFAULT_RESPONSIBILITY
    box = Card(desktop.content)
    ttk.Label(box, text='参考职责声明').pack(anchor='w')
    box.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))
    role = str(asset.get('reference_role') or DEFAULT_RESPONSIBILITY)
    exclude = str(asset.get('reference_exclude') or DEFAULT_EXCLUDE)
    DescriptionBlock(box, text='负责：' + role).pack(anchor='w')
    DescriptionBlock(box, text='不继承：' + exclude).pack(anchor='w')
    SecondaryButton(box, text='编辑',
               command=lambda: desktop.safe(lambda: edit_role(desktop, aid))).pack(anchor='w', pady=(SPACING['xs'], SPACING['none']))
    return box


def _variants_block(desktop, aid, asset):
    """区域 5：状态变体折叠区（折叠标题「状态变体（N 个）」）。"""
    from contract.asset_contract import state_variants
    rows = state_variants(asset)
    box = ttk.Frame(desktop.content)
    box.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))
    body = Card(desktop.content)
    ttk.Label(body, text='状态变体').pack(anchor='w')
    state = {'open': False}
    def toggle():
        state['open'] = not state['open']
        if state['open']:
            body.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))
        else:
            body.pack_forget()
        button.configure(text=title_text() + ('（收起）' if state['open'] else '（展开）'))
    def title_text():
        return '状态变体（' + str(len(rows)) + ' 个）'
    button = SecondaryButton(box, text=title_text() + '（展开）', command=toggle)
    button.pack(anchor='w')
    base = _base(desktop)
    if not rows:
        DescriptionBlock(body, text='还没有：剧本有换装需求时再新增（编号自动排 CST-01、CST-02…）').pack(anchor='w')
    for item in rows:
        line = ttk.Frame(body)
        line.pack(fill='x', anchor='w', pady=SPACING['xs'])
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
            label.pack(side='left', padx=(SPACING['none'], SPACING['sm']))
            label.bind('<Return>', lambda _e, button=label: (button.invoke(), 'break')[1])
        else:
            label = '（缩略图暂不可用）' if thumbnail_unavailable else '（缺缩略图）'
            ttk.Label(line, text=label, foreground=COLORS['text_muted'], width=CHAR_WIDTH['xl']).pack(
                side='left', padx=(SPACING['none'], SPACING['sm']))
        ttk.Label(line, text=item['state_id'] + ' · ' + (item['name'] or '未命名') + '：'
                           + (item['override'] or '缺覆盖描述'), wraplength=TEXT_DESC['wraplength'],
                  justify='left').pack(side='left')
        SecondaryButton(line, text='缩略图',
                   command=lambda sid=item['state_id']:
                   desktop.safe(lambda: _bind_variant_image(desktop, aid, sid))).pack(side='left', padx=SPACING['xs'])
        SecondaryButton(line, text='编辑',
                   command=lambda sid=item['state_id']:
                   desktop.safe(lambda: edit_variant(desktop, aid, sid))).pack(side='left')
        SecondaryButton(line, text='删除',
                   command=lambda sid=item['state_id']:
                   desktop.safe(lambda: delete_variant(desktop, aid, sid))).pack(side='left', padx=SPACING['xs'])
    SecondaryButton(body, text='新增状态变体',
               command=lambda: desktop.safe(lambda: add_variant(desktop, aid))).pack(
                   anchor='w', pady=(SPACING['sm'], SPACING['none']))
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
    _complete(desktop, aid, '已绑定状态变体缩略图：' + state_id)
    return dest


_FRAME_LABELS = {'latest': '最新', 'stale': '过期', 'missing': '缺失'}
_FRAME_FOREGROUND_TOKENS = {'latest': 'success_text', 'stale': 'warning_text',
                            'missing': 'danger_text'}


def _usage_label(parent, text, foreground):
    """使用情况逐镜行的单行标签：前景色用 configure 下发，构造只给排版。"""
    label = ttk.Label(parent, text=text, anchor='w', justify='left')
    label.configure(foreground=foreground)
    return label


def _usage_block(desktop, aid, asset=None):
    """使用情况块（DES-S05-51／UX-S05-53）：参考职责／状态变体之后、JSON 原文之前。"""
    box = Card(desktop.content)
    ttk.Label(box, text='使用情况').pack(anchor='w')
    box.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))
    try:
        from stage_execution_service import asset_usage
        usage = asset_usage(desktop.root, aid)
    except Exception:
        DescriptionBlock(box, text='使用情况暂时读不出，不影响本页其他内容。').pack(anchor='w')
        return box
    if usage.get('orphan') or not usage.get('rows'):
        DescriptionBlock(box, text='当前没有采用镜头引用，属可回收的孤立资产').pack(anchor='w')
        return box
    DescriptionBlock(
        box, text='被 %d 个采用镜头引用' % len(usage['rows'])).pack(anchor='w')
    # 逐镜行放进可滚动区，避免引用多时撑开整页；状态色只取 COLORS，不写内联十六进制。
    canvas = tk.Canvas(box, highlightthickness=0, height=SPACING['2xl'] * 4)
    scroll = ttk.Scrollbar(box, orient='vertical', command=canvas.yview)
    rows_host = ttk.Frame(canvas)
    rows_host.bind('<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.create_window((0, 0), window=rows_host, anchor='nw')
    canvas.configure(yscrollcommand=scroll.set)
    canvas.pack(side='left', fill='both', expand=True, pady=(SPACING['xs'], SPACING['none']))
    scroll.pack(side='right', fill='y', pady=(SPACING['xs'], SPACING['none']))
    from ui.video_progress import stale_videos_notice, usage_video_appearance
    for row in usage['rows']:
        frame_key = row.get('frame') if row.get('frame') in _FRAME_LABELS else 'stale'
        reason = str(row.get('frame_reason') or '').strip()
        line = ttk.Frame(rows_host)
        line.pack(fill='x', anchor='w', pady=SPACING['xs'])
        _usage_label(line, '%s · %s' % (row.get('episode') or '', row.get('shot') or ''),
                     COLORS['text_secondary']).pack(side='left')
        _usage_label(line, '首帧：' + _FRAME_LABELS[frame_key],
                     COLORS[_FRAME_FOREGROUND_TOKENS[frame_key]]).pack(
                         side='left', padx=(SPACING['xs'], SPACING['none']))
        if reason:
            _usage_label(line, '（' + reason + '）', COLORS['text_secondary']).pack(side='left')
        video_text, color = usage_video_appearance(row.get('video'), row.get('video_version'))
        _usage_label(line, video_text, color).pack(side='left', padx=(SPACING['xs'], SPACING['none']))
    videos = usage.get('videos') or []
    if str(aid or '').startswith('CHAR_') and videos:
        DescriptionBlock(
            box, text='出现过的镜头视频：' + '、'.join(str(item) for item in videos)).pack(
                anchor='w', pady=(SPACING['xs'], SPACING['none']))
    notice = stale_videos_notice(usage.get('stale_videos'))
    if notice:
        DescriptionBlock(box, text=notice).pack(anchor='w', pady=(SPACING['xs'], SPACING['none']))
    return box


_SOURCE_BADGES = {'generated': '生成', 'imported': '导入', 'manual': '手改'}
_VERSION_ROWS = 20
_COMPARE_THUMB = 240


def _version_line(key, fields):
    if key not in fields:
        return key + '：（这一版没有）'
    value = fields[key]
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False)
    return key + '：' + value


def _evolution_block(desktop, aid, asset=None):
    """演变记录块（AST-VERSION-2／DOC-D9-2）：使用情况之后、原始 JSON 之前。

    详情页打开时才读版本文件：先摆占位让页面先画出来，一拍后再建行；
    读失败只降级一行提示，不阻断本页其余块。
    """
    box = Card(desktop.content)
    ttk.Label(box, text='演变记录').pack(anchor='w')
    box.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))
    host = ttk.Frame(box)
    host.pack(fill='x')
    HintLabel(host, text='版本记录读取中…').pack(anchor='w')
    def populate():
        if not host.winfo_exists():
            return
        try:
            from domain.asset_versions import list_versions
            records = list_versions(desktop.root, aid)
        except Exception:
            records = None
        for child in host.winfo_children():
            child.destroy()
        if records is None:
            DescriptionBlock(host, text='版本记录暂时读不出，不影响本页其他内容。').pack(anchor='w')
        elif not records:
            DescriptionBlock(host, text='暂无历史').pack(anchor='w')
        else:
            _version_rows(desktop, aid, host, records)
    win = getattr(desktop, 'win', None)
    if win is not None:
        win.after_idle(populate)
    else:
        populate()
    return box


def _version_rows(desktop, aid, host, records):
    """版本行：勾选框＋版本号＋时间＋来源徽标＋一句话；默认最近 20 条可展开全部。"""
    from domain.asset_versions import describe
    state = {'expanded': False, 'vars': {}}
    def build():
        for child in host.winfo_children():
            child.destroy()
        state['vars'] = {}
        shown = records if state['expanded'] else records[-_VERSION_ROWS:]
        for record in shown:
            line = ttk.Frame(host)
            line.pack(fill='x', anchor='w', pady=SPACING['xs'])
            var = tk.BooleanVar(value=False)
            state['vars'][record.get('version')] = var
            ttk.Checkbutton(line, variable=var).pack(side='left')
            ttk.Label(line, text='v' + str(record.get('version'))).pack(side='left')
            HintLabel(line, text='　' + str(record.get('at') or '')).pack(side='left')
            source = _SOURCE_BADGES.get(record.get('source'), record.get('source') or '')
            HintLabel(line, text='　' + source).pack(side='left')
            ttk.Label(line, text='　' + describe(record), justify='left',
                      wraplength=TEXT_DESC['wraplength']).pack(side='left')
        bar = ttk.Frame(host)
        bar.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))
        SecondaryButton(bar, text='并排对比', command=lambda: desktop.safe(
            lambda: _compare_pick(desktop, aid, records, state['vars']))).pack(side='left')
        SecondaryButton(bar, text='退回此版', command=lambda: desktop.safe(
            lambda: _restore_pick(desktop, aid, records, state['vars']))).pack(
                side='left', padx=SPACING['sm'])
        if len(records) > _VERSION_ROWS and not state['expanded']:
            SecondaryButton(bar, text='展开全部（共 %d 条）' % len(records),
                            command=lambda: (state.__setitem__('expanded', True),
                                             build())).pack(side='left')
    build()


def _checked(vars_):
    return [n for n, var in vars_.items() if var.get()]


def _compare_pick(desktop, aid, records, vars_):
    chosen = _checked(vars_)
    if len(chosen) != 2:
        desktop.status.set('勾选两条记录再并排对比')
        return None
    return compare_versions(desktop, aid, records, chosen[0], chosen[1])


def _restore_pick(desktop, aid, records, vars_):
    chosen = _checked(vars_)
    if len(chosen) != 1:
        desktop.status.set('勾选一条记录再退回')
        return None
    return restore_to_version(desktop, aid, chosen[0], records)


def _version_image(desktop, summary):
    """版本记录里的图片摘要 → 缩略图；图不在资产库或那一版没有图给 ``None``。"""
    if not isinstance(summary, dict):
        return None
    rel = str(summary.get('path') or '')
    if not rel:
        return None
    base = _base(desktop)
    path = (base / rel).resolve()
    if not path.is_file() or not path.is_relative_to(base):
        return None
    return asset_thumbs.thumbnail(desktop.win, path, _COMPARE_THUMB)


def compare_versions(desktop, aid, records, a, b):
    """两版并排对比（只读）：文字左右两栏 difflib 逐行高亮；图片左右缩略图并排。"""
    from domain.asset_versions import snapshot_at
    snap_a, snap_b = snapshot_at(records, a), snapshot_at(records, b)
    fields_a, fields_b = snap_a['fields'], snap_b['fields']
    keys = sorted(set(fields_a) | set(fields_b))
    left_lines = [_version_line(key, fields_a) for key in keys]
    right_lines = [_version_line(key, fields_b) for key in keys]
    win = BaseDialog(desktop.win, aid + ' · 第 %s 版 ↔ 第 %s 版' % (a, b), modal=False)
    panes = ttk.Frame(win.content)
    panes.pack(fill='both', expand=True)
    left = TextArea(panes, wrap='none', height=TEXT_ROWS['xl'],
                    bg=COLORS['background_card'], fg=COLORS['text_primary'],
                    width=CHAR_WIDTH['3xl'] * 4)
    right = TextArea(panes, wrap='none', height=TEXT_ROWS['xl'],
                     bg=COLORS['background_card'], fg=COLORS['text_primary'],
                     width=CHAR_WIDTH['3xl'] * 4)
    left.tag_configure('diff', foreground=COLORS['danger_text'])
    right.tag_configure('diff', foreground=COLORS['success_text'])
    for item in difflib.ndiff(left_lines, right_lines):
        code, text = item[:2], item[2:]
        if code == '- ':
            left.insert('end', text + '\n', 'diff')
            right.insert('end', '\n')
        elif code == '+ ':
            left.insert('end', '\n')
            right.insert('end', text + '\n', 'diff')
        elif code == '  ':
            left.insert('end', text + '\n')
            right.insert('end', text + '\n')
    for pane in (left, right):
        pane.configure(state='disabled')
        pane.pack(side='left', fill='both', expand=True,
                  padx=(SPACING['none'], SPACING['sm']))
    if 'image' in snap_a or 'image' in snap_b:
        row = ttk.Frame(win.content)
        row.pack(fill='x', pady=(SPACING['sm'], SPACING['none']))
        for title, snap in (('第 %s 版' % a, snap_a), ('第 %s 版' % b, snap_b)):
            cell = ttk.Frame(row)
            cell.pack(side='left', padx=SPACING['sm'])
            ttk.Label(cell, text=title).pack(anchor='w')
            image = _version_image(desktop, snap.get('image'))
            if image is not None:
                label = ttk.Label(cell, image=image)
                label.image = image
                label.pack(anchor='w')
            else:
                HintLabel(cell, text='（那一版没有图）' if snap.get('image') is None
                          else '（图已不在资产库）').pack(anchor='w')
    win.add_action('关闭', win.close)
    return win


def _short(value):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = text.replace('\n', ' ')
    return text if len(text) <= 40 else text[:39] + '…'


def _restore_preview(desktop, aid, asset, snap, n):
    """确认窗正文：列出将被覆盖的当前内容（字段与图片）。"""
    lines = ['退回第 %d 版后，下面的当前内容会被覆盖（演变记录本身一条不删）：' % n]
    for key in sorted(snap['fields']):
        target = snap['fields'][key]
        if target is None and key not in asset:
            continue
        if target is not None and asset.get(key) == target:
            continue
        lines.append('%s：%s → %s' % (
            key, _short(asset.get(key)) if key in asset else '（没有）',
            _short(target) if target is not None else '（删除）'))
    if 'image' in snap:
        from domain.asset_versions import image_summary
        base = _base(desktop)
        rel = ''
        try:
            registry = read(base / 'assets.json')
            if isinstance(registry, dict):
                rel = str((registry.get(aid) or {}).get('image') or '')
        except (OSError, ValueError):
            pass
        current = image_summary((base / rel).resolve(), base) if rel else None
        target = snap['image']
        same = (isinstance(target, dict) and current
                and target.get('sha256') == current.get('sha256'))
        if not same:
            lines.append('图片：%s → %s' % (
                rel or '（没有图）', (target or {}).get('path') or '（没有图）'))
    if len(lines) == 1:
        lines.append('（当前内容与这一版一致，只追加一条退回记录）')
    return '\n'.join(lines)


def restore_to_version(desktop, aid, n, records=None):
    """「退回此版」：确认窗列出将被覆盖的当前内容；确认后走 restore_version。"""
    from domain import asset_versions
    asset = desktop.asset_requirements().get(aid) or {}
    if asset.get('locked'):
        notify(desktop.win, aid + ' 已锁定：先解锁再退回历史版本。',
               level='error', title='无法退回', status=desktop.status, modal=False)
        return None
    if records is None:
        records = asset_versions.list_versions(desktop.root, aid)
    preview = _restore_preview(desktop, aid, asset,
                               asset_versions.snapshot_at(records, n), n)
    if not ask_confirmation(desktop.win, '退回第 %d 版' % n, preview, dangerous=True):
        return None
    from stage_execution_service import asset_batch_gateway
    base = (desktop.asset_write_base() if hasattr(desktop, 'asset_write_base')
            else _base(desktop))
    try:
        record = asset_versions.restore_version(base, aid, n,
                                                gateway=asset_batch_gateway())
    except (ValueError, TypeError) as exc:
        notify(desktop.win, error_codes.user_text(exc), level='error', title='无法退回',
               status=desktop.status, modal=False)
        return None
    _complete(desktop, aid, '已退回第 %d 版（当前内容已覆盖，旧记录一条没删）' % n)
    return record


def _raw_block(desktop, aid):
    """区域 6：原始 JSON（折叠；只读，便于核对）。"""
    holder = ttk.Frame(desktop.content)
    holder.pack(fill='x', pady=(SPACING['xs'], SPACING['sm']))
    body = Card(desktop.content)
    ttk.Label(body, text='原始数据').pack(anchor='w')
    state = {'open': False}
    def toggle():
        state['open'] = not state['open']
        if state['open']:
            body.pack(fill='both', pady=(SPACING['xs'], SPACING['sm']))
        else:
            body.pack_forget()
        button.configure(text='资产 JSON 原文' + ('（收起）' if state['open'] else '（展开）'))
    button = SecondaryButton(holder, text='资产 JSON 原文（展开）', command=toggle)
    button.pack(anchor='w')
    from domain.asset_plan import plan_file
    text = '{}'
    try:
        data = read(plan_file(desktop.root, _base(desktop)))
        row = data.get(aid) if isinstance(data, dict) else None
        text = json.dumps(row if row is not None else {}, ensure_ascii=False, indent=2)
    except (OSError, ValueError):
        text = '（读不出来）'
    view = TextArea(body, wrap='none', height=TEXT_ROWS['2xl'], bg=COLORS['background_card'], fg=COLORS['text_primary'],
                    padx=SPACING['md'], pady=SPACING['md'])
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
        ttk.Label(desktop.content, text=message, style='Muted.TLabel',
                  wraplength=TEXT_DESC['wraplength']).pack(
                      anchor='w', padx=SPACING['sm'], pady=(SPACING['sm'], SPACING['xs']))
        SecondaryButton(desktop.content, text='← 返回资产管理',
                   command=lambda: desktop.safe(desktop.close_asset_detail)).pack(anchor='w',padx=SPACING['sm'])
        return None
    _header(desktop, aid, asset)
    note = ('这一页只摆这一项资产：正典板、锚点、参考职责与状态变体都在这里改；'
            '改完立刻写进资产清单 assets.json，主页面同步刷新。')
    try:
        from stage_execution_service import asset_impact
        note += asset_impact_note(asset_impact(desktop.root, aid))
    except (OSError, ValueError):
        pass
    desktop.note(note)
    _gates_block(desktop, aid)
    _board_block(desktop, aid, asset)
    from domain.asset_versions import motion_lines
    box = Card(desktop.content); ttk.Label(box, text='动态参考').pack(anchor='w'); box.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))
    for text, run, thumb in motion_lines(desktop, aid, safe=desktop.safe):
        thumb = asset_thumbs.media_thumbnail(box, thumb, CELL_SIZE) if thumb else None
        button = SecondaryButton(box, image=thumb, text=text, compound='left', command=run or (lambda: None), state='normal' if run else 'disabled'); button.image = thumb; button.pack(anchor='w')
    if aid.startswith('CHAR_'):
        _anchor_block(desktop, aid, asset)
        _role_block(desktop, aid, asset)
        _variants_block(desktop, aid, asset)
    else:
        _role_block(desktop, aid, asset)
    _usage_block(desktop, aid, asset)
    _evolution_block(desktop, aid, asset)
    _raw_block(desktop, aid)
    return aid


# ── 资产清单（第 71 期任务 2）────────────────────────────────────────────────
# 侧栏「05 资产管理」下面那一级缩进的「资产清单」摆的就是这一页：一页看完每个角色的
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
    label.pack(side=side, padx=(SPACING['none'], SPACING['sm']), pady=SPACING['xs'] // 4)
    label.bind('<Button-1>', lambda _e, path=path, name=title:
               desktop.safe(lambda: _open_zoom(desktop, path, name)))
    return label


def _roster_role(desktop, aid, asset):
    """一个角色一块：正典板那几格 ＋ 换状态那几条（场景／道具只有正典板）。"""
    from contract.asset_contract import cells, state_variants
    base = _base(desktop)
    box = Card(desktop.content)
    ttk.Label(box, text=aid + ' · ' + str(asset.get('name') or aid) + '　'
                       + TYPE_NAMES.get(aid.split('_')[0], '资产')).pack(anchor='w')
    box.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))
    grid = cells(asset)
    board = ttk.Frame(box)
    board.pack(fill='x')
    ttk.Label(board, text='正典板', width=ROSTER_PANEL_WIDTH,
              foreground=COLORS['text_heading']).pack(side='left', anchor='n')
    bound = 0
    for cell in grid:
        holder = ttk.Frame(board)
        holder.pack(side='left', padx=(SPACING['none'], SPACING['md']), anchor='n')
        ttk.Label(holder, text=cell['label'],
                  foreground=COLORS['success_text'] if cell['ready'] else COLORS['text_muted']).pack(anchor='w')
        if _roster_thumb(desktop, holder, base, cell['image'] if cell['ready'] else '',
                         aid + ' · ' + cell['label'], side='top') is None:
            HintLabel(holder, text='（缺图）').pack(anchor='w')
        else:
            bound += 1
    states = state_variants(asset) if aid.startswith('CHAR_') else []
    if aid.startswith('CHAR_'):
        panel = ttk.Frame(box)
        panel.pack(fill='x', pady=(SPACING['sm'], SPACING['none']))
        ttk.Label(panel, text='换状态', width=ROSTER_PANEL_WIDTH,
                  foreground=COLORS['text_heading']).pack(side='left', anchor='n')
        if not states:
            DescriptionBlock(panel, text='还没有状态变体：剧本有换装需求时，在详情页新增（编号自动排 CST-01…）').pack(side='left')
        for item in states:
            line = ttk.Frame(panel)
            line.pack(side='left', padx=(SPACING['none'], SPACING['md']), anchor='n')
            _roster_thumb(desktop, line, base, item.get('reference_image'),
                          aid + ' · ' + str(item.get('state_id') or ''))
            ttk.Label(line, text=str(item.get('state_id') or '') + ' · '
                               + str(item.get('name') or '未命名') + '：'
                               + str(item.get('override') or '缺覆盖描述'),
                      wraplength=TEXT_HINT['wraplength'], justify='left').pack(side='left')
    foot = ttk.Frame(box)
    foot.pack(fill='x', pady=(SPACING['sm'], SPACING['none']))
    SecondaryButton(foot, text='编辑这一项',
               command=lambda: desktop.safe(lambda: desktop.open_asset_detail(aid))).pack(side='left')
    DescriptionBlock(foot, text='正典板 ' + str(bound) + '/' + str(len(grid)) + ' 格已绑定 · 状态变体 '
                                + str(len(states)) + ' 个').pack(
                                    side='left', padx=(SPACING['md'], SPACING['none']))
    return box


def show_roster(desktop):
    """把资产清单页摆进 desktop.content（侧栏「资产清单」那一格）。"""
    registry = desktop.asset_requirements()
    rows = roster_rows(registry)
    head = FlowBar(desktop.content)
    head.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
    SecondaryButton(head, text='← 返回资产管理',
               command=lambda: desktop.safe(desktop.close_asset_detail)).pack(
                   side='left', padx=(SPACING['none'], SPACING['md']), pady=SPACING['xs'])
    ttk.Label(head, text='资产清单', font=FONTS['heading_3']).pack(side='left')
    ttk.Label(head, text='　共 ' + str(len(rows)) + ' 项').pack(side='left')
    if not rows:
        desktop.note('这个项目还没有资产清单：先到'+pet_bus.stage_step('storyboard')+'采用一份分镜，回来点「手动制作资产」。')
        return []
    desktop.note('正典板与换状态面板都取自资产清单 assets.json；点小图放大，要改内容点每一项下面的「编辑这一项」。')
    for aid, asset in rows:
        _roster_role(desktop, aid, asset)
    return [aid for aid, _asset in rows]


def asset_impact_note(impact):
    """资产详情页顶部的只读影响提示：被哪些采用镜头引用、要复核什么、能否回收。"""
    if not isinstance(impact, dict):
        return ''
    if impact.get('orphan'):
        return '　当前没有采用镜头引用这一项（属可回收的孤立资产）。'
    if not impact.get('references'):
        return ''
    parts = ['被 %d 个采用镜头引用' % len(impact['references'])]
    if impact.get('files'):
        parts.append('改动需复核 %d 个首帧' % len(impact['files']))
    if impact.get('videos'):
        parts.append('%d 段视频受影响' % len(impact['videos']))
    if impact.get('variants'):
        parts.append('%d 个状态变体' % len(impact['variants']))
    return '　' + '；'.join(parts) + '。改正典前先核对引用镜头，改状态变体不动正典。'
