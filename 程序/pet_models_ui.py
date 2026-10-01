# -*- coding: utf-8 -*-
"""三虎设置 → 模型… 与 模型管理…：两扇窗都只是层皮（第 43 期）。

规格（用户附件《三虎模型设置》）：
- 三虎设置 → 模型：四个任务维度各一个下拉框，底部 测试连接／打开模型管理／保存／重置；
- 模型管理：模型池＋API 配置的唯一入口——加一条、改一条、删一条、测一条连接都在这里；
- 两处的选项都从模型池长出来，不硬编码；改完即时生效（写盘 ＋ 叠进正在用的那份客户端）。

读写在 model_pool、路由在 model_router、生效由 pet.apply_agent_models() 负责；这一层只管画。
窗口照 skill_panel 那套来：Toplevel ＋ transient ＋ Escape 关闭，关掉不留尾巴。
"""
import tkinter as tk
from tkinter import ttk

import model_pool
from ui_tokens import FONTS, SPACING
from ui_widgets import PrimaryButton, SecondaryButton

TITLE = '三虎 · 设置'
SETTINGS_TITLE = '三虎模型配置'          # 第 46 期第 6 条：这一页与它的独立窗口都叫这个名字
MANAGER_BUTTON = 'API 统一配置'          # 第 46 期第 6 条：原「打开模型管理」，挪到抬头行右侧
# 第 51 期第 1 条：这颗键原来用 Highlight（琥珀底、10pt 粗体、大内边距），摆在一排 Compact 按钮里
# 格式不一致；现在与同排的分页按钮／「关闭」一样用 Compact.TButton，名字也补上那个半角空格。
MANAGER_TITLE = '模型管理'
SETTINGS_GEOMETRY = '700x430'


def model_options(records, with_auto=True):
    """模型设置页展示候选；桌面 Agent 状态只在此按需查询一次。"""
    import workflow_settings
    return model_pool.options(records, with_auto=with_auto,
                              labeler=workflow_settings.desktop_model_label)
# 第 51 期第 2 条：窗口长高 90px，多出来的高度全归上面的模型池（下面那张表单同时收紧，见 open_manager）。
MANAGER_GEOMETRY = '1180x860'
# 第 52 期第 1 条：这扇窗原来是个写死的尺寸，在 1366x768 这类屏上比主界面还高。现在按主界面的
# 比例算（再小也留下限，九行表单要塞得下），并摆回主界面正中。
# 第 65 期任务 5：用户要「模型池内容框优先显示全部内容」——比例 80% → 90%、上限长高 80px，
# 多出来的高度全归上面那张模型池。
MANAGER_RATIO = 0.9
MANAGER_MIN = (820, 620)
NOTE_ABOUT = '三虎用于决策、对话、路由；子模块执行模型在阶段配置里选。'
NOTE_MANAGER = '模型池与 API 配置的唯一入口；密钥只写在 .env 里，这里只填变量名。'
# 列表那一行照规格那张表：显示名／Provider／模型 ID／能力标签／状态，另加两个用得上又不好猜的
# （API 根地址、密钥名）。协议在下面表单里选，列表不再占一格。
COLUMNS = (('label', '显示名', 120), ('provider', 'Provider', 100), ('model', '模型 ID', 140),
           ('capabilities', '能力标签', 170), ('base_url', 'API 根地址', 190),
           ('wire_api', '协议', 80), ('key_env', '密钥名', 130), ('state', '状态', 120))
FORM_FIELDS = (('label', '显示名'), ('model', '模型 ID'), ('base_url', 'API 根地址'),
               ('key_env', '密钥名（.env 里的变量名）'))


def parent_of(pet):
    return getattr(pet, 'win', None)


def main_box(parent):
    """主界面的位置与大小；量不出来（自检里窗口还没摆开）返回 None。"""
    if parent is None:
        return None
    try:
        parent.update_idletasks()
        width, height = parent.winfo_width(), parent.winfo_height()
        if width <= 1 or height <= 1:
            return None
        return parent.winfo_rootx(), parent.winfo_rooty(), width, height
    except Exception:
        return None


