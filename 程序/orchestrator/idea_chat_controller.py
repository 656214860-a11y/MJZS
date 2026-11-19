"""剧本准备对话的无 Tk 控制状态与回调编排。"""
import queue
import threading
import time
from enum import Enum
from pathlib import Path

import infra.executors as executors


BUBBLE_COLLAPSE_CHARS = 360
BUBBLE_COLLAPSE_LINES = 8
# 首绘后回填：``fit_pending`` 连续这么多拍为假才算布局稳定；最长等这么多秒，超时直接回填。
IDEA_UPDATE_STABLE_TICKS = 3
IDEA_UPDATE_TIMEOUT_SECONDS = 2.0


class ChatStatus(str, Enum):
    """会话级状态机（借鉴 AI SDK ``submitted/streaming/ready/error``）。

    与 part 级子状态（``domain.message_parts.PartState``）解耦：本状态只说「整轮
    对话进行到哪」，part 状态说「单个 part 的子阶段」。停止走取消令牌；``max_tokens``
    或用户停止后置 ``can_continue``，供「继续生成」复用。
    """

    SUBMITTED = 'submitted'
    STREAMING = 'streaming'
    READY = 'ready'
    ERROR = 'error'


class DeferredFill:
    """首绘后「布局稳定」判定：每拍问一次 ``ready``，Tk 只管用 ``after`` 排下一拍。

    时钟注入，测试不必真等；一个实例对应一次页面进入。
    """

    def __init__(self, clock=time.monotonic, *, ticks=IDEA_UPDATE_STABLE_TICKS,
                 timeout=IDEA_UPDATE_TIMEOUT_SECONDS):
        self._clock = clock
        self._ticks = ticks
        self._deadline = clock() + timeout
        self._stable = 0

    def ready(self, fit_pending):
        """本拍之后是否该回填：连续稳定够拍数，或已超时。"""
        self._stable = 0 if fit_pending else self._stable + 1
        return self._stable >= self._ticks or self._clock() >= self._deadline


def bubble_timestamp(at):
    """气泡上面那一行小字：这条是什么时候说的（认不出格式就空着）。"""
    from datetime import datetime
    for shape in ('%Y%m%d_%H%M%S_%f', '%Y%m%d_%H%M%S'):
        try:
            return datetime.strptime(str(at), shape).strftime('%m-%d %H:%M')
        except (ValueError, TypeError):
            continue
    return ''


def collapse_preview(text, *, chars=BUBBLE_COLLAPSE_CHARS, lines=BUBBLE_COLLAPSE_LINES):
    """过长的消息先给紧凑预览；完整内容仍在内存和对话 JSON 中。"""
    raw = str(text).strip()
    rows = raw.splitlines()
    if len(raw) <= chars and len(rows) <= lines:
        return raw, False
    preview = '\n'.join(rows[:lines])
    if len(preview) > chars:
        preview = preview[:chars].rsplit('\n', 1)[0]
    return preview.rstrip() + '…', True


def speaker_name(row, *, you='您', prefix='对话AI · ', fallback='AI 助手'):
    """气泡署名：用户自己说话叫「您」，其余按模型名。"""
    if str(row.get('role')) == 'user':
        return you
    return prefix + str(row.get('model') or fallback).strip()


# 模型目录条里「全部」标签对应的过滤键（空串＝不按模型过滤，显示所有模型的记录）。
ALL_MODELS = ''


def model_bar_items(rows):
    """按首次出现顺序返回聊天记录里调用过的模型显示名（去重、去空）。

    首次出现以每条记录的时间戳 ``at``（``%Y%m%d_%H%M%S_%f`` 字符串可直接按字典序比较）
    为准；没有时间戳的旧记录排在有时间戳的之后、按原顺序。
    """
    first = {}
    for row in rows or ():
        if not isinstance(row, dict):
            continue
        name = str(row.get('model') or '').strip()
        if not name:
            continue
        at = str(row.get('at') or '')
        if name not in first or (at and at < first[name]):
            first[name] = at
    def key(name):
        at = first[name]
        return (0, at) if at else (1, '')
    return sorted(first, key=key)


