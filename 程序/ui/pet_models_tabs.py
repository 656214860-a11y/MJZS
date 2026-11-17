# -*- coding: utf-8 -*-
"""模型管理窗口的调用方式页签 + 模态（功能）分类：从 _ModelManager 拆出的 Mixin（R2399）。

按调用方式（API／Desktop／CLI）分页签，列表只显示当前调用方式的模型，并按「功能 → Provider」
分组排序。模态（文本/图片/语音/视频）当前只有「文本」有实际模型，其余分类先建好暂空。

模型记录读写仍在 model_pool，这里只负责页签联动与列表的按调用方式过滤／模态分组。
"""
import infra.model_pool as model_pool

MODES = ('API', 'Desktop', 'CLI')  # 左上角页签顺序，与 ttk.Notebook tabs() 索引一一对应


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
