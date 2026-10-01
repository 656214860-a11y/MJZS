# -*- coding: utf-8 -*-
"""第三层：次级执行页（第 54 期附件三／五）。

「手动制作XX」那一窗里的「直接执行」落到这一页：本阶段勾上的 SKILL 摆在最上面，下面是
实时进度、日志与失败项；失败项可以「重试失败项」，办完有「返回阶段页面」。

剪辑／交付这两步原来没有自己的制作窗口，第 54 期给它们补的「手动制作剪辑／交付」就把
这一页摆出来——手动与自动共用同一台编排器，只有 trigger 不同（这一页按 'manual'）。
"""
import stage_flow
import skill_orchestrator


def _run_script_structure(desktop, project, names, trigger):
    """Writer 提取、Editor 审校并按反馈返工后，才把结构化正稿写入 script.md。"""
    import script_contract
    from stage_execution_service import build_orchestrator, publish_stage_text, stage_context
    state = {}

    def execute(action, _context):
        if action == 'read_script_raw':
            source = script_contract.resolve_script_source(project)
            if source is None:
                raise ValueError('未找到可读取的剧本原稿，请先在“剧本准备”生成或下载剧本。')
            state['raw'] = source.read_text(encoding='utf-8-sig')
            state['source'] = source
            state['source_name'] = script_contract._source_label(project, source)
            return {'ok': True, 'status': skill_orchestrator.DONE, 'detail': '已读取 ' + state['source_name']}
        if action == 'writer_extract_structure':
            state['structured'] = script_contract.structure_script(state.get('raw', ''), state.get('source_name', script_contract.RAW_SCRIPT_NAME))
            return {'ok': True, 'status': skill_orchestrator.DONE, 'detail': 'Writer 已提取角色、场景、道具和分场'}
        if action == 'editor_review_structure':
            state['review'] = script_contract.review_structured_script(state.get('raw', ''), state.get('structured', ''))
            notes = state['review']['feedback']
            detail = 'Editor 审校通过' if state['review']['approved'] else 'Editor 要求修正：' + '；'.join(notes)
            return {'ok': True, 'status': skill_orchestrator.DONE, 'detail': detail}
        if action == 'writer_revise_structure':
            review = state.get('review') or {'approved': False, 'feedback': ('未完成 Editor 审校。',)}
            if review['approved']:
                return {'ok': True, 'status': skill_orchestrator.DONE, 'detail': 'Editor 已通过，Writer 无需返工'}
            state['structured'] = script_contract.revise_structured_script(
                state.get('raw', ''), review['feedback'], state.get('source_name', script_contract.RAW_SCRIPT_NAME))
            return {'ok': True, 'status': skill_orchestrator.DONE, 'detail': 'Writer 已按 Editor 反馈重新提取'}
        if action == 'editor_final_review':
            review = script_contract.review_structured_script(state.get('raw', ''), state.get('structured', ''))
            if not review['approved']:
                raise ValueError('Editor 复审未通过：' + '；'.join(review['feedback']))
            return {'ok': True, 'status': skill_orchestrator.DONE, 'detail': 'Editor 复审通过，可写入正稿'}
        if action == 'write_structured_script':
            target = script_contract.write_structured_script(
                project, state.get('structured'), state.get('source'), publisher=publish_stage_text)
            return {'ok': True, 'status': skill_orchestrator.DONE, 'detail': '已写入 ' + str(target)}
        raise ValueError('未知剧本结构动作：' + str(action))

    orchestrator = build_orchestrator(desktop, project)
    # 用户从“手动制作”入口启动本阶段，即视为对模板中整理步骤的明确确认。
    return orchestrator.run_stage_with_template('script_structure', stage_context(desktop, 'script_structure'),
                                                names=names, mode='auto', execute_action=execute)

TITLE = '次级执行页'


def failures(run):
    """这一批里没成的那些（失败／缺工具），重试就重试这几个。"""
    rows = list((run or {}).get('results') or [])
    return [row for row in rows
            if row.get('status') in (skill_orchestrator.FAILED, skill_orchestrator.MISSING)]


