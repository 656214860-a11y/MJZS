"""In-app first-frame production: local ComfyUI (FLUX Klein) or the Seedream 5.0 API."""
import app_logging
import queue
import threading
from pathlib import Path
from file_cache import remove_temporary_file
import tkinter as tk
from tkinter import ttk, messagebox

from agent.core import read, save, save_bytes
from contract.platform_tools import open_path
import ui_plugin_registry
from responsive_ui import FlowBar, CHECK_COLUMN_WIDTH, configure_check_column, refresh_check_heading, scroll_form
from contract.storyboard_paths import media_root
from ui_tokens import CHAR_WIDTH, TEXT_ROWS, WRAPLENGTH, COLORS, FONTS, SPACING
from domain.keyframe_batch import (MODE_LABELS, MODE_MISSING, MODE_RETRY, STATE_MISSING,
                            batch_plan, frame_prompt, frame_state, plan_summary)
from contract.production_model_contract import (LOCAL_KEYFRAME_MODEL,
                                       SEEDREAM_KEYFRAME_MODEL,
                                       KEYFRAME_MODELS)
from ui_widgets import (SelectBox, BaseDialog, Card, DataTable, DescriptionBlock, LineInput, PrimaryButton,
                        ProgressLabel, SecondaryButton, TextArea, ask_confirmation, notify)

CONFIG_FILE = Path(__file__).with_name('batch_frames_tool') / 'config.json'
# Compatibility exports for callers and existing project extensions.
LOCAL_MODEL = LOCAL_KEYFRAME_MODEL
SEEDREAM = SEEDREAM_KEYFRAME_MODEL
MODELS = KEYFRAME_MODELS
ASPECTS = ('9:16', '16:9', '1:1')
FORMATS = ('横屏 768×432', '竖屏 432×768')
STAGE = 'assets'
DEFAULTS = {'url': 'http://127.0.0.1:8188', 'model': '', 'text_encoder': '', 'vae': '', 'width': 768, 'height': 432}


def engine():
    """Reuse the standalone batch engine so graph, records and retries stay in one place."""
    from batch_frames_tool import batch_frames
    return batch_frames


def saved_settings():
    data = read(CONFIG_FILE) if CONFIG_FILE.is_file() else {}
    return dict(data) if isinstance(data, dict) else {}


def missing_settings(values):
    """返回本地 ComfyUI 自动首帧所必需的未配置字段。"""
    return [key for key in ('url', 'model', 'text_encoder', 'vae') if not str(values.get(key, '')).strip()]


def initial_settings():
    settings = dict(DEFAULTS)
    settings.update({key: value for key, value in saved_settings().items() if key in settings})
    return settings


def write_settings(values):
    """Persist only the shared interface fields; other keys stay untouched for the standalone tool."""
    data = saved_settings()
    data.update({key: value for key, value in values.items() if key not in ('shot_ids', 'model_name')})
    save(CONFIG_FILE, data)
    return data


def current_model(project):
    """「首帧制作」窗口这会儿用的首帧模型（第 46 期第 7 条）。

    用户要的是「把『生成模型与接口』下拉框里的模型搬到统一模型下拉框」，所以这份清单不再各存
    一份：挑中的那一档就写在项目的 skill_config.json（阶段 id＝keyframe）里，页面上的勾选框、
    这里、以及共享输入框的模型下拉框读到的都是同一格；「自动」与认不出来的值一律按本地 FLUX 显示。

    升级上来的老项目里 ui_settings.json 存过的那一档仍然兜底：模型下拉框还没挑过生产模型时按它
    显示，看到的还是原来那个模型（换过 Agent 引擎的人不会突然回到本地）；挑过就以统一配置为准。
    """
    from orchestrator.keyframe_model_service import current_model as resolve
    return resolve(project)


def format_of(width, height):
    return FORMATS[1] if int(width) < int(height) else FORMATS[0]


def pending_shots(shots, base):
    """Shots without a usable first frame; existing and deleted shots are never produced here."""
    base = Path(base).resolve()
    result = []
    for shot in shots if isinstance(shots, list) else []:
        if not isinstance(shot, dict) or not shot.get('id'):
            continue
        if frame_state(base, shot) == STATE_MISSING:
            result.append(shot)
    return result


def reference_count(shot):
    try:
        from domain.asset_context import references
        return len({value for _, value in references(shot)})
    except Exception:
        return 0


def check_shot(source, shot):
    """Return (prompt, images) for one shot, raising the same errors the engines report."""
    from batch_frames_tool.batch_frames import load_assets, shot_inputs
    return shot_inputs(shot, media_root(source), load_assets(source))


def seedream_cost_preview(project, source, shots, options):
    """报价只覆盖尚需发送的镜头；不释放未知请求，不把恢复算作新增。"""
    from seedream_api import UNSETTLED, load_profile
    from pet_llm import RequestLedger
    source = Path(source).resolve(); base = media_root(source).resolve()
    current = {shot['id']: shot for shot in read(source).get('shots', [])}
    count = 0
    for shot in shots:
        sid = shot['id']; item = current.get(sid)
        if item is None:continue
        path = source.parent / '首帧任务' / ('seedream_' + sid + '.json')
        record = read(path) if path.is_file() else {}
        if record.get('state') in UNSETTLED:continue
        if record.get('state') == 'completed' and frame_state(base, item) == 'done':continue
        count += 1
    if not count:return '本批无新增 Seedream 请求；仅接续已有结果或提示待核实记录。'
    profile = load_profile(options.get('seedream_profile', ''))
    return f'本批至多新增 {count} 张；已完成及待核实镜头不重复提交。\n' + RequestLedger(project).preview_text(
        profile['model'], 'images', {'images': count})


