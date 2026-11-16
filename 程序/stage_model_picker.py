"""共享输入框右下角的模型选择器（R2942 定版）：Menubutton 弹出菜单，项内只列模型名，
推理档位内嵌子菜单，不再弹模态选择窗。

模型的唯一写入口仍是 ``stage_config.put``；选项仍来自 ``grouped_model_choices``（模型池＋页面生产模型）。
REQ-S01-82：菜单项只显示模型名称（不带供应商前缀），带 reasoning 能力标签的模型
右侧标「推理·<当前档位>」；「推理等级」子菜单的档位写进阶段配置的 ``reasoning`` 字段。
"""
import tkinter as tk
from tkinter import ttk

import model_pool
import model_router
import stage_config
from skill_panel_support import (
    desktop_project, grouped_model_choices, pet_of, pool_records, register_live,
                                 stage_for, unregister_live)
from ui_widgets import ContextMenu

ADD_MODEL_LABEL = '+ 添加模型…'
LEVEL_MENU = '推理等级：%s'


class StageModelPicker(ttk.Frame):
    """模型选择器：Menubutton＋弹出菜单；无项目时只读展示「自动」。"""

    def __init__(self, master, desktop, stage):
        ttk.Frame.__init__(self, master)
        self.desktop = desktop
        self.stage = stage_for(stage)
        self.groups = {}
        self.model = tk.StringVar(value='')
        self._picked = ''
        self._by_display = {}          # 模型显示名 → 稳定模型 id（同名取先出现的一条）
        self._items = []               # [(model_id, 显示名)]
        self._capable = set()          # 带 reasoning 能力标签的模型 id
        self._choice = tk.StringVar(value='')
        self._level = tk.StringVar(value='auto')
        self.models = ttk.Menubutton(self, textvariable=self.model)
        self.models.pack(side='left')
        self._menu_ctx = ContextMenu(self.models)
        self._menu = self._menu_ctx.menu
        self.models.configure(menu=self._menu)
        self._level_ctx = self._menu_ctx.submenu()
        self._level_menu = self._level_ctx.menu
        for value in stage_config.REASONING_LEVELS:
            self._level_ctx.radio(
                label=stage_config.REASONING_LABELS[value], variable=self._level,
                value=value, command=lambda level=value: self.choose_reasoning(level))
        register_live(self)
        self.bind('<Destroy>', lambda event: unregister_live(self) if event.widget is self else None, add='+')
        self.refresh_models()

    # ── 数据 ────────────────────────────────────────────────────────────────
    def project(self):
        return desktop_project(self.desktop)

    def _entry(self):
        """当前阶段的已保存配置；读不到就是默认的一份。"""
        project = self.project()
        if not project:
            return {'model': model_router.AUTO, stage_config.REASONING: 'auto'}
        try:
            return stage_config.get(project, self.stage)
        except Exception:
            return {'model': model_router.AUTO, stage_config.REASONING: 'auto'}

    def saved_model(self):
        return str(self._entry().get('model') or model_router.AUTO).strip()

    def saved_reasoning(self):
        return stage_config.clean_reasoning(self._entry().get(stage_config.REASONING))

    def model_id(self):
        """当前文案 → 稳定模型 id；空或「自动」返回自动。"""
        display = str(self.model.get() or '').strip()
        if not display or display == model_pool.AUTO_LABEL:
            return model_router.AUTO
        return self._by_display.get(display) or model_router.AUTO

    def refresh_models(self):
        """模型池或项目变了：重读选项，并把已保存的那一档摆回去。"""
        self.groups = grouped_model_choices(self.desktop, self.stage)
        records = pool_records(self.desktop)
        self._items = []
        self._by_display = {}
        self._capable = set()
        for options in self.groups.values():
            for model_id, label in options:
                self._by_display.setdefault(label, model_id)
                self._items.append((model_id, label))
                if 'reasoning' in model_pool.capabilities_of(
                        (records.get(model_id) or {}).get('capabilities')):
                    self._capable.add(model_id)
        self._level.set(self.saved_reasoning())
        self.set_model(self.saved_model())
        self._fill_menu()
        return self.groups

    def set_model(self, model):
        """按模型 id 同步选择器；认不出的值显示为「自动」，不改写已保存的配置。"""
        wanted = str(model or model_router.AUTO)
        for model_id, label in self._items:
            if model_id == wanted:
                self.model.set(label)
                self._picked = label
                return wanted
        if wanted != model_router.AUTO:
            # 手写的本地模型 id 还没登记到模型池：照原样显示，不丢配置。
            self._by_display.setdefault(wanted, wanted)
            self._items.append((wanted, wanted))
            self.model.set(wanted)
            self._picked = wanted
            return wanted
        self.model.set(model_pool.AUTO_LABEL)
        self._picked = model_pool.AUTO_LABEL
        return model_router.AUTO

    def set_model_label(self, label):
        """按显示名同步选择器（点击模型目录条时用）；找不到匹配就不改动当前选择。"""
        wanted = str(label or '').strip()
        if not wanted:
            return None
        for options in self.groups.values():
            for model_id, item_label in options:
                if item_label == wanted:
                    self.model.set(item_label)
                    self._picked = item_label
                    return model_id
        return None

    def labels(self):
        """菜单里的模型项显示名（「+ 添加模型…」不在内）。"""
        return [label for _model_id, label in self._items]

    # ── 菜单 ────────────────────────────────────────────────────────────────
    def _fill_menu(self):
        """重建菜单条目：模型池或推理档位变了就重新摆一遍（条目持久，只有内容重建）。"""
        level = self.saved_reasoning()
        self._level.set(level)
        level_label = stage_config.REASONING_LABELS[level]
        self._menu_ctx.clear()
        self._choice.set(self._by_display.get(str(self.model.get() or ''), ''))
        for model_id, label in self._items:
            self._menu_ctx.radio(
                label=label, variable=self._choice, value=model_id,
                command=lambda value=model_id: self.choose_model(value))
            if model_id in self._capable:
                self._menu.entryconfigure(self._menu.index('end'),
                                          accelerator='推理·' + level_label)
        self._menu_ctx.separator()
        self._menu_ctx.cascade(label=LEVEL_MENU % level_label, submenu=self._level_ctx)
        self._menu_ctx.separator()
        self._menu_ctx.command(ADD_MODEL_LABEL, self.open_model_manager)

    # ── 交互 ────────────────────────────────────────────────────────────────
    def choose_model(self, model_id=None):
        if model_id is not None:
            if model_id == ADD_MODEL_LABEL:
                return self.open_model_manager()
            self.set_model(model_id)
            return self.save()
        if self.model.get() == ADD_MODEL_LABEL:
            self.model.set(self._picked)
            return self.open_model_manager()
        self._picked = self.model.get()
        return self.save()

    def choose_reasoning(self, level):
        """写本阶段的推理等级；界面档位立即跟随（不写模型与 SKILL）。"""
        level = stage_config.clean_reasoning(level)
        self._level.set(level)
        project = self.project()
        if not project:
            return None
        entry = stage_config.put(project, self.stage, reasoning=level)
        self._fill_menu()
        return entry

    def save(self):
        """只写模型这一项，SKILL 勾选与推理等级保持原样。"""
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

# R2942：页面级「阶段配置」按钮＋模型下拉框删除——模型选择收进共享输入框的下拉框按钮。
# StageModelPicker（Menubutton＋弹出菜单）保留，就是共享输入框右下角那颗的通用实现；
# 原 StageConfigButton／stage_button_for／attach_stage_pickers 三个按钮工厂不再有调用方，一并删除。
