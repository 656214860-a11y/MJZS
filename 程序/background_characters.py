# -*- coding: utf-8 -*-
"""Scan adopted storyboards and mark background / non-face characters as non-assets."""
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from agent.core import read, save
from responsive_ui import scroll_form
from ui_widgets import BaseDialog

# 名称/别名匹配（高置信，命中的会展示给用户二次确认）
NAME_KEYWORDS = (
    '背景', '路人', '群演', '群众', '龙套', '围观', '过路', '群像', '群杂',
    '避雨',
)
# 描述匹配（更谨慎，只放最明确的措辞）
DESC_KEYWORDS = (
    '不新增固定角色', '不增加固定角色', '匿名', '不可辨识', '无清晰脸部',
    '不要求面部身份', '背景人物', '群众演员', '群演', '无台词',
)


def _ref_id(value):
    if isinstance(value, dict):
        return value.get('id') or value.get('name')
    return value


def _asset_map(project):
    from asset_context import library_dir
    project = Path(project).resolve()
    lib = library_dir(project, project / 'episode')
    plan_file = lib / 'assets' / '资产清单' / 'assets.json'
    plan = read(plan_file) if plan_file.is_file() else {}
    registry = read(lib / 'assets.json') if (lib / 'assets.json').is_file() else {}
    merged = dict(plan)
    for aid, asset in registry.items():
        merged.setdefault(aid, {k: v for k, v in asset.items() if k != 'image'})
    return lib, plan_file, merged


def scan(project):
    """Return candidates: list of dicts with aid/name/hit/source/used."""
    from agent.core import read
    project = Path(project).resolve()
    _, _, merged = _asset_map(project)
    candidates = []
    for aid, asset in merged.items():
        if not isinstance(aid, str) or not aid.startswith('CHAR_'):
            continue
        if not isinstance(asset, dict):
            continue
        if asset.get('appearance_locked') is True or asset.get('prompt_stage') == 'writing':
            continue
        if asset.get('requires_asset') is False or asset.get('character_importance') in ('background', 'extra', 'non_face'):
            continue
        name = str(asset.get('name', '') or '')
        aliases = [str(a) for a in asset.get('aliases', []) if isinstance(a, str)]
        hit = None
        source = ''
        for text in [name, *aliases]:
            for kw in NAME_KEYWORDS:
                if kw in text:
                    hit, source = kw, '名称'
                    break
            if hit:
                break
        if not hit:
            desc = asset.get('description', '')
            if isinstance(desc, str):
                for kw in DESC_KEYWORDS:
                    if kw in desc:
                        hit, source = kw, '描述'
                        break
        if not hit:
            continue
        used = asset.get('used_in', [])
        if not isinstance(used, list):
            used = []
        candidates.append({'aid': aid, 'name': name, 'hit': hit, 'source': source, 'used': used})
    return candidates


def apply(project, selected):
    """Mark selected chars as non-assets and remove them from adopted storyboards."""
    from storyboard_selection import adopted
    project = Path(project).resolve()
    selected = {str(aid) for aid in selected}
    if not selected:
        return 0, 0
    lib, plan_file, _ = _asset_map(project)
    plan = read(plan_file) if plan_file.is_file() else {}
    for aid in selected:
        entry = plan.setdefault(aid, {})
        entry['requires_asset'] = False
        entry['character_importance'] = 'background'
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    save(plan_file, plan)

    touched = 0
    for source in adopted(project):
        ep = read(source)
        dirty = False
        for shot in ep.get('shots', []):
            if not isinstance(shot, dict):
                continue
            for key in ('characters', 'first_frame_assets'):
                values = shot.get(key, [])
                values = values if isinstance(values, list) else [values] if values else []
                kept = [v for v in values if _ref_id(v) not in selected]
                if len(kept) != len(values):
                    shot[key] = kept
                    dirty = True
        if dirty:
            save(source, ep)
            touched += 1
    return len(selected), touched


def show(desktop):
    candidates = scan(desktop.root)
    if not candidates:
        messagebox.showinfo('识别背景人物', '未发现疑似背景/不露脸人物（按名称关键词匹配）。', parent=desktop.win)
        return
    win = BaseDialog(desktop.win, '识别背景人物', geometry='780x540',
                     minsize=(620, 380), modal=False, chrome=False)
    win.transient(desktop.win)
    ttk.Label(
        win,
        text=f'以下 {len(candidates)} 个角色疑似背景/不露脸/局部人物。勾选后点击“标记为背景人物”，将不再建档、不再生成图片，并从分镜引用中移除。',
        wraplength=740, style='Muted.TLabel',
    ).pack(anchor='w', padx=12, pady=(12, 4))

    top = ttk.Frame(win); top.pack(fill='x', padx=12, pady=(0, 4))
    vars_ = {}

    def set_all(value):
        for v in vars_.values():
            v.set(value)

    ttk.Button(top, text='全选', command=lambda: set_all(True)).pack(side='left', padx=(0, 6))
    ttk.Button(top, text='全不选', command=lambda: set_all(False)).pack(side='left')

    body = ttk.Frame(win); body.pack(fill='both', expand=True, padx=12, pady=4)
    view = scroll_form(body); inner = view.form

    for c in candidates:
        var = tk.BooleanVar(value=True); vars_[c['aid']] = var
        used = f'{len(c["used"])} 镜' if c['used'] else '未引用'
        label = f"{c['aid']}　{str(c['name'] or '未命名')}　（命中“{c['hit']}”·{c['source']}·{used}）"
        ttk.Checkbutton(inner, text=label, variable=var).pack(anchor='w', pady=2)

    view.bind_wheel()          # 候选多到要滚的时候，滚轮也得落在这批勾选框上

    footer = ttk.Frame(win); footer.pack(fill='x', padx=12, pady=12)

    def confirm():
        selected = [aid for aid, v in vars_.items() if v.get()]
        if not selected:
            messagebox.showinfo('识别背景人物', '未勾选任何角色。', parent=win)
            return
        try:
            n, touched = apply(desktop.root, selected)
        except Exception as exc:
            messagebox.showerror('识别背景人物', str(exc), parent=win)
            return
        win.destroy()
        desktop.asset_kind = 'characters'
        desktop.show(2)
        desktop.status.set(f'已标记 {n} 个背景人物为不建档，并清理 {touched} 份分镜中的引用。')

    ttk.Button(footer, text='标记为背景人物', command=confirm).pack(side='right')
    ttk.Button(footer, text='取消', command=win.destroy).pack(side='right', padx=6)