def run_seedream(source, shots, options, log, stop=None, *, project=None):
    """Generate first frames through the user's Volcengine Seedream API, one shot at a time."""
    from seedream_api import UNSETTLED, load_profile, request_image
    from pet_llm import RequestLedger, BudgetRejected
    from uuid import uuid4
    from infra.native_asset_codec import seedream_payload as _seedream_payload, to_png as _to_png, seedream_provenance as _seedream_provenance
    from importlib import import_module
    keyframe_import = import_module('keyframe_import')
    register, fingerprint = keyframe_import.register, keyframe_import.fingerprint
    source = Path(source).resolve(); base = media_root(source).resolve()
    profile = load_profile(options.get('seedream_profile', ''))
    log(seedream_cost_preview(project, source, shots, options))
    from contract.asset_contract import resolve_aspect_ratio
    aspect = resolve_aspect_ratio(options.get('workflow_lock'), options.get('aspect_ratio'), '9:16')
    folder = source.parent / '首帧任务'; folder.mkdir(parents=True, exist_ok=True)
    done = []; failed = []; blocked = []
    for index, shot in enumerate(shots, 1):
        sid = shot['id']
        if stop is not None and stop.is_set():
            log('已停止 Seedream 首帧生成；已完成的镜头保留。'); break
        episode = read(source)
        current = next((item for item in episode.get('shots', []) if item.get('id') == sid), None)
        record_file = folder / ('seedream_' + sid + '.json')
        record = read(record_file) if record_file.is_file() else {}
        if current is None:
            log(sid + '：镜头已删除，跳过'); continue
        if record.get('state') == 'completed' and current.get('frame') and not current.get('frame_deleted'):
            path = (base / current['frame']).resolve()
            if path.is_relative_to(base) and path.is_file():
                log(sid + '：已有首帧，跳过'); continue
        if record.get('state') in UNSETTLED:
            # 上次请求没拿到响应：可能已经扣费，绝不自动重复提交。首帧其实已登记就补齐记录，
            # 否则跳过本镜并提示先核实，不再像以前那样直接中断整批生成。
            path = (base / current['frame']).resolve() if current.get('frame') else None
            if path and not current.get('frame_deleted') and path.is_relative_to(base) and path.is_file():
                save(record_file, {'state': 'completed', 'model': profile['model'], 'shot_id': sid, 'file': str(path), 'note': '按已登记首帧补齐记录'})
                log(sid + '：首帧已登记，补齐记录，未重复提交'); continue
            blocked.append(sid + '（记录 ' + record_file.name + '）')
            log(sid + '：上次请求结果不确定，未重复提交；请先在火山控制台核实，记录：' + str(record_file)); continue
        log(f'{index}/{len(shots)} · {sid}：正在调用 Seedream 5.0 API 生成…')
        try:
            prompt, images = check_shot(source, current)
        except ValueError as exc:
            failed.append(sid + '：' + str(exc)); log(sid + '：' + str(exc)); continue
        if len(images) > 10:
            failed.append(sid + '：参考图超过 10 张'); log(sid + '：参考图超过 10 张，Seedream 每项最多 10 张'); continue
        payload = _seedream_payload(profile['model'], prompt, aspect, images)
        trace = {'model': profile['model'], 'shot_id': sid, 'provenance': _seedream_provenance(payload)}
        from domain.keyframe_evidence import source_evidence
        frozen_source = source_evidence(source, episode, current)
        request_id = 'image:' + uuid4().hex
        save(record_file, {'request_id': request_id, 'state': 'sending', **trace})
        try:
            with RequestLedger(project).metered_units(request_id, profile['model'], 'keyframe', 'images', 1):
                raw = request_image(profile, payload)
        except BudgetRejected as exc:
            save(record_file, {'request_id': request_id, 'state': 'failed', **trace, 'not_submitted': True, 'error': str(exc)})
            failed.append(sid + '：' + str(exc)); log(sid + '：未发送，' + str(exc)); continue
        except Exception as exc:
            save(record_file, {'request_id': request_id, 'state': 'uncertain', **trace, 'error': str(exc)})
            failed.append(sid + '：' + str(exc)); log(sid + '：' + str(exc)); continue
        temp = folder / (sid + '_seedream.png')
        try:
            save_bytes(temp, _to_png(raw))
            dest = register(source, {'shot_id': sid, 'shot_signature': fingerprint(current), 'output': sid + '.png',
                                    'source_evidence': frozen_source, 'aspect_ratio': aspect}, temp)
        except Exception as exc:
            # 已拿到响应（可能已扣费）却未能登记：保留图片并标记待核实，绝不按 failed 自动重投，避免重复扣费。
            pending = folder / (sid + '_待确认.png')
            try:
                if temp.is_file():
                    save_bytes(pending, temp.read_bytes())
            except OSError:
                pass
            kept = pending.is_file()
            save(record_file, {'request_id': request_id, 'state': 'uncertain', **trace,
                               'error': str(exc), 'file': str(pending) if kept else ''})
            blocked.append(sid + '（结果待核实，未重复提交' + ('，图片 ' + pending.name if kept else '') + '，记录 ' + record_file.name + '）')
            log(sid + '：' + str(exc) + ('；图片保留在 ' + pending.name + '，请核实后导入，未重复提交' if kept else '；请核实，未重复提交')); continue
        finally:
            remove_temporary_file(temp)
        save(record_file, {'request_id': request_id, 'state': 'completed', **trace, 'file': str(dest)})
        done.append(sid); log(sid + '：已保存并关联 ' + dest.name)
    message = f'Seedream 已生成并导入 {len(done)}/{len(shots)} 镜。'
    if failed:
        message += ' 未完成：' + '；'.join(failed)
    if blocked:
        message += ' 未完成（结果待核实，未重复提交）：' + '；'.join(blocked)
    return message


