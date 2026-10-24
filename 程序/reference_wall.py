# -*- coding: utf-8 -*-
"""资产参考图候选图墙：读候选清单 → 打分排序 → 勾选复核版权 → 确认入库。

程序里没有配置图库接口，所以检索交给助手或手工导出的候选清单（JSON／JSONL，字段见
asset_reference_search.normalize）。这里只做图墙：按打分阈值过滤、按许可决定默认勾选、
把勾选结果交给 asset_reference_search.adopt 下载入库，版权信息一并记进资产库。
"""
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox

import asset_reference_search as search
from asset_reference_images import ROLE_GROUPS
from cell_hover import bind_row_menu
from responsive_ui import CheckboxColumn, auto_columns, configure_check_column, bind_row_toggle
from ui_dialogs import FileDialog
from ui_tokens import BUTTON_GAP, CHAR_WIDTH, TEXT_ROWS, WRAPLENGTH, SPACING
from ui_widgets import SelectBox, BaseDialog, Card, DataTable, PrimaryButton, SecondaryButton, notify


def rows(candidates, asset, threshold=search.DEFAULT_THRESHOLD, limit=search.DEFAULT_LIMIT):
    """图墙内容：打分排序后的候选；可商用的默认勾上，其余留给用户主动确认。"""
    return [{**item, 'checked': bool(item['commercial'] and search.usable(item))}
            for item in search.rank(candidates, asset, threshold, limit)]


def picks(items):
    """确认入库时交出去的候选：勾上的那些，打分与理由随行带着，便于事后追溯。"""
    return [item for item in items if item['checked']]


def show(app, aid=None, parent=None, on_saved=None, assets=None, base=None, candidates=None, fetch=None):
    """打开候选图墙；取消或没有候选时返回 None。"""
    return _ReferenceWall(app=app, aid=aid, parent=parent, on_saved=on_saved, assets=assets, base=base, candidates=candidates, fetch=fetch).build()


