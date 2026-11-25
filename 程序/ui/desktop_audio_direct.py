# -*- coding: utf-8 -*-
"""配音脚本直连 API 与逐句配音控制的界面胶水（L4，REQ-S11-50 / FIX-S11-E4）。"""
import queue
import threading
import tkinter as tk
from domain.project_naming import dated_path


def run_audio_direct(host, config):
    """配音与字幕阶段选了模型池 API 模型时由程序直连（唯一分流点在 _FlowAgentLaunch.build）。"""
    from orchestrator.audio_direct_api import launch
    from orchestrator.workflow_settings import skill_prompt
    source = host.current_frame_json()
    if not source:
        raise ValueError('还没有选定分镜 JSON，不能直连制作配音脚本。')
    messages = queue.Queue()
    state = {}

    def drain():
        while True:
            try:
                text = messages.get_nowait()
            except queue.Empty:
                break
            host.status.set(text)
            if hasattr(host, 'pet_report'):
                host.pet_report('audio', text)
        job = state.get('job')
        if job is not None and job.is_alive():
            host.win.after(500, drain)
        elif job is not None:
            finish(job)

    def finish(job):
        result = job.results[0] if job.results else {'ok': False, 'stopped': False, 'error': job.error}
        if result.get('stopped'):
            host.status.set('配音脚本直连已停止，未写入文件。')
        elif result['ok']:
            host.status.set('配音脚本直连完成：已写入配音脚本与字幕。')
        else:
            host.status.set('配音脚本直连失败：%s' % result.get('error'))

    state['job'] = launch(host.root, config, skill_prompt(config, 'audio', inline=True), source=source,
                          report=messages.put)
    host.status.set('正在直连 API 制作配音脚本（后台进行，可点「强制停止制作」中断）…')
    host.win.after(500, drain)


def render_recovery_focus(page):
    """把任务中心传来的配音句定位成页内说明；只定位与提示，绝不触发提交。"""
    row = getattr(page, '_tts_recovery_focus', None)
    if not isinstance(row, dict) or row.get('stage') != 'audio':
        return
    page._tts_recovery_focus = None
    from tkinter import ttk
    from ui_tokens import SPACING
    from ui_widgets import Card, DescriptionBlock
    box = Card(page.content)
    box.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
    ttk.Label(box, text='任务中心定位的配音句').pack(anchor='w')
    shot = row.get('task_id') or row.get('shot_id') or '未登记'
    batch = row.get('batch') or row.get('version') or '未登记'
    line = row.get('line_index') or '未知'
    text = row.get('text_preview') or '未登记'
    state = row.get('state') or 'unknown'
    operation = row.get('operation') or row.get('recovery') or '未登记'
    lines = ['批次/版本：%s；第 %s 句；镜头/任务：%s' % (batch, line, shot),
             '台词：%s' % text,
             '恢复状态：%s；请求号：%s；费用请求号：%s' % (
                 state, row.get('attempt_id') or '未登记', row.get('cost_request_id') or '未登记'),
             '下一步：%s' % operation,
             '本次只是打开本页并定位这一句，没有发送任何配音请求。']
    if state == 'reconcile':
        lines.append('结果未知句在人工核对并明确放开前不会被重新提交；不要把它当作确定失败重发。')
    elif state == 'recorded_ready':
        lines.append('这句已有可沿用成品；恢复与续跑不会为它重复扣费。')
    DescriptionBlock(box, text='\n'.join(lines)).pack(anchor='w')
    page.status.set('已定位配音句：%s 第 %s 句；未发送任何请求' % (batch, line))


def run_tts_per_line(page, quote_gate):
    """逐句配音：报价确认、句间停止控制、状态总线进度上屏与收尾按钮恢复。"""
    import domain.tts_api as tts_api
    episode = page.current_episode()
    entries, _estimated = page.dialogue_entries(episode)
    assets = page.dialogue_assets()
    if not entries:
        raise ValueError('当前分镜没有对白，无法生成配音')
    tts_settings = tts_api.read_settings()
    lines = tts_api.build_lines(entries, assets, tts_settings.get('voices'),
                                tts_settings.get('speeds'), settings=tts_settings)
    from contract.project_stages import audio
    folder = audio(page.root) / '配音分句'
    # 同一项目可有多集：把集标识纳入批次指纹，两集同名台词／音色不会共用缓存目录。
    token = (episode.get('episode_id') or episode.get('id')) if isinstance(episode, dict) else None
    out = tts_api.resume_folder(folder, lines, token)
    resumed = out is not None
    out = out or dated_path(folder, '配音批次')
    quote, _pending, early = quote_gate(page, lines, out, tts_settings)
    if early:
        page.status.set(early)
        return
    tip = quote['text']
    if not page.media_page_services.confirm(page.win, '逐句配音（付费）', tip + '\n\n继续提交？', dangerous=True):
        page.status.set('已取消逐句配音：未提交任何句子，也没有产生费用')
        return
    # 逐句进度经状态总线上屏（工作线程安全）；stop 只在句间生效，由 L2 run_lines 判定。
    from ui.ui_status_bus import Message
    stop = threading.Event()
    finished = threading.Event()
    page._tts_lines_stop = stop
    stop_button = getattr(page, '_tts_lines_stop_button', None)
    if stop_button is not None:
        try:
            stop_button.configure(state='normal')
        except tk.TclError:
            pass

    def report(text):
        page.status_bus.publish(Message.make('info', str(text), source='tts_per_line', auto=False))

    def work():
        from stage_execution_service import run_tts_lines
        try:
            ok, reused, failed = run_tts_lines(lines, out, episode=token, project=page.root, report=report, stop=stop)
        finally:
            finished.set()
        if stop.is_set():
            note = f'逐句配音已停止：成功 {ok}/{len(lines)}，失败 {failed}；再次点击会接续本批次'
        else:
            note = f'逐句配音完成：成功 {ok}/{len(lines)}，失败 {failed}'
        if reused:
            note += f'（沿用已生成 {reused} 句，未重复扣费）'
        if resumed:
            note += '；已接续上次未完成的批次'
        return note + f'；目录 {out}'

    def watch():
        # 批次收尾（完成/失败/停止）恢复停止入口；只认自己那一批的 stop，防止误清新批次。
        if not finished.is_set():
            try:
                page.win.after(200, watch)
            except tk.TclError:
                pass
            return
        if getattr(page, '_tts_lines_stop', None) is not stop:
            return
        page._tts_lines_stop = None
        button = getattr(page, '_tts_lines_stop_button', None)
        if button is not None:
            try:
                button.configure(state='disabled')
            except tk.TclError:
                pass

    try:
        page.win.after(200, watch)
    except tk.TclError:
        pass
    try:
        page.async_(work)
    except Exception:
        finished.set()
        raise


def stop_tts_per_line(page):
    """停止逐句配音：只在句与句之间生效，在途的那句跑完后不再提交新句（L2 run_lines 判定）。"""
    stop = getattr(page, '_tts_lines_stop', None)
    if stop is None:
        page.status.set('当前没有正在进行的逐句配音批次')
        return
    stop.set()
    page.status.set('已请求停止逐句配音：当前句完成后不再提交新句')
