# -*- coding: utf-8 -*-
"""初步分镜直连 API 的界面胶水（L4，REQ-S03-53）：起后台作业，进度经队列回到 Tk 主线程播报。"""
import queue


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
        host.status.set('初步分镜直连完成：成功 %d 集，失败 %d 集。'%(len(done),len(failed)))
        pet=getattr(host,'pet',None)
        if failed and not done and pet is not None and getattr(getattr(pet,'auto',None),'active',None)=='storyboard':
            pet._emit('stage.failed',stage='storyboard',error='；'.join(r['error'] for r in failed))
    scripts=selected_many(host.root,'script');boards=selected_many(host.root,'storyboard')
    state['job']=launch(host.root,config,skill_prompt(config,'storyboard',inline=True),
                        scripts=scripts,existing=boards,report=messages.put)
    host.status.set('正在直连 API 制作初步分镜（后台进行，可点「强制停止制作」中断）…')
    host.win.after(500,drain)