class _ReferenceWall:
    """候选图墙窗口；闭包状态挂在实例上。"""
    def __init__(self, **context):
        self.__dict__.update(context)

    def build(self):
        from stage_execution_service import sync_asset_plan
        from asset_context import scope_sources
        self.project = Path(self.app.root)
        self.base = Path(self.base) if self.base else Path(self.app.asset_base())
        self.parent = self.parent or self.app.win
        if self.candidates is None:
            path = FileDialog(self.parent).open_file(title='选择参考图候选清单',
                                              filetypes=[('候选清单', '*.json *.jsonl'), ('全部文件', '*.*')])
            if not path:
                return None
            self.candidates = search.candidates_from_file(path)
        if self.assets is None:
            self.assets = sync_asset_plan(self.project, self.base, scope_sources(self.project, 'adopted'), scope='adopted')
        if not self.assets:
            raise ValueError('请先采用分镜，再挑选参考图候选')
        self.labels = {key + ' · ' + str(value.get('name', key)): key for key, value in self.assets.items()}
        self.tick_images = list(getattr(self.app.win, '_tick_images', None) or ('', ''))
        if len(self.tick_images) < 2:
            self.tick_images = ['', '']
        self.win = BaseDialog(self.parent, '参考图候选 · 打分与入库', geometry='1000x640',
                         minsize=(780, 480), modal=False, chrome=False); self.win.withdraw()
        body = Card(self.win, padding=SPACING['md']); body.pack(fill='both', expand=True)
        tools = ttk.Frame(body); tools.pack(fill='x')
        ttk.Label(tools, text='资产').pack(side='left')
        self.asset_box = SelectBox(tools, values=list(self.labels)); self.asset_box.pack(side='left', padx=(SPACING['xs'], SPACING['sm']))
        self.asset_box.set(next((text for text, key in self.labels.items() if key == self.aid), next(iter(self.labels), '')))
        ttk.Label(tools, text='参考用途').pack(side='left')
        self.role_box = SelectBox(tools); self.role_box.pack(side='left', padx=(SPACING['xs'], SPACING['sm']))
        ttk.Label(tools, text='打分阈值').pack(side='left')
        self.threshold_box = ttk.Spinbox(tools, from_=0, to=100, width=CHAR_WIDTH['sm']); self.threshold_box.set(search.DEFAULT_THRESHOLD)
        self.threshold_box.pack(side='left', padx=(SPACING['xs'], SPACING['sm']))
        ttk.Label(tools, text='最多显示').pack(side='left')
        self.limit_box = ttk.Spinbox(tools, from_=1, to=24, width=CHAR_WIDTH['sm']); self.limit_box.set(search.DEFAULT_LIMIT)
        self.limit_box.pack(side='left', padx=(SPACING['xs'], SPACING['sm']))
        self.status = tk.StringVar()
        table_box = ttk.Frame(body); table_box.pack(fill='both', expand=True, pady=(SPACING['sm'], SPACING['xs']))
        table_shell = DataTable(table_box, columns=[
            ('score', '分数', 60), ('license', '许可', 150), ('commercial', '可商用', 70),
            ('title', '标题', 240), ('page', '来源页', 240), ('reasons', '打分理由', 460),
            ('license_url', '许可依据', 200), ('collected_at', '采集日期', 110),
            ('state', '状态', 190), ('alts', '同图来源', 90),
        ], show='tree headings', height=TEXT_ROWS['2xl'], selectmode='browse', empty_text='暂无参考图候选')
        self.table = table_shell.tree
        configure_check_column(self.table)
        for key, title, width in [('score', '分数', 60), ('license', '许可', 150), ('commercial', '可商用', 70),
                                  ('title', '标题', 240), ('page', '来源页', 240), ('reasons', '打分理由', 460),
                                  ('license_url', '许可依据', 200), ('collected_at', '采集日期', 110),
                                  ('state', '状态', 190), ('alts', '同图来源', 90)]:
            self.table.heading(key, text=title); self.table.column(key, width=width, minwidth=50)
        auto_columns(self.table)
        table_shell.pack(fill='both', expand=True)
        self.checked = {}
        self.box = CheckboxColumn(self.table, self.tick_images, lambda url: self.checked.get(url, False),
                             lambda url, value: self.checked.__setitem__(url, value))
        self.table.heading('#0', command=self.box.toggle_all)
        bind_row_toggle(self.table, self.box.toggle)
        ttk.Label(body, textvariable=self.status, wraplength=WRAPLENGTH['4xl'], justify='left').pack(fill='x')
        bottom = ttk.Frame(body); bottom.pack(fill='x', pady=(SPACING['sm'], SPACING['none']))
        self.state = {'items': []}
        self.dropped = set()          # 第 46 期第 9 条：右键「删除」剔掉的那些候选（只影响这一批结果）

        SecondaryButton(tools, text='重新打分', command=lambda: self.safe(self.reload)).pack(side='left')
        SecondaryButton(bottom, text='打开候选清单…',
                        command=lambda: self.safe(self.pick_file)).pack(side='left')
        PrimaryButton(bottom, text='确认入库', command=self.safe_commit).pack(side='right')
        SecondaryButton(bottom, text='取消', command=self.win.destroy).pack(side='right', padx=(SPACING['none'], BUTTON_GAP))

        # 第 46 期第 1 条：内容框的右键菜单（查看／删除），目标永远是右键点中的那一行。
        bind_row_menu(self.table,
                      view=lambda row,_column:self.safe(lambda:self.open_page(row)),
                      delete=lambda row:self.safe(lambda:self.drop_row(row)))
        self.asset_box.bind('<<ComboboxSelected>>', self.asset_changed)
        self.asset_changed()
        self.win.update_idletasks()
        x = max(0, self.parent.winfo_rootx() + (self.parent.winfo_width() - self.win.winfo_width()) // 2)
        y = max(0, self.parent.winfo_rooty() + (self.parent.winfo_height() - self.win.winfo_height()) // 2)
        self.win.geometry(f'+{x}+{y}'); self.win.deiconify()
        return self.win

    def current(self):
        return self.labels.get(self.asset_box.get()), self.role_box.get()

    def asset_changed(self, event=None):
        roles = ROLE_GROUPS.get(str(self.labels.get(self.asset_box.get()) or '').split('_')[0], ())
        self.role_box.set_values(list(roles))
        if roles:
            self.role_box.set(roles[0])
        self.reload()

    def numbers(self):
        try:
            return max(0, int(self.threshold_box.get())), max(1, int(self.limit_box.get()))
        except (TypeError, ValueError):
            return search.DEFAULT_THRESHOLD, search.DEFAULT_LIMIT

    def blocked_note(self, aid_value, threshold):
        """把被挡在图墙外的候选按状态计数，写进状态栏，说明「为什么没显示」。"""
        blocked = [row for row in search.suppressed(self.candidates, self.assets.get(aid_value) or {}, threshold)
                   if row['url'] not in self.dropped]
        if not blocked:
            return ''
        counts = {}
        for row in blocked:
            counts[row['state']] = counts.get(row['state'], 0) + 1
        labels = {'low_score': '低分', 'duplicate': '同图重复', 'missing_license': '缺许可',
                  'missing_source': '缺来源', 'missing_url': '缺地址', 'non_commercial': '不可商用'}
        detail = '、'.join(f'{labels.get(key, key)} {count}' for key, count in sorted(counts.items()))
        return f' 已挡下 {len(blocked)} 张（{detail}）。'

    def reload(self, event=None):
        aid_value, _role = self.current()
        threshold, limit = self.numbers()
        # 第 46 期第 9 条：右键剔掉过的候选不再回到这一批结果里。
        self.state['items'] = [item for item in rows(self.candidates, self.assets.get(aid_value) or {}, threshold, limit)
                          if item['url'] not in self.dropped]
        self.checked.clear(); self.checked.update({item['url']: item['checked'] for item in self.state['items']})
        self.table.delete(*self.table.get_children())
        for item in self.state['items']:
            self.table.insert('', 'end', iid=item['url'], text='', image=self.tick_images[int(item['checked'])],
                         values=('%.0f' % item['score'], item['license'],
                                 '可商用' if item['commercial'] else '不可商用',
                                 item['title'] or '（没有标题）', item['page'] or '（没有来源页）',
                                 '；'.join(item['reasons']),
                                 item['license_url'] or '（没有许可链接）',
                                 item['collected_at'] or '（未记录）',
                                 item['note'], str(len(item['alts'])) if item['alts'] else '—'))
        self.box.refresh_header()
        self.status.set(f'候选 {len(self.state["items"])} 张（阈值 {threshold}，最多 {limit}）：'
                   f'可商用的默认已勾上；未声明许可的不入库，勾了也会被跳过。'
                   + self.blocked_note(aid_value, threshold))

    def finish(self, result):
        skipped = result.get('skipped') or []
        note = ('；'.join(str(item.get('reason')) for item in skipped[:3])) if skipped else ''
        self.app.status.set(f'参考图入库 {len(result.get("adopted") or [])} 张'
                       + (f'，跳过 {len(skipped)} 张：' + note if skipped else ''))
        if self.on_saved:
            self.on_saved()
        else:
            self.app.show(2)
        self.win.destroy()

    def commit(self):
        chosen = picks(self.state['items'])
        aid_value, role = self.current()
        if not aid_value:
            raise ValueError('请先选择资产编号')
        if not chosen:
            raise ValueError('请先勾选要入库的候选图')
        self.status.set(f'正在下载并入库 {len(chosen)} 张…（版权与来源会一并记进资产库）')
        from stage_execution_service import prepare_asset_write
        self.app.async_(lambda: search.adopt(prepare_asset_write(self.project, self.base), aid_value,
                                        chosen, role=role, fetch=self.fetch), self.finish)

    def safe_commit(self):
        try:
            self.commit()
        except (ValueError, OSError) as exc:
            notify(self.win, str(exc), level='error', title='入库未开始', status=self.status)

    def safe(self, fn):
        def run():
            try:
                fn()
            except (ValueError, OSError) as exc:
                notify(self.win, str(exc), level='error', title='操作提示', status=self.status)
        return run()

    def pick_file(self):
        path = FileDialog(self.win).open_file(title='选择参考图候选清单',
                                          filetypes=[('候选清单', '*.json *.jsonl'), ('全部文件', '*.*')])
        if not path:
            return
        self.candidates[:] = list(search.candidates_from_file(path))
        self.reload()

    def open_page(self, row):
        """查看：用浏览器打开这一条候选的来源页（目标就是右键那一行）。"""
        item = next((entry for entry in self.state['items'] if entry['url'] == row), None)
        if item is None:
            return
        page = str(item.get('page') or item.get('url') or '').strip()
        if not page:
            raise ValueError('这一条候选没有来源页')
        import webbrowser
        webbrowser.open(page)

    def drop_row(self, row):
        """删除：把这一条候选从这批结果里剔掉——不动已入库的图，也不看勾选与高亮。"""
        self.dropped.add(str(row))
        self.reload()
