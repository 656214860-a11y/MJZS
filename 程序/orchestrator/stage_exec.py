# -*- coding: utf-8 -*-
"""第三层：次级执行页（第 54 期附件三／五）。

「手动制作XX」那一窗里的「直接执行」落到这一页：本阶段勾上的 SKILL 摆在最上面，下面是
实时进度、日志与失败项；失败项可以「重试失败项」，办完有「返回阶段页面」。

剪辑／交付这两步原来没有自己的制作窗口，第 54 期给它们补的「手动制作剪辑／交付」就把
这一页摆出来——手动与自动共用同一台编排器，只有 trigger 不同（这一页按 'manual'）。
"""
import stage_flow
import skill_orchestrator


# L4 在应用组合时注入窗口构造；本层只保留执行结果和重试语义。
_EXECUTION_PRESENTER = None


def set_execution_presenter(presenter):
    """登记 L4 执行页呈现器，避免阶段编排层反向依赖 UI 组件。"""
    global _EXECUTION_PRESENTER
    _EXECUTION_PRESENTER = presenter


def install_ui_presenters(execution_presenter, plan_presenter, confirmation_presenter):
    """由 L4 组合根一次安装阶段窗口与确认呈现器。"""
    import stage_models
    set_execution_presenter(execution_presenter)
    stage_models.set_plan_window_presenter(plan_presenter)
    stage_models.set_confirmation_presenter(confirmation_presenter)


def _run_script_structure(desktop, project, names, trigger):
    """本地规则提取、规则校验并按反馈重提取后，才把结构化正稿写入 script.md（不调用模型）。"""
    import contract.script_contract as script_contract
    from stage_execution_service import build_orchestrator, publish_stage_text, stage_context
    state = {}

    def execute(action, _context):
        if action == 'read_script_raw':
            source = script_contract.resolve_script_source(project)
            if source is None:
                raise ValueError('未找到可读取的剧本原稿，请先在“剧本准备”生成或添加剧本。')
            state['raw'] = source.read_text(encoding='utf-8-sig')
            state['source'] = source
            state['source_name'] = script_contract._source_label(project, source)
            return {'ok': True, 'status': skill_orchestrator.DONE, 'detail': '已读取 ' + state['source_name']}
        if action == 'writer_extract_structure':
            state['structured'] = script_contract.structure_script(state.get('raw', ''), state.get('source_name', script_contract.RAW_SCRIPT_NAME))
            return {'ok': True, 'status': skill_orchestrator.DONE, 'detail': '规则提取完成：角色、场景、道具和分场（本地规则，未调用模型）'}
        if action == 'editor_review_structure':
            state['review'] = script_contract.review_structured_script(state.get('raw', ''), state.get('structured', ''))
            notes = state['review']['feedback']
            detail = ('规则校验通过（未调用模型）' if state['review']['approved']
                      else '规则校验要求修正：' + '；'.join(notes))
            return {'ok': True, 'status': skill_orchestrator.DONE, 'detail': detail}
        if action == 'writer_revise_structure':
            review = state.get('review') or {'approved': False, 'feedback': ('未完成规则校验。',)}
            if review['approved']:
                return {'ok': True, 'status': skill_orchestrator.DONE, 'detail': '规则校验已通过，无需重新提取'}
            state['structured'] = script_contract.revise_structured_script(
                state.get('raw', ''), review['feedback'], state.get('source_name', script_contract.RAW_SCRIPT_NAME))
            return {'ok': True, 'status': skill_orchestrator.DONE, 'detail': '已按反馈用本地规则重新提取'}
        if action == 'editor_final_review':
            review = script_contract.review_structured_script(state.get('raw', ''), state.get('structured', ''))
            if not review['approved']:
                raise ValueError('规则复审未通过：' + '；'.join(review['feedback']))
            return {'ok': True, 'status': skill_orchestrator.DONE, 'detail': '规则复审通过，可写入正稿'}
        if action == 'write_structured_script':
            def supersede(paths):
                from storage_maintenance import recycle_paths
                recycle_paths(project, list(paths), '重新生成同源结构剧本，回收旧份')
            target = script_contract.write_structured_script(
                project, state.get('structured'), state.get('source'),
                publisher=publish_stage_text, supersede=supersede)
            return {'ok': True, 'status': skill_orchestrator.DONE, 'detail': '已写入 ' + str(target)}
        raise ValueError('未知剧本结构动作：' + str(action))

    orchestrator = build_orchestrator(desktop, project)
    # 用户从“手动制作”入口启动本阶段，即视为对模板中整理步骤的明确确认。
    return orchestrator.run_stage_with_template('script_structure', stage_context(desktop, 'script_structure'),
                                                names=names, mode='auto', execute_action=execute)

def _run_delivery(desktop, project, names, trigger):
    """按交付模板四步程序化执行：核验已确认成片与质检 → 打包 → 报告 → 写清单（不调用模型）。"""
    import stage_completion_service as service
    from stage_execution_service import build_orchestrator, stage_context
    state = {}

    def execute(action, _context):
        done = skill_orchestrator.DONE
        if action == 'verify_deliverables':
            record = service.delivery_record(project)
            state['count'] = len(record['outputs'])
            return {'ok': True, 'status': done, 'detail': '成片 %d 份已确认，质检通过' % state['count']}
        if action == 'package_delivery':
            state['files'] = service.package_delivery(project)
            return {'ok': True, 'status': done, 'detail': '已落盘质检报告与交付摘要'}
        if action == 'generate_delivery_report':
            return {'ok': True, 'status': done, 'detail': '已写入 ' + str(service.publish_delivery_report(project))}
        if action == 'write_delivery_manifest':
            files = service.package_delivery(project)
            return {'ok': True, 'status': done, 'detail': '交付清单共 %d 个文件' % len(files)}
        raise ValueError('未知交付动作：' + str(action))

    orchestrator = build_orchestrator(desktop, project)
    return orchestrator.run_stage_with_template('delivery', stage_context(desktop, 'delivery'),
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
    if not names:
        # R2905：勾选列表为空是「这一步没勾 SKILL」，不是「跑全部」——直接回一份
        # skipped 汇总，手动执行页如实展示，自动链由 stage_handler_registry 先行跳过。
        text = '「%s」未勾选 SKILL：请先在阶段配置里勾选，或点「恢复默认」。' % stage_flow.stage_name(stage)
        return {'ok': False, 'skipped': True, 'skills': [], 'results': [], 'failed': [],
                'errors': [text], 'text': text}
    if stage == 'script_structure':
        return _run_script_structure(desktop, project, names, trigger)
    if stage == 'delivery':
        return _run_delivery(desktop, project, names, trigger)
    from stage_execution_service import build_orchestrator, stage_context
    orchestrator = build_orchestrator(desktop, project)
    return orchestrator.run(names, stage_context(desktop, stage), trigger=trigger)


def show(desktop, stage, parent=None):
    """把次级执行页摆出来，返回这一页的把手（自检直接读它，不猜控件）。"""
    if _EXECUTION_PRESENTER is None:
        raise RuntimeError('执行页呈现器尚未安装。')
    project = stage_flow.project_of(desktop)
    names = stage_flow.selected_skills(project, stage)

    def go_back():
        index = stage_flow.OWN_ORDER.index(stage) if stage in stage_flow.OWN_ORDER else None
        if index is not None:
            desktop.show(index)

    return _EXECUTION_PRESENTER(desktop, stage, parent=parent,
                                title='执行：' + stage_flow.stage_name(stage), names=names,
                                runner=run, failed_rows=failures, progress=progress_text,
                                on_back=go_back)
