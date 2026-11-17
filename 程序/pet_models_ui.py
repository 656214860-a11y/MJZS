# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
import model_pool
from ui.pet_models_tabs import MODES, ModelManagerModeTabsMixin
from responsive_ui import auto_height
from ui_tokens import (BUTTON_GAP, COMBOBOX_PADDING, TEXT_ROWS, FONTS, FORM_LABEL_WIDTH, INPUT_PADDING_X,
                       SPACING, TEXT_DESC, TEXT_HINT, OVERLAY_RATIO)
from ui_dialogs import FileDialog
from account_inputs import PasswordInput
from ui_widgets import (BusyState, NotificationDispatcher, SelectBox, BaseDialog, Card, DataTable,
                        LineInput, PrimaryButton, SecondaryButton)
TITLE = '三虎 · 设置'
SETTINGS_TITLE = '三虎模型配置'          # 第 46 期第 6 条：这一页与它的独立窗口都叫这个名字
MANAGER_BUTTON = '模型配置'              # 用户要求：原「API 统一配置」改名为「模型配置」，仍打开模型管理
MANAGER_TITLE = '模型管理'
SETTINGS_GEOMETRY = '700x430'
SETTINGS_MIN = (620, 430)
def form_column_width(labels):
    """表单标签列宽：令牌字符宽给下限，再按实际标签量出像素，避免中文标签被裁。

    `FORM_LABEL_WIDTH` 是共用表单基准（skill_panel 的同名列同源）；中文标签按字符数
    直接当像素会裁字，所以再用令牌字体实测一次，取两者较大值。标签列还要留出与输入列
    之间的 `SPACING['md']` 间距，一并计入后同一窗口的各页才能共用同一条输入竖线。
    """
    measure = tkfont.Font(font=FONTS['body']).measure
    gap = SPACING['md']
    floor = measure('0') * FORM_LABEL_WIDTH + gap
    return max([floor] + [measure(str(label)) + gap for label in labels])


def report_error(hint, message):
    """可恢复错误只写非模态提示（`NotificationDispatcher.error` 默认 modal=False）。

    模型检测、保存失败等失败不应弹模态框锁住整扇窗；破坏性删除仍走宿主确认。
    """
    return NotificationDispatcher(hint).error(str(message))


def model_options(records, with_auto=True):
    """模型设置页展示候选；桌面 Agent 状态只在此按需查询一次。"""
    import orchestrator.workflow_settings as workflow_settings
    return model_pool.options(records, with_auto=with_auto,
                              labeler=workflow_settings.desktop_model_label)
# 第 51 期第 2 条：窗口长高 90px，多出来的高度全归上面的模型池（下面那张表单同时收紧，见 open_manager）。
MANAGER_GEOMETRY = '1180x860'
MANAGER_MIN = (820, 620)
NOTE_ABOUT = '三虎用于决策、对话、路由；子模块执行模型在阶段配置里选。'
# 「模型 ID」一栏在本地调用（Desktop／CLI）时填的是程序名，API 时才是接口模型名。
MODEL_FIELD_LOCAL, MODEL_FIELD_API = '程序名', '模型 ID'
NOTE_MANAGER = '点左上角页签选择调用方式：Desktop 配置桌面应用，API 配置接口与密钥，CLI 配置命令行程序。'
# 列表按「功能 → Provider」两级分组；只有 Provider 列头可点（翻转分组顺序）。
COLUMNS = (('modality', '功能', 60), ('provider', 'Provider', 90), ('call_mode', '调用方式', 70),
           ('model', '模型 ID', 150), ('label', '显示名', 160), ('capabilities', '能力标签', 270),
           ('state', '状态', 200))
FORM_FIELDS = (('label', '显示名'), ('model', '模型 ID'), ('base_url', 'API 根地址'),
               ('key_env', '密钥名（.env 里的变量名）'))
TASK_FIELD_LABELS = tuple(label for _key, label, _note in model_pool.TASK_FIELDS)
# 模型管理表单的全部标签；列宽按最宽的一条量，避免中文标签被定宽裁掉。
MANAGER_FORM_LABELS = ('Provider', '模型 ID', '显示名', '功能', 'API 根地址',
                       '密钥名（.env 里的变量名）', '直接输入密钥', '协议', '能力标签',
                       '上下文长度（可选）', '每分钟请求上限（可选）', '模型组（可选）',
                       '权重（可选）', '备注（可选）', '应用安装路径', '命令行程序路径')
# 密钥框只给占位宽度，真正可输入区由输入列伸缩；不把整把密钥回显到界面。
SECRET_FIELD_WIDTH = 30
# 表单里的下拉框与输入框只给够用的宽度；成对的两项并在一行（左对左、右对右）。
FORM_COMBO_WIDTH = 14
FORM_DEFAULT_PROVIDER = model_pool.PROVIDER_LABELS['custom']  # 新建默认「自定义」
FORM_RIGHT_LABEL_PAD = (SPACING['lg'], SPACING['xs'])


def provider_choices():  # 下拉不含「OpenAI 兼容接口」（旧记录仍按原名显示），按首字母排序
    return sorted((l for v, l in model_pool.PROVIDERS if v != model_pool.DEFAULT_PROVIDER), key=str.casefold)


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


