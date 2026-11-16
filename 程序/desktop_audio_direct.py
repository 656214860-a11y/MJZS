# -*- coding: utf-8 -*-
"""配音脚本直连 API 的界面胶水（L4，REQ-S11-50）：起后台作业，进度经队列回到 Tk 主线程播报。"""
import queue


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
