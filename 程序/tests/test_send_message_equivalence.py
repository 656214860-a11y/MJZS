"""desktop_idea_chat.send_message 拆出 _idea_api_received：HEAD 旧实现原样内嵌，宿主替身与模块函数全部记账，
让新旧实现走同一条直连 API 发送路径，再把截获的回调喂同一组模型结果，对照全部调用记录。"""
import threading
import unittest
from unittest import mock

import desktop_idea_chat as module
import idea_chat
import stage_config
import stage_execution_service
import workflow_settings
import writing_api
from window_diff_support import legacy

LEGACY = 'def send_message(self):\n    """提交创意；显式 API 模型在聊天框内回复，其余仍启动剧本 Agent。"""\n    box=getattr(self,\'idea_input\',None)\n    if box is None or not box.winfo_exists():raise ValueError(\'这一页还没建好，请重新打开这一页\')\n    value=self.draft_text()\n    prepared=self.idea_chat_controller.prepare_submission(self.root, value, is_example=False)\n    import idea_chat\n    import writing_api\n    import workflow_settings\n    workflow_settings.validate_selected_skills(self.root, \'writing\')\n    request_model = writing_api.capture_request_model(self.root)\n    direct_model = request_model[\'label\']\n    continuing = bool(direct_model and prepared and\n                      writing_api.preparation_continuation(self.root, value))\n    import stage_config, workflow_settings\n    workflow_config = stage_config.current_workflow(self.root)\n    preset = workflow_settings.WORKFLOW_PRESETS.get(workflow_config.get(\'name\'), {})\n    lock_definitions = preset.get(\'locks\') or tuple(\n        item for definition in workflow_settings.WORKFLOW_PRESETS.values() for item in definition.get(\'locks\', ()))\n    attachment_fields = {}\n    if prepared is not None:\n        from stage_execution_service import stage_idea_brief_defaults\n        reference = prepared[\'attachments\']\n        attachment_fields.update(stage_idea_brief_defaults(self.root, reference=reference)[\'values\'])\n        # 普通字段沿用 L2 别名；锁标签只来自统筹定义，不再维护第二张映射表。\n        lock_labels = tuple(label for item in lock_definitions\n                            for label in (item[\'label\'], *item.get(\'aliases\', ())))\n        lock_fields = {}\n        for text in reference.get(\'brief_texts\', ()):\n            for label, field in idea_chat.extract_brief_creation(\n                    text, extra_labels=lock_labels, include_extra=True).items():\n                lock_fields.setdefault(label, field)\n        attachment_fields.update(lock_fields)\n    from script_contract import PRODUCTION_LOCK_DEFINITIONS\n    configured_locks = stage_config.workflow_lock(self.root)\n    attachment_fields.update({item[\'label\']: configured_locks[item[\'key\']]\n        for item in PRODUCTION_LOCK_DEFINITIONS if configured_locks.get(item[\'key\'])})\n    missing = () if continuing else idea_chat.inline_required_missing(None, value,\n                                                attachment_fields=attachment_fields,\n                                                stage=\'script\', lock_definitions=lock_definitions,\n                                                created_at=stage_config.project_created_at(self.root))\n    if missing:\n        notice = idea_chat.BRIEF_ATTACHMENT_NOTICE + \'\\n\' if prepared and prepared[\'attachments\'].get(\'brief_unreadable\') else \'\'\n        self.show_missing_idea_brief(missing, attachment_fields, notice)\n        return\n    if prepared is None:\n        return\n    submission=prepared[\'submission\']\n    visible_value=prepared[\'visible_value\']\n    if direct_model and self.idea_chat_controller.requesting:\n        raise ValueError(\'模型正在回复，请不要重复发送。\')\n    # UI 故事字段与阶段锁门禁通过后仍核验底层四项契约；缺项只提示，不启动模型。\n    brief = {\'missing\': ()} if continuing else idea_chat.receive_brief(self.idea_chat_context(), submission, workflow=workflow_config,\n                                    lock_definitions=lock_definitions, gateway=self.idea_chat_gateway(),\n                                    attachment_reference=prepared[\'attachments\'], inline_text=value, stage=\'script\',\n                                    created_at=stage_config.project_created_at(self.root))\n    if brief[\'missing\']:\n        self.notifier.info((brief.get(\'attachment_notice\', \'\') + \'\\n\' + brief[\'followup\']).strip(), modal=True)\n        return\n    if brief.get(\'workflow_projection\') is not None:\n        stage_config.put_workflow(self.root, brief[\'workflow_projection\'])\n    request_model = writing_api.capture_request(self.root)\n    direct_model = request_model[\'label\']\n    if direct_model:\n        model = direct_model\n        cleared = False\n    else:\n        model, cleared = request_model[\'settings\'][\'display_model\'], False\n    self.idea_chat_controller.mark_sent()\n    if not direct_model:\n        # 启动失败不能吞掉用户刚输入的内容；成功启动后才落聊天记录并清空编辑框。\n        try:model, cleared = self.start_script_workflow(submission, config=request_model[\'settings\'])\n        except Exception:\n            self.idea_chat_controller.rollback_sent()\n            raise\n    if not continuing:\n        idea_chat.save_brief_creation(self.idea_chat_context(), value, gateway=self.idea_chat_gateway())\n    idea_chat.append(self.idea_chat_context(),\'user\',visible_value,model=model,gateway=self.idea_chat_gateway(),\n                     skill_injection=request_model[\'settings\'][\'skill_injection\'])\n    # 本次发送已确定模型，废弃旧的异步解析并用同一分区显示刚保存的消息。\n    self._idea_view_model_request=getattr(self,\'_idea_view_model_request\',0)+1\n    self._idea_view_model_cache=(self.root,model)\n    if self.stage_button is not None and self.stage_button.winfo_exists():\n        self.stage_button.configure(text=ui_plugin_registry.module(\'skill_panel\').stage_button_label(self,\'script\'))\n    box.delete(\'1.0\',\'end\')\n    self.discard_idea_draft()\n    self.idea_attachment_paths=()\n    self.update_idea_attachment_status()\n    self.show_conversation()\n    prefix = \'已打开 \'+model+\' 的独立对话；\' if cleared else \'\'\n    if direct_model:\n        project = self.root\n        token, cancelled = self.idea_chat_controller.begin_request(cancellable=True)\n        async_ticket={\'value\':None}\n        if getattr(self,\'idea_send\',None) is not None:self.idea_send.state([\'disabled\'])\n        self.update_script_interrupt_button()\n        self.show_thinking(model)\n        def received(result):\n            from writing_api import preparation_reply_message\n            if not self.idea_chat_controller.finish_request(token):return\n            if getattr(self,\'idea_send\',None) is not None and self.idea_send.winfo_exists():self.idea_send.state([\'!disabled\'])\n            self.update_script_interrupt_button()\n            self.clear_thinking()\n            visible_reply = str(result.get(\'response_text\') or result.get(\'text\') or \'\')\n            self.show_script_quality(result)\n            if visible_reply.strip():\n                idea_chat.append(self.idea_chat_context(),\'assistant\',visible_reply,model=model,gateway=self.idea_chat_gateway(),\n                                 context_budget=result.get(\'context_budget\'), request_usage=result.get(\'request_usage\'),\n                                 skill_injection=request_model[\'settings\'][\'skill_injection\'])\n                self.show_conversation()\n            if not result.get(\'ok\'):\n                error=str(result.get(\'error\') or \'未收到模型回复\')\n                kind=(\'budget\' if result.get(\'reason\') == \'context_budget_exceeded\'\n                      else str(result.get(\'kind\') or \'\'))\n                if kind in (\'network\', \'server\'):\n                    message=\'模型暂时无法响应，请稍后重试\'\n                elif kind in (\'auth\', \'budget\', \'client\', \'\'):\n                    message=\'模型调用未完成：\'+error\n                else:\n                    message=\'系统内部错误，已记录日志\'\n                if kind not in (\'auth\', \'budget\', \'client\', \'\'):\n                    LOGGER.warning(\'模型调用失败（kind=%s）：%s\', kind or \'missing\', error)\n                self.status.set(preparation_reply_message(result) or message)\n                if result.get(\'reason\') == \'context_budget_exceeded\' or \'上下文超过\' in error or \'超过模型上下文\' in error:\n                    self.notifier.error(message, title=\'请求校验未通过\')\n                else:\n                    self.notifier.error(message, title=\'模型调用失败\')\n                # 直接 API 模型与桌面 Agent 共用“剧本准备”这个自动阶段。\n                # 失败若只写状态栏，三虎会一直把 script 视为 active；仅当\n                # 自动链确实正在等待 script 时，才把可恢复的调用失败交给它。\n                auto=getattr(getattr(self,\'pet\',None),\'auto\',None)\n                if getattr(auto,\'active\',None)==\'script\':\n                    # 直连 API 的失败已经是终态；再让通用 Agent 重试只会留下\n                    # 一个没有新请求的 retrying 状态。因此直接发出终态失败，\n                    # 明确停在可由用户重试的剧本阶段。\n                    self.pet._emit(\'stage.failed\',stage=\'script\',error=message)\n                return\n            reply=str(result.get(\'text\') or \'\').strip()\n            if not reply:\n                self.notifier.error(idea_chat.why_empty(result), title=\'模型调用失败\')\n                self.status.set(idea_chat.why_empty(result));return\n            self.show_conversation();self.update_script_download_button()\n            if result.get(\'preparation_path\'):\n                refresh=getattr(self,\'refresh_script_list\',None)\n                if callable(refresh):refresh()\n                self.status.set(preparation_reply_message(result) or (result[\'preparation_stage\']+\'已保存，请审阅后回复“确认”；需要修改请直接说明。\'))\n                return\n            if result.get(\'script_raw_path\'):\n                refresh=getattr(self,\'refresh_script_list\',None)\n                if callable(refresh):refresh()\n                if result.get(\'quality_passed\') is not False:\n                    self.pet_report(\'script\', script_raw_saved_notice(result.get(\'natural_script_path\', \'\')))\n            if result.get(\'quality_summary\'):\n                self.show_script_quality(result)\n                return\n            if result.get(\'natural_script_path\'):\n                self.status.set(preparation_reply_message(result) or (\'自然剧本已自动保存：\'+result[\'natural_script_path\']))\n            else:\n                self.status.set(\'已收到 \'+model+\' 的回复；完整剧本可下载保存。\')\n        def ask():\n            from stage_execution_service import reply_to_writing\n            return reply_to_writing(\n                project, submission, user_message=value, request_model=request_model,\n                cancelled=cancelled.is_set)\n        self.submit_idea_api_request(project, token, cancelled, ask, received,\n                                     model+\' 模型正在思考…\', async_ticket)\n    else:\n        self._script_agent_launching=True\n        self.update_script_interrupt_button()\n        self.status.set(prefix+\'已提交创意并启动剧本 Agent；模型回复完整剧本后可下载保存。\')\n    self.update_script_download_button()\n'

