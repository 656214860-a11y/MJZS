"""reference_wall.show 改写成 _ReferenceWall：HEAD 旧实现原样内嵌，与新实现开同样的候选图墙，
对照初态控件树、逐个点按钮后的控件树与宿主回调记录。"""
import base64
import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

import reference_wall as module
from skip_reasons import PLATFORM_TKINTER
from window_diff_support import FakeApp, drive, legacy

LEGACY = 'def show(app, aid=None, parent=None, on_saved=None, assets=None, base=None, candidates=None, fetch=None):\n    """打开候选图墙；取消或没有候选时返回 None。"""\n    from stage_execution_service import sync_asset_plan\n    from asset_context import scope_sources\n    project = Path(app.root)\n    base = Path(base) if base else Path(app.asset_base())\n    parent = parent or app.win\n    if candidates is None:\n        path = FileDialog(parent).open_file(title=\'选择参考图候选清单\',\n                                          filetypes=[(\'候选清单\', \'*.json *.jsonl\'), (\'全部文件\', \'*.*\')])\n        if not path:\n            return None\n        candidates = search.candidates_from_file(path)\n    if assets is None:\n        assets = sync_asset_plan(project, base, scope_sources(project, \'adopted\'), scope=\'adopted\')\n    if not assets:\n        raise ValueError(\'请先采用分镜，再挑选参考图候选\')\n    labels = {key + \' · \' + str(value.get(\'name\', key)): key for key, value in assets.items()}\n    tick_images = list(getattr(app.win, \'_tick_images\', None) or (\'\', \'\'))\n    if len(tick_images) < 2:\n        tick_images = [\'\', \'\']\n    win = BaseDialog(parent, \'参考图候选 · 打分与入库\', geometry=\'1000x640\',\n                     minsize=(780, 480), modal=False, chrome=False); win.withdraw()\n    body = Card(win, padding=SPACING[\'md\']); body.pack(fill=\'both\', expand=True)\n    tools = ttk.Frame(body); tools.pack(fill=\'x\')\n    ttk.Label(tools, text=\'资产\').pack(side=\'left\')\n    asset_box = SelectBox(tools, values=list(labels)); asset_box.pack(side=\'left\', padx=(SPACING[\'xs\'], SPACING[\'sm\']))\n    asset_box.set(next((text for text, key in labels.items() if key == aid), next(iter(labels), \'\')))\n    ttk.Label(tools, text=\'参考用途\').pack(side=\'left\')\n    role_box = SelectBox(tools); role_box.pack(side=\'left\', padx=(SPACING[\'xs\'], SPACING[\'sm\']))\n    ttk.Label(tools, text=\'打分阈值\').pack(side=\'left\')\n    threshold_box = ttk.Spinbox(tools, from_=0, to=100, width=5); threshold_box.set(search.DEFAULT_THRESHOLD)\n    threshold_box.pack(side=\'left\', padx=(SPACING[\'xs\'], SPACING[\'sm\']))\n    ttk.Label(tools, text=\'最多显示\').pack(side=\'left\')\n    limit_box = ttk.Spinbox(tools, from_=1, to=24, width=5); limit_box.set(search.DEFAULT_LIMIT)\n    limit_box.pack(side=\'left\', padx=(SPACING[\'xs\'], SPACING[\'sm\']))\n    status = tk.StringVar()\n    table_box = ttk.Frame(body); table_box.pack(fill=\'both\', expand=True, pady=(SPACING[\'sm\'], SPACING[\'xs\']))\n    table_shell = DataTable(table_box, columns=[\n        (\'score\', \'分数\', 60), (\'license\', \'许可\', 150), (\'commercial\', \'可商用\', 70),\n        (\'title\', \'标题\', 240), (\'page\', \'来源页\', 240), (\'reasons\', \'打分理由\', 460),\n        (\'license_url\', \'许可依据\', 200), (\'collected_at\', \'采集日期\', 110),\n        (\'state\', \'状态\', 190), (\'alts\', \'同图来源\', 90),\n    ], show=\'tree headings\', height=12, selectmode=\'browse\', empty_text=\'暂无参考图候选\')\n    table = table_shell.tree\n    configure_check_column(table)\n    for key, title, width in [(\'score\', \'分数\', 60), (\'license\', \'许可\', 150), (\'commercial\', \'可商用\', 70),\n                              (\'title\', \'标题\', 240), (\'page\', \'来源页\', 240), (\'reasons\', \'打分理由\', 460),\n                              (\'license_url\', \'许可依据\', 200), (\'collected_at\', \'采集日期\', 110),\n                              (\'state\', \'状态\', 190), (\'alts\', \'同图来源\', 90)]:\n        table.heading(key, text=title); table.column(key, width=width, minwidth=50)\n    auto_columns(table)\n    table_shell.pack(fill=\'both\', expand=True)\n    checked = {}\n    box = CheckboxColumn(table, tick_images, lambda url: checked.get(url, False),\n                         lambda url, value: checked.__setitem__(url, value))\n    table.heading(\'#0\', command=box.toggle_all)\n    bind_row_toggle(table, box.toggle)\n    ttk.Label(body, textvariable=status, wraplength=960, justify=\'left\').pack(fill=\'x\')\n    bottom = ttk.Frame(body); bottom.pack(fill=\'x\', pady=(SPACING[\'sm\'], SPACING[\'none\']))\n    state = {\'items\': []}\n    dropped = set()          # 第 46 期第 9 条：右键「删除」剔掉的那些候选（只影响这一批结果）\n\n    def current():\n        return labels.get(asset_box.get()), role_box.get()\n\n    def asset_changed(event=None):\n        roles = ROLE_GROUPS.get(str(labels.get(asset_box.get()) or \'\').split(\'_\')[0], ())\n        role_box.set_values(list(roles))\n        if roles:\n            role_box.set(roles[0])\n        reload()\n\n    def numbers():\n        try:\n            return max(0, int(threshold_box.get())), max(1, int(limit_box.get()))\n        except (TypeError, ValueError):\n            return search.DEFAULT_THRESHOLD, search.DEFAULT_LIMIT\n\n    def blocked_note(aid_value, threshold):\n        """把被挡在图墙外的候选按状态计数，写进状态栏，说明「为什么没显示」。"""\n        blocked = [row for row in search.suppressed(candidates, assets.get(aid_value) or {}, threshold)\n                   if row[\'url\'] not in dropped]\n        if not blocked:\n            return \'\'\n        counts = {}\n        for row in blocked:\n            counts[row[\'state\']] = counts.get(row[\'state\'], 0) + 1\n        labels = {\'low_score\': \'低分\', \'duplicate\': \'同图重复\', \'missing_license\': \'缺许可\',\n                  \'missing_source\': \'缺来源\', \'missing_url\': \'缺地址\', \'non_commercial\': \'不可商用\'}\n        detail = \'、\'.join(f\'{labels.get(key, key)} {count}\' for key, count in sorted(counts.items()))\n        return f\' 已挡下 {len(blocked)} 张（{detail}）。\'\n\n    def reload(event=None):\n        aid_value, _role = current()\n        threshold, limit = numbers()\n        # 第 46 期第 9 条：右键剔掉过的候选不再回到这一批结果里。\n        state[\'items\'] = [item for item in rows(candidates, assets.get(aid_value) or {}, threshold, limit)\n                          if item[\'url\'] not in dropped]\n        checked.clear(); checked.update({item[\'url\']: item[\'checked\'] for item in state[\'items\']})\n        table.delete(*table.get_children())\n        for item in state[\'items\']:\n            table.insert(\'\', \'end\', iid=item[\'url\'], text=\'\', image=tick_images[int(item[\'checked\'])],\n                         values=(\'%.0f\' % item[\'score\'], item[\'license\'],\n                                 \'可商用\' if item[\'commercial\'] else \'不可商用\',\n                                 item[\'title\'] or \'（没有标题）\', item[\'page\'] or \'（没有来源页）\',\n                                 \'；\'.join(item[\'reasons\']),\n                                 item[\'license_url\'] or \'（没有许可链接）\',\n                                 item[\'collected_at\'] or \'（未记录）\',\n                                 item[\'note\'], str(len(item[\'alts\'])) if item[\'alts\'] else \'—\'))\n        box.refresh_header()\n        status.set(f\'候选 {len(state["items"])} 张（阈值 {threshold}，最多 {limit}）：\'\n                   f\'可商用的默认已勾上；未声明许可的不入库，勾了也会被跳过。\'\n                   + blocked_note(aid_value, threshold))\n\n    def finish(result):\n        skipped = result.get(\'skipped\') or []\n        note = (\'；\'.join(str(item.get(\'reason\')) for item in skipped[:3])) if skipped else \'\'\n        app.status.set(f\'参考图入库 {len(result.get("adopted") or [])} 张\'\n                       + (f\'，跳过 {len(skipped)} 张：\' + note if skipped else \'\'))\n        if on_saved:\n            on_saved()\n        else:\n            app.show(2)\n        win.destroy()\n\n    def commit():\n        chosen = picks(state[\'items\'])\n        aid_value, role = current()\n        if not aid_value:\n            raise ValueError(\'请先选择资产编号\')\n        if not chosen:\n            raise ValueError(\'请先勾选要入库的候选图\')\n        status.set(f\'正在下载并入库 {len(chosen)} 张…（版权与来源会一并记进资产库）\')\n        from stage_execution_service import prepare_asset_write\n        app.async_(lambda: search.adopt(prepare_asset_write(project, base), aid_value,\n                                        chosen, role=role, fetch=fetch), finish)\n\n    def safe_commit():\n        try:\n            commit()\n        except (ValueError, OSError) as exc:\n            notify(win, str(exc), level=\'error\', title=\'入库未开始\', status=status)\n\n    SecondaryButton(tools, text=\'重新打分\', command=lambda: safe(reload)).pack(side=\'left\')\n    SecondaryButton(bottom, text=\'打开候选清单…\',\n                    command=lambda: safe(pick_file)).pack(side=\'left\')\n    PrimaryButton(bottom, text=\'确认入库\', command=safe_commit).pack(side=\'left\', padx=(SPACING[\'sm\'], SPACING[\'none\']))\n    SecondaryButton(bottom, text=\'取消\', command=win.destroy).pack(side=\'right\')\n\n    def safe(fn):\n        def run():\n            try:\n                fn()\n            except (ValueError, OSError) as exc:\n                notify(win, str(exc), level=\'error\', title=\'操作提示\', status=status)\n        return run()\n\n    def pick_file():\n        path = FileDialog(win).open_file(title=\'选择参考图候选清单\',\n                                          filetypes=[(\'候选清单\', \'*.json *.jsonl\'), (\'全部文件\', \'*.*\')])\n        if not path:\n            return\n        candidates[:] = list(search.candidates_from_file(path))\n        reload()\n\n    def open_page(row):\n        """查看：用浏览器打开这一条候选的来源页（目标就是右键那一行）。"""\n        item = next((entry for entry in state[\'items\'] if entry[\'url\'] == row), None)\n        if item is None:\n            return\n        page = str(item.get(\'page\') or item.get(\'url\') or \'\').strip()\n        if not page:\n            raise ValueError(\'这一条候选没有来源页\')\n        import webbrowser\n        webbrowser.open(page)\n\n    def drop_row(row):\n        """删除：把这一条候选从这批结果里剔掉——不动已入库的图，也不看勾选与高亮。"""\n        dropped.add(str(row))\n        reload()\n\n    # 第 46 期第 1 条：内容框的右键菜单（查看／删除），目标永远是右键点中的那一行。\n    bind_row_menu(table,\n                  view=lambda row,_column:safe(lambda:open_page(row)),\n                  delete=lambda row:safe(lambda:drop_row(row)))\n    asset_box.bind(\'<<ComboboxSelected>>\', asset_changed)\n    asset_changed()\n    win.update_idletasks()\n    x = max(0, parent.winfo_rootx() + (parent.winfo_width() - win.winfo_width()) // 2)\n    y = max(0, parent.winfo_rooty() + (parent.winfo_height() - win.winfo_height()) // 2)\n    win.geometry(f\'+{x}+{y}\'); win.deiconify()\n    return win\n'

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
ASSET = {'id': 'CHAR_001', 'name': '银发少女', 'image_prompt': '银发长大衣少女，正面全身立绘，冷色调'}


