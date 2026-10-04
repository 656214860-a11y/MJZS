"""无人值守资产批量生成的 L3 编排入口。"""
import threading
from pathlib import Path

from asset_batch_execution import run_batch
from asset_batch_service import KINDS, asset_prompt, current_model, unattended_plan
from cloud_assets import LOCAL, MODELS
from comfy_service import Comfy
from project_context_factory import project_context


class _LogEvents:
    def __init__(self, log): self.log = log
    def put(self, text): self.log(str(text))


def auto_batch(project, base, sources, scope='adopted', log=None, stop=None, client_factory=None, gateway=None):
    """不创建 Tk 窗口地执行自动资产生成。"""
    log = log or (lambda text: None)
    project, base = Path(project), Path(base)
    items, skipped, saved = unattended_plan(project, base, sources, scope, gateway=gateway,
                                          context=project_context(project))
    if not items:
        return '无人值守批量资产：没有需要独立生成的资产' + (f'；{len(skipped)} 项资产清单待补齐' if skipped else '')
    url = saved.get('url') or 'http://127.0.0.1:8189'
    stop = stop if stop is not None else threading.Event()
    from importlib import import_module
    native_apps = import_module('native_apps')
    try:
        native_apps.wait_comfy(url, log, timeout=5, cancelled=stop.is_set)
    except ValueError:
        log('本地 ComfyUI 未运行，正在启动…')
        native_apps.open_comfy(); native_apps.wait_comfy(url, log, timeout=120, cancelled=stop.is_set)
    for aid, asset in items: asset_prompt(asset, KINDS[aid.split('_')[0]][0])
    options = {key: saved.get(key, '') for key in ('backend', 'aspect_ratio', 'quality', 'workflow', 'model', 'node', 'field')}
    options['backend'], options['url'] = current_model(project), url
    backend = str(options['backend'] or LOCAL)
    log('本次生图模型：' + backend + ('（云端按次计费，请确认账户余额）' if backend in MODELS else '（本地 ComfyUI，免费）'))
    summary = '无人值守批量资产结束：' + run_batch(project, base, items, options, _LogEvents(log), stop, client_factory or Comfy)
    if skipped:
        detail = '、'.join(aid + ' ' + reason for aid, reason in skipped[:5]) + ('…' if len(skipped) > 5 else '')
        summary += f'；跳过 {len(skipped)} 项（' + detail + '）'
    return summary