RESULTS = (
    {'ok': True, 'text': '剧本', 'response_text': '可见回复'},
    {'ok': True, 'text': ''},
    {'ok': True, 'text': 'x', 'preparation_path': 'p', 'preparation_stage': '大纲'},
    {'ok': True, 'text': 'x', 'script_raw_path': 'r', 'natural_script_path': 'n'},
    {'ok': True, 'text': 'x', 'script_raw_path': 'r', 'quality_passed': False, 'quality_summary': 'q'},
    {'ok': True, 'text': 'x', 'natural_script_path': 'n', 'prep_msg': '准备好了'},
    {'ok': False, 'error': 'e', 'kind': 'network'},
    {'ok': False, 'error': 'e', 'kind': 'auth'},
    {'ok': False, 'error': '超过模型上下文', 'kind': 'weird'},
    {'ok': False, 'error': 'e', 'reason': 'context_budget_exceeded'},
)


class _Rec:
    def __init__(self, log, name, **attrs):
        self._log, self._name = log, name
        self.__dict__.update(attrs)

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        return lambda *a, **k: (self._log.append((self._name + '.' + name, a, sorted(k))), True)[1]


class _Host:
    def __init__(self, log, finished=True, auto='script'):
        self.log = log
        self.root = 'P'
        self.stage_button = None
        self._idea_view_model_request = 0
        self.idea_input = _Rec(log, 'box')
        self.idea_send = _Rec(log, 'send')
        self.status = _Rec(log, 'status')
        self.notifier = _Rec(log, 'notifier')
        self.pet = _Rec(log, 'pet', auto=_Rec(log, 'auto', active=auto))
        self.idea_chat_controller = _Rec(
            log, 'ctl', requesting=False,
            prepare_submission=lambda *a, **k: {'attachments': {}, 'submission': 'S', 'visible_value': 'V'},
            begin_request=lambda **k: ('T', threading.Event()),
            finish_request=lambda token: (log.append(('finish', token)), finished)[1])
        self.captured = []

    # 宿主替身挂上被测类里的同名方法：新实现拆出的方法要真的执行，不能被兜底记账吞掉。
    _idea_api_received = getattr(module.IdeaChatMixin, '_idea_api_received', None)

    def draft_text(self):
        return '创意'

    def submit_idea_api_request(self, project, token, cancelled, ask, received, label, ticket):
        self.log.append(('submit', project, token, label, ticket))
        self.captured.append(received)

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        return lambda *a, **k: (self.log.append((name, a, sorted(k))), None)[1]


