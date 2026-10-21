"""pet_models_ui.open_manager 的闭包→类改写：旧实现原样内嵌，用同一份脚本驱动两个窗口，逐步对照可观察状态。

可观察状态 = 表单各控件的文本／勾选／显隐、列表行、提示语、模型池落盘内容、宠物被调用的记录、
窗口上挂的 _pet_* 句柄集合。真 Tk，自动搜寻线程与本机密钥存取用替身，不碰注册表／DPAPI／用户项目。
"""
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

import model_pool
import pet_models_ui
from skip_reasons import PLATFORM_TKINTER

LEGACY_SRC = r'''def _legacy_open_manager(pet):
    """模型管理…：模型池＋API 配置的唯一入口（增／删／改／测连接）。"""
    program = program_of(pet)
    win, card = window(pet, MANAGER_TITLE, MANAGER_GEOMETRY, minsize=MANAGER_MIN)
    fit_to_main(win, parent_of(pet), MANAGER_GEOMETRY)     # 第 52 期第 1 条：比主界面小一圈、居中
    # 动作区先占住窗口底边，窗口被压矮时只压缩上面的模型列表与表单。
    footer = ttk.Frame(card)
    footer.pack(side='bottom', fill='x')
    body = ttk.Frame(card)
    body.pack(fill='both', expand=True)
    body.columnconfigure(0, weight=1)
    body.rowconfigure(2, weight=1)
    row = heading(body, MANAGER_TITLE, NOTE_MANAGER, columns=1)
    keys = [key for key, _title, _width in COLUMNS]
    # 表单行不叠加纵向外边距；控件保留自身内边距，窗口剩余高度全部交给模型列表。
    # 列宽随窗口伸展，长名称与地址可以通过滚动条查看。
    table_shell = DataTable(body, columns=COLUMNS, show='headings', height=20,
                            empty_text='暂无模型配置')
    tree = table_shell.tree
    for key, title, width in COLUMNS:
        tree.heading(key, text=title)
        tree.column(key, width=width, anchor='w', stretch=True)
    table_shell.grid(row=2, column=0, sticky='nsew')
    form = ttk.Frame(body, padding=(SPACING['none'], SPACING['xs']))
    form.grid(row=3, column=0, columnspan=2, sticky='ew')
    form.columnconfigure(0, minsize=form_column_width(MANAGER_FORM_LABELS))
    form.columnconfigure(1, weight=1)
    entries = {}
    caps = {}
    provider = tk.StringVar(value=model_pool.PROVIDER_LABELS[model_pool.DEFAULT_PROVIDER])
    wire = tk.StringVar(value=model_pool.WIRE_LABELS[model_pool.DEFAULT_WIRE])
    mode = tk.StringVar(value='API')

    def text_row(index, key, label):
        """一行「标签 ＋ 输入框」；行号往下走，表单中间插下拉框／多选都不会错位。"""
        ttk.Label(form, text=label).grid(row=index, column=0, sticky='w')
        entry = LineInput(form)
        entry.grid(row=index, column=1, sticky='ew')
        entries[key] = entry
        return index + 1

    # 表单次序：Provider、模型 ID、显示名（按 ID 自动推断）、根地址、密钥、协议、能力标签、上下文、备注。
    ttk.Label(form, text='调用方式').grid(row=0, column=0, sticky='w')
    mode_box = SelectBox(form, textvariable=mode, values=('Desktop', 'API', 'CLI'))
    mode_box.grid(row=0, column=1, sticky='ew')
    index = 1
    ttk.Label(form, text='Provider').grid(row=index, column=0, sticky='w')
    # 第 65 期任务 5：用户报「provider → 自定义不可用」。原来这一格是只读下拉，只能挑三档固定
    # 名字，选了「自定义」既不能写自己的服务商名、也没有自定义路径的入口。现在改成可编辑：
    # 挑现成的，或者直接敲一个名字；存的就是填进去的那个名字。
    provider_box = SelectBox(form, textvariable=provider, state='normal',
                                values=[label for _value, label in model_pool.PROVIDERS])
    provider_box.grid(row=index, column=1, sticky='ew')
    def match_wire(event=None):
        """第 65 期任务 8：换了 Provider，「协议」栏自动摆到它默认的那一档。

        只挂「选中了一项」，不挂失焦——用户在协议栏手改过的那一档不会被蹭掉。
        """
        if desktop_mode():
            return None                  # 本机程序不走 HTTP 协议，换厂商名不改协议档
        value = model_pool.wire_for_provider(
            model_pool.id_of_label(provider.get(), model_pool.PROVIDERS))
        wire.set(model_pool.WIRE_LABELS.get(value, model_pool.WIRE_LABELS[model_pool.DEFAULT_WIRE]))
    provider_box.bind('<<ComboboxSelected>>', match_wire)
    provider_box.bind('<<ComboboxSelected>>', lambda event: detect_program(), add='+')

    index = text_row(index + 1, 'model', '模型 ID')
    index = text_row(index, 'label', '显示名')
    index = text_row(index, 'base_url', 'API 根地址')
    index = text_row(index, 'key_env', '密钥名（.env 里的变量名）')
    # 规格里的第二种放法：密钥直接输进来，用系统加密存本机（明文不落盘、配置 JSON 里不写）。
    ttk.Label(form, text='直接输入密钥').grid(row=index, column=0, sticky='w')
    key_row = ttk.Frame(form)
    key_row.grid(row=index, column=1, sticky='w')
    key_entry = LineInput(key_row, width=SECRET_FIELD_WIDTH, show='*')
    key_entry.pack(side='left')
    SecondaryButton(key_row, text='保存到本机', command=lambda: local_save()).pack(side='left', padx=(SPACING['sm'], SPACING['none']))
    SecondaryButton(key_row, text='清除本机密钥', command=lambda: local_clear()).pack(side='left', padx=(SPACING['xs'], SPACING['none']))
    # 密钥状态紧跟在按钮后面，不再单独占一行。
    key_state = tk.StringVar(value='')
    ttk.Label(key_row, textvariable=key_state, style='Muted.TLabel').pack(side='left', padx=(SPACING['sm'], SPACING['none']))
    index += 1
    ttk.Label(form, text='协议').grid(row=index, column=0, sticky='w')
    SelectBox(form, textvariable=wire,
                 values=[label for _value, label in model_pool.WIRE_APIS]).grid(
        row=index, column=1, sticky='ew')
    index += 1
    ttk.Label(form, text='能力标签').grid(row=index, column=0, sticky='w')
    cap_row = ttk.Frame(form)
    cap_row.grid(row=index, column=1, sticky='w')
    for tag in model_pool.CAPABILITY_TAGS:
        var = tk.BooleanVar(value=False)
        caps[tag] = var
        ttk.Checkbutton(cap_row, text=model_pool.CAPABILITY_LABELS[tag],
                        variable=var).pack(side='left', padx=(SPACING['none'], SPACING['sm']))
    index = text_row(index + 1, 'context_length', '上下文长度（可选）')
    text_row(index, 'note', '备注（可选）')
    hint = tk.StringVar(value='选一条改，或者「新建一条」；「保存这条」立刻写进模型池。')
    api_rows = {4, 5, 6, 7}
    api_controls = [widget for widget in form.winfo_children()
                    if int(widget.grid_info().get('row', -1)) in api_rows]
    program_label = ttk.Label(form, text='应用安装路径')
    program_label.grid(row=4, column=0, sticky='w')
    program_row = ttk.Frame(form)
    program_row.grid(row=4, column=1, sticky='ew')
    program_row.columnconfigure(0, weight=1)
    program_entry = LineInput(program_row)
    program_entry.grid(row=0, column=0, sticky='ew')
    entries['program'] = program_entry
    from desktop_automation_service import BackgroundTaskLifecycle
    from queue import Queue, Empty
    from threading import Thread
    search = BackgroundTaskLifecycle()
    search_poll = {'after': None}
    search_busy = BusyState(hint)

    def stop_search():
        search.cancel()
        if search_poll['after'] is not None:
            win.after_cancel(search_poll['after'])
            search_poll['after'] = None
        search_busy.set_busy(False)
        search_button.configure(text='自动搜寻')

    def browse_program():
        stop_search()
        path = FileDialog(win).open_file(title='选择应用可执行文件', filetypes=[('程序', '*.exe')])
        if path:
            program_entry.delete(0, 'end')
            program_entry.insert(0, path)
    def detect_program(event=None, quiet=True):
        """只用当前表单身份搜寻，绝不借用被编辑记录的旧 ID。"""
        if not desktop_mode() or (quiet and program_entry.get().strip()):
            return None
        from workflow_settings import find_model_program
        model = entries['model'].get().strip()
        if not model:
            report_error(hint, '请先填写模型 ID，再自动搜寻安装路径。')
            return None
        if pending['after'] is not None:
            win.after_cancel(pending['after'])
            pending['after'] = None
        stop_search()
        ticket = search.submit(object(), label='安装路径搜寻')
        call_mode, original_path = mode.get(), program_entry.get()
        results = Queue()
        hint.set('正在搜寻「%s」：检查注册表、商店安装记录和常见安装目录…' % model)
        search_button.configure(text='正在搜寻…')
        search_busy.set_busy(True, controls=(search_button,), progress=False)

        def worker():
            try:
                results.put((find_model_program(model, call_mode), ''))
            except Exception as exc:
                results.put(('', str(exc)))

        def poll():
            search_poll['after'] = None
            if not search.accepts(ticket):
                return
            try:
                path, error = results.get_nowait()
            except Empty:
                search_poll['after'] = win.after(50, poll)
                return
            search.finish(ticket, succeeded=bool(path), error=error)
            search_busy.set_busy(False)
            search_button.configure(text='自动搜寻')
            _apply_program_search(path, error, original_path, program_entry, hint)

        Thread(target=worker, daemon=True).start()
        search_poll['after'] = win.after(50, poll)

    search_button = SecondaryButton(program_row, text='自动搜寻', command=lambda: detect_program(quiet=False))
    search_button.grid(row=0, column=1, padx=(SPACING['xs'], SPACING['none']))
    SecondaryButton(program_row, text='浏览…', command=browse_program).grid(
        row=0, column=2, padx=(SPACING['xs'], SPACING['none']))
    def desktop_mode():
        return mode.get() in ('Desktop', 'CLI')

    def refresh_connection_fields(*_args):
        local = desktop_mode()
        for widget in api_controls:
            widget.grid_remove() if local else widget.grid()
        for widget in (program_label, program_row):
            widget.grid() if local else widget.grid_remove()
        program_label.configure(text='命令行程序路径' if mode.get() == 'CLI' else '应用安装路径')
        tree.configure(displaycolumns=(('provider', 'model', 'label', 'capabilities', 'state')
                                       if local else keys))
        probe_button.configure(text='检查程序' if local else '测试连接')
    pending = {'after': None, 'loading': False}

    def changed_identity(*_args):
        if pending['loading']:
            return
        stop_search()
        if pending['after'] is not None:
            win.after_cancel(pending['after'])
            pending['after'] = None
        program_entry.delete(0, 'end')
        hint.set('正在编辑 %s 配置。' % mode.get())
        refresh_connection_fields()
        if desktop_mode() and model_text.get().strip():
            pending['after'] = win.after(450, delayed_detect)

    def delayed_detect():
        pending['after'] = None
        detect_program()

    def cancel_detection(event):
        if event.widget is win:
            search.cancel()
            if search_poll['after'] is not None:
                win.after_cancel(search_poll['after'])
                search_poll['after'] = None
        if event.widget is win and pending['after'] is not None:
            win.after_cancel(pending['after'])
            pending['after'] = None

    win.bind('<Destroy>', cancel_detection, add='+')

    model_text = tk.StringVar()
    entries['model'].configure(textvariable=model_text)
    auto_label = {'text': ''}

    def fill_label(event=None):
        """填模型 ID 时自动推断显示名；用户手改过的显示名不覆盖。"""
        current = entries['label'].get().strip()
        if current and current != auto_label['text']:
            return None
        guess = model_pool.suggest_label(entries['model'].get(), pet.agent_model_records())
        entries['label'].delete(0, 'end')
        entries['label'].insert(0, guess)
        auto_label['text'] = guess
        return guess
    entries['model'].bind('<KeyRelease>', fill_label, add='+')
    entries['model'].bind('<FocusOut>', detect_program, add='+')
    entries['model'].bind('<KeyRelease>', refresh_connection_fields, add='+')
    manager_hint = ttk.Label(body, textvariable=hint, style='PaleGreenHint.TLabel',
                             wraplength=TEXT_DESC['wraplength'])
    manager_hint.grid(
        row=4, column=0, columnspan=2, sticky='w', pady=(SPACING['xs'], SPACING['xs']))
    state = {'id': ''}

    def load_rows():
        # 自定义 Provider 已随模型记录写入模型池；每次刷新列表时从同一份记录回填，
        # 新建下一条模型即可直接从下拉选择，无需再维护第二份厂商配置。
        builtins = [label for _value, label in model_pool.PROVIDERS]
        saved = {model_pool.provider_name(model_id, item)
                 for model_id, item in pet.agent_model_records().items()}
        provider_box.configure(values=[*builtins, *sorted((item for item in saved if item and item not in builtins),
                                                          key=str.casefold)])
        tree.delete(*tree.get_children())
        records = pet.agent_model_records()
        rows = sorted(((model_pool.provider_name(model_id, item), model_id, item)
                       for model_id, item in records.items()),
                      key=lambda row: (row[0].casefold(), str(row[2].get('label') or '').casefold(), row[1]))
        last = None
        for name, model_id, item in rows:
            # 同一 Provider 只在分组第一行写名字，后面留空，读起来像合并单元格。
            shown, last = ('' if name == last else name), name
            tree.insert('', 'end', iid=model_id,
                        values=(shown, item['model'], item['label'],
                                model_pool.capability_text(item['capabilities']),
                                item['base_url'],
                                model_pool.WIRE_LABELS.get(item['wire_api'], item['wire_api']),
                                item['key_env'], status_text(item, program)))
        table_shell.refresh_empty_state()
        return tree

    def show_key_state(value=None):
        """本机加密那份现在什么情况：只报前 4 位 ＋ ****，别把整把钥匙摆到界面上。"""
        item = value if isinstance(value, dict) else read_form()
        local = model_pool.local_key_of(item, program, state['id'])
        key_state.set(('本机已存密钥：%s（明文本机不落盘）' % model_pool.redacted(local)) if local
                      else '本机没存密钥；走 .env 的话只填上面的密钥名')
        return local

    def local_save():
        """保存直接输入的密钥到本机 DPAPI；回车和失焦均走此唯一入口。"""
        text = key_entry.get().strip()
        try:
            item = model_pool.record(read_form(), state['id'])
            model_pool.save_key_env(item, text, program, state['id'])
            item['key_env'] = model_pool.secret_name(item, state['id'])
        except (ValueError, OSError) as exc:
            report_error(hint, exc)
            return None
        key_entry.delete(0, 'end')
        self_id = state['id']
        state['id'] = model_pool.model_id_of(item, self_id)
        pet.save_pool(item, self_id)
        load_rows()
        show_key_state(item)
        hint.set('密钥已加密保存到当前 Windows 用户的本机存储；界面只露前 4 位。')
        return item

    def local_clear():
        """删掉本机加密那份密钥。"""
        if not model_pool.clear_local_key(read_form(), program, state['id']):
            hint.set('本机本来就没存这一条。')
            return False
        show_key_state()
        hint.set('已删掉本机加密的那份密钥。')
        return True

    def save_typed_key(event=None):
        """第 65 期任务 5：密钥框里一敲进去就自动存，回车或点到别处都算一次提交。

        用户报「密钥名和密钥输入后没有自动保存」——原来必须再点一下「保存到本机」。框里
        是空的就什么都不做，免得点来点去把提示刷成报错。
        """
        if desktop_mode() or not key_entry.get().strip():
            return None
        try:
            return local_save()
        except Exception:
            return None

    key_entry.bind('<Return>', save_typed_key)
    key_entry.bind('<FocusOut>', save_typed_key)

    def fill(model_id, item):
        stop_search()
        pending['loading'] = True
        if pending['after'] is not None:
            win.after_cancel(pending['after'])
            pending['after'] = None
        state['id'] = model_id
        mode.set(model_pool.call_mode(item, model_id))
        key_entry.delete(0, 'end')          # 只写不读：界面里从不回显整把密钥
        for key, _label in FORM_FIELDS:
            entries[key].delete(0, 'end')
            entries[key].insert(0, str(item.get(key) or ''))
        entries['context_length'].delete(0, 'end')
        if item.get('context_length'):
            entries['context_length'].insert(0, str(item['context_length']))
        entries['note'].delete(0, 'end')
        entries['note'].insert(0, str(item.get('note') or ''))
        for tag, var in caps.items():
            var.set(tag in (item.get('capabilities') or []))
        saved_provider = str(item.get('provider') or '').strip()
        if item.get('provider_label') or (saved_provider == 'desktop' and model_pool.desktop_engine(model_id)):
            # 本机 Claude／ChatGPT 显示厂商名；保存时由 read_form 按 desktop_mode 写回 desktop。
            vendor = model_pool.provider_name(model_id, item)
            provider.set(model_pool.PROVIDER_LABELS.get(vendor.casefold(), vendor))
        else:
            provider.set(model_pool.PROVIDER_LABELS.get(
                saved_provider, saved_provider or model_pool.PROVIDER_LABELS[model_pool.DEFAULT_PROVIDER]))
        wire.set(model_pool.WIRE_LABELS.get(item.get('wire_api'), model_pool.WIRE_LABELS[model_pool.DEFAULT_WIRE]))
        program_entry.delete(0, 'end')
        program_entry.insert(0, item.get('program') or '')
        pending['loading'] = False
        auto_label['text'] = entries['label'].get().strip()
        refresh_connection_fields()
        if saved_provider != 'desktop':show_key_state(item)

    def read_form():
        value = {key: entries[key].get().strip() for key, _label in FORM_FIELDS}
        # 本机程序条目的存储协议仍是 desktop（model_pool.status 按它判定可用性）；界面只显示厂商名。
        value['provider'] = 'desktop' if desktop_mode() else model_pool.id_of_label(provider.get(), model_pool.PROVIDERS)
        value['provider_label'] = provider.get().strip() if desktop_mode() else ''
        value['call_mode'] = mode.get()
        value['wire_api'] = model_pool.id_of_label(wire.get(), model_pool.WIRE_APIS)
        value['capabilities'] = [tag for tag, var in caps.items() if var.get()]
        value['context_length'] = entries['context_length'].get().strip()
        value['note'] = entries['note'].get().strip()
        value['program'] = program_entry.get().strip()
        return value

    def on_select(event=None):
        picked = tree.selection()
        if not picked:
            return None
        item = pet.agent_model_records().get(picked[0]) or {}
        fill(picked[0], item)
        hint.set('正在改「%s」；改完点「保存这条」。' % (item.get('label') or picked[0]))
        return item

    def new_one():
        pending['loading'] = True
        state['id'] = ''
        for key, _label in FORM_FIELDS:
            entries[key].delete(0, 'end')
        for key in ('context_length', 'note', 'program'):
            entries[key].delete(0, 'end')
        for var in caps.values():
            var.set(False)
        key_entry.delete(0, 'end')
        show_key_state()
        provider.set(model_pool.PROVIDER_LABELS[model_pool.DEFAULT_PROVIDER])
        wire.set(model_pool.WIRE_LABELS[model_pool.DEFAULT_WIRE])
        pending['loading'] = False
        auto_label['text'] = ''
        changed_identity()
        hint.set('新建 %s 模型：填写模型 ID；本地调用会自动搜寻对应程序。' % mode.get())
        return state

    def save_one():
        try:
            if desktop_mode() and program_entry.get().strip():
                from pathlib import Path
                path = Path(program_entry.get().strip()).expanduser()
                if not path.is_absolute() or path.suffix.lower() != '.exe' or not path.is_file():
                    raise ValueError('请选择存在的应用 .exe 安装路径')
                from workflow_settings import gui_claude_program, GUI_CLAUDE_CLI_HINT
                if mode.get() == 'CLI' and gui_claude_program(str(path)):
                    raise ValueError(GUI_CLAUDE_CLI_HINT)
                _adapted, switched = _derive_client_profile(
                    str(path), entries['label'].get().strip(), mode, entries, probe=False)
                if switched:
                    hint.set('PE 头显示这是%s程序，已切换调用方式；请确认后保存。' %
                             ('命令行' if switched == 'CLI' else '桌面'))
            if not desktop_mode() and key_entry.get().strip():     # 第 65 期任务 5：密钥框里还有字，连它一起存
                local_save()
            pet.save_pool(read_form(), state['id'])
        except (ValueError, OSError) as exc:
            report_error(hint, exc)
            return None
        load_rows()
        hint.set('已保存「%s」；「切换模型」里立刻点得到。' % (read_form().get('label') or ''))
        return read_form()

    def delete_one():
        # 不能依赖上一次 <<TreeviewSelect>> 留下的缓存：刷新列表／点过「新建一条」后，
        # 那个缓存可能已经不是用户眼前选中的行。删除目标只认此刻高亮的这一条。
        selected = tree.selection()
        model_id = selected[0] if selected else ''
        if not model_id:
            report_error(hint, '先选一条。')
            return None
        item = pet.agent_model_records().get(model_id) or {}
        name = item.get('label') or model_id
        if not pet.confirm_start('删除模型', '把「%s」从模型池里删掉？（.env 里的密钥不动）' % name):
            return None
        pet.delete_pool_model(model_id)
        # 保存后必须回读确认；否则表格刷新看似消失、重开又出现时用户会误以为已经删除。
        if model_id in pet.agent_model_records():
            report_error(hint, '未能删除「%s」，请重试。' % name)
            return None
        state['id'] = ''
        load_rows()
        hint.set('已删除「%s」。' % name)
        return model_id

    def probe_one():
        value = read_form()
        if value['provider'] == 'desktop':
            return _probe_local_model(pet, value, mode, entries, program_entry, hint)
        if not value.get('model'):
            report_error(hint, '先填模型 ID。')
            return None
        hint.set(probe_line(model_pool.record(value), pet))
        return value

    tree.bind('<<TreeviewSelect>>', on_select)
    load_rows()
    bar = ttk.Frame(footer)
    bar.pack(fill='x')
    SecondaryButton(bar, text='新建一条', command=new_one).pack(side='left')
    probe_button = SecondaryButton(bar, text='测试连接', command=probe_one)
    probe_button.pack(side='left', padx=(SPACING['sm'], SPACING['none']))
    provider.trace_add('write', refresh_connection_fields)
    mode.trace_add('write', changed_identity)
    model_text.trace_add('write', changed_identity)
    refresh_connection_fields()
    SecondaryButton(bar, text='删除这条', command=delete_one).pack(
        side='left', padx=(SPACING['sm'], SPACING['none']))
    # 主操作贴最右，取消（关闭）紧挨其左：关窗键不再压在主按钮右侧。
    PrimaryButton(bar, text='保存这条', command=save_one).pack(side='right')
    SecondaryButton(bar, text='关闭', command=win.destroy).pack(
        side='right', padx=(SPACING['none'], SPACING['sm']))
    win._pet_api_controls = api_controls
    win._pet_program_row = program_row
    win._pet_reload = load_rows
    win._pet_hint = hint
    win._pet_manager_hint_label = manager_hint
    win._pet_entries = entries
    win._pet_provider = provider
    win._pet_mode = mode
    win._pet_mode_box = mode_box
    win._pet_detect_program = detect_program
    win._pet_read_form = read_form
    win._pet_provider_box = provider_box
    win._pet_tree = tree
    win._pet_delete_one = delete_one
    # 自检要按的那两颗（密钥那条链只能从界面上走一遍）：本机保存／清除 ＋ 那个只写不读的输入框。
    win._pet_key_entry = key_entry
    win._pet_save_key = local_save
    win._pet_save_typed = save_typed_key
    win._pet_clear_key = local_clear
    win._pet_key_state = key_state.get
    return win
'''


