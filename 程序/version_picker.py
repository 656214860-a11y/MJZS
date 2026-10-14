# -*- coding: utf-8 -*-
"""交付页「选择采用版本」：回退到旧的已验收版本，或恢复为最新已验收版本。

只调用 `Studio.version_rows` / `Studio.pin_version`；不删除、不改动版本文件和验收记录。
"""
import tkinter as tk

from ui_tokens import SPACING
from ui_widgets import BaseDialog, DataTable, PrimaryButton, ProgressLabel, SecondaryButton, SelectBox


def open_picker(app):
    studio = app.studio
    shots = [shot['id'] for shot in studio.episode['shots'] if not shot.get('video_deleted')]
    if not shots:
        raise ValueError('本集没有可选择版本的镜头')
    win = BaseDialog(app.win, '选择采用版本', geometry='760x420', minsize=(600, 320), modal=False)
    shot_var, status = tk.StringVar(value=shots[0]), tk.StringVar(value='只有已验收通过的版本可以采用；不会删除任何版本。')
    bar = tk.Frame(win.content)
    bar.pack(fill='x')
    SelectBox(bar, textvariable=shot_var, values=shots, width=14).pack(side='left')
    table_shell = DataTable(win.content, columns=[('version', '版本', 70), ('state', '状态', 90), ('qc', '技术QC', 80),
                                                  ('review', '验收', 220), ('use', '采用', 160)],
                            height=8, empty_text='本镜没有版本')
    table_shell.pack(fill='both', expand=True, pady=(SPACING['sm'], 0))
    table = table_shell.tree
    ProgressLabel(win.content, textvariable=status).pack(anchor='w', pady=(SPACING['sm'], 0))

    def refresh(event=None):
        table.delete(*table.get_children())
        for row in studio.version_rows(shot_var.get()):
            use = '锁定采用' if row['pinned'] and row['adopted'] else ('当前采用' if row['adopted'] else '')
            qc = {True: '通过', False: '未通过'}.get(row['qc_pass'], '未检查')
            table.insert('', 'end', iid=str(row['version']),
                         values=('v%s' % row['version'], row['state'], qc, row['review'], use))

    def selected():
        chosen = table.selection()
        return int(chosen[0]) if chosen else None

    def apply(number, done):
        try:
            studio.pin_version(shot_var.get(), number)
        except (ValueError, OSError, RuntimeError) as exc:
            status.set(str(exc))
            return False
        refresh()
        status.set(done)
        app.status.set('%s：%s；重新打开交付页可看到最新采用列。' % (shot_var.get(), done))
        return True

    def adopt():
        number = selected()
        if number is None:
            status.set('先在表里选一个版本。')
            return False
        return apply(number, '已采用 v%d' % number)

    def restore():
        return apply(None, '已恢复为最新已验收版本')

    shot_var.trace_add('write', lambda *_: refresh())
    PrimaryButton(win.actions, text='采用所选版本', command=adopt).pack(side='left')
    SecondaryButton(win.actions, text='恢复为最新已验收版', command=restore).pack(side='left', padx=(SPACING['sm'], 0))
    SecondaryButton(win.actions, text='关闭', command=win.destroy).pack(side='right')
    refresh()
    win._picker = {'table': table, 'status': status, 'shot': shot_var, 'adopt': adopt, 'restore': restore,
                   'refresh': refresh}
    return win
