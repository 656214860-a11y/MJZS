# -*- coding: utf-8 -*-
"""创意输入实时必填校验与发送键可用态（从 ``desktop_idea_chat.IdeaChatMixin`` 迁出）。

迁出原因：``desktop_idea_chat`` 超出模块行数棘轮上限（1081 > 1000）。REQ-S01-86
要求简报必填校验前置到输入框——缺字段实时置灰发送键；这一簇（防抖刷新、缺失判据、
附件字段缓存）自成一事，整块搬出后方法体未改、``self`` 语义不变。
``IdeaChatMixin`` 通过继承 ``IdeaSendGateMixin`` 获得这些方法；仍与 Tk 控件和
``self`` 状态紧耦合，故与 ``desktop_idea_chat`` 同属 L4。
"""
import tkinter as tk


class IdeaSendGateMixin:
    """剧本准备页发送键实时门禁：输入或附件变化后按简报必填判据刷新可用态。"""
    def refresh_idea_send_state(self):
        """输入或附件变化后防抖刷新发送可用态（REQ-S01-86：简报必填前置到输入框）。"""
        win = getattr(self, 'win', None)
        if win is None:
            return
        pending = getattr(self, '_idea_send_state_after', None)
        if pending is not None:
            try:
                win.after_cancel(pending)
            except tk.TclError:
                pass
        try:
            self._idea_send_state_after = win.after(250, self._apply_idea_send_state)
        except tk.TclError:
            self._idea_send_state_after = None

    def _apply_idea_send_state(self):
        self._idea_send_state_after = None
        stage = getattr(getattr(self, 'shared_input', None), 'stage', None)
        if isinstance(stage, str) and stage and stage != 'script':
            return
        try:
            missing = self._idea_live_missing()
        except Exception:
            missing = ()
        # R2923：发送键并入共享输入框（send_button）；状态唯一入口是
        # update_script_interrupt_button（运行中=终止键，空闲时按必填置灰）。
        sync = getattr(self, 'update_script_interrupt_button', None)
        if callable(sync):
            sync()
        hint = '还缺必填：' + '、'.join(missing) if missing else ''
        if hint != getattr(self, '_idea_send_hint', ''):
            self._idea_send_hint = hint
            status = getattr(self, 'status', None)
            if status is not None:
                status.set(hint or '就绪')

    def _idea_live_missing(self):
        """与 send_message 同判据：当前输入现在送出去会不会被必填缺失拦下。"""
        import domain.idea_chat as idea_chat
        import orchestrator.stage_config as stage_config
        import writing_api
        value = self.draft_text()
        if writing_api.preparation_continuation(self.root, value):
            return ()
        from contract.script_contract import PRODUCTION_LOCK_DEFINITIONS
        lock_definitions = PRODUCTION_LOCK_DEFINITIONS
        return idea_chat.inline_required_missing(
            None, value, attachment_fields=self._idea_live_attachment_fields(lock_definitions),
            stage='script', lock_definitions=lock_definitions,
            created_at=stage_config.project_created_at(self.root))

    def _idea_live_attachment_fields(self, lock_definitions):
        """附件与制作锁提供的字段值（按附件路径集合缓存，避免每次按键重读文件）。"""
        import domain.idea_chat as idea_chat
        import orchestrator.stage_config as stage_config
        paths = tuple(self.idea_attachment_paths)
        if getattr(self, '_idea_live_attach_key', None) == paths:
            return self._idea_live_attach_fields
        from stage_execution_service import (stage_idea_attachment_reference,
                                             stage_idea_brief_defaults)
        from contract.script_contract import PRODUCTION_LOCK_DEFINITIONS
        reference = stage_idea_attachment_reference(self.root, self.draft_text(), paths)
        fields = dict(stage_idea_brief_defaults(self.root, reference=reference)['values'])
        lock_labels = tuple(label for item in lock_definitions
                            for label in (item['label'], *item.get('aliases', ())))
        for text in reference.get('brief_texts', ()):
            for label, field in idea_chat.extract_brief_creation(
                    text, extra_labels=lock_labels, include_extra=True).items():
                fields.setdefault(label, field)
        configured_locks = stage_config.workflow_lock(self.root)
        fields.update({item['label']: configured_locks[item['key']]
                       for item in PRODUCTION_LOCK_DEFINITIONS if configured_locks.get(item['key'])})
        self._idea_live_attach_key, self._idea_live_attach_fields = paths, fields
        return fields
