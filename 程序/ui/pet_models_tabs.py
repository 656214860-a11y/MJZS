# -*- coding: utf-8 -*-
"""模型管理窗口的调用方式页签 + 模态（功能）分类 + 表单脏检查：从 _ModelManager 拆出的 Mixin（R2399）。

按调用方式（API／Desktop／CLI）分页签，列表只显示当前调用方式的模型，并按「功能 → Provider」
分组排序。模态（文本/图片/语音/视频）当前只有「文本」有实际模型，其余分类先建好暂空。

模型记录读写仍在 model_pool，这里只负责页签联动、列表的按调用方式过滤／模态分组，
以及 DES《05》§15 的「未保存改动」确认守卫（ModelManagerFormGuardMixin）与新建预填默认。
"""
import infra.model_pool as model_pool

MODES = ('API', 'Desktop', 'CLI')  # 左上角页签顺序，与 ttk.Notebook tabs() 索引一一对应
FORM_FIELDS = (('label', '显示名'), ('model', '模型 ID'), ('base_url', 'API 根地址'),
               ('key_env', '密钥名（.env 里的变量名）'))
FORM_DEFAULT_PROVIDER = model_pool.PROVIDER_LABELS['custom']  # 新建默认「自定义」
# UX-MODEL-PAGE：模型管理页「新建一条」时编辑区的预填默认（DES《05》§15.3，均标「可改」）。
# 只新增默认值，不改存量字段语义；已存记录没有这些字段时不回填（record 对缺省字段保持空串）。
DEFAULT_CONTEXT_LENGTH = 262144          # 上下文窗口 256K＝256×1024
NEW_MODEL_DEFAULTS = {'context_length': DEFAULT_CONTEXT_LENGTH,
                      'max_output': 8192,          # 最大输出 tokens（本项目设计选择）
                      'temperature': 0.7,          # 温度（本项目设计选择）
                      'timeout': 120,              # 请求超时秒（本项目设计选择）
                      'retries': 2}                # 失败重试次数（本项目设计选择）


def list_status(record, program):
    """模型列表「状态」那一格：用得了只写「可用」（模型 ID 已有自己一列），用不了写缺什么。"""
    ok, why = model_pool.status(record, program)
    return '可用' if ok else why


class ModelManagerModeTabsMixin:
    """调用方式页签 + 模态分类；宿主 _ModelManager 提供 self.mode／self.mode_tabs／self.tree 等属性。"""

    def _on_tab_changed(self, _event=None):
        """页签点击：把调用方式同步过去（换页签即切换 Desktop／API／CLI）。"""
        current = self.mode_tabs.tab('current', 'text')
        if current != self.mode.get():
            self.mode.set(current)

    def _on_mode_change(self, *_args):
        """调用方式变了：同步页签并按新调用方式重刷列表（值没变不刷）。"""
        current = self.mode.get()
        if current == self._last_mode:
            return
        self._last_mode = current
        if current in MODES:
            self.mode_tabs.select(self.mode_tabs.tabs()[MODES.index(current)])
        if not self.pending['loading']:   # fill 回填期间只同步页签，不重建列表
            self.load_rows()

    def _render_mode_rows(self, records):
        """按当前调用方式过滤并插入列表行；只显示本调用方式的模型，按「功能 → Provider」分组。"""
        self.tree.delete(*self.tree.get_children())
        current = self.mode.get()
        rows = sorted(((model_pool.MODALITY_LABELS.get(item.get('modality'), '文本'),
                        model_pool.provider_name(model_id, item), model_id, item)
                       for model_id, item in records.items()
                       if model_pool.call_mode(item, model_id) == current),
                      key=lambda r: (r[0], r[1].casefold(), str(r[3].get('label') or '').casefold(), r[2]),
                      reverse=self.provider_descending)
        last = None
        for modality, name, model_id, item in rows:
            # 同一功能内同一 Provider 只在分组第一行写名字，后面留空，读起来像合并单元格。
            shown, last = ('' if (modality, name) == last else name), (modality, name)
            self.tree.insert('', 'end', iid=model_id,
                        values=(modality, shown, model_pool.call_mode(item, model_id), item['model'], item['label'],
                                model_pool.capability_text(item['capabilities']),
                                list_status(item, self.program)))
        self.table_shell.refresh_empty_state()


