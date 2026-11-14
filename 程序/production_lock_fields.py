"""制作锁共用视图：契约选项、换行、依赖和必选提示。"""
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from script_contract import PRODUCTION_LOCK_DEFINITIONS, production_lock_active
from ui_tokens import SPACING, STAGE_PANEL_LAYOUT
from ui_tooltip import Tooltip
from ui_widgets import SelectBox


def label_pixel_width(widget, texts, style='TLabel'):
    """一组标签里最宽的像素宽度（含防裁字余量），用来把各行的标签列对齐。"""
    widest = 0
    for text in texts:
        # 用真实标签量宽：样式查到的字体和控件实际渲染字体可能不一致，量错会裁字。
        probe = ttk.Label(widget, text=str(text), style=style,
                          padding=(STAGE_PANEL_LAYOUT['label_indent'], 0, 0, 0))
        widest = max(widest, probe.winfo_reqwidth())
        probe.destroy()
    return widest + SPACING['sm']


class CompactLabel(ttk.Label):
    """保留 width=10 的旧契约，实际排版只请求文字宽度（可用 min_px 对齐标签列）。"""

    def __init__(self, parent=None, min_px=0, **kwargs):
        kwargs.setdefault('width', STAGE_PANEL_LAYOUT['label_width'])
        kwargs.setdefault('anchor', 'w')  # 文字左对齐，左侧缩进 label_indent
        kwargs.setdefault('padding', (STAGE_PANEL_LAYOUT['label_indent'], 0, 0, 0))
        super().__init__(parent, **kwargs)
        self.min_px = int(min_px)

    def winfo_reqwidth(self):
        style = self.cget('style') or 'TLabel'
        spec = self.cget('font') or ttk.Style(self).lookup(style, 'font')
        font = tkfont.Font(root=self, font=spec or 'TkDefaultFont')
        # 多留一个 xs 的余量：按字形宽度精确请求时，部分字体渲染会被右侧裁掉半个字。
        return max(1, self.min_px,
                   font.measure(str(self.cget('text') or '')) + SPACING['xs']
                   + STAGE_PANEL_LAYOUT['label_indent'])


def align_label_column(root, px):
    """把 root 下按旧标签列宽（root.label_px）对齐的 CompactLabel 改到 px，并让所在行重排。"""
    old = int(getattr(root, 'label_px', 0) or 0)
    if not old or old == px:
        return
    root.label_px = px
    pending = list(root.winfo_children())
    while pending:
        widget = pending.pop()
        pending.extend(widget.winfo_children())
        if isinstance(widget, CompactLabel) and widget.min_px == old:
            widget.min_px = px
            relayout = (getattr(widget.master, 'schedule', None)
                        or getattr(widget.master, '_schedule_wrap', None))
            if relayout:
                relayout()


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
                extra = self._gap_after(row[-1]) if row else 0
                width = self._wrap_width(item)
                if row and used + extra + width > available:
                    rows.append(row)
                    row, used, extra = [], 0, 0
                row.append(item)
                used += extra + width
            if row:
                rows.append(row)
            self._rows = rows
            self._layout_width = available
        self._fit_columns(rows)
        y = 0
        for index, row in enumerate(rows):
            self._place_row(row, y, available, index == len(rows) - 1)
            y += max(item['height'] for item in row) + self.row_gap
        height = max(1, y - self.row_gap)
        self._force_reflow = False
        if int(self.cget('height')) != height:
            self.configure(height=height)

    def _wrap_width(self, item):
        """折行时按多宽计算一项；默认就是自然宽度。"""
        return item['natural']

    def _fit_columns(self, rows):
        """折行定下后、摆放前的钩子：子类可按列收窄各项（改 item['natural']）。"""

    def _gap_after(self, item):
        """某项之后的间距：控件可带 gap_after 属性（如下拉框后留大间距），否则用统一 gap。"""
        return int(getattr(item['widget'], 'gap_after', self.gap))

    def _place_row(self, row, y, available, last):
        gaps = [self._gap_after(item) for item in row[:-1]]
        base = sum(item['natural'] for item in row) + sum(gaps)
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
            leftover = available - (sum(widths) + sum(gaps))
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
        for index, (item, width) in enumerate(zip(row, widths)):
            item['widget'].place(x=x, y=y, width=max(1, min(width, available)),
                                 height=row_height)
            x += width + (gaps[index] if index < len(gaps) else self.gap)