class _Pet:
    """用真的模型池落盘（临时目录），其余只记账。"""

    def __init__(self, win, program):
        self.win = win
        self.program = Path(program)
        self.codex_home = Path(program)
        self.project = None
        self.agent = None
        self.calls = []

    def agent_model_records(self):
        return model_pool.pool(program=self.program)

    def save_pool(self, value, old_id=''):
        data = model_pool.raw(self.program)
        key = model_pool.model_id_of(value, old_id)
        if str(old_id or '').strip() and str(old_id).strip() != key:
            data = model_pool.remove(data, old_id)
        data = model_pool.upsert(data, value)
        model_pool.store(data, self.program)
        self.calls.append(('save_pool', key, str(old_id)))
        return key

    def delete_pool_model(self, model_id):
        model_pool.store(model_pool.remove(model_pool.raw(self.program), model_id), self.program)
        self.calls.append(('delete', model_id))
        return model_id

    def confirm_start(self, title, text):
        self.calls.append(('confirm', title, text))
        return True


def _pump(win, seconds):
    end = time.time() + seconds
    while time.time() < end:
        win.update()
        time.sleep(0.01)


def _walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


def _button(win, text):
    for widget in _walk(win):
        if widget.winfo_class() in ('TButton', 'Button') and str(widget.cget('text')) == text:
            return widget
    raise AssertionError(text)