def auto_batch(source, log, stop=None):
    """无人值守首帧批次（本地 ComfyUI，免费后端）：沿用「首帧制作」窗口里保存的连接与模型设置。

    只处理缺首帧的镜头；缺参考图、已有首帧的镜头由批次逐镜跳过并写明原因；任务记录可断点续跑，
    中断或停止后下次继续查询已提交任务，不会重复提交。返回结果摘要文本。
    """
    source = Path(source).resolve()
    values = {key: value for key, value in saved_settings().items() if key not in ('shot_ids', 'shot_id')}
    missing = missing_settings(values)
    if missing:
        raise ValueError('请先在「首帧制作」窗口保存本地 ComfyUI 设置后再自动补首帧：缺少 ' + '、'.join(missing))
    stop = stop if stop is not None else threading.Event()
    # Keep the UI-facing facade here: it is also the single integration seam
    # for native startup/probing and can be safely replaced by tests.
    from importlib import import_module
    native_apps = import_module('native_apps')
    try:
        native_apps.wait_comfy(values['url'], log, timeout=5, cancelled=stop.is_set)
    except ValueError:
        log('本地 ComfyUI 未运行，正在启动…')
        native_apps.open_comfy()          # 未配置程序时给出明确错误，不静默失败
        native_apps.wait_comfy(values['url'], log, timeout=120, cancelled=stop.is_set)
    plan = batch_plan(source, mode=MODE_MISSING, model=values.get('model', ''))
    for item in plan['skipped']:
        log('跳过 ' + item['shot_id'] + '：' + item['reason'])
    before = [item['shot_id'] for item in plan['targets']]
    engine().run(source, values, log, stop)
    still = [shot['id'] for shot in pending_shots(read(source).get('shots'), media_root(source)) if shot['id'] in before]
    summary = f'无人值守首帧批次结束：处理 {len(before)} 镜，已生成 {len(before) - len(still)} 镜'
    return summary + (f'，仍未完成 {len(still)} 镜（明细见 首帧任务 记录）' if still else '')


def show(app, source, initial=None):
    return _KeyframeComfyWindow(app, source, initial).build()


class _KeyframeComfyRows:
    """镜头列表：列宽、勾选与选择项（从窗口类拆出，控制类长度）。"""

    def fit_columns(self, width=None):
        from tkinter import font as tkfont
        style = ttk.Style(self.win)
        body = tkfont.Font(root=self.win, font=style.lookup('Treeview', 'font') or 'TkDefaultFont')
        heading = tkfont.Font(root=self.win, font=style.lookup('Treeview.Heading', 'font') or 'TkHeadingFont')
        items = self.table.get_children()
        def measure(label, key, low, high):
            widest = max([heading.measure(label)] + [body.measure(str(self.table.set(item, key))) for item in items])
            return min(high, max(low, widest + 20))
        shot_width = measure('镜头号', 'shot', 110, 210)
        title_width = measure('内容', 'title', 100, 240)
        ref_width = measure('参考图', 'references', 72, 120)
        available = max(1, (width or self.table.winfo_width()) - 4)
        self.table.column('shot', width=shot_width)
        self.table.column('title', width=title_width)
        self.table.column('references', width=ref_width)
        self.table.column('prompt', width=max(180, available - CHECK_COLUMN_WIDTH - shot_width - title_width - ref_width))

    def pending(self):
        return [shot for shot in self.rows.values() if shot['id'] not in self.excluded]

    def reload_rows(self):
        self.episode = read(self.source)
        self.rows = {shot['id']: shot for shot in pending_shots(self.episode.get('shots'), self.base)}

    def refresh(self, keep=True):
        position = self.table.yview()[0] if keep else 0
        selected = self.table.selection()
        focused = self.table.focus()
        self.table.delete(*self.table.get_children())
        for shot in self.rows.values():
            self.table.insert('', 'end', iid=shot['id'], text='',
                         image=self.app.win._tick_images[0 if shot['id'] in self.excluded else 1],
                         values=(shot['id'], shot.get('title', ''), str(reference_count(shot)) + ' 个',
                                 frame_prompt(shot).replace('\n', ' ') or '待补齐首帧提示词'))
        ids = list(self.rows)
        refresh_check_heading(self.table, self.app.win._tick_images, lambda sid: sid not in self.excluded)
        self.table.selection_set([sid for sid in selected if self.table.exists(sid)])
        if self.table.exists(focused):
            self.table.focus(focused)
        self.table.configure(height=max(2, min(6, len(ids))))
        self.fit_columns()
        self.table.yview_moveto(position)
        incomplete = [sid for sid, shot in self.rows.items() if not frame_prompt(shot).strip() or not reference_count(shot)]
        note = f'已勾选 {len(self.pending())} / {len(ids)} 镜'
        if incomplete:
            note += '；' + str(len(incomplete)) + ' 镜需补齐参考图或首帧提示词：' + '、'.join(incomplete[:8]) + ('…' if len(incomplete) > 8 else '')
        self.status.set(note)
        try:
            self.plan_note.set(plan_summary(self.current_plan()))
        except Exception as exc:
            self.plan_note.set('目标集预览不可用：%s' % exc)

    def toggle(self, sids):
        for sid in sids:
            if sid in self.excluded:
                self.excluded.remove(sid)
            else:
                self.excluded.add(sid)
        self.refresh()

    def click_check(self, event):
        sid = self.table.identify_row(event.y)
        if sid and self.table.identify_region(event.x, event.y) in ('tree', 'cell'):
            self.table.selection_set(sid)
            self.table.focus(sid)
            self.toggle([sid])
            return 'break'

    def space_check(self, event):
        self.toggle(self.table.selection())
        return 'break'

    def select_checks(self, value):
        ids = list(self.rows)
        if value:
            self.excluded.difference_update(ids)
        else:
            self.excluded.update(ids)
        self.refresh()

    def toggle_all(self):
        ids = list(self.rows)
        if not ids:
            return
        # 表头勾选框要「全选 ↔ 全部取消」：此前传的是当前状态，点表头只会全部取消，永远勾不上。
        self.select_checks(not all(sid not in self.excluded for sid in ids))

    def build_choices(self):
        """把「阶段配置 → 模型」里挑的那一档翻成 (种类, 引擎)：本地 ComfyUI／Seedream／首帧 Agent。

        第 46 期第 7 条：选项清单仍在这里算（它要读工作流设置里每个引擎当前的模型名），但不再喂给
        本窗口的下拉框——显示的模型就是阶段配置里那一格；认不出来（比如那一格挑的是给 SKILL 编排
        用的模型池条目）时按本地 ComfyUI 走。
        """
        from importlib import import_module
        settings = import_module('workflow_settings')
        cfg = settings.load(self.project, STAGE)
        items = {LOCAL_MODEL: ('local', None), SEEDREAM: ('cloud', None)}
        for engine_name, display in settings.ENGINES.items():
            name = cfg['profiles'][engine_name].get('model', '').strip() or display
            while name in items:
                name += ' · ' + display
            items[name] = ('agent', engine_name)
        self.choices.clear(); self.choices.update(items)
        chosen = current_model(self.project)
        if chosen not in self.choices:
            chosen = LOCAL_MODEL
        self.model.set(chosen)
        try:
            self.agent_stamp[0] = settings.settings_path(self.project).stat().st_mtime_ns
        except OSError:
            self.agent_stamp[0] = 0
        return cfg