class ProductionLockFields(FlowFields):
    def __init__(self, parent, *, on_change=None, definitions=PRODUCTION_LOCK_DEFINITIONS,
                 prefix=None, leading=(),
                 visible_keys=None, label_px=None):
        self.definitions = tuple(definitions)
        self.on_change = on_change
        self.inputs, self.hints, self.fields = {}, {}, {}
        self.tooltips = {}          # key → Tooltip；提示改悬停浮层，不再占一行黄色文字
        self.leading_inputs = {}
        self.enabled = True
        self.context_values = {}
        super().__init__(parent, gap=STAGE_PANEL_LAYOUT['item_gap'])
        # 折行按最宽标签算（每行放几项不随列宽抖动）；摆放时每列标签只取本列最宽，
        # 短标签多的列下拉框随之左移。label_px 是第一列的下限（与页面其他行的标签列对齐）。
        self.first_column_px = int(label_px or 0)
        self.on_first_column = None  # 调用方可挂回调：第一列宽度变化时同步页面其他行
        self.label_px = max(self.first_column_px, label_pixel_width(
            self, [spec['label'] for spec in leading] + [item['label'] for item in self.definitions]))
        self.column_px = {}
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
        label = ttk.Label(field, text=spec['label'], style=spec.get('style', 'TLabel'),
                          padding=(STAGE_PANEL_LAYOUT['label_indent'], 0, 0, 0))
        label.grid(row=0, column=0, sticky='w')  # 左对齐缩进：同列标签起点一致
        field.columnconfigure(0, minsize=self.label_px)
        entry = spec['factory'](field)
        entry.grid(row=0, column=1, sticky='w', padx=(STAGE_PANEL_LAYOUT['field_gap'], SPACING['none']))
        key = spec['key']
        self.leading_inputs[key] = entry
        self.fields[key] = {'frame': field, 'label': label, 'entry': entry, 'hint': None}
        self.add(field, key=key)

    def _add_lock(self, item):
        key = item['key']
        field = ttk.Frame(self)
        label = ttk.Label(field, text=item['label'],
                          padding=(STAGE_PANEL_LAYOUT['label_indent'], 0, 0, 0))
        label.grid(row=0, column=0, sticky='w')  # 左对齐缩进：同列标签起点一致
        field.columnconfigure(0, minsize=self.label_px)
        entry = SelectBox(field, values=item.get('options') or (), state='normal',
                          width=STAGE_PANEL_LAYOUT['select_width'])
        entry.grid(row=0, column=1, sticky='w', padx=(STAGE_PANEL_LAYOUT['field_gap'], SPACING['none']))
        # 说明与「必填」提示不再占一行黄色文字，改挂悬停卡片（Tooltip），各字段行高一致。
        self.inputs[key] = entry
        self.hints[key] = Tooltip(entry, '')
        self.fields[key] = {'frame': field, 'label': label, 'entry': entry, 'hint': self.hints[key]}
        self.add(field, key=key)
        for event in ('<Return>', '<KeyRelease>', '<FocusOut>', '<<ComboboxSelected>>'):
            entry.bind(event, self.changed)

    def _field_item(self, item):
        key = item['key']
        return key in self.fields and self.fields[key]['frame'] is item['widget']

    def _entry_span(self, key):
        entry = self.fields[key]['entry']
        return STAGE_PANEL_LAYOUT['field_gap'] + max(1, int(entry.winfo_reqwidth()))

    def _wrap_width(self, item):
        if not self._field_item(item):
            return item['natural']
        return self.label_px + self._entry_span(item['key'])

    def _label_req(self, item):
        return int(self.fields[item['key']]['label'].winfo_reqwidth())

    def _fit_columns(self, rows):
        # 只有以字段开头的行才成列；以按钮／提示开头的行（展开选填锁后）各字段只按自己的标签收窄，
        # 免得把不在同一列的标签算进某一列。
        grid_rows = [row for row in rows if self._field_item(row[0])]
        columns = {}
        for row in grid_rows:
            for index, item in enumerate(row):
                if self._field_item(item):
                    columns[index] = max(columns.get(index, 0), self._label_req(item))
        if not columns:
            return
        columns[0] = max(columns.get(0, 0), self.first_column_px)
        for row in rows:
            in_grid = any(row is grid for grid in grid_rows)
            for index, item in enumerate(row):
                if self._field_item(item):
                    px = columns[index] if in_grid else self._label_req(item)
                    self.fields[item['key']]['frame'].columnconfigure(0, minsize=px)
                    item['natural'] = px + self._entry_span(item['key'])
        changed = columns.get(0) != self.column_px.get(0)
        self.column_px = columns
        if changed and self.on_first_column:
            self.on_first_column(columns[0])

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

    def _depends_resolvable(self, item, values):
        """依赖字段是否在当前视图/取值里可判定；缺了依赖字段（如补充创作信息弹窗不含
        视频模型版本）时不因 depends_on 而禁用，放行让用户直接选（依赖约束仍由 SKILL 层兜底）。"""
        return all(key in self.inputs or key in values for key in item.get('depends_on', {}))

    def refresh_states(self):
        values = {**self.context_values, **self.values()}
        for item in self.definitions:
            key = item['key']
            resolvable = self._depends_resolvable(item, values)
            active = production_lock_active(item, values) if resolvable else True
            self.inputs[key].configure(state='normal' if self.enabled and active else 'disabled')
            required_missing = bool(item.get('required_from') and not values[key])
            # 标签不再因「必填缺失」染警示色（与 brief 字段统一黑字），必填与说明并入悬停卡片。
            self.fields[key]['label'].configure(foreground='')
            hint = ('仅 Seedance 2.5' if key == 'reference_mode' and not active else
                    '多段任务用' if key == 'splice_mode' else
                    '预设，≤4 张，逗号分隔' if key == 'style_directors' else '')
            if required_missing and not hint:
                hint = '必填'
            elif required_missing and hint:
                hint = hint + ' · 必填'
            self.hints[key].text = hint
        for entry in self.inputs.values():
            entry.refit()
        self.schedule()

    def changed(self, _event=None):
        self.refresh_states()
        if self.on_change:
            self.on_change()
