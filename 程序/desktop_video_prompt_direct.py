# -*- coding: utf-8 -*-
"""视频提示词直连 API 的界面胶水（L4，REQ-S10-50）：起后台作业，进度经队列回到 Tk 主线程播报。
结果文件写好后由视频页 PromptResults 轮询导入并保存，这里只管状态文案。"""
import queue


def run_video_prompt_direct(host, config, direct):
    """视频页提示词渲染选了模型池 API 模型时由程序直连（唯一分流点在 _FlowAgentLaunch.build）。"""
    from orchestrator.video_prompt_direct_api import launch
    from orchestrator.workflow_settings import skill_prompt
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
                host.pet_report('video', text)
        job = state.get('job')
        if job is not None and job.is_alive():
            host.win.after(500, drain)
        elif job is not None:
            finish(job)

    def finish(job):
        result = job.results[0] if job.results else {'ok': False, 'stopped': False, 'error': job.error}
        if result.get('stopped'):
            host.status.set('视频提示词直连已停止，未写入文件。')
        elif result['ok']:
            host.status.set('视频提示词直连完成：结果将自动导入并保存。')
        else:
            host.status.set('视频提示词直连失败：%s' % result.get('error'))

    state['job'] = launch(host.root, config, skill_prompt(config, 'video_prompt', inline=True),
                          direct=direct, report=messages.put)
    host.status.set('正在直连 API 整理视频提示词（后台进行，可点「强制停止制作」中断）…')
    host.win.after(500, drain)