def _snapshot(win, pet, label):
    win.update_idletasks()
    entries = win._pet_entries
    tree = win._pet_tree
    shown = {}
    for widget in _walk(win):
        if widget.winfo_class() in ('TButton', 'Button', 'TLabel', 'Label'):
            try:
                shown[str(widget.cget('text'))] = bool(widget.winfo_manager())
            except tk.TclError:
                pass
    return {
        'label': label,
        'entries': {key: entry.get() for key, entry in sorted(entries.items())},
        'mode': win._pet_mode.get(), 'provider': win._pet_provider.get(),
        'hint': win._pet_hint.get(), 'key_state': win._pet_key_state(),
        'form': win._pet_read_form(),
        'rows': [(iid, tuple(tree.item(iid, 'values'))) for iid in tree.get_children()],
        'selection': tuple(tree.selection()),
        'display': tuple(str(c) for c in tree.cget('displaycolumns')),
        'visible_texts': shown,
        'api_controls_mapped': sorted(bool(w.winfo_manager()) for w in win._pet_api_controls),
        'program_row_mapped': bool(win._pet_program_row.winfo_manager()),
        'handles': sorted(name for name in vars(win) if name.startswith('_pet_')),
        'pool': {key: dict(value) for key, value in sorted(pet.agent_model_records().items())},
        'calls': list(pet.calls),
    }


