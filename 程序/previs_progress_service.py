"""白模预演进度文件的无界面读取与状态映射。"""
import json
import math
from pathlib import Path

from agent.core import save_text
from file_cache import read_json


def publish(path, shot_id, stage, completed=None, total=None):
    """原子发布单镜头的渲染进度。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {'shot_id': shot_id, 'stage': stage}
    if completed is not None and total is not None:
        data.update(completed=completed, total=total)
    save_text(path, json.dumps(data, ensure_ascii=False))


def install_blender_progress(path, shot_id):
    """向 Blender 渲染处理器安装基于真实帧数的进度发布器。"""
    import bpy
    completed = set()

    def started(scene, *args):
        completed.clear()
        publish(path, shot_id, 'render', 0, len(range(scene.frame_start, scene.frame_end + 1, scene.frame_step)))

    def written(scene, *args):
        completed.add(scene.frame_current)
        publish(path, shot_id, 'render', len(completed), len(range(scene.frame_start, scene.frame_end + 1, scene.frame_step)))

    def finished(scene, *args): publish(path, shot_id, 'encoding')
    def cancelled(scene, *args): publish(path, shot_id, 'cancelled')
    for name, handler in [('render_init', started), ('render_write', written), ('render_complete', finished), ('render_cancel', cancelled)]:
        handlers = getattr(bpy.app.handlers, name)
        for old in tuple(handlers):
            if getattr(old, '_drama_progress', False): handlers.remove(old)
        handler._drama_progress = True
        handlers.append(handler)
    publish(path, shot_id, 'scene')


def status_value(state, project, sid, status):
    """将已验证的进度文件转换成界面无关的进度状态。"""
    key = str(project) + '|' + sid
    phase = state.get('progress', {}).get(key)
    if status.startswith('失败'): return ('determinate', 0, '失败')
    if status == '已就绪': return ('determinate', 100, '100%')
    if phase == 'cancelled': return ('determinate', 0, '已停止')
    if phase == 'queued': return ('determinate', 0, '排队')
    if phase == 'validating': return ('indeterminate', 0, '校验视频')
    if phase != 'running' and not (state.get('busy') and '制作中' in status): return None
    path = Path(state.get('log_dir', '')) / (sid + '_进度.json')
    try:
        data = read_json(path)
        if data.get('shot_id') != sid: raise ValueError('镜头不匹配')
        step = data.get('stage')
        if step == 'render':
            done, total = data.get('completed'), data.get('total')
            if isinstance(done, bool) or isinstance(total, bool): raise ValueError('帧数无效')
            if not isinstance(done, (int, float)) or not isinstance(total, (int, float)): raise ValueError('帧数无效')
            if not math.isfinite(done) or not math.isfinite(total) or total <= 0 or done < 0 or done > total: raise ValueError('帧数无效')
            percent = done / total * 100
            return ('determinate', percent, f'渲染 {percent:.0f}%')
        labels = {'scene': '准备场景', 'encoding': '合成视频', 'cancelled': '渲染已停止', 'validating': '校验视频'}
        return ('indeterminate', 0, labels.get(step, 'Agent 制作中'))
    except (OSError, ValueError, AttributeError, TypeError):
        return ('indeterminate', 0, 'Agent 制作中')
