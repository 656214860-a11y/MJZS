# -*- coding: utf-8 -*-
"""资产参考图候选图墙：读候选清单 → 打分排序 → 勾选复核版权 → 确认入库。

程序里没有配置图库接口，所以检索交给助手或手工导出的候选清单（JSON／JSONL，字段见
asset_reference_search.normalize）。这里只做图墙：按打分阈值过滤、按许可决定默认勾选、
把勾选结果交给 asset_reference_search.adopt 下载入库，版权信息一并记进资产库。
"""
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

import asset_reference_search as search
from asset_reference_images import ROLE_GROUPS
from cell_hover import bind_row_menu
from responsive_ui import CheckboxColumn, auto_columns, configure_check_column, bind_row_toggle


def rows(candidates, asset, threshold=search.DEFAULT_THRESHOLD, limit=search.DEFAULT_LIMIT):
    """图墙内容：打分排序后的候选；可商用的默认勾上，其余留给用户主动确认。"""
    return [{**item, 'checked': bool(item['commercial'] and search.usable(item))}
            for item in search.rank(candidates, asset, threshold, limit)]


def picks(items):
    """确认入库时交出去的候选：勾上的那些，打分与理由随行带着，便于事后追溯。"""
    return [item for item in items if item['checked']]


def show(app, aid=None, parent=None, on_saved=None, assets=None, base=None, candidates=None, fetch=None):
    """打开候选图墙；取消或没有候选时返回 None。"""
    from asset_plan import sync_plan
    from asset_context import scope_sources
    project = Path(app.root)
    base = Path(base) if base else Path(app.asset_base())
    parent = parent or app.win
    if candidates is None:
        path = filedialog.askopenfilename(parent=parent, title='选择参考图候选清单',
                                          filetypes=[('候选清单', '*.json *.jsonl'), ('全部文件', '*.*')])
        if not path:
            return None
        candidates = search.candidates_from_file(path)
    if assets is None:
        assets = sync_plan(project, base, scope_sources(project, 'adopted'), scope='adopted')
    if not assets:
        raise ValueError('请先采用分镜，再挑选参考图候选')
    labels = {key + ' · ' + str(value.get('name', key)): key for key, value in assets.items()}
    tick_images = list(getattr(app.win, '_tick_images', None) or ('', ''))
    if len(tick_images) < 2:
        tick_images = ['', '']
    win = tk.Toplevel(parent); win.withdraw(); win.transient(parent)
    win.title('参考图候选 · 打分与入库'); win.geometry('1000x640'); win.minsize(780, 480)
    body = ttk.Frame(win, padding=12); body.pack(fill='both', expand=True)
    tools = ttk.Frame(body); tools.pack(fill='x')
    ttk.Label(tools, text='资产').pack(side='left')
    asset_box = ttk.Combobox(tools, state='readonly', width=24, values=list(labels)); asset_box.pack(side='left', padx=(4, 10))
    asset_box.set(next((text for text, key in labels.items() if key == aid), next(iter(labels), '')))
    ttk.Label(tools, text='参考用途').pack(side='left')
    role_box = ttk.Combobox(tools, state='readonly', width=14); role_box.pack(side='left', padx=(4, 10))
    ttk.Label(tools, text='打分阈值').pack(side='left')
    threshold_box = ttk.Spinbox(tools, from_=0, to=100, width=5); threshold_box.set(search.DEFAULT_THRESHOLD)
    threshold_box.pack(side='left', padx=(4, 10))
    ttk.Label(tools, text='最多显示').pack(side='left')
    limit_box = ttk.Spinbox(tools, from_=1, to=24, width=5); limit_box.set(search.DEFAULT_LIMIT)
    limit_box.pack(side='left', padx=(4, 10))
    status = tk.StringVar()
    table_box = ttk.Frame(body); table_box.pack(fill='both', expand=True, pady=(10, 6))
    table = ttk.Treeview(table_box, columns=('score', 'license', 'commercial', 'title', 'page', 'reasons'),
                         show='tree headings', height=12, selectmode='browse')
    scroll = ttk.Scrollbar(table_box, orient='vertical', command=table.yview)
    scroll.pack(side='right', fill='y'); table.configure(yscrollcommand=scroll.set)
    configure_check_column(table)
    for key, title, width in [('score', '分数', 60), ('license', '许可', 150), ('commercial', '可商用', 70),
                              ('title', '标题', 240), ('page', '来源页', 240), ('reasons', '打分理由', 460)]:
        table.heading(key, text=title); table.column(key, width=width, minwidth=50)
    auto_columns(table)
    table.pack(fill='both', expand=True)
    checked = {}
    box = CheckboxColumn(table, tick_images, lambda url: checked.get(url, False),
                         lambda url, value: checked.__setitem__(url, value))
    table.heading('#0', command=box.toggle_all)
    bind_row_toggle(table, box.toggle)
    ttk.Label(body, textvariable=status, wraplength=960, justify='left').pack(fill='x')
    bottom = ttk.Frame(body); bottom.pack(fill='x', pady=(10, 0))
    state = {'items': []}
    dropped = set()          # 第 46 期第 9 条：右键「删除」剔掉的那些候选（只影响这一批结果）

    def current():
        return labels.get(asset_box.get()), role_box.get()

    def asset_changed(event=None):
        roles = ROLE_GROUPS.get(str(labels.get(asset_box.get()) or '').split('_')[0], ())
        role_box.configure(values=list(roles))
        if roles:
            role_box.set(roles[0])
        reload()

    def numbers():
        try:
            return max(0, int(threshold_box.get())), max(1, int(limit_box.get()))
        except (TypeError, ValueError):
            return search.DEFAULT_THRESHOLD, search.DEFAULT_LIMIT

    def reload(event=None):
        aid_value, _role = current()
        threshold, limit = numbers()
        # 第 46 期第 9 条：右键剔掉过的候选不再回到这一批结果里。
        state['items'] = [item for item in rows(candidates, assets.get(aid_value) or {}, threshold, limit)
                          if item['url'] not in dropped]
        checked.clear(); checked.update({item['url']: item['checked'] for item in state['items']})
        table.delete(*table.get_children())
        for item in state['items']:
            table.insert('', 'end', iid=item['url'], text='', image=tick_images[int(item['checked'])],
                         values=('%.0f' % item['score'], item['license'],
                                 '可商用' if item['commercial'] else '不可商用',
                                 item['title'] or '（没有标题）', item['page'] or '（没有来源页）',
                                 '；'.join(item['reasons'])))
        box.refresh_header()
        status.set(f'候选 {len(state["items"])} 张（阈值 {threshold}，最多 {limit}）：'
                   f'可商用的默认已勾上；未声明许可的不入库，勾了也会被跳过。')

    def finish(result):
        skipped = result.get('skipped') or []
        note = ('；'.join(str(item.get('reason')) for item in skipped[:3])) if skipped else ''
        app.status.set(f'参考图入库 {len(result.get("adopted") or [])} 张'
                       + (f'，跳过 {len(skipped)} 张：' + note if skipped else ''))
        if on_saved:
            on_saved()
        else:
            app.show(2)
        win.destroy()

    def commit():
        chosen = picks(state['items'])
        aid_value, role = current()
        if not aid_value:
            raise ValueError('请先选择资产编号')
        if not chosen:
            raise ValueError('请先勾选要入库的候选图')
        status.set(f'正在下载并入库 {len(chosen)} 张…（版权与来源会一并记进资产库）')
        app.async_(lambda: search.adopt(base, aid_value, chosen, role=role, fetch=fetch), finish)

    def safe_commit():
        try:
            commit()
        except (ValueError, OSError) as exc:
            messagebox.showerror('入库未开始', str(exc), parent=win)

    ttk.Button(tools, text='重新打分', style='Compact.TButton', command=lambda: safe(reload)).pack(side='left')
    ttk.Button(bottom, text='打开候选清单…', style='Compact.TButton',
               command=lambda: safe(pick_file)).pack(side='left')
    ttk.Button(bottom, text='确认入库', style='Primary.TButton', command=safe_commit).pack(side='left', padx=(8, 0))
    ttk.Button(bottom, text='取消', style='Compact.TButton', command=win.destroy).pack(side='right')

    def safe(fn):
        def run():
            try:
                fn()
            except (ValueError, OSError) as exc:
                messagebox.showerror('操作提示', str(exc), parent=win)
        return run()

    def pick_file():
        path = filedialog.askopenfilename(parent=win, title='选择参考图候选清单',
                                          filetypes=[('候选清单', '*.json *.jsonl'), ('全部文件', '*.*')])
        if not path:
            return
        candidates[:] = list(search.candidates_from_file(path))
        reload()

    def open_page(row):
        """查看：用浏览器打开这一条候选的来源页（目标就是右键那一行）。"""
        item = next((entry for entry in state['items'] if entry['url'] == row), None)
        if item is None:
            return
        page = str(item.get('page') or item.get('url') or '').strip()
        if not page:
            raise ValueError('这一条候选没有来源页')
        import webbrowser
        webbrowser.open(page)

    def drop_row(row):
        """删除：把这一条候选从这批结果里剔掉——不动已入库的图，也不看勾选与高亮。"""
        dropped.add(str(row))
        reload()

    # 第 46 期第 1 条：内容框的右键菜单（查看／删除），目标永远是右键点中的那一行。
    bind_row_menu(table,
                  view=lambda row,_column:safe(lambda:open_page(row)),
                  delete=lambda row:safe(lambda:drop_row(row)))
    asset_box.bind('<<ComboboxSelected>>', asset_changed)
    asset_changed()
    win.update_idletasks()
    x = max(0, parent.winfo_rootx() + (parent.winfo_width() - win.winfo_width()) // 2)
    y = max(0, parent.winfo_rooty() + (parent.winfo_height() - win.winfo_height()) // 2)
    win.geometry(f'+{x}+{y}'); win.deiconify()
    return win