def progress_text(run):
    """一句话说清这一批：真做完的／要回页面按的／没成的，各几个。"""
    rows = list((run or {}).get('results') or [])
    done = [row for row in rows if row.get('status') == skill_orchestrator.DONE]
    waiting = [row for row in rows
               if row.get('status') in (skill_orchestrator.PAGE, skill_orchestrator.INPUT)]
    return '做完了 %d 个，%d 个要回页面按，没成 %d 个' % (len(done), len(waiting), len(failures(run)))


def run(desktop, stage, only=None, trigger='manual'):
    """（trigger 默认 'manual'：这一页是用户自己在页面上按出来的。）"""
    """跑这一阶段勾上的 SKILL（only 给了就只跑那几个）：返回编排器那份汇总。"""
    project = stage_flow.project_of(desktop)
    if project is None:
        raise ValueError('请先选择项目。')
    names = list(only) if only else stage_flow.selected_skills(project, stage)
    if stage == 'script_structure':
        return _run_script_structure(desktop, project, names, trigger)
    from stage_execution_service import build_orchestrator, stage_context
    orchestrator = build_orchestrator(desktop, project)
    return orchestrator.run(names, stage_context(desktop, stage), trigger=trigger)


def show(desktop, stage, parent=None):
    """把次级执行页摆出来，返回这一页的把手（自检直接读它，不猜控件）。"""
    import tkinter as tk
    from tkinter import ttk
    host = parent if parent is not None else getattr(desktop, 'win', None)
    standalone = host is None
    window = tk.Tk() if standalone else tk.Toplevel(host)
    window.title('执行：' + stage_flow.stage_name(stage))
    if not standalone:
        window.transient(host)
    window.resizable(True, True)
    window.minsize(520, 360)
    body = ttk.Frame(window, padding=10)
    body.pack(fill='both', expand=True)
    ttk.Label(body, text='执行：' + stage_flow.stage_name(stage),
              font=('Microsoft YaHei UI', 11, 'bold')).pack(anchor='w')
    project = stage_flow.project_of(desktop)
    names = stage_flow.selected_skills(project, stage)
    ttk.Label(body, text='本阶段 SKILL：' + ('、'.join(names) if names else '（还没勾上）'),
              style='Muted.TLabel', wraplength=520, justify='left').pack(anchor='w', pady=(4, 0))
    progress = ttk.Label(body, text='还没开始', style='Muted.TLabel')
    progress.pack(anchor='w', pady=(6, 0))
    log = tk.Text(body, height=10, wrap='word')
    log.pack(fill='both', expand=True, pady=(6, 0))
    row = ttk.Frame(body)
    row.pack(fill='x', pady=(6, 0))
    handle = {'window': window, 'stage': stage, 'run': None, 'log': log, 'names': names,
              'failures': [], 'progress': progress}

    def start(only=None):
        try:
            result = run(desktop, stage, only=only)
        except Exception as exc:
            result = {'results': [], 'text': str(exc), 'failed': []}
        handle['run'] = result
        handle['failures'] = [row.get('skill') for row in failures(result)]
        try:
            log.delete('1.0', 'end')
            log.insert('end', str(result.get('text') or result.get('errors') or ''))
        except Exception:
            pass
        progress.configure(text=progress_text(result))
        retry.configure(state='normal' if handle['failures'] else 'disabled')
        return result

    def go_back():
        index = stage_flow.OWN_ORDER.index(stage) if stage in stage_flow.OWN_ORDER else None
        try:
            if index is not None:
                desktop.show(index)
        except Exception:
            pass
        window.destroy()

    retry = ttk.Button(row, text='重试失败项', style='Compact.TButton',
                       command=lambda: start(only=handle['failures']))
    retry.pack(side='left')
    retry.configure(state='disabled')
    ttk.Button(row, text='返回阶段页面', style='Compact.TButton',
               command=go_back).pack(side='left', padx=(6, 0))
    ttk.Button(row, text='关闭', style='Compact.TButton',
               command=window.destroy).pack(side='left', padx=(6, 0))
    handle['retry'] = lambda: start(only=handle['failures'])
    handle['start'] = start
    handle['back'] = go_back
    start()
    if standalone:
        window.mainloop()
    return handle