def _script(win, pet):
    out = []
    snap = lambda label: out.append(_snapshot(win, pet, label))
    entries = win._pet_entries
    _pump(win, 0.1)
    snap('opened')
    # 新建一条 API 模型并保存
    _button(win, '新建一条').invoke()
    _pump(win, 0.1)
    snap('after new')
    entries['model'].insert(0, 'acme-chat-1')
    entries['model'].event_generate('<KeyRelease>')
    entries['base_url'].insert(0, 'https://example.invalid/v1')
    entries['key_env'].insert(0, 'DEMO_KEY')
    entries['note'].insert(0, '备注一')
    _pump(win, 0.1)
    snap('typed')
    win._pet_provider.set('OpenAI')
    _pump(win, 0.1)
    snap('provider changed')
    _button(win, '保存这条').invoke()
    _pump(win, 0.1)
    snap('saved api')
    # 选中该行再改显示名
    tree = win._pet_tree
    rows = tree.get_children()
    if rows:
        tree.selection_set(rows[0])
        _pump(win, 0.1)
        snap('selected')
        entries['label'].delete(0, 'end')
        entries['label'].insert(0, '改过的名字')
        _button(win, '保存这条').invoke()
        _pump(win, 0.1)
        snap('relabelled')
    win._pet_mode.set('API')
    _pump(win, 0.1)
    # 测试连接（API）：无模型 ID 与有模型 ID 各一次
    _button(win, '新建一条').invoke()
    _pump(win, 0.1)
    _button(win, '测试连接').invoke()
    snap('probe without model')
    entries['model'].insert(0, 'probe-model')
    _button(win, '测试连接').invoke()
    snap('probe with model')
    # 切到 Desktop：程序路径行出现、自动搜寻线程跑一轮
    win._pet_mode.set('Desktop')
    _pump(win, 0.8)
    snap('desktop mode')
    _button(win, '自动搜寻').invoke()
    snap('searching')
    _pump(win, 0.5)
    snap('searched')
    _button(win, '保存这条').invoke()
    snap('save desktop (bad path)')
    win._pet_mode.set('CLI')
    _pump(win, 0.2)
    snap('cli mode')
    win._pet_mode.set('API')
    _pump(win, 0.2)
    snap('back to api')
    # 本机密钥：输入、保存、清除
    entries['model'].delete(0, 'end')
    entries['model'].insert(0, 'key-model')
    win._pet_key_entry.insert(0, 'SECRET-VALUE-1234')
    win._pet_save_typed()
    _pump(win, 0.1)
    snap('typed key saved')
    win._pet_clear_key()
    snap('key cleared')
    win._pet_save_key()
    snap('save key with empty box')
    # 删除：未选 → 选中后删
    win._pet_tree.selection_remove(*win._pet_tree.selection())
    win._pet_delete_one()
    snap('delete nothing selected')
    rows = win._pet_tree.get_children()
    if rows:
        win._pet_tree.selection_set(rows[-1])
        _pump(win, 0.1)
        win._pet_delete_one()
        _pump(win, 0.1)
        snap('deleted one')
    win._pet_reload()
    snap('reloaded')
    # 关闭
    _button(win, '关闭').invoke()
    _pump(win, 0.2)
    out.append({'label': 'closed', 'exists': bool(win.winfo_exists())})
    return out


