"""「运行状况」弹窗（L4）：只读展示 task_center_service 的快照。"""
from __future__ import annotations

import tkinter as tk

import infra.diagnostic_capture as diagnostic_capture
import domain.task_center_service as task_center_service
from ui_widgets import BaseDialog, DescriptionBlock, TextArea, LineInput
from ui_tokens import TEXT_ROWS


def show(desktop):
    """由设置页按钮打开；数据来自桌面当前的后台任务生命周期与诊断记录。"""
    try:
        degradations = diagnostic_capture._state().get('degradations') or []
    except Exception:
        degradations = []
    data = task_center_service.snapshot(getattr(desktop, 'background_tasks', None), degradations,
                                         getattr(desktop, 'task_queue', None),
                                         getattr(desktop, 'retry_registry', None))
    project = getattr(desktop, 'root', None)
    if project is not None:
        from agent.core import read
        from infra.pet_state import state_path
        import orchestrator.stage_parallel as stage_parallel
        from contract.pet_bus import STAGES
        path = state_path(project)
        errors = []
        try:
            saved = read(path) if path.is_file() else {}
            stages = saved.get('stages', {})
            if not isinstance(stages, dict):
                raise ValueError('阶段状态格式错误')
        except (OSError, ValueError, AttributeError) as exc:
            stages = {}
            errors.append('阶段快照读取失败：' + type(exc).__name__)
        gates = {}
        for stage in STAGES:
            try:
                gates[stage] = stage_parallel.evaluate(project, stage, mode=stage_parallel.PRODUCTION)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                gates[stage] = {'ok': False, 'detail': '当前门禁读取失败：' + type(exc).__name__}
        data['project_runtime'] = task_center_service.project_snapshot(project, stage_records=stages, gates=gates)
        data['project_runtime']['errors'].extend(errors)
        from pathlib import Path
        selected = str(Path(project).resolve())
        data['unresolved_execution'] = [row for row in data['unresolved_execution']
                                        if row.get('project') in (None, selected)]
    dialog = BaseDialog(desktop.win, '运行状况', geometry='640x520', minsize=(420, 320))
    query = LineInput(dialog.content, placeholder='镜头/句子/批次/请求号/运行号（留空显示全部尝试）')
    query.pack(fill='x')
    feedback = DescriptionBlock(dialog.content, text='')
    feedback.pack(fill='x')
    text = TextArea(dialog.content, wrap='word', height=TEXT_ROWS['4xl'])
    text.pack(fill='both', expand=True)
    text.insert('1.0', '\n'.join(task_center_service.format_lines(data)))
    text.set_readonly(True)
    def filtered_rows():
        runtime = data.get('project_runtime') or {}
        key = query.get().strip()
        return [row for row in runtime.get('tasks', []) if task_center_service.task_matches(row, key)]

    def focus_error(message):
        query.set_error(message)
        feedback.configure(text=message)

    def filter_attempts():
        query.clear_error()
        feedback.configure(text='')
        view = dict(data)
        if data.get('project_runtime'):
            runtime = dict(data['project_runtime'])
            runtime['tasks'] = filtered_rows()
            view['project_runtime'] = runtime
        text.set_readonly(False)
        text.delete('1.0', 'end')
        text.insert('1.0', '\n'.join(task_center_service.format_lines(view)))
        text.set_readonly(True)

    def open_audio_focus():
        rows = [row for row in filtered_rows() if row.get('stage') == 'audio']
        if not rows:
            focus_error('没有匹配的配音句')
            return
        if len(rows) > 1:
            focus_error('匹配到 %d 句配音，请先用批次、句序或请求号缩小到一句' % len(rows))
            return
        row = rows[0]
        page_of = getattr(desktop, 'page_of', None)
        index = page_of('audio') if callable(page_of) else None
        if index is None:
            focus_error('当前桌面没有配音页入口')
            return
        query.clear_error()
        feedback.configure(text='')
        fields = ('stage', 'state', 'task_id', 'batch', 'version', 'line_index', 'text_preview',
                  'attempt_id', 'cost_request_id', 'operation', 'recovery')
        desktop._tts_recovery_focus = {key: row[key] for key in fields if row.get(key) is not None}
        dialog.close()
        go = getattr(desktop, 'go', None)
        go_page = getattr(desktop, 'go_page', None)
        if callable(go):
            go(index)
        elif callable(go_page):
            go_page(index)
        else:
            desktop.show(index)
    dialog.add_action('查询尝试', filter_attempts)
    dialog.add_action('打开配音页定位', open_audio_focus)
    query.bind('<Return>', lambda event: filter_attempts())
    if data.get('queued'):
        dialog.add_action('取消全部待执行任务', lambda: (desktop.task_queue.clear(), dialog.close()))
    if data.get('retry_ticket') is not None:
        dialog.add_action('重试最近失败的任务', lambda: (desktop.retry_failed_task(), dialog.close()))
    dialog.add_action('关闭', dialog.close)
    return dialog
