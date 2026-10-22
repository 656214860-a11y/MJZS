"""制作锁共用视图：契约选项、换行、依赖和必选提示。"""
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from script_contract import PRODUCTION_LOCK_DEFINITIONS, production_lock_active
from ui_tokens import SPACING, COLORS, STAGE_PANEL_LAYOUT
from ui_widgets import SelectBox


class CompactLabel(ttk.Label):
    """保留 width=10 的旧契约，实际排版只请求文字宽度。"""

    def __init__(self, parent=None, **kwargs):
        kwargs.setdefault('width', STAGE_PANEL_LAYOUT['label_width'])
        super().__init__(parent, **kwargs)

    def winfo_reqwidth(self):
        style = self.cget('style') or 'TLabel'
        spec = self.cget('font') or ttk.Style(self).lookup(style, 'font')
        font = tkfont.Font(root=self, font=spec or 'TkDefaultFont')
        return max(1, font.measure(str(self.cget('text') or '')))


class FlowFields(ttk.Frame):
    """标签＋控件流：按可用宽度换行，除最后一行外把行填满。"""

    def __init__(self, parent, *, gap=None, row_gap=None, fill_last=False, **kwargs):
        super().__init__(parent, **kwargs)
        self.gap = STAGE_PANEL_LAYOUT['field_gap'] if gap is None else int(gap)
        self.row_gap = STAGE_PANEL_LAYOUT['row_gap'] if row_gap is None else int(row_gap)
        self.fill_last = bool(fill_last)
        self._items = []
        self._pending = None
        self._last_width = None
        self._rows = None
        self._layout_width = 0
        self._force_reflow = True
        self.pack_propagate(False)
        self.configure(height=1)
        self.bind('<Configure>', self._schedule, add='+')
        self.bind('<Destroy>', self._cancel, add='+')
        self._schedule()

    def add(self, widget, *, grow=False, key=None):
        if widget.winfo_manager() == 'pack':
            widget.pack_forget()
        elif widget.winfo_manager() == 'grid':
            widget.grid_forget()
        self._items.append({'widget': widget, 'grow': bool(grow), 'key': key,
                            'visible': True})
        self._force_reflow = True
        self._schedule()
        return widget

    def item(self, key):
        for item in self._items:
            if item['key'] == key:
                return item
        return None

    def insert_after(self, after_key, widget, *, grow=False, key=None):
        """把一项插到指定 key 项之后，参与同一套流式换行。"""
        if widget.winfo_manager() == 'pack':
            widget.pack_forget()
        elif widget.winfo_manager() == 'grid':
            widget.grid_forget()
        item = {'widget': widget, 'grow': bool(grow), 'key': key,
                'visible': True}
        index = next((i for i, existing in enumerate(self._items)
                      if existing['key'] == after_key), None)
        if index is None:
            self._items.append(item)
        else:
            self._items.insert(index + 1, item)
        self._force_reflow = True
        self._schedule()
        return widget

    def remove(self, widget):
        """从流式布局移除一项（删除勾选框后立即腾出位置）。"""
        for index, item in enumerate(self._items):
            if item['widget'] is widget:
                self._items.pop(index)
                if widget.winfo_manager() == 'place':
                    widget.place_forget()
                self._force_reflow = True
                self._schedule()
                return item
        return None

    def set_visible(self, key, visible):
        item = self.item(key)
        if item is None or item['visible'] == bool(visible):
            return item
        item['visible'] = bool(visible)
        if not item['visible']:
            item['widget'].place_forget()
        self._force_reflow = True
        self._schedule()
        return item

    def field_visible(self, key):
        item = self.item(key)
        return bool(item and item['visible'])

    def _schedule(self, event=None):
        if event is not None and event.widget is self:
            width = int(getattr(event, 'width', 0))
            if width == self._last_width:
                return
            self._last_width = width
        if self._pending is None:
            self._pending = self.after_idle(self.layout)

    def schedule(self, event=None):
        self._force_reflow = True
        self._schedule(event)

    def _schedule_wrap(self, event=None):
        self._schedule(event)

    def _cancel(self, event=None):
        if event is not None and event.widget is not self:
            return
        if self._pending is not None:
            try:
                self.after_cancel(self._pending)
            except tk.TclError:
                pass
            self._pending = None

    @staticmethod
    def _natural_size(widget):
        return (max(1, int(widget.winfo_reqwidth())),
                max(1, int(widget.winfo_reqheight())))

    def layout(self):
        self._pending = None
        if not self.winfo_exists():
            return
        available = int(self.winfo_width())
        if available <= 1:
            master = self.master
            available = int(master.winfo_width()) if master is not None else 1
            try:
                padding = master.cget('padding')
                if isinstance(padding, (tuple, list)):
                    available -= 2 * int(padding[0])
                elif padding:
                    available -= 2 * int(str(padding).split()[0])
            except (tk.TclError, ValueError, TypeError, IndexError):
                pass
        if available <= 1:
            return
        available = max(1, available)
        visible = [item for item in self._items
                   if item['visible'] and item['widget'].winfo_exists()]
        if not visible:
            self.configure(height=1)
            return
        for item in visible:
            item['natural'], item['height'] = self._natural_size(item['widget'])
        reuse = (not self._force_reflow and self._rows is not None
                 and abs(available - self._layout_width) <= 24)
        if reuse:
            rows = self._rows
        else:
            rows, row, used = [], [], 0
            for item in visible:
                extra = self.gap if row else 0
                if row and used + extra + item['natural'] > available:
                    rows.append(row)
                    row, used, extra = [], 0, 0
                row.append(item)
                used += extra + item['natural']
            if row:
                rows.append(row)
            self._rows = rows
            self._layout_width = available
        y = 0
        for index, row in enumerate(rows):
            self._place_row(row, y, available, index == len(rows) - 1)
            y += max(item['height'] for item in row) + self.row_gap
        height = max(1, y - self.row_gap)
        self._force_reflow = False
        if int(self.cget('height')) != height:
            self.configure(height=height)

    def _place_row(self, row, y, available, last):
        base = sum(item['natural'] for item in row) + self.gap * (len(row) - 1)
        extra = max(0, available - base) if (self.fill_last or not last) else 0
        grow_total = sum(item['natural'] for item in row if item['grow'])
        widths = []
        for item in row:
            width = item['natural']
            if extra and item['grow'] and grow_total:
                width += int(extra * item['natural'] / grow_total)
            widths.append(width)
        if base > available:
            need = base - available
            grow_indexes = [index for index, item in enumerate(row) if item['grow']]
            pool = sum(widths[index] for index in grow_indexes)
            if pool:
                for index in grow_indexes:
                    cut = int(need * widths[index] / pool)
                    widths[index] = max(1, widths[index] - cut)
        if (self.fill_last or not last) and widths:
            leftover = available - (sum(widths) + self.gap * (len(row) - 1))
            if leftover:
                target = None
                for index in range(len(row) - 1, -1, -1):
                    if row[index]['grow']:
                        target = index
                        break
                if target is not None:
                    widths[target] = max(1, widths[target] + leftover)
        row_height = max(item['height'] for item in row)
        x = 0
        for item, width in zip(row, widths):
            item['widget'].place(x=x, y=y, width=max(1, min(width, available)),
                                 height=row_height)
            x += width + self.gap