def _record(log, name):
    return lambda *a, **k: (log.append((name, a, sorted(k))), None)[1]


def _session(fn, result, **host_kw):
    log = []
    host = _Host(log, **host_kw)
    model = {'label': 'M', 'settings': {'display_model': 'M', 'skill_injection': 'inj'}}
    with mock.patch.object(writing_api, 'capture_request_model', return_value=model), \
            mock.patch.object(writing_api, 'capture_request', return_value=model), \
            mock.patch.object(writing_api, 'preparation_continuation', return_value=True), \
            mock.patch.object(writing_api, 'preparation_reply_message', side_effect=lambda r: r.get('prep_msg')), \
            mock.patch.object(workflow_settings, 'validate_selected_skills', _record(log, 'validate')), \
            mock.patch.object(stage_config, 'current_workflow', return_value={}), \
            mock.patch.object(stage_config, 'workflow_lock', return_value={}), \
            mock.patch.object(stage_execution_service, 'stage_idea_brief_defaults', return_value={'values': {}}), \
            mock.patch.object(idea_chat, 'append', _record(log, 'append')), \
            mock.patch.object(idea_chat, 'save_brief_creation', _record(log, 'save_brief')), \
            mock.patch.object(idea_chat, 'why_empty', return_value='空回复'), \
            mock.patch.object(module.LOGGER, 'warning', _record(log, 'warn')):
        fn(host)
        for received in host.captured:
            received(dict(result))
    return [repr(item) for item in log]


class SendMessageEquivalence(unittest.TestCase):
    def test_matches_legacy(self):
        old = legacy(module, LEGACY, 'send_message')
        for result in RESULTS:
            for kw in ({}, {'finished': False}, {'auto': None}):
                with self.subTest(result=result, host=kw):
                    self.assertEqual(_session(module.IdeaChatMixin.send_message, result, **kw),
                                     _session(old, result, **kw))


if __name__ == '__main__':
    unittest.main()
