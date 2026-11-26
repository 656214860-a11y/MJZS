"""Model-scoped connection and Google Flow profile editors."""
import re
from infra.workflow_process_registry import spawn
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from ui.ui_dialogs import FileDialog
from ui_widgets import BaseDialog, LineInput, TextArea, SelectBox, SecondaryButton, NotificationDispatcher
from ui_tokens import SPACING

from infra import model_pool


def dialog(manager, title):
    window = BaseDialog(manager.win, title)
    window.title(title)
    window.transient(manager.win)
    body = ttk.Frame(window, padding=SPACING['md'])
    body.pack(fill='both', expand=True)
    window.grab_set()
    return window, body


def open_flow(manager):
    from infra.gflow_images import executable
    win, body = dialog(manager, 'Google Flow 制图')
    models = ('nano2', 'nano21', 'nano-pro', 'nano2-lite', 'imagen4')
    records = manager.pet.agent_model_records()
    selected = manager.state['id']
    model = tk.StringVar(value=selected[6:] if selected.startswith('gflow-') else 'nano2')
    path = tk.StringVar()
    profiles = tk.StringVar()
    project = tk.StringVar()
    def load(*_):
        row = records.get('gflow-' + model.get(), {})
        project.set(row.get('flow_project', ''))
        path.set(row.get('program') or executable())
        profiles.set(', '.join(row.get('profiles') or ['default']))
    load()
    ttk.Label(body, text='图片模型').grid(row=0, column=0, sticky='w')
    SelectBox(body, state='readonly', values=models, textvariable=model).grid(row=0, column=1, sticky='ew')
    model.trace_add('write', load)
    ttk.Label(body, text='gflow.exe').grid(row=1, column=0, sticky='w')
    LineInput(body, textvariable=path).grid(row=1, column=1)
    def browse():
        result = FileDialog(win).open_file( filetypes=[('gflow.exe', 'gflow.exe')])
        if result:
            path.set(result)
    SecondaryButton(body, text='浏览', command=browse).grid(row=1, column=2)
    ttk.Label(body, text='账号配置名').grid(row=2, column=0, sticky='w')
    LineInput(body, textvariable=profiles).grid(row=2, column=1, sticky='ew')
    ttk.Label(body, text='用逗号分隔配置名，按顺序使用。每个账号首次使用时登录一次。').grid(row=3, columnspan=3)
    ttk.Label(body, text='项目链接（可选）').grid(row=4, column=0, sticky='w')
    LineInput(body, textvariable=project).grid(row=4, column=1, sticky='ew')
    login_name = tk.StringVar()
    ttk.Label(body, text='登录配置名（默认首个）').grid(row=5, column=0, sticky='w')
    LineInput(body, textvariable=login_name).grid(row=5, column=1, sticky='ew')
    def apply(login=False):
        names = list(dict.fromkeys(n.strip() for n in re.split('[,，]', profiles.get()) if n.strip()))
        try:
            if not names or any(not re.fullmatch('[A-Za-z0-9_-]+', n) for n in names):
                raise ValueError('账号配置名可用字母、数字、下划线和短横线')
            cli = Path(path.get())
            if cli.name.lower() != 'gflow.exe' or not cli.is_file():
                raise ValueError('请选择已安装的 gflow.exe')
            if login:
                name = login_name.get().strip() or names[0]
                if name not in names:
                    raise ValueError('请输入列表中的配置名')
                spawn('engine_cli', [str(cli), 'auth', 'login', '--browser', 'chrome', '--profile', name],
                      project=cli.parent, stage='Flow 登录', timeout=600)
                return
            project_id = project.get().strip().rstrip('/').rsplit('/', 1)[-1]
            if project_id:
                from uuid import UUID
                project_id = str(UUID(project_id))
            mid = 'gflow-' + model.get()
            manager.pet.save_pool(dict(model=mid, label='Google Flow · ' + model.get(), provider='desktop',
                                       provider_label='Google Flow', call_mode='CLI', program=str(cli.resolve()),
                                       modality='image', profiles=names, flow_project=project_id))
            manager.load_rows()
            manager.select_model(mid)
            win.destroy()
        except (ValueError, OSError) as exc:
            NotificationDispatcher(manager.hint, win).error(str(exc), modal=True)
    SecondaryButton(body, text='登录账号…', command=lambda: apply(True)).grid(row=6, column=0)
    SecondaryButton(body, text='保存到模型池', command=apply).grid(row=6, column=1, sticky='e')


def open_client_accounts(manager, item):
    if not manager.desktop_mode() or not item.get('model'):
        NotificationDispatcher(manager.hint, manager.win).info('请选择 Desktop 或 CLI 模型。', modal=True)
        return
    if item['model'].startswith('gflow-'):
        return open_flow(manager)
    if model_pool.desktop_engine(item['model']) not in ('', 'client-cli', 'desktop-app'):
        NotificationDispatcher(manager.hint, manager.win).info('此专用引擎使用自己的会话管理。可新建自定义客户端模型，使用支持账号配置参数的程序。', modal=True)
        return
    win, body = dialog(manager, '客户端账号 · ' + item['model'])
    ttk.Label(body, text='填入客户端支持的账号参数，各账号须已在客户端登录。').pack(anchor='w')
    ttk.Label(body, text='每行一个账号，例如 --profile work。新调用按顺序轮换。').pack(anchor='w')
    editor = TextArea(body)
    editor.pack(fill='both', expand=True)
    editor.insert('1.0', '\n'.join(p['option'] + ' ' + p['value'] for p in item.get('client_accounts', [])))
    def save():
        try:
            accounts = []
            for line in editor.get('1.0', 'end').splitlines():
                if not line.strip():
                    continue
                parts = line.strip().split(None, 1)
                if len(parts) != 2 or not re.fullmatch(r'--[\w-]+=?', parts[0]):
                    raise ValueError('每行填写一个参数名、空格及配置名或目录')
                accounts.append(dict(option=parts[0], value=parts[1]))
            manager.pet.save_pool({**item, 'client_accounts': accounts}, manager.state['id'])
            manager.load_rows()
            manager.select_model(item['model'])
            win.destroy()
        except (OSError, ValueError) as exc:
            NotificationDispatcher(manager.hint, win).error(str(exc), modal=True)
    SecondaryButton(body, text='保存账号', command=save).pack(anchor='e')