def model_bar_selection(selected, items, current):
    """目录条当前生效的选中项（返回值同时也是过滤键）。

    目录条没有「全部」标签（R2350）：选中项总是某个有记录的模型。
    - 已选模型仍有记录：保持；
    - 未选、选空或已选模型记录清空：回落当前模型，当前模型无记录则取第一个标签；
    - 没有任何标签：返回 ``ALL_MODELS``（显示无署名的旧版记录或示例）。
    """
    items = list(items or ())
    selected = str(selected or '').strip()
    if selected in items:
        return selected
    current = str(current or '').strip()
    if current in items:
        return current
    return items[0] if items else ALL_MODELS


def slot_decision(claimed):
    """进程槽位回执 → 下一步：('run', 槽位) 开工；('wait', 位次) 继续排队；('refuse', 原因) 放弃。"""
    state = claimed.get('state')
    if state == 'granted':
        return 'run', claimed['slot']
    if state == 'queued':
        return 'wait', claimed['position']
    return 'refuse', claimed.get('reason', '模型请求已取消')


def queue_notice(position):
    return '模型请求排队中（第%d位），界面保持响应。' % position


def has_interruptible(api_active, processes, launching, queued):
    """剧本 API 请求、已启动进程、启动中、排队中任一存在，才有东西可中断。"""
    return bool(api_active or processes or launching or queued)


