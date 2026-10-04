"""剧本准备对话的无 Tk 控制状态与回调编排。"""
import queue
import threading
import time


class IdeaChatController:
    """保存对话请求、发送节流与附档引用，不持有任何 Tk 控件。"""

    SEND_DEBOUNCE_SECONDS = 0.3

    def __init__(self, *, clock=time.monotonic):
        self._clock = clock
        self.requesting = False
        self.script_agent_launching = False
        self.cancel_event = None
        self.attachment_paths = ()
        self.attachment_details = ()
        self.attachment_preparing = False
        self._attachment_token = None
        self._attachment_results = queue.Queue()
        self._last_sent_at = float('-inf')
        self._active_token = None

    def prepare_submission(self, project, value, *, is_example):
        """按既有附档规则拼装模型输入和用户可见的引用标记。"""
        if self.attachment_preparing:
            raise ValueError('附档正在入库和校验，请完成后再发送。')
        from stage_execution_service import stage_idea_attachment_reference
        attachments = stage_idea_attachment_reference(project, value, self.attachment_paths)
        visible = value.strip()
        if (not visible and not attachments['context']) or is_example:
            return None
        submission = visible
        if attachments['context']:
            submission = (submission + '\n\n' if submission else '') + attachments['context']
        if attachments['names']:
            visible = (visible + '\n【已引用：%s】' % '、'.join(attachments['names'])).strip()
        return {'submission': submission, 'visible_value': visible or '【已提交附档】',
                'attachments': attachments}

    def mark_sent(self):
        now = self._clock()
        if now - self._last_sent_at < self.SEND_DEBOUNCE_SECONDS:
            raise ValueError('发送过于频繁，请稍后再试。')
        self._last_sent_at = now

    def rollback_sent(self):
        """仅在尚未真正提交工作流时撤销本次发送占位。"""
        self._last_sent_at = float('-inf')

    def begin_request(self, *, cancellable):
        if self.requesting:
            raise ValueError('模型正在回复，请不要重复发送。')
        token = object()
        self.requesting = True
        self.script_agent_launching = False
        self._active_token = token
        self.cancel_event = threading.Event() if cancellable else None
        return token, self.cancel_event

    def finish_request(self, token):
        if token is not self._active_token:
            return False
        self.requesting = False
        self._active_token = None
        self.cancel_event = None
        return True

    def cancel_request(self):
        if self.cancel_event is not None:
            self.cancel_event.set()
        self.requesting = False
        self.script_agent_launching = False
        self.cancel_event = None
        self._active_token = None

    def progress_callback(self, token, ticket, emit):
        """工作线程只经注入队列投递；取消后的旧流式进度直接丢弃。"""
        def report(role, step):
            if token is self._active_token:
                emit(ticket, str(role), int(step))
        return report

    def replace_attachments(self, paths, details=()):
        self.attachment_paths = tuple(str(path) for path in paths)
        self.attachment_details = tuple(details or ())
        return self.attachment_paths

    def add_attachment(self, path):
        value = str(path)
        if value not in self.attachment_paths:
            self.attachment_paths += (value,)
        return self.attachment_paths

    def start_attachment_preparation(self, root, paths):
        """后台完成入库与内容校验；结果由 Tk 主线程轮询消费。"""
        if self.attachment_preparing:
            raise ValueError('附档正在入库和校验，请稍候。')
        token = object()
        self.attachment_preparing = True
        self._attachment_token = token
        selected = tuple(paths or ())
        def work():
            try:
                import idea_attachments
                from stage_execution_service import archive_idea_attachments
                archived = archive_idea_attachments(root, selected)
                prepared = idea_attachments.prepare(archived)
                self._attachment_results.put((token, True, prepared))
            except (OSError, ValueError) as exc:
                self._attachment_results.put((token, False, str(exc)))
        threading.Thread(target=work, daemon=True).start()
        return token

    def poll_attachment_preparation(self):
        """返回最近一次附件任务结果；过期任务永远不覆盖当前选择。"""
        try:
            token, ok, value = self._attachment_results.get_nowait()
        except queue.Empty:
            return None
        if token is not self._attachment_token:
            return None
        self.attachment_preparing = False
        self._attachment_token = None
        if ok:
            self.replace_attachments(value['paths'], value.get('details', ()))
        return {'ok': ok, 'value': value}

    def clear_attachments(self):
        self.attachment_paths = ()
        self.attachment_details = ()