def _candidate(**values):
    item = {'url': 'https://a/1.png', 'page': 'https://example.com/a', 'title': '银发少女 立绘', 'author': '张三',
            'license': 'CC BY', 'width': 1200, 'height': 1600, 'tags': ['银发', '长发']}
    item.update(values)
    return item


def _session(root, fn, candidates):
    log = []
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / 'library'
        file = base / 'assets/资产清单/assets.json'
        file.parent.mkdir(parents=True)
        file.write_text(json.dumps({'CHAR_001': {'name': '银发少女'}}, ensure_ascii=False), encoding='utf-8')
        app = FakeApp(root, log)
        app.root = td
        win = fn(app, aid='CHAR_001', parent=root, assets={'CHAR_001': ASSET}, base=base,
                 candidates=list(candidates), fetch=lambda url: PNG + b'\x00' * 4096)
        root.update()
        steps = drive(win, [td], log, skip=('打开候选清单…', '取消'))
        if win.winfo_exists():
            win.destroy()
    return steps


CASES = ([_candidate()], [_candidate(), _candidate(url='https://b/2.png', title='银发少女 设定集', license='CC BY-NC')],
         [_candidate(width=600, height=800)])


class ReferenceWallEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except Exception:
            cls.root = None
            return
        cls.root.withdraw()
        cls.root._tick_images = (tk.PhotoImage(width=1, height=1), tk.PhotoImage(width=1, height=1))
        _session(cls.root, legacy(module, LEGACY, 'show'), CASES[0])   # 预热：首次建窗布局不同

    @classmethod
    def tearDownClass(cls):
        if cls.root is not None:
            cls.root.destroy()

    def setUp(self):
        if self.root is None:
            self.skipTest(PLATFORM_TKINTER)

    def test_matches_legacy(self):
        old = legacy(module, LEGACY, 'show')
        for index, candidates in enumerate(CASES):
            with self.subTest(case=index):
                self.assertEqual(_session(self.root, module.show, candidates), _session(self.root, old, candidates))


if __name__ == '__main__':
    unittest.main()