def fit_to_main(win, parent, geometry, ratio=OVERLAY_RATIO, floor=MANAGER_MIN, cap=None):
    """把这扇窗摆成「主界面的固定比例、落在主界面正中、永不超出主界面」。

    - 目标尺寸＝主界面 × ratio（默认 OVERLAY_RATIO）；
    - 内容兜底 floor 先被主界面尺寸封顶；cap 是可选绝对上限（None＝只封顶到主界面，
      不另设绝对上限，弹窗在超大屏上也严格＝主界面 × ratio）；
    - 主界面量不出来就退回给的那个尺寸（自检里就是这样）。
    """
    try:
        back_w, back_h = (int(value) for value in str(geometry).split('x'))
    except (TypeError, ValueError):
        return geometry
    box = main_box(parent)
    if box is None:
        win.geometry(geometry)
        return geometry
    left, top, parent_width, parent_height = box
    cap_width = parent_width if cap is None else min(parent_width, cap[0])
    cap_height = parent_height if cap is None else min(parent_height, cap[1])
    # 兜底值先被主界面封顶，再与覆盖比例取大；上限是主界面与（可选）写死尺寸的较小者。
    width = min(cap_width, max(int(parent_width * ratio), min(floor[0], parent_width)))
    height = min(cap_height, max(int(parent_height * ratio), min(floor[1], parent_height)))
    x = max(0, left + (parent_width - width) // 2)
    y = max(0, top + (parent_height - height) // 2)
    win.geometry('%dx%d+%d+%d' % (width, height, x, y))
    return win.geometry()


def program_of(pet):
    return getattr(pet, 'program', model_pool.PROGRAM)


def transport_of(pet):
    return getattr(pet, 'probe_transport', None)


def window(pet, title, geometry, minsize=None):
    """一扇小窗：transient 挂在三虎的窗口上，Escape 关掉。"""
    parent = parent_of(pet)
    win = BaseDialog(parent, '', modal=False, chrome=False)
    win.title(title)
    win.geometry(geometry)
    if minsize:
        win.minsize(*minsize)
    win.transient(parent or None)
    win.bind('<Escape>', lambda event: win.destroy())
    body = Card(win)
    body.pack(fill='both', expand=True, padx=SPACING['md'], pady=SPACING['md'])
    return win, body


def heading(body, title, note, columns=3):
    """标题与说明同占一行（说明跟在标题右侧），把纵向空间留给下面的模型列表。"""
    row = ttk.Frame(body)
    row.grid(row=0, column=0, columnspan=columns, sticky='ew', pady=(SPACING['none'], SPACING['sm']))
    ttk.Label(row, text=title, font=FONTS['title']).pack(side='left')
    ttk.Label(row, text=note, style='Muted.TLabel', wraplength=TEXT_DESC['wraplength']).pack(
        side='left', anchor='s', padx=(SPACING['md'], SPACING['none']))
    return 1


# 模型管理表单用紧凑输入框：纵向内边距归零，行高约为常规输入框一半，空出高度给模型列表。
COMPACT_PREFIX = 'Compact.'
COMPACT_COMBOBOX_STYLE = COMPACT_PREFIX + 'Tokens.Combobox.TCombobox'
# 下拉框纵向内边距：零内边距时框高约 19px，上下各 3px 后约 25px，高出三分之一。
COMPACT_COMBOBOX_PAD_Y = SPACING['xs'] - SPACING['xs'] // 4


class CompactLineInput(LineInput):
    NORMAL_STYLE = COMPACT_PREFIX + LineInput.NORMAL_STYLE
    PLACEHOLDER_STYLE = COMPACT_PREFIX + LineInput.PLACEHOLDER_STYLE
    ERROR_STYLE = COMPACT_PREFIX + LineInput.ERROR_STYLE


def install_compact_form_styles(widget):
    """派生样式只改 padding，其余颜色、边框与状态映射沿用父样式。"""
    style = ttk.Style(widget)
    for name in (CompactLineInput.NORMAL_STYLE, CompactLineInput.PLACEHOLDER_STYLE, CompactLineInput.ERROR_STYLE):
        style.configure(name, padding=(INPUT_PADDING_X, SPACING['none']))
    style.configure(COMPACT_COMBOBOX_STYLE, padding=(COMBOBOX_PADDING[0], COMPACT_COMBOBOX_PAD_Y))


def status_text(record, program):
    """一条记录现在的样子：可用／缺什么（与客户端真发请求时的判据同一份）。"""
    ok, why = model_pool.status(record, program)
    if not ok:
        return why
    return '可用 · %s' % record['model']


def probe_breakdown(result, record, program=None):
    """把「测试连接」拆开说明：连通／协议／模型标识／能力／完整任务，另附配置版本与最近完整任务。"""
    marks = {True: '通过', False: '异常'}
    lines = ['%s：%s%s' % (entry['label'], marks.get(entry['ok'], '未验证'),
                           (' · ' + entry['detail']) if entry.get('detail') else '')
             for entry in (result.get('checks') or [])]
    version = result.get('config_version')
    if version:
        lines.append('配置版本：' + version)
    latest = model_pool.health_of(record, program=program)
    if latest:
        stamp = latest.get('at') or '（未记时间）'
        tail = latest.get('error') or ('正文 %s 字' % latest.get('content_length'))
        lines.append('最近完整任务：%s · %s · %s'
                     % (stamp, '通过' if latest.get('ok') else '失败', tail))
    else:
        lines.append('最近完整任务：还没跑过（点「小样本验证」会发一次真实短请求）')
    return '\n'.join(lines)


def probe_line(record, pet):
    """测一条连接：发一次最小请求，结果翻成人话；再分项说清这趟证明了什么、没证明什么。"""
    program = program_of(pet)
    result = model_pool.probe(record, transport_of(pet), program)
    name = record.get('label') or record.get('model') or '这一条'
    if result.get('ok'):
        note = result.get('usage_note') or ''
        head = '%s：连接成功，延迟 %d ms' % (name, int(result.get('ms') or 0))
        head = head + ('（' + note + '）' if note else '')
    else:
        status = result.get('status')
        reason = result.get('error') or '没有响应'
        head = '%s：%s%s' % (name, ('HTTP %s · ' % status) if status else '', reason)
    return head + '\n' + probe_breakdown(result, record, program)


def verify_line(record, pet):
    """小样本验证：用户点名才发一次真实短请求，跑完把「最近完整任务结果」记下来。"""
    program = program_of(pet)
    outcome = model_pool.verify_sample(record, transport_of(pet), program)
    model_pool.record_health(record, outcome, program)
    name = record.get('label') or record.get('model') or '这一条'
    verdict = '通过' if outcome.get('ok') else '没通过'
    tail = outcome.get('error') or ('正文 %s 字' % outcome.get('content_length'))
    return '%s：完整任务%s · %s（配置版本 %s）' % (name, verdict, tail, outcome.get('config_version'))


def open_settings(pet):
    """「设置 → 模型配置」单独开一扇窗时走的这条路（规格里的「三虎设置 → 模型」页）。

    第 44 期：整页抽成 settings_page——「设置」窗口把它当一格嵌进去，右键那条路照旧单独开窗。
    """
    win, body = window(pet, SETTINGS_TITLE, SETTINGS_GEOMETRY, minsize=SETTINGS_MIN)
    page = settings_page(body, pet, close=win.destroy)
    win._pet_hint, win._pet_refresh = page['hint'], page['refresh']
    return win


def settings_page(parent, pet, close=None, with_manager=True, label_width=None, show_save=True):
    """把「模型配置」这一页画进 parent；给了 close 才多摆一颗「关闭」（嵌进分页时由分页自己收）。

    第 48 期第 1 条：「API统一配置」那颗键往上挪一级——嵌在「设置」的分页按钮行上（就在
    「三虎模型配置」右边，见 pet_settings_ui），所以嵌进分页时 with_manager=False，这一页只有
    一行说明；它自己单独开一扇窗时（没有上一级）才照旧摆那颗键。
    """
    program = program_of(pet)
    records = pet.agent_model_records()
    choices = {'default': model_options(records, with_auto=True),
               'plain': model_options(records, with_auto=False)}
    # 底部动作区先占住窗口底边，窗口被压矮时只压缩上面的表单，保存／关闭不会掉出可视区。
    actions = ttk.Frame(parent)
    actions.pack(side='bottom', fill='x', pady=(SPACING['md'], SPACING['none']))
    body = ttk.Frame(parent)
    body.pack(fill='both', expand=True)
    body.columnconfigure(0, minsize=label_width or form_column_width(TASK_FIELD_LABELS))
    body.columnconfigure(1, weight=1)
    # 第 46 期第 6 条：抬头那行标题文字（原来在分页里显示成「三虎模型设置」）删掉——分页上已经写着
    # 「三虎模型配置」，页里再写一遍是重影。
    ttk.Label(body, text=NOTE_ABOUT, style='Muted.TLabel', wraplength=TEXT_DESC['wraplength']).grid(
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
    cert_var = tk.BooleanVar(value=model_pool.require_certified(program))
    for key, label, note in model_pool.TASK_FIELDS:
        pairs = choices['default'] if key == 'default' else choices['plain']
        values = [text for _model_id, text in pairs]
        import orchestrator.workflow_settings as workflow_settings
        var = tk.StringVar(value=model_pool.label_of(tasks.get(key) or model_pool.TASKS_DEFAULT[key],
                                                     records, labeler=workflow_settings.desktop_model_label))
        picked[key] = var
        ttk.Label(body, text=label).grid(row=row, column=0, sticky='w', pady=(SPACING['xs'], SPACING['none']))
        SelectBox(body, textvariable=var, values=values).grid(
            row=row, column=1, sticky='ew', pady=(SPACING['xs'], SPACING['none']))
        state = ttk.Label(body, text='', style='Muted.TLabel', wraplength=TEXT_HINT['wraplength'])
        state.grid(row=row, column=2, sticky='w', padx=(SPACING['md'], SPACING['none']), pady=(SPACING['xs'], SPACING['none']))
        states[key] = state
        row += 1
        ttk.Label(body, text=note, style='Muted.TLabel').grid(row=row, column=1, columnspan=2, sticky='w')
        row += 1
    ttk.Checkbutton(body, text='无人值守前要求五合一认证',
                    variable=cert_var).grid(row=row, column=1, columnspan=2, sticky='w',
                                            pady=(SPACING['xs'], SPACING['none']))
    row += 1
    ttk.Label(body, text='五项：连接/协议/模型/能力/完整任务', style='Muted.TLabel').grid(
        row=row, column=1, columnspan=2, sticky='w')
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
            report_error(hint, '池里还没有可测的模型，先去「模型管理」加一条。')
            return []
        lines = [probe_line(records[name], pet) for name in seen]
        hint.set('\n\n'.join(lines))
        refresh()
        return lines

    def probe_sample():
        """小样本验证：只在「默认模型」这一条上发一次真实短请求，跑完记下最近完整任务。"""
        model_id = model_of('default')
        if model_id == model_pool.AUTO or model_id not in records:
            report_error(hint, '先在「默认模型」里选一条具体模型，再点「小样本验证」。')
            return None
        line = verify_line(records[model_id], pet)
        hint.set(line)
        refresh()
        return line

    def save():
        chosen = {key: model_of(key) for key, _label, _note in model_pool.TASK_FIELDS}
        try:
            pet.save_agent_models(chosen)
            model_pool.set_require_certified(cert_var.get(), program)
        except (ValueError, OSError) as exc:
            report_error(hint, exc)
            return None
        refresh()
        hint.set('已保存：默认模型＝%s（下一次调用生效）。'
                 % model_pool.label_of(chosen['default'], records))
        return chosen

    def reset():
        now = pet.agent_model_tasks()
        cert_var.set(model_pool.require_certified(program))
        for key, _label, _note in model_pool.TASK_FIELDS:
            picked[key].set(model_pool.label_of(now.get(key) or model_pool.TASKS_DEFAULT[key], records))
        refresh()
        hint.set('已按盘上的设置还原。')

    refresh()
    ttk.Label(body, textvariable=hint, style='PaleGreenHint.TLabel', wraplength=TEXT_DESC['wraplength']).grid(
        row=row, column=0, columnspan=3, sticky='w', pady=(SPACING['md'], SPACING['none']))
    row += 1
    bar = ttk.Frame(actions)
    bar.pack(fill='x')
    SecondaryButton(bar, text='测试连接', command=probe_all).pack(side='left')
    SecondaryButton(bar, text='小样本验证',
                    command=probe_sample).pack(side='left', padx=(BUTTON_GAP, SPACING['none']))
    # 主操作贴最右，取消（关闭）紧挨其左，重置再往左：关窗键不再压在主按钮右侧。
    if show_save:
        PrimaryButton(bar, text='保存', command=save).pack(side='right')
    if close is not None:
        SecondaryButton(bar, text='关闭', command=close).pack(
            side='right', padx=(SPACING['none'], BUTTON_GAP))
    SecondaryButton(bar, text='重置', command=reset).pack(
        side='right', padx=(SPACING['none'], BUTTON_GAP))
    return {'hint': hint, 'refresh': refresh, 'picked': picked, 'states': states, 'records': records,
            'choice_groups': choices, 'probe_all': probe_all, 'probe_sample': probe_sample,
            'save': save, 'reset': reset,
            'manager': manager_button}


def _derive_client_profile(path, display, mode, entries, *, probe):
    '''Adapt one executable and fill the model id when only a path was given.'''
    from client_profiles import adapt_executable
    adapted = adapt_executable(path, display=display, probe=probe)
    profile = adapted.get('profile') or {}
    kind = profile.get('kind')
    switched = ''
    if kind:
        wanted = 'CLI' if kind == 'cli' else 'Desktop'
        if mode.get() != wanted:
            mode.set(wanted)
            switched = wanted
        if not entries['model'].get().strip():
            entries['model'].insert(0, profile.get('id', ''))
    return adapted, switched


def _probe_local_model(pet, value, mode, entries, program_entry, hint):
    '''Locate and adapt a local Desktop program, filling the path back into the form.'''
    from pathlib import Path
    from orchestrator.workflow_settings import find_model_program, current_store_program
    if not value.get('program') and not value.get('model'):
        report_error(hint, '先填模型 ID，或点“浏览…”选择 .exe。')
        return None
    try:
        path = (current_store_program(value['program']) if value['program'] else
                find_model_program(value['model'], mode.get()))
        if not Path(path).is_file():
            raise ValueError('应用路径不存在')
        program_entry.delete(0, 'end')
        program_entry.insert(0, path)
        adapted, _switched = _derive_client_profile(
            path, value.get('label') or value.get('model'), mode, entries, probe=True)
        hint.set('已找到程序：%s；%s。请保存这条。' %
                 (path, adapted.get('reason') or '已记录程序路径'))
    except (ValueError, KeyError) as exc:
        report_error(hint, '检查程序失败：' + str(exc))
    return value


def _apply_program_search(path, error, original_path, program_entry, hint):
    """自动搜寻结束后回填路径；用户在等待期间手填过就不覆盖。"""
    if program_entry.get() != original_path:
        hint.set('搜寻已结束；保留您手动填写的安装路径。')
        return
    if not path:
        report_error(hint, '未自动找到安装路径：%s' % error)
        return
    program_entry.delete(0, 'end')
    program_entry.insert(0, path)
    hint.set('已自动找到安装路径：%s；确认后点「保存这条」。' % path)


def open_manager(pet):
    """模型管理…：模型池＋API 配置的唯一入口（增／删／改／测连接）。"""
    return _ModelManager(pet).build()


class _ModelManager(ModelManagerModeTabsMixin):
    """模型管理窗口（从 open_manager 的闭包原样改写成类，R1812）：共享的局部变量成了实例属性，嵌套函数成了方法。"""
    def __init__(self, pet):
        self.pet = pet

    def build(self):
        footer, body = self._build_window_and_table()
        self._build_form_fields()
        self._build_program_row(body, footer)
        self.win._pet_detect_program = self.detect_program
        self.win._pet_read_form = self.read_form
        self.win._pet_provider_box = self.provider_box
        self.win._pet_tree = self.tree
        self.win._pet_delete_one = self.delete_one
        # 自检要按的那两颗（密钥那条链只能从界面上走一遍）：本机保存／清除 ＋ 那个只写不读的输入框。
        self.win._pet_labels = self.labels
        self.win._pet_key_entry = self.key_entry
        self.win._pet_save_key = self.local_save
        self.win._pet_save_typed = self.save_typed_key
        self.win._pet_clear_key = self.local_clear
        self.win._pet_key_state = self.key_state.get
        return self.win

    def _build_window_and_table(self):
        """窗口外壳、标题与模型列表（从 build 原样切出，R1812）。"""
        self.program = program_of(self.pet)
        self.win, card = window(self.pet, MANAGER_TITLE, MANAGER_GEOMETRY, minsize=MANAGER_MIN)
        fit_to_main(self.win, parent_of(self.pet), MANAGER_GEOMETRY)     # 第 52 期第 1 条：比主界面小一圈、居中
        # 动作区先占住窗口底边，窗口被压矮时只压缩上面的模型列表与表单。
        footer = ttk.Frame(card)
        footer.pack(side='bottom', fill='x')
        body = ttk.Frame(card)
        body.pack(fill='both', expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)
        heading(body, MANAGER_TITLE, NOTE_MANAGER, columns=1)
        # 表单行不叠加纵向外边距；控件保留自身内边距，窗口剩余高度全部交给模型列表。
        # 列宽随窗口伸展，长名称与缺项说明可以通过滚动条查看。
        self.table_shell = DataTable(body, columns=COLUMNS, show='headings', height=TEXT_ROWS['4xl'],
                                empty_text='暂无模型配置')
        self.tree = self.table_shell.tree
        self.provider_descending = False
        for key, title, width in COLUMNS:
            # DataTable 默认给每个列头挂按显示文本排序；这里只留 Provider 一列可点，其余清掉。
            self.tree.heading(key, text=title, command=self.flip_provider_order if key == 'provider' else '')
            self.tree.column(key, width=width, anchor='w', stretch=True)
        self.mode_tabs = ttk.Notebook(body)
        self.mode_tabs.grid(row=1, column=0, columnspan=2, sticky='w')
        for mode in MODES:
            self.mode_tabs.add(ttk.Frame(self.mode_tabs, padding=(SPACING['none'], SPACING['xs'])), text=mode)
        self.table_shell.grid(row=2, column=0, sticky='nsew')
        self._fit_model_list = auto_height(self.tree, self.table_shell)
        install_compact_form_styles(body)
        self.form = ttk.Frame(body, padding=(SPACING['none'], SPACING['xs']))
        self.form.grid(row=3, column=0, columnspan=2, sticky='ew')
        self.form.columnconfigure(0, minsize=form_column_width(MANAGER_FORM_LABELS))
        self.form.columnconfigure(1, weight=1, uniform='fields')
        self.form.columnconfigure(2, minsize=form_column_width(('功能', '显示名', '备注（可选）')))
        self.form.columnconfigure(3, weight=1, uniform='fields')
        self.entries = {}
        self.labels = {}
        self.caps = {}
        self.provider = tk.StringVar(value=FORM_DEFAULT_PROVIDER)
        self.wire = tk.StringVar(value=model_pool.WIRE_LABELS[model_pool.DEFAULT_WIRE])
        self.mode = tk.StringVar(value='API')

        # 表单次序：Provider｜功能、模型 ID｜显示名、根地址、密钥、协议、能力标签、上下文｜备注。
        return footer, body

    def _build_form_fields(self):
        """表单：Provider、功能、模型 ID／显示名／地址／密钥、协议、能力标签（调用方式由左上角页签决定）。"""
        ttk.Label(self.form, text='Provider').grid(row=0, column=0, sticky='w')
        # 第 65 期任务 5：可编辑下拉——挑现成的，或直接敲一个服务商名；存的就是填进去的那个名字。
        self.provider_box = SelectBox(self.form, textvariable=self.provider, state='normal',
                                    values=provider_choices(), style=COMPACT_COMBOBOX_STYLE, width=FORM_COMBO_WIDTH)
        self.provider_box.grid(row=0, column=1, sticky='ew')
        self.provider_box.bind('<<ComboboxSelected>>', self.match_wire)
        self.provider_box.bind('<<ComboboxSelected>>', lambda event: self.detect_program(), add='+')
        ttk.Label(self.form, text='功能').grid(row=0, column=2, sticky='e', padx=FORM_RIGHT_LABEL_PAD)
        self.modality = tk.StringVar(value=model_pool.MODALITY_LABELS[model_pool.DEFAULT_MODALITY])
        self.modality_box = SelectBox(self.form, textvariable=self.modality, style=COMPACT_COMBOBOX_STYLE,
                                      values=[label for _value, label in model_pool.MODALITIES])
        self.modality_box.grid(row=0, column=3, sticky='ew')
        self.text_row(1, 'model', '模型 ID')
        self.text_row(1, 'label', '显示名', column=2)
        index = self.text_row(2, 'base_url', 'API 根地址', span=3)
        self.text_row(index, 'key_env', '密钥名（.env 里的变量名）')
        ttk.Label(self.form, text='协议').grid(row=index, column=2, sticky='e', padx=FORM_RIGHT_LABEL_PAD)
        SelectBox(self.form, textvariable=self.wire, style=COMPACT_COMBOBOX_STYLE,
                  values=[label for _value, label in model_pool.WIRE_APIS]).grid(row=index, column=3, sticky='ew')
        index += 1
        # 规格里的第二种放法：密钥直接输进来，用系统加密存本机（明文不落盘、配置 JSON 里不写）。
        ttk.Label(self.form, text='直接输入密钥').grid(row=index, column=0, sticky='w')
        key_row = ttk.Frame(self.form)
        key_row.grid(row=index, column=1, columnspan=3, sticky='w')
        self.key_entry = PasswordInput(key_row, width=SECRET_FIELD_WIDTH, mask='*')
        self.key_entry.pack(side='left')
        SecondaryButton(key_row, text='保存到本机', command=lambda: self.local_save()).pack(side='left', padx=(BUTTON_GAP, SPACING['none']))
        SecondaryButton(key_row, text='清除本机密钥', command=lambda: self.local_clear()).pack(side='left', padx=(SPACING['xs'], SPACING['none']))
        # 密钥状态紧跟在按钮后面，不再单独占一行。
        self.key_state = tk.StringVar(value='')
        ttk.Label(key_row, textvariable=self.key_state, style='Muted.TLabel').pack(side='left', padx=(SPACING['sm'], SPACING['none']))
        index += 1
        ttk.Label(self.form, text='能力标签').grid(row=index, column=0, sticky='w')
        cap_row = ttk.Frame(self.form)
        cap_row.grid(row=index, column=1, columnspan=3, sticky='w')
        for tag in model_pool.CAPABILITY_TAGS:
            var = tk.BooleanVar(value=False)
            self.caps[tag] = var
            ttk.Checkbutton(cap_row, text=model_pool.CAPABILITY_LABELS[tag],
                            variable=var).pack(side='left', padx=(SPACING['none'], SPACING['sm']))
        self.text_row(index + 1, 'context_length', '上下文长度（可选）')
        self.text_row(index + 1, 'note', '备注（可选）', column=2)
        self.text_row(index + 2, 'rpm', '每分钟请求上限（可选）')
        self.text_row(index + 2, 'group', '模型组（可选）', column=2)
        self.text_row(index + 3, 'weight', '权重（可选）')
        self.hint = tk.StringVar(value='选一条改，或者「新建一条」；「保存这条」立刻写进模型池。')
        self.api_rows = {2, 3, 4, index + 2, index + 3}
        self.api_controls = [widget for widget in self.form.winfo_children()
                        if int(widget.grid_info().get('row', -1)) in self.api_rows]
        self.program_label = ttk.Label(self.form, text='应用安装路径')
        self.program_label.grid(row=2, column=0, sticky='w')
        self.program_row = ttk.Frame(self.form)
        self.program_row.grid(row=2, column=1, columnspan=3, sticky='ew')
        self.program_row.columnconfigure(0, weight=1)
        self.program_entry = CompactLineInput(self.program_row)
        self.program_entry.grid(row=0, column=0, sticky='ew')

    def _build_program_row(self, body, footer):
        """应用安装路径行、自动搜寻与浏览按钮、连接字段显隐、身份变化监听（从 build 原样切出，R1812）。"""
        self.entries['program'] = self.program_entry
        from orchestrator.desktop_automation_service import BackgroundTaskLifecycle
        from queue import Queue, Empty
        self.Queue = Queue; self.Empty = Empty
        from threading import Thread
        self.Thread = Thread
        self.search = BackgroundTaskLifecycle()
        self.search_poll = {'after': None}
        self.search_busy = BusyState(self.hint)

        self.search_button = SecondaryButton(self.program_row, text='自动搜寻', command=lambda: self.detect_program(quiet=False))
        self.search_button.grid(row=0, column=1, padx=(SPACING['xs'], SPACING['none']))
        SecondaryButton(self.program_row, text='浏览…', command=self.browse_program).grid(
            row=0, column=2, padx=(SPACING['xs'], SPACING['none']))

        self.pending = {'after': None, 'loading': False}

        self.win.bind('<Destroy>', self.cancel_detection, add='+')

        self.model_text = tk.StringVar()
        self.entries['model'].configure(textvariable=self.model_text)
        self.auto_label = {'text': ''}

        self.entries['model'].bind('<KeyRelease>', self.fill_label, add='+')
        self.entries['model'].bind('<FocusOut>', self.detect_program, add='+')
        self.entries['model'].bind('<KeyRelease>', self.refresh_connection_fields, add='+')
        manager_hint = ttk.Label(body, textvariable=self.hint, style='PaleGreenHint.TLabel',
                                 wraplength=TEXT_DESC['wraplength'])
        manager_hint.grid(
            row=4, column=0, columnspan=2, sticky='w', pady=(SPACING['xs'], SPACING['xs']))
        self.state = {'id': ''}

        self.key_entry.bind('<Return>', self.save_typed_key)
        self.key_entry.bind('<FocusOut>', self.save_typed_key)

        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        self.load_rows()
        bar = ttk.Frame(footer)
        bar.pack(fill='x')
        SecondaryButton(bar, text='新建一条', command=self.new_one).pack(side='left')
        self.probe_button = SecondaryButton(bar, text='测试连接', command=self.probe_one)
        self.probe_button.pack(side='left', padx=(BUTTON_GAP, SPACING['none']))
        self.provider.trace_add('write', self.refresh_connection_fields)
        self.mode.trace_add('write', self.changed_identity)
        self.model_text.trace_add('write', self.changed_identity)
        self._last_mode = self.mode.get()
        self.mode.trace_add('write', self._on_mode_change)
        self.refresh_connection_fields()
        SecondaryButton(bar, text='删除这条', command=self.delete_one).pack(
            side='left', padx=(BUTTON_GAP, SPACING['none']))
        # 「保存这条」并入左侧条目操作；「关闭」只关窗、不保存，贴最右。
        SecondaryButton(bar, text='保存这条', command=self.save_one).pack(
            side='left', padx=(BUTTON_GAP, SPACING['none']))
        SecondaryButton(bar, text='语音识别…', command=lambda: open_speech_settings(self.pet, self.win)).pack(
            side='left', padx=(BUTTON_GAP, SPACING['none']))
        PrimaryButton(bar, text='关闭', command=self.win.destroy).pack(
            side='right', padx=(BUTTON_GAP, SPACING['none']))
        self.win._pet_api_controls = self.api_controls
        self.win._pet_program_row = self.program_row
        self.win._pet_reload = self.load_rows
        self.win._pet_hint = self.hint
        self.win._pet_manager_hint_label = manager_hint
        self.win._pet_entries = self.entries
        self.win._pet_provider = self.provider
        self.win._pet_mode = self.mode
        self.win._pet_modality_box = self.modality_box
        self.mode_tabs.bind('<<NotebookTabChanged>>', self._on_tab_changed)

    def text_row(self, index, key, label, *, column=0, width=None, span=1):
        """一格「标签 ＋ 输入框」（column 0 左半边、2 右半边），返回下一行号；span 横跨右边，width 按字符数定宽。"""
        self.labels[key] = ttk.Label(self.form, text=label)
        self.labels[key].grid(row=index, column=column, sticky='w' if column == 0 else 'e', padx=0 if column == 0 else FORM_RIGHT_LABEL_PAD)
        entry = CompactLineInput(self.form, **({} if width is None else {'width': width}))
        entry.grid(row=index, column=column + 1, columnspan=span, sticky='ew' if width is None else 'w')
        self.entries[key] = entry
        return index + 1

    def match_wire(self, event=None):
        """第 65 期任务 8：换了 Provider，「协议」栏自动摆到它默认的那一档。

        只挂「选中了一项」，不挂失焦——用户在协议栏手改过的那一档不会被蹭掉。
        """
        if self.desktop_mode():
            return None                  # 本机程序不走 HTTP 协议，换厂商名不改协议档
        value = model_pool.wire_for_provider(
            model_pool.id_of_label(self.provider.get(), model_pool.PROVIDERS))
        self.wire.set(model_pool.WIRE_LABELS.get(value, model_pool.WIRE_LABELS[model_pool.DEFAULT_WIRE]))

    def stop_search(self):
        self.search.cancel()
        if self.search_poll['after'] is not None:
            self.win.after_cancel(self.search_poll['after'])
            self.search_poll['after'] = None
        self.search_busy.set_busy(False)
        self.search_button.configure(text='自动搜寻')

    def browse_program(self):
        self.stop_search()
        path = FileDialog(self.win).open_file(title='选择应用可执行文件', filetypes=[('程序', '*.exe')])
        if path:
            self.program_entry.delete(0, 'end')
            self.program_entry.insert(0, path)

    def detect_program(self, event=None, quiet=True):
        """只用当前表单身份搜寻，绝不借用被编辑记录的旧 ID。"""
        if not self.desktop_mode() or (quiet and self.program_entry.get().strip()):
            return None
        from orchestrator.workflow_settings import find_model_program
        model = self.entries['model'].get().strip()
        if not model:
            report_error(self.hint, '请先填写模型 ID，再自动搜寻安装路径。')
            return None
        if self.pending['after'] is not None:
            self.win.after_cancel(self.pending['after'])
            self.pending['after'] = None
        self.stop_search()
        ticket = self.search.submit(object(), label='安装路径搜寻')
        call_mode, original_path = self.mode.get(), self.program_entry.get()
        results = self.Queue()
        self.hint.set('正在搜寻「%s」：检查注册表、商店安装记录和常见安装目录…' % model)
        self.search_button.configure(text='正在搜寻…')
        self.search_busy.set_busy(True, controls=(self.search_button,))

        def worker():
            try:
                results.put((find_model_program(model, call_mode), ''))
            except Exception as exc:
                results.put(('', str(exc)))

        def poll():
            self.search_poll['after'] = None
            if not self.search.accepts(ticket):
                return
            try:
                path, error = results.get_nowait()
            except self.Empty:
                self.search_poll['after'] = self.win.after(50, poll)
                return
            self.search.finish(ticket, succeeded=bool(path), error=error)
            self.search_busy.set_busy(False)
            self.search_button.configure(text='自动搜寻')
            _apply_program_search(path, error, original_path, self.program_entry, self.hint)

        self.Thread(target=worker, daemon=True).start()
        self.search_poll['after'] = self.win.after(50, poll)

    def desktop_mode(self):
        return self.mode.get() in ('Desktop', 'CLI')

    def refresh_connection_fields(self, *_args):
        local = self.desktop_mode()
        for widget in self.api_controls:
            widget.grid_remove() if local else widget.grid()
        for widget in (self.program_label, self.program_row):
            widget.grid() if local else widget.grid_remove()
        self.program_label.configure(text='命令行程序路径' if self.mode.get() == 'CLI' else '应用安装路径')
        self.labels['model'].configure(text=MODEL_FIELD_LOCAL if local else MODEL_FIELD_API)
        self.probe_button.configure(text='检查程序' if local else '测试连接')

    def changed_identity(self, *_args):
        if self.pending['loading']:
            return
        self.stop_search()
        if self.pending['after'] is not None:
            self.win.after_cancel(self.pending['after'])
            self.pending['after'] = None
        self.program_entry.delete(0, 'end')
        self.hint.set('正在编辑 %s 配置。' % self.mode.get())
        self.refresh_connection_fields()
        if self.desktop_mode() and self.model_text.get().strip():
            self.pending['after'] = self.win.after(450, self.delayed_detect)

    def delayed_detect(self):
        self.pending['after'] = None
        self.detect_program()

    def cancel_detection(self, event):
        if event.widget is self.win:
            self.search.cancel()
            if self.search_poll['after'] is not None:
                self.win.after_cancel(self.search_poll['after'])
                self.search_poll['after'] = None
        if event.widget is self.win and self.pending['after'] is not None:
            self.win.after_cancel(self.pending['after'])
            self.pending['after'] = None

    def fill_label(self, event=None):
        """填模型 ID 时自动推断显示名；用户手改过的显示名不覆盖。"""
        current = self.entries['label'].get().strip()
        if current and current != self.auto_label['text']:
            return None
        guess = model_pool.suggest_label(self.entries['model'].get(), self.pet.agent_model_records())
        self.entries['label'].delete(0, 'end')
        self.entries['label'].insert(0, guess)
        self.auto_label['text'] = guess
        return guess

    def load_rows(self):
        # 自定义 Provider 已随模型记录写入模型池；每次刷新从同一份记录回填，无需第二份厂商配置。
        builtins = provider_choices()
        records = self.pet.agent_model_records()
        saved = {model_pool.provider_name(model_id, item) for model_id, item in records.items()}
        # 本机程序记录写的厂商名（Anthropic）与内建项（anthropic）只差大小写，按 casefold 去重，保留内建项。
        seen = {label.casefold() for label in builtins}
        extra = []
        for item in sorted((item for item in saved if item), key=str.casefold):
            if item.casefold() not in seen:
                seen.add(item.casefold())
                extra.append(item)
        self.provider_box.configure(values=sorted([*builtins, *extra], key=str.casefold))
        self._render_mode_rows(records)
        self._fit_model_list()
        return self.tree

    def flip_provider_order(self):
        """点 Provider 列头：分组顺序正反翻转（同组内仍按显示名、模型 ID 排）。"""
        self.provider_descending = not self.provider_descending
        self.load_rows()

    def show_key_state(self, value=None):
        """本机加密那份现在什么情况：只报前 4 位 ＋ ****，别把整把钥匙摆到界面上。"""
        item = value if isinstance(value, dict) else self.read_form()
        local = model_pool.local_key_of(item, self.program, self.state['id'])
        self.key_state.set(('本机已存密钥：%s（明文本机不落盘）' % model_pool.redacted(local)) if local
                      else '本机没存密钥；走 .env 的话只填上面的密钥名')
        return local

    def local_save(self):
        """保存直接输入的密钥到本机 DPAPI；回车和失焦均走此唯一入口。"""
        text = self.key_entry.get().strip()
        try:
            item = model_pool.record(self.read_form(), self.state['id'])
            model_pool.save_key_env(item, text, self.program, self.state['id'])
            item['key_env'] = model_pool.secret_name(item, self.state['id'])
        except (ValueError, OSError) as exc:
            report_error(self.hint, exc)
            return None
        self.key_entry.delete(0, 'end')
        self_id = self.state['id']
        self.state['id'] = model_pool.model_id_of(item, self_id)
        self.pet.save_pool(item, self_id)
        self.load_rows()
        self.show_key_state(item)
        self.hint.set('密钥已加密保存到当前 Windows 用户的本机存储；界面只露前 4 位。')
        return item

    def local_clear(self):
        """删掉本机加密那份密钥。"""
        if not model_pool.clear_local_key(self.read_form(), self.program, self.state['id']):
            self.hint.set('本机本来就没存这一条。')
            return False
        self.show_key_state()
        self.hint.set('已删掉本机加密的那份密钥。')
        return True

    def save_typed_key(self, event=None):
        """第 65 期任务 5：密钥框里一敲进去就自动存，回车或点到别处都算一次提交。

        用户报「密钥名和密钥输入后没有自动保存」——原来必须再点一下「保存到本机」。框里
        是空的就什么都不做，免得点来点去把提示刷成报错。
        """
        if self.desktop_mode() or not self.key_entry.get().strip():
            return None
        try:
            return self.local_save()
        except Exception:
            return None

    def fill(self, model_id, item):
        self.stop_search()
        self.pending['loading'] = True
        if self.pending['after'] is not None:
            self.win.after_cancel(self.pending['after'])
            self.pending['after'] = None
        self.state['id'] = model_id
        self.mode.set(model_pool.call_mode(item, model_id))
        self.key_entry.delete(0, 'end')          # 只写不读：界面里从不回显整把密钥
        for key, _label in FORM_FIELDS:
            self.entries[key].delete(0, 'end')
            self.entries[key].insert(0, str(item.get(key) or ''))
        # 可选字段统一「先清空、有值才回填」；note 原本无值时也写空串，等价于保持清空。
        for key in ('context_length', 'rpm', 'group', 'weight', 'note'):
            self.entries[key].delete(0, 'end')
            if item.get(key):
                self.entries[key].insert(0, str(item[key]))
        for tag, var in self.caps.items():
            var.set(tag in (item.get('capabilities') or []))
        saved_provider = str(item.get('provider') or '').strip()
        if item.get('provider_label') or (saved_provider == 'desktop' and model_pool.desktop_engine(model_id)):
            # 本机 Claude／ChatGPT 显示厂商名；保存时由 read_form 按 desktop_mode 写回 desktop。
            vendor = model_pool.provider_name(model_id, item)
            self.provider.set(model_pool.PROVIDER_LABELS.get(vendor.casefold(), vendor))
        else:
            self.provider.set(model_pool.PROVIDER_LABELS.get(
                saved_provider, saved_provider or FORM_DEFAULT_PROVIDER))
        self.wire.set(model_pool.WIRE_LABELS.get(item.get('wire_api'), model_pool.WIRE_LABELS[model_pool.DEFAULT_WIRE]))
        self.modality.set(model_pool.MODALITY_LABELS.get(item.get('modality'), model_pool.MODALITY_LABELS[model_pool.DEFAULT_MODALITY]))
        self.program_entry.delete(0, 'end')
        self.program_entry.insert(0, item.get('program') or '')
        self.pending['loading'] = False
        self.auto_label['text'] = self.entries['label'].get().strip()
        self.refresh_connection_fields()
        if saved_provider != 'desktop':self.show_key_state(item)

    def read_form(self):
        value = {key: self.entries[key].get().strip() for key, _label in FORM_FIELDS}
        # 本机程序条目的存储协议仍是 desktop（model_pool.status 按它判定可用性）；界面只显示厂商名。
        value['provider'] = 'desktop' if self.desktop_mode() else model_pool.id_of_label(self.provider.get(), model_pool.PROVIDERS)
        value['provider_label'] = self.provider.get().strip() if self.desktop_mode() else ''
        value['call_mode'] = self.mode.get()
        value['wire_api'] = model_pool.id_of_label(self.wire.get(), model_pool.WIRE_APIS)
        value['capabilities'] = [tag for tag, var in self.caps.items() if var.get()]
        value['context_length'] = self.entries['context_length'].get().strip()
        value['rpm'] = self.entries['rpm'].get().strip()
        value['group'] = self.entries['group'].get().strip()
        value['weight'] = self.entries['weight'].get().strip()
        value['note'] = self.entries['note'].get().strip()
        value['program'] = self.program_entry.get().strip()
        value['modality'] = model_pool.id_of_label(self.modality.get(), model_pool.MODALITIES)
        return value

    def on_select(self, event=None):
        picked = self.tree.selection()
        if not picked:
            return None
        item = self.pet.agent_model_records().get(picked[0]) or {}
        self.fill(picked[0], item)
        self.hint.set('正在改「%s」；改完点「保存这条」。' % (item.get('label') or picked[0]))
        return item

    def new_one(self):
        self.pending['loading'] = True
        self.state['id'] = ''
        for key, _label in FORM_FIELDS:
            self.entries[key].delete(0, 'end')
        for key in ('context_length', 'rpm', 'group', 'weight', 'note', 'program'):
            self.entries[key].delete(0, 'end')
        for var in self.caps.values():
            var.set(False)
        self.key_entry.delete(0, 'end')
        self.show_key_state()
        self.provider.set(FORM_DEFAULT_PROVIDER)
        self.wire.set(model_pool.WIRE_LABELS[model_pool.DEFAULT_WIRE])
        self.modality.set(model_pool.MODALITY_LABELS[model_pool.DEFAULT_MODALITY])
        self.pending['loading'] = False
        self.auto_label['text'] = ''
        self.changed_identity()
        self.hint.set('新建 %s 模型：填写模型 ID；本地调用会自动搜寻对应程序。' % self.mode.get())
        return self.state

    def save_one(self):
        try:
            if self.desktop_mode() and self.program_entry.get().strip():
                from pathlib import Path
                path = Path(self.program_entry.get().strip()).expanduser()
                if not path.is_absolute() or path.suffix.lower() != '.exe' or not path.is_file():
                    raise ValueError('请选择存在的应用 .exe 安装路径')
                from orchestrator.workflow_settings import gui_claude_program, GUI_CLAUDE_CLI_HINT
                if self.mode.get() == 'CLI' and gui_claude_program(str(path)):
                    raise ValueError(GUI_CLAUDE_CLI_HINT)
                _adapted, switched = _derive_client_profile(
                    str(path), self.entries['label'].get().strip(), self.mode, self.entries, probe=False)
                if switched:
                    self.hint.set('PE 头显示这是%s程序，已切换调用方式；请确认后保存。' %
                             ('命令行' if switched == 'CLI' else '桌面'))
            if not self.desktop_mode() and self.key_entry.get().strip():     # 第 65 期任务 5：密钥框里还有字，连它一起存
                self.local_save()
            self.pet.save_pool(self.read_form(), self.state['id'])
        except (ValueError, OSError) as exc:
            report_error(self.hint, exc)
            return None
        self.load_rows()
        self.hint.set('已保存「%s」；「切换模型」里立刻点得到。' % (self.read_form().get('label') or ''))
        return self.read_form()

    def delete_one(self):
        # 不能依赖上一次 <<TreeviewSelect>> 留下的缓存：刷新列表／点过「新建一条」后，
        # 那个缓存可能已经不是用户眼前选中的行。删除目标只认此刻高亮的这一条。
        selected = self.tree.selection()
        model_id = selected[0] if selected else ''
        if not model_id:
            report_error(self.hint, '先选一条。')
            return None
        item = self.pet.agent_model_records().get(model_id) or {}
        name = item.get('label') or model_id
        presets = '、'.join('%s「%s」' % pair for pair in self.pet.pool_model_presets(model_id))
        notice = '\n\n这些 SKILL 预设用的是它，删除后模型改为「自动」：' + presets if presets else ''
        stages = '、'.join(self.pet.pool_model_stages(model_id))
        notice += ('\n\n当前项目这些阶段选的是它，删除后改为「自动」：' + stages) if stages else ''
        if not self.pet.confirm_start('删除模型', '把「%s」从模型池里删掉？（.env 里的密钥不动）' % name + notice):
            return None
        self.pet.delete_pool_model(model_id)
        # 保存后必须回读确认；否则表格刷新看似消失、重开又出现时用户会误以为已经删除。
        if model_id in self.pet.agent_model_records():
            report_error(self.hint, '未能删除「%s」，请重试。' % name)
            return None
        self.state['id'] = ''
        self.load_rows()
        # 表单清成「新建」：还停在被删那条的话，紧接着点「保存这条」会把它原样存回去。
        self.new_one()
        self.hint.set('已删除「%s」。' % name)
        return model_id

    def probe_one(self):
        value = self.read_form()
        if value['provider'] == 'desktop':
            return _probe_local_model(self.pet, value, self.mode, self.entries, self.program_entry, self.hint)
        if not value.get('model'):
            report_error(self.hint, '先填模型 ID。')
            return None
        self.hint.set(probe_line(model_pool.record(value), self.pet))
        return value



def open_speech_settings(pet, parent=None):
    import ui.speech_settings_ui as speech_settings_ui
    return speech_settings_ui.open_speech_settings(pet, parent)