def interrupt_notice(stopped, api_active, cancellation_text=''):
    """中断完成后的状态栏文字；``stopped`` 是已结束的进程号。"""
    detail = ('，已结束进程 ' + ', '.join(stopped)) if stopped else ''
    notice = (' ' + cancellation_text) if cancellation_text else ''
    preserved = '已返回正文会归档到 responses/ 供核对；' if api_active else ''
    return ('已中断剧本 Agent 调用' + detail + '；' + preserved
            + '本机不再把这次回复写入界面或正式采用，可修改创意后重新发送。' + notice)


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
        self._request_cleanup = None
        self.status = ChatStatus.READY
        self.stop_reason = ''
        self.can_continue = False
        self._pending_sends = []
        self._last_request = None
        self._side_effects_done = False

    def prepare_submission(self, project, value, *, is_example):
        """按既有附档规则拼装模型输入和用户可见的引用标记。"""
        if self.attachment_preparing:
            raise ValueError('附档正在入库和校验，请完成后再发送。')
        from stage_execution_service import stage_idea_attachment_reference
        attachments = stage_idea_attachment_reference(project, value, self.attachment_paths)
        visible = value.strip()
        if not visible and not attachments['context']:
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

    def begin_request(self, *, cancellable, request=None):
        if self.requesting:
            raise ValueError('模型正在回复，请不要重复发送。')
        token = object()
        self.requesting = True
        self.script_agent_launching = False
        self._active_token = token
        self.cancel_event = threading.Event() if cancellable else None
        self.status = ChatStatus.SUBMITTED
        self.stop_reason = ''
        self.can_continue = False
        self._side_effects_done = False
        if request is not None:
            self._last_request = dict(request)
        return token, self.cancel_event

    def mark_streaming(self, token=None):
        """首个增量到达：SUBMITTED → STREAMING。过期 token 不推进状态。"""
        if self.requesting and (token is None or token is self._active_token):
            self.status = ChatStatus.STREAMING
            return True
        return False

    def finish_request(self, token, *, error=False, stop_reason=''):
        if token is not self._active_token:
            return False
        self.requesting = False
        self._active_token = None
        self.cancel_event = None
        self._cleanup_request()
        self.stop_reason = str(stop_reason or ('error' if error else ''))
        self.status = ChatStatus.ERROR if error else ChatStatus.READY
        self.can_continue = self.stop_reason == 'max_tokens'
        return True

    def request_is_current(self, token):
        return self.requesting and token is self._active_token

    def accepts(self, token, cancelled, current_root, project):
        """这次请求的结果还算数吗：仍是当前请求、未取消、仍在发起它的项目里。"""
        return self.request_is_current(token) and not cancelled.is_set() and current_root == project

    def set_request_cleanup(self, token, cleanup):
        if not self.request_is_current(token):
            cleanup()
            return
        self._request_cleanup = cleanup

    def _cleanup_request(self):
        cleanup, self._request_cleanup = self._request_cleanup, None
        if cleanup is not None:
            cleanup()

    def cancel_request(self):
        if self.cancel_event is not None:
            self.cancel_event.set()
        self.requesting = False
        self.script_agent_launching = False
        self.cancel_event = None
        self._active_token = None
        self.status = ChatStatus.READY
        self.stop_reason = 'cancelled'
        self.can_continue = True
        self._cleanup_request()

    def progress_callback(self, token, ticket, emit):
        """工作线程只经注入队列投递；取消后的旧流式进度直接丢弃。"""
        def report(role, step):
            if token is self._active_token:
                self.mark_streaming(token)
                emit(ticket, str(role), int(step))
        return report

    # ---- 发送排队：生成中发送自动排队、可撤销、turn 结束 flush（A7）----
    def enqueue_send(self, text, *, attachments=None):
        self._pending_sends.append({'text': str(text), 'attachments': tuple(attachments or ())})
        return len(self._pending_sends)

    def pending_sends(self):
        return [dict(item) for item in self._pending_sends]

    def pop_pending_send(self):
        """取出队首待发消息（turn 结束 flush 时逐条消费）。"""
        return self._pending_sends.pop(0) if self._pending_sends else None

    def undo_pending_send(self):
        """撤销最后一条排队消息。"""
        return self._pending_sends.pop() if self._pending_sends else None

    def clear_pending_sends(self):
        self._pending_sends.clear()

    # ---- 继续 / 重新生成（基于最近一次请求的复用计划）----
    def last_request(self):
        return dict(self._last_request) if isinstance(self._last_request, dict) else None

    def regenerate_plan(self):
        """重新生成：复用最近一次请求（同一消息重发）；没有可复用请求时返回 None。"""
        return self.last_request()

    def continue_plan(self, *, partial_text=''):
        """继续生成：复用最近一次请求，并把已产出的部分文本作为续写前缀。"""
        plan = self.last_request()
        if plan is None or not self.can_continue:
            return None
        plan = dict(plan)
        plan['partial'] = str(partial_text or '')
        return plan

    # ---- 副作用幂等：中断恢复时不重复执行（A5）----
    def mark_side_effects_done(self):
        self._side_effects_done = True

    def side_effects_done(self):
        return self._side_effects_done

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
                from stage_execution_service import archive_idea_attachments, prepare_idea_attachment_selection
                archived = archive_idea_attachments(root, selected)
                prepared = prepare_idea_attachment_selection(root, archived)
                self._attachment_results.put((token, True, prepared))
            except (OSError, ValueError) as exc:
                self._attachment_results.put((token, False, str(exc)))
        executors.submit('io', work, label='idea-attachment-prep')
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

    def delete_attachment(self, project, path):
        """只回收当前项目的入库副本，成功后同步移除待提交引用。"""
        if self.attachment_preparing or self.requesting or self.script_agent_launching:
            raise ValueError('附档处理或模型请求进行中，请完成后再删除。')
        from stage_execution_service import stage_idea_attachment_paths
        from infra.storage_maintenance import recycle_paths
        from domain.idea_attachments import archive_pair
        path = Path(path)
        # 模型切换会改变列表优先展示的副本；原件与转换稿仍属于同一份归档。
        if not any(path in archive_pair(uploaded) for uploaded in stage_idea_attachment_paths(project)):
            raise ValueError('文件不在当前项目的已上传列表中，请刷新后重试。')
        pair = tuple(dict.fromkeys(archive_pair(path)))
        if not recycle_paths(project, pair, '删除创意附档'):
            raise OSError('附档未能移入回收站，请刷新后重试。')
        self.attachment_paths = tuple(value for value in self.attachment_paths if Path(value) not in pair)
        self.attachment_details = tuple(item for item in self.attachment_details if item[0] not in {p.name for p in pair})

    def unreference_attachment(self, path):
        """只取消本轮引用：不动项目里的入库副本（输入框 @ 行右键「取消引用」用，R3060）。"""
        from domain.idea_attachments import archive_pair
        pair = tuple(dict.fromkeys(archive_pair(Path(path))))
        self.attachment_paths = tuple(value for value in self.attachment_paths if Path(value) not in pair)
        self.attachment_details = tuple(item for item in self.attachment_details if item[0] not in {p.name for p in pair})
