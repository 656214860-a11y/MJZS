# -*- coding: utf-8 -*-
"""资产／首帧出图直连的界面胶水（L4，REQ-S05-50／REQ-S08-52）：起后台作业，结束后在 Tk 主线程播报。
图片由既有 watch() 轮询执行状态.json 与批次清单导入，这里只管状态文案。"""


def run_image_direct(host, direct):
    """引擎为 qwen 的资产／首帧出图由程序直连（唯一分流点在 _FlowAgentLaunch.build）。"""
    from image_direct import launch
    state = {}

    def drain():
        job = state['job']
        if job.is_alive():
            host.win.after(500, drain)
            return
        result = job.results[0] if job.results else {'ok': False, 'stopped': False, 'error': job.error}
        if result.get('stopped'):
            text = '图片制作已停止；已出图的会照常导入，其余可重新提交。'
        elif result['ok']:
            text = '图片制作完成：图片将自动导入。'
        else:
            text = '图片制作失败：%s' % result.get('error')
        host.status.set(text)
        if hasattr(host, 'pet_report'):
            host.pet_report('assets', text)

    state['job'] = launch(host.root, {'engine': 'qwen'}, manifest=direct['image'])
    host.status.set('正在后台制作图片（程序直接调用 ComfyUI，可点「强制停止制作」中断）…')
    host.win.after(500, drain)
