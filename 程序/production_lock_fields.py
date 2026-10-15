"""制作锁共用视图：契约选项、换行、依赖和必选提示。"""
from tkinter import ttk
from responsive_ui import FlowBar
from script_contract import PRODUCTION_LOCK_DEFINITIONS, production_lock_active
from ui_tokens import COLORS, SPACING, PRODUCTION_LOCK_WIDTH
from ui_widgets import SelectBox


class ProductionLockFields(FlowBar):
    def __init__(self, parent, *, on_change=None, definitions=PRODUCTION_LOCK_DEFINITIONS,
                 prefix=None, horizontal=False):
        self.horizontal = horizontal
        super().__init__(parent)
        self.definitions = definitions
        self.on_change = on_change
        self.inputs, self.hints = {}, {}
        self.enabled = True
        self.context_values = {}
        if prefix:
            prefix(self)
        for column, item in enumerate(definitions):
            key = item['key']
            field = ttk.Frame(self)
            if horizontal:
                self.columnconfigure(column, weight=1, uniform='locks')
                field.grid(row=0, column=column, sticky='ew', padx=SPACING['xs'])
            else:
                field.pack(side='left', padx=SPACING['xs'])
            ttk.Label(field, text=item['label']).grid(row=0, column=0, sticky='w')
            width = PRODUCTION_LOCK_WIDTH['compact' if key in ('aspect_ratio', 'fps') else
                                          'directors' if key == 'style_directors' else 'normal']
            entry = SelectBox(field, values=item.get('options') or (), state='normal', width=width)
            field.columnconfigure(1, weight=1)
            entry.grid(row=0, column=1, sticky='ew', padx=SPACING['xs'])
            hint = ttk.Label(field, foreground=COLORS['warning'])
            hint.grid(row=1, column=0, columnspan=2, sticky='w')
            self.inputs[key], self.hints[key] = entry, hint
            for event in ('<Return>', '<KeyRelease>', '<FocusOut>', '<<ComboboxSelected>>'):
                entry.bind(event, self.changed)
        self.set_values({})

    def layout(self):
        if self.horizontal:
            # 旧五锁保持 grid 同排；高度交给 grid 的几何传播。
            self.pending = None
        else:
            super().layout()

    def values(self):
        return {key: entry.get().strip() for key, entry in self.inputs.items()}

    def set_values(self, values, *, enabled=True):
        self.enabled = enabled
        self.context_values = dict(values)
        for item in self.definitions:
            entry = self.inputs[item['key']]
            entry.configure(state='normal')
            entry.delete(0, 'end')
            entry.insert(0, str(values.get(item['key'], item.get('default', '')) or ''))
        self.refresh_states()

    def refresh_states(self):
        values = {**self.context_values, **self.values()}
        for item in self.definitions:
            key = item['key']
            active = production_lock_active(item, values)
            self.inputs[key].configure(state='normal' if self.enabled and active else 'disabled')
            hint = ('必选' if item.get('required_from') and not values[key] else
                    '仅 Seedance 2.5' if key == 'reference_mode' and not active else
                    '多段任务用' if key == 'splice_mode' else
                    '预设，≤4 张，逗号分隔' if key == 'style_directors' else '')
            self.hints[key].configure(text=hint)
            if hint:
                self.hints[key].grid()
            else:
                self.hints[key].grid_remove()
        self.schedule()

    def changed(self, _event=None):
        self.refresh_states()
        if self.on_change:
            self.on_change()