class ProductionLockFields(FlowFields):
    def __init__(self, parent, *, on_change=None, definitions=PRODUCTION_LOCK_DEFINITIONS,
                 prefix=None, horizontal=False, label_width=None, leading=(),
                 visible_keys=None):
        self.definitions = tuple(definitions)
        self.on_change = on_change
        self.inputs, self.hints, self.fields = {}, {}, {}
        self.leading_inputs = {}
        self.enabled = True
        self.context_values = {}
        super().__init__(parent)
        if prefix:
            prefix(self)
        for spec in leading:
            self._add_leading(spec)
        for item in self.definitions:
            self._add_lock(item)
        if visible_keys is not None:
            visible = set(visible_keys)
            for item in self.definitions:
                self.set_visible(item['key'], item['key'] in visible)
        self.set_values({})

    def _add_leading(self, spec):
        field = ttk.Frame(self)
        label = ttk.Label(field, text=spec['label'], style=spec.get('style', 'TLabel'))
        label.grid(row=0, column=0, sticky='w')
        entry = spec['factory'](field)
        entry.grid(row=0, column=1, sticky='ew', padx=(STAGE_PANEL_LAYOUT['field_gap'], SPACING['none']))
        field.columnconfigure(1, weight=1)
        key = spec['key']
        self.leading_inputs[key] = entry
        self.fields[key] = {'frame': field, 'label': label, 'entry': entry, 'hint': None}
        self.add(field, grow=True, key=key)

    def _add_lock(self, item):
        key = item['key']
        field = ttk.Frame(self)
        label = ttk.Label(field, text=item['label'])
        label.grid(row=0, column=0, sticky='w')
        entry = SelectBox(field, values=item.get('options') or (), state='normal', fit=True)
        entry.grid(row=0, column=1, sticky='ew', padx=(STAGE_PANEL_LAYOUT['field_gap'], SPACING['none']))
        field.columnconfigure(1, weight=1)
        hint = ttk.Label(field, foreground=COLORS['warning_text'])
        hint.grid(row=0, column=2, sticky='w', padx=(STAGE_PANEL_LAYOUT['field_gap'], SPACING['none']))
        hint.grid_remove()
        self.inputs[key], self.hints[key] = entry, hint
        self.fields[key] = {'frame': field, 'label': label, 'entry': entry, 'hint': hint}
        self.add(field, grow=True, key=key)
        for event in ('<Return>', '<KeyRelease>', '<FocusOut>', '<<ComboboxSelected>>'):
            entry.bind(event, self.changed)

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
        for entry in self.inputs.values():
            entry.refit()
        self.schedule()

    def changed(self, _event=None):
        self.refresh_states()
        if self.on_change:
            self.on_change()
