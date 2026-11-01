"""阶段配置按钮右侧的两级模型选择器：一级选供应商，二级选具体模型，选完立即写进项目配置。

模型的唯一写入口仍是 ``stage_config.put``；选项仍来自 ``grouped_model_choices``（模型池＋页面生产模型）。
这里只是把原先藏在阶段配置面板里的「厂商／模型」两个下拉框拆出来，面板不再重复持有它们。
"""
import tkinter as tk
from tkinter import ttk

import model_router
import stage_config
from skill_panel_support import (
    desktop_project, grouped_model_choices, pet_of, register_live,
                                 stage_for, unregister_live)
from ui_tokens import CHAR_WIDTH, SPACING
from ui_widgets import PrimaryButton, SelectBox

ADD_MODEL_LABEL = '+ 添加模型…'
AUTO_PROVIDER = '自动选择'


class StageModelPicker(ttk.Frame):
    """供应商 → 模型 两级下拉；无项目时只读展示「自动」。"""

    def __init__(self, master, desktop, stage):
        ttk.Frame.__init__(self, master)
        self.desktop = desktop
        self.stage = stage_for(stage)
        self.groups = {}
        self.provider = tk.StringVar(value=AUTO_PROVIDER)
        self.model = tk.StringVar(value='')
        self._picked = ''
        self.providers = SelectBox(self, textvariable=self.provider, width=CHAR_WIDTH['xl'], values=())
        self.providers.pack(side='left')
        self.models = SelectBox(self, textvariable=self.model, width=CHAR_WIDTH['3xl'],
                                accent_values=(ADD_MODEL_LABEL,), values=())
        self.models.pack(side='left', padx=(SPACING['xs'], SPACING['none']))
        self.providers.bind('<<ComboboxSelected>>', lambda event: self.choose_provider())
        self.models.bind('<<ComboboxSelected>>', lambda event: self.choose_model())
        register_live(self)
        self.bind('<Destroy>', lambda event: unregister_live(self) if event.widget is self else None, add='+')
        self.refresh_models()

    # ── 数据 ────────────────────────────────────────────────────────────────
    def project(self):
        return desktop_project(self.desktop)

    def saved_model(self):
        project = self.project()
        if not project:
            return model_router.AUTO
        try:
            return str(stage_config.get(project, self.stage).get('model') or model_router.AUTO).strip()
        except Exception:
            return model_router.AUTO

    def model_id(self):
        """二级下拉当前文案 → 模型 id。"""
        for _provider, options in self.groups.items():
            for model_id, label in options:
                if label == self.model.get() and _provider == self.provider.get():
                    return model_id
        return model_router.AUTO

    def refresh_models(self):
        """模型池或项目变了：重读选项，并把已保存的那一档摆回去。"""
        self.groups = grouped_model_choices(self.desktop, self.stage)
        self.providers.set_values(list(self.groups))
        self.set_model(self.saved_model())
        return self.groups

    def set_model(self, model):
        """按模型 id 同步两级下拉；认不出的值显示为「自动」，不改写已保存的配置。"""
        wanted = str(model or model_router.AUTO)
        for provider, options in self.groups.items():
            for model_id, label in options:
                if model_id == wanted:
                    self._show(provider, options, label)
                    return wanted
        if wanted != model_router.AUTO:
            # 手写的本地模型 id 还没登记到模型池：照原样显示，不丢配置。
            options = self.groups.setdefault('自定义', [])
            if (wanted, wanted) not in options:
                options.append((wanted, wanted))
            self.providers.set_values(list(self.groups))
            self._show('自定义', options, wanted)
            return wanted
        provider = AUTO_PROVIDER if AUTO_PROVIDER in self.groups else next(iter(self.groups), AUTO_PROVIDER)
        options = self.groups.get(provider, [])
        self._show(provider, options, options[0][1] if options else '')
        return model_router.AUTO

    def _show(self, provider, options, label):
        self.provider.set(provider)
        self.models.set_values([item for _id, item in options] + [ADD_MODEL_LABEL])
        self.model.set(label)
        self._picked = label

    # ── 交互 ────────────────────────────────────────────────────────────────
    def choose_provider(self):
        """换供应商：二级默认落在该供应商第一个模型，并立即保存。"""
        options = self.groups.get(self.provider.get(), [])
        if not options:
            return None
        self._show(self.provider.get(), options, options[0][1])
        return self.save()

    def choose_model(self):
        if self.model.get() == ADD_MODEL_LABEL:
            self.model.set(self._picked)
            return self.open_model_manager()
        self._picked = self.model.get()
        return self.save()

    def save(self):
        """只写模型这一项，SKILL 勾选保持原样。"""
        project = self.project()
        if not project:
            return None
        entry = stage_config.put(project, self.stage, model=self.model_id())
        if self.stage == 'script':
            refresh = getattr(self.desktop, 'refresh_script_chat_for_selected_model', None)
            if callable(refresh):
                refresh()
        return entry

    def open_model_manager(self):
        """「+ 添加模型…」：模型池只有模型管理这一扇门。"""
        pet = pet_of(self.desktop)
        if pet is None:
            return ''
        import pet_models_ui
        try:
            return pet_models_ui.open_manager(pet)
        except Exception:
            return ''


class StageConfigButton(PrimaryButton):
    """「阶段配置」按钮；挂了 ``picker_target`` 后，布局时在它右边带上两级模型选择器。"""

    picker_target = None
    picker = None

    def attach_picker(self, desktop, stage):
        self.picker_target = (desktop, stage)
        if self.winfo_manager() == 'pack':      # 按钮已经摆好：就地把选择器补在右边
            self.pack(**self.pack_info())
        return self

    def pack(self, **options):
        result = PrimaryButton.pack(self, **{key: value for key, value in options.items() if key != 'in'})
        if self.picker_target is not None and self.picker is None:
            desktop, stage = self.picker_target
            self.picker = StageModelPicker(self.master, desktop, stage)
        if self.picker is not None:
            self.picker.pack(side=options.get('side', 'left'), after=self,
                             padx=(SPACING['xs'], SPACING['none']), pady=options.get('pady', 0))
        return result

    def pack_forget(self):
        if self.picker is not None:
            self.picker.pack_forget()
        return PrimaryButton.pack_forget(self)

    def destroy(self):
        picker, self.picker = self.picker, None
        if picker is not None:
            try:
                picker.destroy()
            except tk.TclError:
                pass
        PrimaryButton.destroy(self)


def stage_button_for(parent, command, text='阶段配置', desktop=None, stage=None):
    """各阶段统一使用与发送键相同的蓝色填充「阶段配置」按钮。

    给了 ``desktop`` 与 ``stage`` 时，按钮布局后右侧自带两级模型选择器（供应商 → 模型）。
    """
    button = StageConfigButton(parent, text=text, command=command, width=CHAR_WIDTH['3xl'])
    if desktop is not None and stage:
        button.attach_picker(desktop, stage)
    # 这是语义标记而非视觉样式；回归可据此找到入口，不再耦合已废弃的暖色样式名。
    button._stage_config_entry = True
    return button


def attach_stage_pickers(app, desktop):
    """视频工作台里两颗「阶段配置」（提示词＝final、视频＝video）在建好后补上右侧选择器。"""
    for name, stage in (('prompt_stage_button', 'final'), ('stage_button', 'video')):
        button = getattr(app, name, None)
        if isinstance(button, StageConfigButton):
            button.attach_picker(desktop, stage)