class _KeyframeComfyWindow(_KeyframeComfyRows):
    """首帧制作窗口：镜头勾选表、模型与接口设置、逐镜生成与轮询导入。"""
    def __init__(self, app, source, initial=None):
        self.app = app
        self.source = source
        self.initial = initial

    def build(self):
        self.source = Path(self.source).resolve()
        self.batch = engine()
        self.episode = read(self.source)
        self.base = media_root(self.source).resolve()
        self.project = Path(self.app.root).resolve()
        settings = initial_settings()
        self.prefs_file = self.project / 'ui_settings.json'
        prefs = read(self.prefs_file) if self.prefs_file.is_file() else {}
        saved = prefs.get('frame_production', {}) if isinstance(prefs.get('frame_production', {}), dict) else {}
        try:
            scope = '生成范围：' + str(self.episode.get('episode_id') or self.source.stem) + '（' + self.source.relative_to(self.project).as_posix() + '）'
        except ValueError:
            scope = '生成范围：' + str(self.episode.get('episode_id') or self.source.stem)
        self.win = BaseDialog(self.app.win, '首帧制作 · ' + str(self.episode.get('episode_id') or self.source.stem),
                         geometry='900x760', modal=False, chrome=False)
        self.win.withdraw()
        self.win.minsize(760, 560)
        self.win.transient(self.app.win)
        footer = ttk.Frame(self.win)
        footer.pack(side='bottom', fill='x')
        viewport = ttk.Frame(self.win)
        viewport.pack(side='top', fill='both', expand=True)
        view = scroll_form(viewport, bg=COLORS['background_primary'])
        form = view.form                      # 滚动表单区与批量资产共用一份实现

        ttk.Label(form, text='勾选镜头 → 开始逐镜生成 → 按镜头编号自动导入', style='Tokens.Title.TLabel').pack(anchor='w', padx=SPACING['md'], pady=SPACING['md'])
        DescriptionBlock(form, text=scope + '；只处理尚未有首帧的镜头。').pack(anchor='w', padx=SPACING['md'])
        DescriptionBlock(form, text='提示词沿用镜头 JSON 的 frame_prompt，参考图沿用资产图片；缺少参考图或提示词的镜头会被列出并跳过。').pack(anchor='w', padx=SPACING['md'], pady=SPACING['xs'])
        table_shell = DataTable(form, columns=[
            ('shot', '镜头号', 130), ('title', '内容', 150),
            ('references', '参考图', 70), ('prompt', '首帧提示词', 430),
        ], show='tree headings', height=TEXT_ROWS['md'], selectmode='extended', empty_text='暂无待制作镜头')
        self.table = table_shell.tree
        configure_check_column(self.table)
        for key, label, width in [('shot', '镜头号', 130), ('title', '内容', 150), ('references', '参考图', 70), ('prompt', '首帧提示词', 430)]:
            self.table.heading(key, text=label)
            self.table.column(key, width=width, minwidth=50, stretch=False)
        self.table.column('shot', anchor='w')

        self.table.bind('<Configure>', lambda event: self.fit_columns(event.width), add='+')
        table_shell.pack(fill='x', padx=SPACING['md'])
        self.status = tk.StringVar()
        ProgressLabel(form, textvariable=self.status).pack(anchor='w', padx=SPACING['md'], pady=SPACING['xs'])
        self.plan_note = tk.StringVar()
        DescriptionBlock(form, textvariable=self.plan_note).pack(anchor='w', padx=SPACING['md'])
        self.rows = {shot['id']: shot for shot in pending_shots(self.episode.get('shots'), self.base)}
        self.excluded = set()
        if self.initial is not None:
            self.wanted = {str(value) for value in self.initial}
            self.excluded = {sid for sid in self.rows if sid not in self.wanted}

        self.table.heading('#0', command=self.toggle_all)
        self.table.bind('<Button-1>', self.click_check)
        self.table.bind('<space>', self.space_check)
        self.model = tk.StringVar(value=current_model(self.project))
        self.mode_var = tk.StringVar(value=MODE_LABELS[MODE_MISSING])
        self.choices = {}
        # 统筹制作锁只给默认初值；用户已保存的首帧偏好仍是第二优先级。
        from contract.asset_contract import resolve_aspect_ratio
        try:
            import stage_config
            self.locked = stage_config.workflow_lock(self.project)
        except Exception:
            self.locked = {}
        preferred = saved.get('aspect_ratio') if saved.get('aspect_ratio') in ASPECTS else ''
        self.aspect = tk.StringVar(value=resolve_aspect_ratio(self.locked, preferred, '9:16'))
        self.ratio = tk.StringVar(value=format_of(settings['width'], settings['height']))
        self.url = tk.StringVar(value=settings['url'])
        self.model_name = tk.StringVar(value=settings['model'])
        self.encoder = tk.StringVar(value=settings['text_encoder'])
        self.vae = tk.StringVar(value=settings['vae'])
        self.busy = False
        self.stop = threading.Event()
        self.events = queue.Queue()
        self.closed = [False]
        self.poll_id = None
        self.agent_stamp = [0]
        self._build_model_box(form)
        self._build_local_box(form)
        self.account.configure(command=lambda: self.app.safe(self.choose_account))

        self.skill_button.configure(command=lambda: self.app.safe(self.open_agent_settings))

        self.shape.bind('<<ComboboxSelected>>', lambda event: (self.save_prefs(), self.update_model_ui()))

        # 第 46 期第 7 条：模型由阶段配置决定，所以窗口一开就把该引擎档对齐一次（原来靠选下拉框触发）。
        try:
            self.remember_engine()
        except Exception:
            app_logging.swallowed()
        bar = FlowBar(footer)
        bar.pack(fill='x', padx=SPACING['md'], pady=SPACING['sm'])
        self.start_button = PrimaryButton(bar, text='开始逐镜生成', command=lambda: self.app.safe(self.start))
        self.start_button.pack(side='left')
        self.halt = SecondaryButton(bar, text='停止后续镜头', command=self.stop_request)
        self.halt.pack(side='left', padx=SPACING['xs'])
        self.check_button = SecondaryButton(bar, text='检查参考资产', command=lambda: self.app.safe(self.preflight_check))
        self.check_button.pack(side='left', padx=SPACING['xs'])
        SecondaryButton(bar, text='预估费用', command=lambda: self.app.safe(self.preview_cost)).pack(side='left', padx=SPACING['xs'])
        SecondaryButton(bar, text='生成记录', command=self.records).pack(side='left', padx=SPACING['xs'])
        SecondaryButton(bar, text='关闭', command=lambda: self.app.safe(self.close)).pack(side='left', padx=SPACING['xs'])

        self.win.bind('<Destroy>', self.stop_poll, add='+')
        self.win.protocol('WM_DELETE_WINDOW', lambda: self.app.safe(self.close))
        self.refresh()
        self.build_choices()
        self.update_model_ui()
        view.bind_wheel()
        self.buttons()
        self.win.update_idletasks()
        self.win.geometry('+' + str(self.app.win.winfo_rootx() + 40) + '+' + str(self.app.win.winfo_rooty() + 40))
        self.win.deiconify()
        self.poll()
        return self.win

    def _build_model_box(self, form):
        """“生成模型与接口”卡片：只读模型行、画幅、批次意图与设置入口。"""
        self.model_box = Card(form)
        self.model_box.pack(fill='x', padx=SPACING['md'], pady=SPACING['xs'])
        self.model_box.columnconfigure(1, weight=1)
        ttk.Label(self.model_box, text='生成模型与接口').grid(row=0, column=0, columnspan=6, sticky='w')
        # 第 46 期第 7 条：这一格原来是一个「模型」下拉框（本地 ComfyUI／Seedream／首帧 Agent 引擎
        # 三条模型都摆在这儿，与统一模型下拉框重复）。现在只剩只读的一行——挑模型的地方只有
        # 底部共享输入框的模型下拉框，右边留一颗「模型」就地弹开它（R2942）。
        ttk.Label(self.model_box, text='模型').grid(row=1, column=0, sticky='w', padx=(SPACING['none'], SPACING['xs']))
        selector = ttk.Label(self.model_box, textvariable=self.model, anchor='w')
        selector.grid(row=1, column=1, sticky='w')
        ttk.Label(self.model_box, text='画幅').grid(row=1, column=2, padx=(SPACING['md'], SPACING['xs']))
        self.shape = SelectBox(self.model_box, textvariable=self.aspect, values=list(ASPECTS), state='disabled', width=CHAR_WIDTH['md'])
        self.shape.grid(row=1, column=3, padx=SPACING['xs'])
        ttk.Label(self.model_box, text='批次意图').grid(row=1, column=4, padx=(SPACING['md'], SPACING['xs']))
        mode_box = SelectBox(self.model_box, textvariable=self.mode_var,
                             values=[MODE_LABELS[key] for key in (MODE_MISSING, MODE_RETRY)],
                             state='readonly', width=CHAR_WIDTH['lg'])
        mode_box.grid(row=1, column=5, padx=SPACING['xs'])
        mode_box.bind('<<ComboboxSelected>>', lambda event: self.refresh())
        self.hint = tk.StringVar()
        ttk.Label(self.model_box, textvariable=self.hint, wraplength=WRAPLENGTH['2xl'], justify='left').grid(row=2, column=0, columnspan=4, sticky='w', pady=SPACING['sm'])
        self.account = SecondaryButton(self.model_box, text='火山 API 设置')
        self.account.grid(row=3, column=0, sticky='w')
        self.skill_button = SecondaryButton(self.model_box, text='Skill 调用设置')
        self.skill_button.grid(row=3, column=1, sticky='w')
        stage_button = SecondaryButton(self.model_box, text='模型',
                                  command=lambda: self.app.safe(self.open_stage_config))
        stage_button.grid(row=3, column=2, sticky='w', padx=SPACING['xs'])

    def _build_local_box(self, form):
        """ComfyUI 连接卡片与生成记录文本区。"""
        self.local_box = Card(form)
        self.local_box.columnconfigure(1, weight=1)
        ttk.Label(self.local_box, text='ComfyUI 连接与模型接口').grid(row=0, column=0, columnspan=2, sticky='w')
        ttk.Label(self.local_box, text='图片格式').grid(row=1, column=0, sticky='w', padx=SPACING['xs'], pady=SPACING['none'])
        SelectBox(self.local_box, textvariable=self.ratio, values=list(FORMATS)).grid(row=1, column=1, sticky='w', padx=SPACING['xs'])
        self.fields = {}
        for index, (key, label, variable) in enumerate(
                [('url', '本机地址', self.url), ('model', '图像模型', self.model_name), ('text_encoder', '文本编码器', self.encoder), ('vae', 'VAE', self.vae)], start=1):
            ttk.Label(self.local_box, text=label).grid(row=index + 1, column=0, sticky='w', padx=SPACING['xs'], pady=SPACING['none'])
            field = LineInput(self.local_box, textvariable=variable) if key == 'url' else SelectBox(self.local_box, textvariable=variable, state='normal')
            field.grid(row=index + 1, column=1, sticky='ew', padx=SPACING['xs'])
            self.fields[key] = field
        PrimaryButton(self.local_box, text='保存设置', command=lambda: self.app.safe(self.save_api)).grid(row=2, column=2, padx=SPACING['xs'])
        SecondaryButton(self.local_box, text='启动并检测', command=lambda: self.app.safe(self.detect)).grid(row=3, column=2, padx=SPACING['xs'])
        SecondaryButton(self.local_box, text='删除模型', command=lambda: self.app.safe(self.delete_model)).grid(row=4, column=2, padx=SPACING['xs'])
        self.log = TextArea(form, height=TEXT_ROWS['lg'], wrap='word', state='disabled', bg=COLORS['background_card'], fg=COLORS['text_primary'], font=FONTS['body'], padx=SPACING['sm'], pady=SPACING['sm'])
        self.log.pack(fill='both', expand=True, padx=SPACING['md'], pady=SPACING['xs'])

    def kind(self):
        return self.choices.get(self.model.get(), ('local', None))[0]

    def engine_of(self):
        return self.choices.get(self.model.get(), (None, None))[1]

    def log_lines(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', str(text) + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def log_clear(self):
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.configure(state='disabled')

    def save_prefs(self):
        data = read(self.prefs_file) if self.prefs_file.is_file() else {}
        if not isinstance(data, dict):
            data = {}
        data['frame_production'] = {'aspect_ratio': self.aspect.get()}
        save(self.prefs_file, data)

    def update_model_ui(self, *_):
        current = self.kind()
        if current != 'local':
            if self.local_box.winfo_manager():
                self.local_box.pack_forget()
        elif not self.local_box.winfo_manager():
            self.local_box.pack(fill='x', padx=SPACING['md'], pady=SPACING['xs'], after=self.model_box)
        self.shape.configure(state='readonly' if current == 'cloud' else 'disabled')
        if current == 'cloud':
            self.account.grid()
            try:
                from seedream_api import public_profile
                self.hint.set('使用您自己的火山方舟 API Key，费用计入火山账户；当前模型：' + public_profile()['model'])
            except ValueError:
                self.hint.set('使用您自己的火山方舟 API Key，费用计入火山账户；请先在“火山 API 设置”保存模型 ID 和 API Key。')
        else:
            self.account.grid_remove()
            if current == 'agent':
                from importlib import import_module
                cfg = import_module('workflow_settings').load(self.project, STAGE)
                agent_label = import_module('workflow_agents').label
                self.hint.set('交给首帧 Agent 逐镜生成，Skill 用“Skill 调用设置”切换；当前：'
                         + agent_label(cfg['profiles'][self.engine_of()], STAGE, self.engine_of(), '首帧制作'))
            else:
                self.hint.set('本地运行，无需登录；提示词与参考图提交本机 ComfyUI，按“图片格式”的像素尺寸生成。')
        if current == 'agent':
            self.skill_button.grid()
        else:
            self.skill_button.grid_remove()

    def choose_account(self):
        from seedream_settings import show as seedream_show
        seedream_show(self.win, on_saved=self.update_model_ui)

    def open_stage_config(self):
        """R2942：去底部共享输入框的模型下拉框挑首帧模型（唯一入口）。"""
        import stage_models
        stage_models.open_model_dropdown(self.app)

    def open_agent_settings(self):
        self.app.flow_settings(STAGE, '首帧制作')
        self.build_choices()
        self.update_model_ui()

    def remember_engine(self, *_):
        """阶段配置里挑的是某个 Agent 引擎时，把它写回这一流程当前的引擎档。

        第 46 期第 7 条：模型从下拉框搬进阶段配置之后，这里改成「打开窗口就对齐一次」——
        页面、Skill 设置窗口与制作窗口看到的是同一个引擎。
        """
        if self.kind() != 'agent':
            return
        from importlib import import_module
        engine = self.engine_of(); cfg = import_module('workflow_settings').load(self.project, STAGE)
        choose_agent = import_module('workflow_agents').choose
        if engine and engine != cfg['engine']:
            choose_agent(self.project, STAGE, (engine, cfg['profiles'][engine]['skill']))
            self.app.status.set('已切换首帧 Agent 模型：' + self.model.get())

    def options(self):
        values = {'url': self.url.get().strip().rstrip('/'), 'model': self.model_name.get().strip(), 'text_encoder': self.encoder.get().strip(),
                  'vae': self.vae.get().strip(), 'width': 432 if self.ratio.get().startswith('竖') else 768,
                  'height': 768 if self.ratio.get().startswith('竖') else 432, 'shot_ids': [shot['id'] for shot in self.pending()]}
        # 第 46 期第 7 条：上面 values['model'] 是本地 ComfyUI 的图像模型，跟「阶段配置」里
        # 那个生产模型不是一回事，所以这里不再把 model 当「模型名」传下去。
        values['aspect_ratio'] = self.aspect.get()
        values['workflow_lock'] = self.locked
        return values

    def current_mode(self):
        label = self.mode_var.get()
        for key, text in MODE_LABELS.items():
            if text == label:
                return key
        return MODE_MISSING

    def current_plan(self):
        """提交前那份统一目标集：本集、勾选镜头、跳过原因、模型与参考图。"""
        return batch_plan(self.source, shot_ids=[shot['id'] for shot in self.pending()],
                          mode=self.current_mode(), model=self.model.get())

    def log_plan(self, plan):
        """把这一批的意图、目标与逐镜跳过原因写进日志，让用户提交前就看清。"""
        if not plan:
            return
        self.log_lines(plan_summary(plan))
        for item in plan.get('skipped', ()):
            self.log_lines('跳过 ' + str(item.get('shot_id')) + '：' + str(item.get('reason')))

    def check_values(self):
        shots = self.pending()
        if not shots:
            raise ValueError('请至少勾选一个待生成首帧的镜头')
        plan = self.current_plan()
        wanted = {item['shot_id'] for item in plan['targets']}
        shots = [shot for shot in shots if shot['id'] in wanted]
        if not shots:
            details = '；'.join(item['shot_id'] + '（' + item['reason'] + '）'
                               for item in plan['skipped'][:5])
            raise ValueError('本次意图「' + MODE_LABELS[self.current_mode()] + '」没有可提交的镜头'
                             + ('：' + details if details else ''))
        current = self.kind()
        if current == 'agent':
            return {'shots': shots, 'model': self.model.get(), 'engine': self.engine_of(), 'plan': plan}
        if current == 'cloud':
            from seedream_api import load_profile
            profile = load_profile()
            return {'shots': shots, 'model': SEEDREAM, 'aspect_ratio': self.aspect.get(),
                    'workflow_lock': self.locked, 'seedream_profile': profile['profile_id'],
                    'plan': plan}
        values = self.options()
        values['shot_ids'] = [shot['id'] for shot in shots]   # 只提交本次意图要的镜头
        if not all((values['model'], values['text_encoder'], values['vae'])):
            raise ValueError('请先填写或检测图像模型、文本编码器和 VAE 名称')
        return {'shots': shots, 'model': LOCAL_MODEL, 'batch': values, 'plan': plan}

    def save_api(self):
        values = self.options()
        self.batch.Client(values['url'])
        if not all((values['model'], values['text_encoder'], values['vae'])):
            raise ValueError('请填写图像模型、文本编码器和 VAE 名称')
        write_settings(values)
        self.status.set('API 设置已保存，下次打开自动填回。')

    def delete_model(self):
        if self.busy:
            raise ValueError('请等待当前批次结束后再删除模型配置')
        name = self.model_name.get().strip()
        if not name:
            raise ValueError('请先填写或选择要删除的模型')
        if not ask_confirmation(self.win, '删除模型', '删除模型配置 ' + name + '？\n只移除助手中的填写，不删除本地模型文件和已生成首帧。', dangerous=True):
            return
        self.model_name.set('')
        write_settings(self.options())
        self.fields['model'].configure(values=[value for value in self.fields['model']['values'] if value != name])
        self.status.set('模型配置已删除并保存，本地模型文件保留。')

    def detect(self):
        if self.busy:
            raise ValueError('请等待当前批次结束后再检测模型')
        values = self.options()
        client = self.batch.Client(values['url'])
        if not self.app.launch_comfy():
            return
        def load():
            info = client.request('/object_info')
            def names(kind, field):
                spec = info.get(kind, {}).get('input', {}).get('required', {}).get(field)
                if not isinstance(spec, list) or not spec:
                    return []
                return list(spec[0]) if isinstance(spec[0], list) else list(spec[1].get('options', []))
            return {key: names(*target) for key, target in
                    (('model', ('UNETLoader', 'unet_name')), ('text_encoder', ('CLIPLoader', 'clip_name')), ('vae', ('VAELoader', 'vae_name')))}
        def done(found):
            if not self.win.winfo_exists():
                return
            variables = {'model': self.model_name, 'text_encoder': self.encoder, 'vae': self.vae}
            for key, values_list in found.items():
                self.fields[key].configure(values=values_list)
                if not variables[key].get().strip() and len(values_list) == 1:
                    variables[key].set(values_list[0])
            self.status.set('检测到 图像模型 %d 个 / 文本编码器 %d 个 / VAE %d 个，请核对后保存。' % (len(found['model']), len(found['text_encoder']), len(found['vae'])))
        self.app.async_(load, done)

    def preflight_check(self):
        """只检查本地参考资产与首帧提示词，不再检查模型。

        旧版顺带连 ComfyUI 查模型清单：那次查询走后台线程并占用 app.worker，
        ComfyUI 无响应时最长等到 30 秒超时，期间所有按钮都提示「当前操作尚未结束」，
        整个程序看起来就是卡死。参考资产检查只读本地文件，因此直接同步执行。
        """
        if self.busy:
            raise ValueError('请等待当前批次结束后再检查')
        shots = self.pending()
        if not shots:
            raise ValueError('请至少勾选一个待生成首帧的镜头')
        ready = []; skipped = []
        for shot in shots:
            try:
                check_shot(self.source, shot); ready.append(shot)
            except (ValueError, OSError) as exc:
                skipped.append(shot['id'] + '：' + str(exc))
        self.log_lines('参考资产检查完成：可生成 %d 镜，跳过 %d 镜。' % (len(ready), len(skipped)))
        for item in skipped:
            self.log_lines(item)
        self.status.set('参考资产检查完成：可生成 %d 镜，跳过 %d 镜。' % (len(ready), len(skipped)))

    def stop_request(self):
        self.stop.set()
        self.status.set('已请求停止后续镜头；当前镜头完成后不再提交。')

    def close(self):
        if self.busy:
            self.stop.set()
            notify(self.win, '已请求停止后续镜头，当前镜头跑完就停。\n任务编号已保留，下次可以继续查询。', title='正在停止', status=self.status)
            return
        self.win.destroy()

    def buttons(self):
        self.start_button.configure(state='disabled' if self.busy else 'normal')
        self.halt.configure(state='normal' if self.busy else 'disabled')
        self.check_button.configure(state='disabled' if self.busy else 'normal')

    def launch_agent(self, shots):
        """Agent 引擎不在本窗口生成：登记批次后交给桌面 Agent 窗口，完成后自动导入。"""
        from importlib import import_module
        launch = import_module('keyframe_import').launch
        if launch(self.app, self.source, shot_ids=[shot['id'] for shot in shots]) is False:
            self.status.set('已保留上次未完成的首帧任务，本次未重复提交。')
            return
        self.log_lines('已在 Agent 窗口提交 ' + str(len(shots)) + ' 镜；完成后会自动导入并刷新列表。')
        self.status.set('已在 Agent 窗口提交首帧任务。')

    def publish(self, shots):
        """把弹窗里最终的勾选回写页面：页面、下拉框与弹窗三个入口共用同一份勾选状态。"""
        hook = getattr(self.app, 'frame_checks_apply', None)
        if hook is None:
            return
        try:
            hook(self.source, [shot['id'] for shot in shots])
        except Exception:
            app_logging.swallowed()

    def start(self):
        if self.busy:
            return
        checked = self.check_values()
        self.publish(checked['shots'])
        self.save_prefs()
        if checked.get('engine'):
            self.log_clear()
            self.log_lines('首帧 Agent · ' + self.model.get() + ' · 共 ' + str(len(checked['shots'])) + ' 镜')
            self.log_plan(checked.get('plan'))
            self.launch_agent(checked['shots'])
            return
        if checked['model'] == SEEDREAM:
            self.log_clear()
            self.log_lines('Seedream 5.0 Pro · 共 ' + str(len(checked['shots'])) + ' 镜')
            self.log_plan(checked.get('plan'))
            from seedream_settings import confirm_unsettled
            confirmed = confirm_unsettled(self.win, self.source.parent / '首帧任务', [shot['id'] for shot in checked['shots']], '镜头')
            if confirmed:
                self.log_lines('已在火山控制台核实，重新生成：' + '、'.join(confirmed))
            self.log_lines(seedream_cost_preview(self.project, self.source, checked['shots'], checked))
        else:
            values = checked['batch']
            write_settings(values)
            if not self.app.launch_comfy(silent=True):     # 第 62 期任务 8：静默拉起，不弹选择框
                return
            self.log_clear()
            self.log_lines('本地 ComfyUI · ' + str(len(values['shot_ids'])) + ' 镜')
            self.log_plan(checked.get('plan'))
        self.busy = True
        self.stop.clear()
        self.buttons()
        def work():
            try:
                if checked['model'] == SEEDREAM:
                    self.events.put(run_seedream(self.source, checked['shots'], checked, self.events.put, self.stop, project=self.project))
                else:
                    self.batch.run(self.source, checked['batch'], self.events.put, self.stop)
            except Exception as exc:
                self.events.put('未完成：' + str(exc))
            finally:
                self.events.put(None)
        threading.Thread(target=work, daemon=True).start()

    def records(self):
        folder = self.source.parent / '首帧任务'
        folder.mkdir(exist_ok=True)
        open_path(folder)

    def preview_cost(self):
        checked = self.check_values()
        if checked['model'] != SEEDREAM:raise ValueError('当前金额预估支持 Seedream 直连，请按实际供应商核对其他模型费用。')
        self.log_lines(seedream_cost_preview(self.project, self.source, checked['shots'], checked))

    def poll(self):
        if self.closed[0] or not self.win.winfo_exists():
            return
        finished = False
        while True:
            try:
                value = self.events.get_nowait()
            except queue.Empty:
                break
            if value is None:
                finished = True
                continue
            self.log_lines(value)
            self.status.set(str(value))
            self.poll.last = str(value)
        try:
            from importlib import import_module
            stamp = import_module('workflow_settings').settings_path(self.project).stat().st_mtime_ns
        except OSError:
            stamp = 0
        if stamp != self.agent_stamp[0]:
            self.build_choices()
            self.update_model_ui()
        if finished:
            self.busy = False
            self.buttons()
            self.reload_rows()
            self.refresh(keep=False)
            # 第 47 期第 5 条：这一批首帧收了尾，三虎说一句（末尾那一句就是结局）。
            last = getattr(self.poll, 'last', '')
            self.poll.last = ''
            from importlib import import_module
            import_module('pet_ui').report_done(self.app, 'keyframe', last)
            try:
                if self.app.win.winfo_exists() and Path(self.app.current_frame_json()).resolve() == self.source:
                    self.app.show_stage('keyframe')
            except Exception:
                app_logging.swallowed()
        self.poll_id = self.win.after(250, self.poll)

    def stop_poll(self, event=None):
        if event is not None and event.widget is not self.win:
            return
        self.closed[0] = True
        if self.poll_id is not None:
            try:
                self.win.after_cancel(self.poll_id)
            except Exception:
                app_logging.swallowed()
            self.poll_id = None
