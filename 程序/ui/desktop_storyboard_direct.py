# -*- coding: utf-8 -*-
"""初步分镜直连 API 的界面胶水（L4，REQ-S03-53）：起后台作业，进度经队列回到 Tk 主线程播报。"""
import queue
from pathlib import Path


def _reason_text(result):
    """单条失败 → 「文件名：原因」；整批未启动那条不写文件名；各截 160 字。"""
    text = str(result.get('error') or '')[:160]
    name = Path(str(result.get('source') or '')).name
    return ('%s：%s' % (name, text)) if name else text


def summary_text(results):
    """直连完成的最终状态文字：带失败集的文件名与原因；整批没开工不写「失败 1 集」。"""
    results = list(results or ())
    done = [r for r in results if r.get('ok')]
    failed = [r for r in results if not r.get('ok') and not r.get('stopped')]
    if failed and not done and len(results) == 1 and not str(results[0].get('source') or ''):
        return '初步分镜直连没有启动：' + str(results[0].get('error') or '')[:160]
    head = '初步分镜直连完成：成功 %d 集，失败 %d 集。' % (len(done), len(failed))
    if not failed:
        return head
    lines = [_reason_text(r) for r in failed[:2]]
    if len(failed) > 2:
        lines.append('等 %d 条失败，详见通知和 logs\\app.log' % len(failed))
    return head + '；'.join(lines)


def run_storyboard_direct(host, config):
    """初步分镜直连 API：后台线程执行，进度经队列在 Tk 主线程播报（REQ-S03-53）。"""
    from orchestrator.storyboard_direct_api import launch
    from orchestrator.storyboard_selection import selected_many
    from orchestrator.workflow_settings import skill_prompt
    messages=queue.Queue()
    state={}
    def drain():
        while True:
            try:text=messages.get_nowait()
            except queue.Empty:break
            host.status.set(text)
            if hasattr(host,'pet_report'):host.pet_report('storyboard',text)
        job=state.get('job')
        if job is not None and job.is_alive():host.win.after(500,drain)
        elif job is not None:finish(job)
    def finish(job):
        failed=[r for r in job.results if not r['ok'] and not r.get('stopped')]
        done=[r for r in job.results if r['ok']]
        if any(r.get('stopped') for r in job.results) and not done:
            host.status.set('初步分镜直连已停止，未写入文件。');return
        host.status.set(summary_text(job.results))
        if done:
            panel = getattr(host, 'files_panel', None)
            if panel is not None and callable(getattr(panel, 'fill_script_list', None)):
                panel.fill_script_list()
            page = getattr(host, 'storyboard_editor_page', None)
            if page is not None and callable(getattr(page, 'refresh', None)):
                page.refresh()
        notifier=getattr(host,'notifier',None)
        if failed and notifier is not None:
            notifier.error('；'.join(_reason_text(r) for r in failed), title='初步分镜未完成')
        pet=getattr(host,'pet',None)
        if failed and not done and pet is not None and getattr(getattr(pet,'auto',None),'active',None)=='storyboard':
            pet._emit('stage.failed',stage='storyboard',error='；'.join(r['error'] for r in failed))
    scripts=selected_many(host.root,'script');boards=selected_many(host.root,'storyboard')
    req_text=str(getattr(host,'_storyboard_request_text','') or (config or {}).get('request_text') or '')
    state['job']=launch(host.root,config,skill_prompt(config,'storyboard',inline=True),
                        scripts=scripts,existing=boards,
                        request_text=req_text,
                        report=messages.put)
    host.status.set('正在直连 API 制作初步分镜（后台进行，可点「强制停止制作」中断）…')
    host.win.after(500,drain)