class ModelManagerFormGuardMixin:
    """DES《05》§15.2：模型管理表单的「未保存改动」守卫。

    真实键入（<KeyRelease>）、下拉挑选（<<ComboboxSelected>>）与能力勾选把表单弄脏；
    fill/new_one 这类程序化回填不算。表单脏时，切换列表行、新建一条、切换调用方式页签、
    点取消／Esc／窗口 X 都先经 pet.confirm_start 确认；拒绝则留在原地。
    宿主 _ModelManager 提供 self.pet／self.win／self.tree／self.entries 等属性；
    _on_tab_changed 的 super() 落在 ModelManagerModeTabsMixin 上（宿主须同时继承它、
    且把本 Mixin 排在 MRO 更前）。
    """

    def _bind_dirty_marks(self):
        """未保存改动只认真实键入／下拉／勾选；fill/new_one 这类程序化回填不算。"""
        for entry in self.entries.values():
            entry.bind('<KeyRelease>', self._mark_dirty, add='+')
        for box in (self.provider_box, self.modality_box, self.wire_box):
            box.bind('<<ComboboxSelected>>', self._mark_dirty, add='+')

    def _mark_dirty(self, *_args):
        """真实键入／下拉／勾选才算未保存改动；程序化回填不触发这些事件。"""
        self._dirty = True

    def _confirm_discard(self, action):
        """有未保存改动时先确认；干净表单直接放行。"""
        if not self._dirty:
            return True
        return bool(self.pet.confirm_start('放弃未保存的改动',
                                           '有未保存的改动，%s后不保留。继续吗？' % action))

    def _restore_selection(self):
        """确认被拒：把列表高亮拉回正在编辑的那一条（新建态则清掉高亮）。"""
        self._selecting = True
        try:
            current = self.state['id']
            if current and self.tree.exists(current):
                self.tree.selection_set(current)
            else:
                for iid in self.tree.selection():
                    self.tree.selection_remove(iid)
        finally:
            self._selecting = False

    def on_select(self, event=None):
        if self._selecting:
            return None
        picked = self.tree.selection()
        if not picked:
            return None
        if str(picked[0]) != str(self.state['id']) and not self._confirm_discard('切换编辑对象'):
            self._restore_selection()
            return None
        item = self.pet.agent_model_records().get(picked[0]) or {}
        self.fill(picked[0], item)
        self.hint.set('正在改「%s」；改完点「保存这条」。' % (item.get('label') or picked[0]))
        return item

    def _on_tab_changed(self, _event=None):
        """DES《05》§15.2：有未保存改动时切调用方式页签也要确认；拒绝则页签弹回原位。"""
        current = self.mode_tabs.tab('current', 'text')
        if current != self.mode.get() and not self._confirm_discard('切换调用方式'):
            if self.mode.get() in MODES:
                self.mode_tabs.select(self.mode_tabs.tabs()[MODES.index(self.mode.get())])
            return None
        return super()._on_tab_changed(_event)

    def new_one(self, _confirmed=False):
        if not _confirmed and not self._confirm_discard('新建一条'):
            return None
        self.pending['loading'] = True
        self.state['id'] = ''
        for key, _label in FORM_FIELDS:
            self.entries[key].delete(0, 'end')
        for key in ('context_length', 'rpm', 'group', 'weight', 'note', 'program',
                    'max_output', 'temperature', 'timeout', 'retries'):
            self.entries[key].delete(0, 'end')
        # DES《05》§15.3：新建预填主流默认（NEW_MODEL_DEFAULTS，均可改）。
        for key, value in NEW_MODEL_DEFAULTS.items():
            self.entries[key].insert(0, str(value))
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
        self._dirty = False
        self.hint.set('新建 %s 模型：填写模型 ID；本地调用会自动搜寻对应程序。' % self.mode.get())
        return self.state

    def cancel(self, *_args):
        """「取消」／Esc／窗口 X：有未保存改动先确认，拒绝则留在页内。"""
        if not self._confirm_discard('关闭窗口'):
            return None
        self.win.destroy()
        return True

    def save_and_close(self):
        """底行「保存」：写入并关闭；失败留在页内（原因已由 save_one 写进提示）。"""
        if self.save_one() is not None:
            self.win.destroy()