class OpenManagerEquivalence(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except Exception:
            self.skipTest(PLATFORM_TKINTER)
        self.root.withdraw()
        self.addCleanup(lambda: self.root.winfo_exists() and self.root.destroy())
        self.namespace = dict(vars(pet_models_ui))
        exec(compile(LEGACY_SRC, 'legacy_open_manager', 'exec'), self.namespace)

    def _run(self, opener):
        with tempfile.TemporaryDirectory() as td:
            pet = _Pet(self.root, td)
            keys = {}

            def save_key_env(item, text, program, state_id):
                keys[(model_pool.model_id_of(item, state_id))] = text
                return None

            def local_key_of(item, program, state_id):
                return keys.get(model_pool.model_id_of(item, state_id), '')

            def clear_local_key(item, program, state_id):
                return keys.pop(model_pool.model_id_of(item, state_id), None) is not None

            def find_program(model, mode):
                if model == 'key-model':
                    raise ValueError('not found')
                return ''

            patches = [
                mock.patch('model_pool.save_key_env', side_effect=save_key_env),
                mock.patch('model_pool.local_key_of', side_effect=local_key_of),
                mock.patch('model_pool.clear_local_key', side_effect=clear_local_key),
                mock.patch('workflow_settings.find_model_program', side_effect=find_program),
                mock.patch.object(pet_models_ui, 'probe_line', return_value='PROBE-LINE'),
                mock.patch.dict(self.namespace, {'probe_line': lambda record, p: 'PROBE-LINE'}),
            ]
            for patch in patches:
                patch.start()
            try:
                win = opener(pet)
                win.transient(self.root)
                try:
                    return _script(win, pet)
                finally:
                    if win.winfo_exists():
                        win.destroy()
            finally:
                for patch in reversed(patches):
                    patch.stop()

    def test_scripted_session_is_identical(self):
        old = self._run(self.namespace['_legacy_open_manager'])
        new = self._run(pet_models_ui.open_manager)
        self.assertEqual(len(new), len(old))
        for a, b in zip(new, old):
            self.assertEqual(a, b, a['label'])
        # 对照不能是空对空：列表里确实产生过行、提示语确实变化过
        labels = {snap['label']: snap for snap in new}
        self.assertTrue(labels['saved api']['rows'])
        self.assertGreater(len({snap.get('hint') for snap in new if 'hint' in snap}), 6)
        self.assertEqual(labels['closed']['exists'], False)


if __name__ == '__main__':
    unittest.main()
