"""skill_panel 的预设功能：保存／删除／改名／套用／跨页面复制。

SPSPLIT 从 skill_panel.py 的 Panel 拆出；Panel 继承 ``PresetMixin``，公开名与行为不变。
本模块与 skill_panel 同处 L4，不 import skill_panel（避免循环），只依赖下层模块与 ui_widgets。
"""
import tkinter as tk
from tkinter import ttk

import stage_config
from pet_bus import STAGE_NAMES
from skill_panel_support import program_of
from ui_tokens import BUTTON_GAP, SPACING
from ui_widgets import BaseDialog, DescriptionBlock, PrimaryButton, SecondaryButton, ask_string


# 预设不是必填项；用明确的占位项避免刚打开面板就误把第一份预设当作当前选择。
PRESET_PLACEHOLDER = '请选择'


class PresetMixin:
    """阶段配置面板的预设区：下拉框、操作下拉与跨页面复制。"""

    def run_preset_action(self):
        """执行预设操作下拉框当前选择，并在操作后回到占位项。"""
        action = str(self.preset_action.get() or '').strip()
        actions = {
            '保存为预设': self.save_preset,
            '删除预设': self.drop_preset,
            '重命名预设': self.rename_preset,
            '复制本预设到其他页面': self.share_preset_copy,
        }
        callback = actions.get(action)
        if callback is None:
            self.state.configure(text='请先选择预设操作')
            return None
        try:
            return callback()
        finally:
            self.preset_action.set('选择操作')

    # ── 跨页面共享预设 ────────────────────────────────────────────────────
    def share_preset_copy(self):
        """把当前页面的预设复制到用户勾选的页面，不再把预设混成全局共用一份。"""
        name = str(self.preset.get() or '').strip()
        if not name or name == PRESET_PLACEHOLDER:
            self.state.configure(text='先在上方选一个预设')
            return None
        dialog = BaseDialog(self.winfo_toplevel(), '复制预设：选择共享页面', chrome=False)
        DescriptionBlock(dialog, text='将预设「%s」复制到以下页面：\n各页面获得独立副本，之后互不影响。' % name).pack(
            anchor='w', padx=SPACING['lg'], pady=(SPACING['md'], SPACING['sm']))
        body = ttk.Frame(dialog)
        body.pack(fill='both', expand=True, padx=SPACING['lg'])
        choices = []
        for stage in STAGE_NAMES:
            if stage == self.stage:
                continue
            variable = tk.BooleanVar(value=False)
            ttk.Checkbutton(body, text=STAGE_NAMES.get(stage, stage), variable=variable).pack(
                anchor='w', pady=SPACING['xs'])
            choices.append((stage, variable))

        def submit():
            targets = [stage for stage, variable in choices if variable.get()]
            if not targets:
                self.state.configure(text='未选择共享页面，预设仍只属于当前页面')
                dialog.destroy()
                return
            try:
                copied = stage_config.share_preset(name, self.stage, targets,
                                                    program=program_of(self.desktop))
            except Exception as exc:
                self.state.configure(text='共享预设失败：' + str(exc))
            else:
                labels = '、'.join(STAGE_NAMES.get(stage, stage) for stage in copied)
                self.state.configure(text='已复制预设「%s」到：%s' % (name, labels))
            dialog.destroy()

        buttons = ttk.Frame(dialog)
        buttons.pack(fill='x', padx=SPACING['lg'], pady=SPACING['md'])
        PrimaryButton(buttons, text='共享到所选页面', command=submit).pack(side='right')
        SecondaryButton(buttons, text='取消', command=dialog.destroy).pack(side='right', padx=(SPACING['none'], BUTTON_GAP))
        dialog.resizable(False, False)
        return dialog

    # ── 预设 ────────────────────────────────────────────────────────────────
    def preset_names(self):
        try:
            return sorted(str(name) for name in stage_config.presets(program_of(self.desktop), self.stage))
        except Exception:
            return []

    def show_presets(self, picked=''):
        """把预设下拉框的选项与选中的那一份对齐（第 62 期任务 1／4：三处调用合成一处）。

        存／删／改名之后都要做同一件事，各写一遍迟早走偏（下拉框里留着一份已经不存在的
        预设，或者删完了还选着它）。
        """
        names = self.preset_names()
        self.presets.set_values([PRESET_PLACEHOLDER] + names)
        self.preset.set(picked if picked in names else PRESET_PLACEHOLDER)
        return names

    def save_preset(self):
        """存一份预设；默认填当前预设，保留同名即可覆盖它。"""
        current = str(self.preset.get() or '').strip()
        if current == PRESET_PLACEHOLDER:
            current = ''
        name = ask_string(self.winfo_toplevel(), '保存为预设', '预设名称（同名将覆盖）：', initialvalue=current)
        name = str(name or '').strip()
        if not name:
            return ''
        replaced = name in self.preset_names()
        stage_config.save_preset(name, self.model_id(), self.selected(),
                                 stage=self.stage, program=program_of(self.desktop))
        self.show_presets(name)
        self.state.configure(text=('已覆盖预设：' if replaced else '已存预设：') + name)
        return name

    def drop_preset(self):
        """删掉下拉框里挑中的那份预设（第 62 期任务 1）；没挑就明说一句，别猜。"""
        name = str(self.preset.get() or '').strip()
        if not name or name == PRESET_PLACEHOLDER:
            self.state.configure(text='先在下拉框里挑一份预设，再删除')
            return ''
        if not stage_config.drop_preset(name, program_of(self.desktop), stage=self.stage):
            self.state.configure(text='没找到这份预设：' + name)
            self.show_presets()
            return ''
        self.show_presets()
        self.state.configure(text='已删除预设：' + name)
        return name

    def rename_preset(self):
        """给下拉框里挑中的那份预设改个名字（第 51 期第 4 条）。

        没挑就明说「先挑一份」；改完下拉框里那份跟着变成新名字，还选着它。
        """
        old = str(self.preset.get() or '').strip()
        if not old or old == PRESET_PLACEHOLDER:
            self.state.configure(text='先在下拉框里挑一份预设，再改名')
            return ''
        name = ask_string(self.winfo_toplevel(), '重命名预设', '把「%s」改成：' % old, initialvalue=old)
        name = ' '.join(str(name or '').split())
        if not name or name == old:
            return ''
        try:
            stage_config.rename_preset(old, name, program_of(self.desktop), stage=self.stage)
        except Exception as exc:
            self.state.configure(text='没改成：' + str(exc))
            return ''
        self.show_presets(name)
        self.state.configure(text='预设已改名：%s → %s' % (old, name))
        return name

    def apply_preset(self):
        name = str(self.preset.get() or '').strip()
        if not name or name == PRESET_PLACEHOLDER:
            return None
        entry = stage_config.apply_preset(self.project(), self.stage, name, registry=self.registry,
                                          program=program_of(self.desktop))
        self.load()
        self.state.configure(text='已套用预设：' + name)
        self.show_desktop_route_notice()
        return entry