def fit_to_main(win, parent, geometry, ratio=MANAGER_RATIO):
    """把这扇窗摆成「比主界面小一圈、落在主界面正中」（第 52 期第 1 条）。

    主界面量不出来就退回给的那个尺寸（自检里就是这样）。
    """
    try:
        width, height = (int(value) for value in str(geometry).split('x'))
    except (TypeError, ValueError):
        return geometry
    box = main_box(parent)
    if box is None:
        win.geometry(geometry)
        return geometry
    left, top, parent_width, parent_height = box
    width = min(width, max(MANAGER_MIN[0], int(parent_width * ratio)))
    height = min(height, max(MANAGER_MIN[1], int(parent_height * ratio)))
    x = max(0, left + (parent_width - width) // 2)
    y = max(0, top + (parent_height - height) // 2)
    win.geometry('%dx%d+%d+%d' % (width, height, x, y))
    return win.geometry()


def program_of(pet):
    return getattr(pet, 'program', model_pool.PROGRAM)


def transport_of(pet):
    return getattr(pet, 'probe_transport', None)


def window(pet, title, geometry):
    """一扇小窗：transient 挂在三虎的窗口上，Escape 关掉。"""
    parent = parent_of(pet)
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry(geometry)
    win.transient(parent or None)
    win.bind('<Escape>', lambda event: win.destroy())
    body = ttk.Frame(win, padding=SPACING['md'])
    body.pack(fill='both', expand=True)
    return win, body


def heading(body, title, note, columns=3):
    ttk.Label(body, text=title, font=FONTS['title']).grid(
        row=0, column=0, columnspan=columns, sticky='w')
    ttk.Label(body, text=note, style='Muted.TLabel', wraplength=620).grid(
        row=1, column=0, columnspan=columns, sticky='w', pady=(SPACING['xs'], SPACING['md']))
    return 2


def status_text(record, program):
    """一条记录现在的样子：可用／缺什么（与客户端真发请求时的判据同一份）。"""
    ok, why = model_pool.status(record, program)
    if not ok:
        return why
    return '可用 · %s' % record['model']


def probe_line(record, pet):
    """测一条连接：发一次最小请求，结果翻成人话。"""
    result = model_pool.probe(record, transport_of(pet), program_of(pet))
    name = record.get('label') or record.get('model') or '这一条'
    if result.get('ok'):
        return '%s：连接成功，延迟 %d ms' % (name, int(result.get('ms') or 0))
    status = result.get('status')
    reason = result.get('error') or '没有响应'
    return '%s：%s%s' % (name, ('HTTP %s · ' % status) if status else '', reason)


def open_settings(pet):
    """「设置 → 模型配置」单独开一扇窗时走的这条路（规格里的「三虎设置 → 模型」页）。

    第 44 期：整页抽成 settings_page——「设置」窗口把它当一格嵌进去，右键那条路照旧单独开窗。
    """
    win, body = window(pet, SETTINGS_TITLE, SETTINGS_GEOMETRY)
    page = settings_page(body, pet, close=win.destroy)
    win._pet_hint, win._pet_refresh = page['hint'], page['refresh']
    return win


def settings_page(parent, pet, close=None, with_manager=True):
    """把「模型配置」这一页画进 parent；给了 close 才多摆一颗「关闭」（嵌进分页时由分页自己收）。

    第 48 期第 1 条：「API统一配置」那颗键往上挪一级——嵌在「设置」的分页按钮行上（就在
    「三虎模型配置」右边，见 pet_settings_ui），所以嵌进分页时 with_manager=False，这一页只有
    一行说明；它自己单独开一扇窗时（没有上一级）才照旧摆那颗键。
    """
    program = program_of(pet)
    records = pet.agent_model_records()
    choices = {'default': model_options(records, with_auto=True),
               'plain': model_options(records, with_auto=False)}
    body = parent
    body.columnconfigure(1, weight=1)
    # 第 46 期第 6 条：抬头那行标题文字（原来在分页里显示成「三虎模型设置」）删掉——分页上已经写着
    # 「三虎模型配置」，页里再写一遍是重影。
    ttk.Label(body, text=NOTE_ABOUT, style='Muted.TLabel', wraplength=560).grid(
        row=0, column=0, columnspan=2, sticky='w')
    manager_button = None
    if with_manager:
        manager_button = SecondaryButton(body, text=MANAGER_BUTTON, command=lambda: pet.open_model_manager())
        manager_button.grid(row=0, column=2, sticky='e')
    row = 1
    tasks = pet.agent_model_tasks()
    picked = {}
    states = {}
    hint = tk.StringVar(value='改完点「保存」立刻生效，不用重启。')
    for key, label, note in model_pool.TASK_FIELDS:
        pairs = choices['default'] if key == 'default' else choices['plain']
        values = [text for _model_id, text in pairs]
        import workflow_settings
        var = tk.StringVar(value=model_pool.label_of(tasks.get(key) or model_pool.TASKS_DEFAULT[key],
                                                     records, labeler=workflow_settings.desktop_model_label))
        picked[key] = var
        ttk.Label(body, text=label).grid(row=row, column=0, sticky='w', padx=(0, SPACING['md']), pady=(SPACING['xs'], 0))
        ttk.Combobox(body, textvariable=var, values=values, state='readonly', width=28).grid(
            row=row, column=1, sticky='w', pady=(SPACING['xs'], 0))
        state = ttk.Label(body, text='', style='Muted.TLabel', wraplength=280)
        state.grid(row=row, column=2, sticky='w', padx=(SPACING['md'], 0), pady=(SPACING['xs'], 0))
        states[key] = state
        row += 1
        ttk.Label(body, text=note, style='Muted.TLabel').grid(row=row, column=1, columnspan=2, sticky='w')
        row += 1

    def model_of(key):
        pairs = choices['default'] if key == 'default' else choices['plain']
        return model_pool.id_of_label(picked[key].get(), pairs)

    def refresh():
        for key, _label, _note in model_pool.TASK_FIELDS:
            model_id = model_of(key)
            if model_id == model_pool.AUTO:
                best = pet.resolve_agent_model(key)
                states[key].config(text=('自动 · %s' % best.label) if best.ok else (
                    '自动 · %s' % best.reason))
                continue
            item = records.get(model_id) or {}
            states[key].config(text=status_text(item, program) if item else '池里没有这一条')
        return states

    first = True

    def probe_all():
        seen = []
        for key, _label, _note in model_pool.TASK_FIELDS:
            model_id = model_of(key)
            names = list(records) if model_id == model_pool.AUTO else [model_id]
            for name in names:
                if name in seen or name not in records:
                    continue
                seen.append(name)
        if not seen:
            hint.set('池里还没有可测的模型，先去「模型管理」加一条。')
            return []
        lines = [probe_line(records[name], pet) for name in seen]
        hint.set('；'.join(lines))
        refresh()
        return lines

    def save():
        chosen = {key: model_of(key) for key, _label, _note in model_pool.TASK_FIELDS}
        pet.save_agent_models(chosen)
        refresh()
        hint.set('已保存：默认模型＝%s（下一次调用生效）。'
                 % model_pool.label_of(chosen['default'], records))

    def reset():
        now = pet.agent_model_tasks()
        for key, _label, _note in model_pool.TASK_FIELDS:
            picked[key].set(model_pool.label_of(now.get(key) or model_pool.TASKS_DEFAULT[key], records))
        refresh()
        hint.set('已按盘上的设置还原。')

    refresh()
    ttk.Label(body, textvariable=hint, style='PaleGreenHint.TLabel', wraplength=640).grid(
        row=row, column=0, columnspan=3, sticky='w', pady=(SPACING['md'], 0))
    row += 1
    bar = ttk.Frame(body)
    bar.grid(row=row, column=0, columnspan=3, sticky='ew', pady=(SPACING['md'], 0))
    SecondaryButton(bar, text='测试连接', command=probe_all).pack(side='left')
    SecondaryButton(bar, text='重置', command=reset).pack(side='right', padx=(0, SPACING['sm']))
    PrimaryButton(bar, text='保存', command=save).pack(side='right', padx=(0, SPACING['sm']))
    if close is not None:
        SecondaryButton(bar, text='关闭', command=close).pack(side='right')
    return {'hint': hint, 'refresh': refresh, 'picked': picked, 'states': states, 'records': records,
            'choice_groups': choices, 'probe_all': probe_all, 'save': save, 'reset': reset,
            'manager': manager_button}


def open_manager(pet):
    """模型管理…：模型池＋API 配置的唯一入口（增／删／改／测连接）。"""
    program = program_of(pet)
    win, body = window(pet, MANAGER_TITLE, MANAGER_GEOMETRY)
    fit_to_main(win, parent_of(pet), MANAGER_GEOMETRY)     # 第 52 期第 1 条：比主界面小一圈、居中
    body.columnconfigure(0, weight=1)
    body.rowconfigure(2, weight=1)
    row = heading(body, MANAGER_TITLE, NOTE_MANAGER, columns=1)
    keys = [key for key, _title, _width in COLUMNS]
    # 第 51 期第 2 条：这一格原来只露 8 行，下面那张九行表单却占掉大半个窗口。现在列表要高
    # （14 行起），表单收紧（行距 3→1、外框内边距减半），多出来的高度都归列表。
    # 第 65 期任务 5：用户要「模型池优先显示全部内容」——14 行 → 20 行，且每一列都允许跟随
    # 窗口宽度伸展（原来只有根地址那一列会伸），名字长一点、地址长一点都看得全。
    tree = ttk.Treeview(body, columns=keys, show='headings', height=20)
    for key, title, width in COLUMNS:
        tree.heading(key, text=title)
        tree.column(key, width=width, anchor='w', stretch=True)
    tree.grid(row=2, column=0, sticky='nsew')
    scroll = ttk.Scrollbar(body, orient='vertical', command=tree.yview)
    scroll.grid(row=2, column=1, sticky='ns')
    tree.configure(yscrollcommand=scroll.set)
    form = ttk.Frame(body, padding=(0, SPACING['xs']))
    form.grid(row=3, column=0, columnspan=2, sticky='ew')
    form.columnconfigure(1, weight=1)
    style = ttk.Style(form)
    # 模型管理的字段都是单行输入。专用紧凑样式把默认控件的纵向空白压到最小，
    # 不牵连其他设置页或聊天输入框。
    style.configure('ModelManager.TEntry', font=FONTS['caption'], padding=(SPACING['xs'], 0))
    style.configure('ModelManager.TCombobox', font=FONTS['caption'], padding=(SPACING['xs'], 0))
    entries = {}
    caps = {}
    provider = tk.StringVar(value=model_pool.PROVIDER_LABELS[model_pool.DEFAULT_PROVIDER])
    wire = tk.StringVar(value=model_pool.WIRE_LABELS[model_pool.DEFAULT_WIRE])

    def text_row(index, key, label):
        """一行「标签 ＋ 输入框」；行号往下走，表单中间插下拉框／多选都不会错位。"""
        ttk.Label(form, text=label).grid(row=index, column=0, sticky='w', padx=(0, SPACING['md']), pady=SPACING['xs'])
        entry = ttk.Entry(form, style='ModelManager.TEntry')
        entry.grid(row=index, column=1, sticky='ew', pady=SPACING['xs'])
        entries[key] = entry
        return index + 1

    # 表单次序照规格那张表：显示名、Provider、根地址、密钥、模型 ID、协议、能力标签、上下文、备注。
    index = text_row(0, 'label', '显示名')
    ttk.Label(form, text='Provider').grid(row=index, column=0, sticky='w', padx=(0, SPACING['md']), pady=SPACING['xs'])
    # 第 65 期任务 5：用户报「provider → 自定义不可用」。原来这一格是只读下拉，只能挑三档固定
    # 名字，选了「自定义」既不能写自己的服务商名、也没有自定义路径的入口。现在改成可编辑：
    # 挑现成的，或者直接敲一个名字；存的就是填进去的那个名字。
    provider_box = ttk.Combobox(form, textvariable=provider, state='normal', style='ModelManager.TCombobox',
                                values=[label for _value, label in model_pool.PROVIDERS])
    provider_box.grid(row=index, column=1, sticky='ew', pady=SPACING['xs'])
    def match_wire(event=None):
        """第 65 期任务 8：换了 Provider，「协议」栏自动摆到它默认的那一档。

        只挂「选中了一项」，不挂失焦——用户在协议栏手改过的那一档不会被蹭掉。
        """
        value = model_pool.wire_for_provider(
            model_pool.id_of_label(provider.get(), model_pool.PROVIDERS))
        wire.set(model_pool.WIRE_LABELS.get(value, model_pool.WIRE_LABELS[model_pool.DEFAULT_WIRE]))
    provider_box.bind('<<ComboboxSelected>>', match_wire)

    index = text_row(index + 1, 'base_url', 'API 根地址')
    index = text_row(index, 'key_env', '密钥名（.env 里的变量名）')
    # 规格里的第二种放法：密钥直接输进来，用系统加密存本机（明文不落盘、配置 JSON 里不写）。
    ttk.Label(form, text='直接输入密钥').grid(row=index, column=0, sticky='w', padx=(0, SPACING['md']), pady=SPACING['xs'])
    key_row = ttk.Frame(form)
    key_row.grid(row=index, column=1, sticky='w', pady=SPACING['xs'])
    key_entry = ttk.Entry(key_row, width=30, show='*', style='ModelManager.TEntry')
    key_entry.pack(side='left')
    SecondaryButton(key_row, text='保存到本机', command=lambda: local_save()).pack(side='left', padx=(SPACING['sm'], 0))
    SecondaryButton(key_row, text='清除本机密钥', command=lambda: local_clear()).pack(side='left', padx=(SPACING['xs'], 0))
    index += 1
    key_state = tk.StringVar(value='')
    ttk.Label(form, textvariable=key_state, style='Muted.TLabel').grid(
        row=index, column=1, sticky='w', pady=(0, SPACING['xs']))
    index += 1
    index = text_row(index, 'model', '模型 ID')
    ttk.Label(form, text='协议').grid(row=index, column=0, sticky='w', padx=(0, SPACING['md']), pady=SPACING['xs'])
    ttk.Combobox(form, textvariable=wire, state='readonly', style='ModelManager.TCombobox',
                 values=[label for _value, label in model_pool.WIRE_APIS]).grid(
        row=index, column=1, sticky='w', pady=SPACING['xs'])
    index += 1
    ttk.Label(form, text='能力标签').grid(row=index, column=0, sticky='w', padx=(0, SPACING['md']), pady=SPACING['xs'])
    cap_row = ttk.Frame(form)
    cap_row.grid(row=index, column=1, sticky='w', pady=SPACING['xs'])
    for tag in model_pool.CAPABILITY_TAGS:
        var = tk.BooleanVar(value=False)
        caps[tag] = var
        ttk.Checkbutton(cap_row, text=model_pool.CAPABILITY_LABELS[tag],
                        variable=var).pack(side='left', padx=(0, SPACING['sm']))
    index = text_row(index + 1, 'context_length', '上下文长度（可选）')
    text_row(index, 'note', '备注（可选）')
    hint = tk.StringVar(value='选一条改，或者「新建一条」；「保存这条」立刻写进模型池。')
    manager_hint = ttk.Label(body, textvariable=hint, style='PaleGreenHint.TLabel', wraplength=860)
    manager_hint.grid(
        row=4, column=0, columnspan=2, sticky='w', pady=(SPACING['xs'], SPACING['xs']))
    state = {'id': ''}

    def load_rows():
        # 自定义 Provider 已随模型记录写入模型池；每次刷新列表时从同一份记录回填，
        # 新建下一条模型即可直接从下拉选择，无需再维护第二份厂商配置。
        builtins = [label for _value, label in model_pool.PROVIDERS]
        saved = {model_pool.PROVIDER_LABELS.get(str(item.get('provider') or '').strip(),
                                                 str(item.get('provider') or '').strip())
                 for item in pet.agent_model_records().values()}
        provider_box.configure(values=[*builtins, *sorted((item for item in saved if item and item not in builtins),
                                                          key=str.casefold)])
        tree.delete(*tree.get_children())
        records = pet.agent_model_records()
        for model_id, item in sorted(records.items(), key=lambda pair: (
                str(pair[1].get('label') or '').casefold(), pair[0])):
            tree.insert('', 'end', iid=model_id,
                        values=(item['label'], model_pool.provider_name(model_id, item), item['model'],
                                model_pool.capability_text(item['capabilities']),
                                item['base_url'],
                                model_pool.WIRE_LABELS.get(item['wire_api'], item['wire_api']),
                                item['key_env'], status_text(item, program)))
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
            hint.set(str(exc))
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
        if not key_entry.get().strip():
            return None
        try:
            return local_save()
        except Exception:
            return None

    key_entry.bind('<Return>', save_typed_key)
    key_entry.bind('<FocusOut>', save_typed_key)

    def fill(model_id, item):
        state['id'] = model_id
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
        provider.set(model_pool.PROVIDER_LABELS.get(
            saved_provider, saved_provider or model_pool.PROVIDER_LABELS[model_pool.DEFAULT_PROVIDER]))
        wire.set(model_pool.WIRE_LABELS.get(item.get('wire_api'), model_pool.WIRE_LABELS[model_pool.DEFAULT_WIRE]))
        show_key_state(item)

    def read_form():
        value = {key: entries[key].get().strip() for key, _label in FORM_FIELDS}
        value['provider'] = model_pool.id_of_label(provider.get(), model_pool.PROVIDERS)
        value['wire_api'] = model_pool.id_of_label(wire.get(), model_pool.WIRE_APIS)
        value['capabilities'] = [tag for tag, var in caps.items() if var.get()]
        value['context_length'] = entries['context_length'].get().strip()
        value['note'] = entries['note'].get().strip()
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
        state['id'] = ''
        for key, _label in FORM_FIELDS:
            entries[key].delete(0, 'end')
        for key in ('context_length', 'note'):
            entries[key].delete(0, 'end')
        for var in caps.values():
            var.set(False)
        key_entry.delete(0, 'end')
        show_key_state()
        provider.set(model_pool.PROVIDER_LABELS[model_pool.DEFAULT_PROVIDER])
        wire.set(model_pool.WIRE_LABELS[model_pool.DEFAULT_WIRE])
        hint.set('填一条新的：显示名、模型 ID、API 根地址、密钥名；协议照旧选 chat。')
        return state

    def save_one():
        try:
            if key_entry.get().strip():     # 第 65 期任务 5：密钥框里还有字，连它一起存
                local_save()
            pet.save_pool(read_form(), state['id'])
        except ValueError as exc:
            hint.set(str(exc))
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
            hint.set('先选一条。')
            return None
        item = pet.agent_model_records().get(model_id) or {}
        name = item.get('label') or model_id
        if not pet.confirm_start('删除模型', '把「%s」从模型池里删掉？（.env 里的密钥不动）' % name):
            return None
        pet.delete_pool_model(model_id)
        # 保存后必须回读确认；否则表格刷新看似消失、重开又出现时用户会误以为已经删除。
        if model_id in pet.agent_model_records():
            hint.set('未能删除「%s」，请重试。' % name)
            return None
        state['id'] = ''
        load_rows()
        hint.set('已删除「%s」。' % name)
        return model_id

    def probe_one():
        value = read_form()
        if not value.get('model'):
            hint.set('先填模型 ID。')
            return None
        hint.set(probe_line(model_pool.record(value), pet))
        return value

    tree.bind('<<TreeviewSelect>>', on_select)
    load_rows()
    bar = ttk.Frame(body)
    bar.grid(row=5, column=0, columnspan=2, sticky='ew')
    SecondaryButton(bar, text='新建一条', command=new_one).pack(side='left')
    SecondaryButton(bar, text='测试连接', command=probe_one).pack(side='left', padx=(SPACING['sm'], 0))
    SecondaryButton(bar, text='删除这条', command=delete_one).pack(side='left', padx=(SPACING['sm'], 0))
    SecondaryButton(bar, text='关闭', command=win.destroy).pack(side='right')
    PrimaryButton(bar, text='保存这条', command=save_one).pack(side='right', padx=(0, SPACING['sm']))
    win._pet_reload = load_rows
    win._pet_hint = hint
    win._pet_manager_hint_label = manager_hint
    win._pet_entries = entries
    win._pet_provider = provider
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
