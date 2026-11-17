# -*- coding: utf-8 -*-
"""跨页复用的麦克风听写组件（语音输入离线化任务书轮 3，从 ``desktop_writing_page.VoiceInput`` 提炼）。

REQ-S01-71：打开后边说边把文字写到绑定输入框的光标处，再点一下关闭。录音线程每
0.1 秒把 PCM 交给 ``speech_api.create_session`` 返回的会话——离线 FunASR 子进程
或云端实时由 ``data/语音识别.json`` 的 ``backend`` 决定；服务端按停顿断句：当前句
中间结果以浅色写在光标处、随结果替换，整句定稿后恢复正常颜色。关麦后等最后一句
定稿再结束（最多 ``timeout`` 秒）。

会话不走 ``Desktop.async_()``（新票号会作废正在运行的请求），而用本组件自己的
``BackgroundTaskLifecycle`` 登记代次；输入框销毁时停录并取消，迟到事件不进界面。
``status`` 接受带 ``.set()`` 的 StringVar 或可调用对象；``listening_style``／
``idle_style`` 让宿主按自身按钮样式给「听写中」高亮。
"""
from __future__ import annotations

import time
import tkinter as tk

import infra.app_logging as app_logging
from ui_tokens import COLORS, VOICE_POLL_MS


class VoiceInput:
    """麦克风听写开关：绑定一个 Text 输入框与一颗按钮，状态写到 ``status``。"""

    LISTENING_STYLE, IDLE_STYLE = 'Tokens.Composer.Send.TButton', 'Tokens.Composer.Icon.TButton'
    SILENCE_PEAK, SILENCE_HINT_SECONDS, LEVEL_BARS = 300, 3, 5
    PARTIAL_TAG = 'voice_partial'

    def __init__(self, box, button, *, status=None, listening_style=None, idle_style=None,
                 project=None):
        self.box, self.button = box, button
        self._status = status
        self.project = project
        if listening_style:
            self.LISTENING_STYLE = listening_style
        if idle_style:
            self.IDLE_STYLE = idle_style
        from desktop_automation_service import BackgroundTaskLifecycle
        self.recorder, self.session, self.settings, self.pending, self.ticket = None, None, None, None, None
        self.spans, self.deadline, self.serial, self.notice = {}, None, 0, None
        self.tasks = BackgroundTaskLifecycle()
        self._dictated, self._ai_ticket, self._ai_after = [], None, None
        box.tag_configure(self.PARTIAL_TAG, foreground=COLORS['text_muted'])
        box.bind('<Destroy>', lambda event: self.stop() if event.widget is box else None, add='+')

    def _say(self, text):
        status = self._status
        try:
            if status is None:
                return
            setter = getattr(status, 'set', None)
            if callable(setter):
                setter(str(text))
            elif callable(status):
                status(str(text))
        except Exception:
            app_logging.swallowed()

    @property
    def listening(self):
        return self.recorder is not None

    @property
    def closing(self):
        return self.session is not None and self.recorder is None

    def toggle(self):
        if self.closing:
            self._say('正在写完最后一句，请稍候…')
            return
        if self.listening:
            self.close()
            return
        import contract.platform_tools as platform_tools
        import domain.speech_api as speech_api
        self.settings = speech_api.read_settings()
        reason = speech_api.missing_reason(self.settings)
        if reason:
            self._say('语音输入未能启动（%s）。' % reason)
            return
        session = speech_api.create_session(self.settings)
        recorder = platform_tools.MicrophoneRecorder(max_seconds=self.settings['max_seconds'], on_chunk=session.send)
        reason = recorder.start()
        if reason:
            self._say('语音输入未能启动（%s）；请检查麦克风连接与 Windows 设置「隐私和安全性 › 麦克风」。' % reason)
            return
        session.start()
        self.ticket = self.tasks.submit(object(), costly=True, label='语音输入',
                                        timeout=self.settings['max_seconds'] + self.settings['timeout'] + 30)
        self.recorder, self.session, self.spans, self.deadline = recorder, session, {}, None
        self.notice = None
        self._dictated = []
        try:
            self.box.mark_unset('voice_ai_start')
            self.box.mark_set('voice_ai_start', 'insert')
            self.box.mark_gravity('voice_ai_start', 'left')
        except tk.TclError:
            pass
        self.button.configure(style=self.LISTENING_STYLE)
        self.box.focus_force()
        self.poll()

    def close(self):
        """关麦：停录、通知服务端收尾，等最后一句定稿后由 poll 结束会话。"""
        recorder, self.recorder = self.recorder, None
        self.button.configure(style=self.IDLE_STYLE)
        recorder.stop()
        self.session.finish()
        self.deadline = time.monotonic() + self.settings['timeout']
        self._say('麦克风已关闭，正在写完最后一句…')
        if recorder.error:
            self._say('录音中断（%s），正在写完已说的内容…' % recorder.error)

    def write(self, item, text, final):
        """把一句的最新结果写进它在输入框里的位置；新句子从当前光标开始。"""
        box = self.box
        if item not in self.spans:
            self.serial += 1
            marks = ('voice_start_%d' % self.serial, 'voice_end_%d' % self.serial)
            box.mark_set(marks[0], 'insert'); box.mark_gravity(marks[0], 'left')
            box.mark_set(marks[1], 'insert'); box.mark_gravity(marks[1], 'right')
            self.spans[item] = marks
        start, end = self.spans[item]
        box.delete(start, end)
        box.insert(start, text, () if final else (self.PARTIAL_TAG,))
        if final:
            box.mark_unset(start, end); del self.spans[item]
            self._dictated.append(text)
        box.see('insert')

    def poll(self):
        import queue
        self.pending = None
        if not self.box.winfo_exists():
            return self.stop()
        session = self.session
        if session is None:
            return None
        while True:
            try:
                kind, item, text = session.events.get_nowait()
            except queue.Empty:
                break
            if kind in ('partial', 'final'):
                self.notice = None
                self.write(item, text, kind == 'final')
            elif kind == 'log':
                self.notice = text
            elif kind == 'error':
                return self.end(False, '语音输入中断（%s）。' % text)
            elif kind == 'closed':
                return self.end(True, '语音输入已关闭。')
        if self.recorder is not None:
            if self.notice:
                self._say(self.notice)
            elif self.recorder.finished:
                self.close()
            elif self.recorder.seconds >= self.SILENCE_HINT_SECONDS and self.recorder.peak < self.SILENCE_PEAK:
                self._say('没听到声音：请检查麦克风是否静音，以及 Windows 设置「隐私和安全性 › 麦克风」是否允许桌面应用使用麦克风。')
            else:
                bars = min(self.LEVEL_BARS, int(self.recorder.level * self.LEVEL_BARS * 2 + 0.5))
                self._say('正在听写 %d 秒  %s  说完再点麦克风关闭。' % (
                    self.recorder.seconds, '▮' * bars + '▯' * (self.LEVEL_BARS - bars)))
        elif self.deadline is not None and time.monotonic() > self.deadline:
            return self.end(False, '识别服务没有及时返回最后一句，语音输入已关闭。')
        self.pending = self.box.after(VOICE_POLL_MS, self.poll)

    def end(self, succeeded, message):
        """会话结束（正常关闭、出错或超时）：未定稿的浅色文字原样保留为正常文字。"""
        ticket, self.ticket = self.ticket, None
        self.notice = None
        self.stop()
        if not self.tasks.finish(ticket, succeeded=succeeded, error='' if succeeded else message):
            self._say('语音输入已取消。')
            return
        self._say(message)
        if succeeded:
            self._maybe_ai_optimize()

    def _maybe_ai_optimize(self):
        """会话正常关闭后：词典开了 AI 优化且本段听写文本与词典替换后一致才优化。

        定位用会话首尾两个 mark；区域文本与累计 final 不一致（用户中途手动改过）
        就跳过——宁可不优化也不覆盖用户编辑。
        """
        import domain.speech_api as speech_api
        config = (speech_api.read_dictionary().get('ai') or {})
        if not config.get('enabled') or not self._dictated or not self.project:
            return
        box = self.box
        try:
            box.mark_set('voice_ai_end', 'insert')
            box.mark_gravity('voice_ai_end', 'right')
            expected = ''.join(self._dictated)
            region = box.get('voice_ai_start', 'voice_ai_end')
        except tk.TclError:
            return
        if region != expected or not expected.strip():
            self._say('内容已手动改动，未自动优化。')
            return
        self._start_ai_optimize(expected, 'voice_ai_start', 'voice_ai_end', config)

    def _start_ai_optimize(self, text, start, end, config):
        """异步跑一次模板化优化：走 writing_api 适配器（模型池＋计量），结果回写输入框。"""
        import queue
        import threading
        import domain.voice_ai as voice_ai
        import writing_api
        project = self.project
        try:
            chosen, record = writing_api.selected_model(project)
        except Exception:
            chosen, record = '', {}
        if not chosen:
            self._say('未配置文本模型，已跳过 AI 优化。')
            return
        adapter = writing_api._writing_adapter(record, chosen, project=project)
        ticket = self.tasks.submit(object(), costly=True, label='语音AI优化', timeout=90)
        self._ai_ticket = ticket
        results = queue.Queue()

        def work():
            try:
                results.put(voice_ai.optimize_text(
                    text, chat=adapter.chat, model=chosen, config=config))
            except Exception as exc:  # noqa: BLE001
                results.put({'ok': False, 'text': text, 'reason': str(exc)[:160]})

        threading.Thread(target=work, daemon=True).start()

        def poll():
            self._ai_after = None
            if not self.box.winfo_exists():
                return
            try:
                result = results.get_nowait()
            except queue.Empty:
                if self.tasks.accepts(ticket):
                    self._ai_after = self.box.after(120, poll)
                return
            self._ai_ticket = None
            finished = self.tasks.finish(ticket, succeeded=bool(result.get('ok')),
                                         error=result.get('reason') or '')
            if not finished:
                return
            if not result.get('ok'):
                self._say(result.get('reason') or 'AI 优化未完成，已保留原文。')
                return
            optimized = result['text']
            try:
                current = self.box.get(start, end)
            except tk.TclError:
                return
            if current != text:
                self._say('内容已改动，AI 优化结果未写入（原文保留）。')
                return
            self.box.delete(start, end)
            self.box.insert(start, optimized)
            self._say('AI 优化完成。')

        self._ai_after = self.box.after(120, poll)

    def stop(self):
        if self.pending is not None:
            try:
                self.box.after_cancel(self.pending)
            except tk.TclError:
                pass
            self.pending = None
        if self._ai_after is not None:
            try:
                self.box.after_cancel(self._ai_after)
            except tk.TclError:
                pass
            self._ai_after = None
        recorder, session, ticket = self.recorder, self.session, self.ticket
        ai_ticket = self._ai_ticket
        self._ai_ticket = None
        self.recorder, self.session, self.ticket, self.deadline = None, None, None, None
        if recorder is not None:
            recorder.stop()
        if session is not None:
            session.cancel()
        if ticket is not None and self.tasks.accepts(ticket):
            self.tasks.cancel(ticket)
        if ai_ticket is not None and self.tasks.accepts(ai_ticket):
            self.tasks.cancel(ai_ticket)
        try:
            self.box.tag_remove(self.PARTIAL_TAG, '1.0', 'end')
            for marks in self.spans.values():
                self.box.mark_unset(*marks)
            self.button.configure(style=self.IDLE_STYLE)
        except tk.TclError:
            return
        finally:
            self.spans = {}
