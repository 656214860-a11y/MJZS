"""桌面模型（Gemini、Claude Desktop 等）续发方式：续用上次对话只发增量，或新对话完整发送（REQ-S01-69）。

``prepare_native()`` 在后台线程准备完整稿与增量稿并各写一份任务文件；``choose()`` 在 Tk 线程按台账计划
弹窗二选一或直接完整发送，选定后交回 ``_FlowAgentLaunch.done()``，复制进剪贴板后立即记台账。
台账与计划的决策在 L3 ``desktop_send_ledger``，本模块只做界面与编排。
"""
import logging
from pathlib import Path

import orchestrator.desktop_send_ledger as ledger
from ui_widgets import BaseDialog, DescriptionBlock

LOGGER = logging.getLogger('desktop_send_choice')
# Claude Desktop 常常不能直接写本机路径、只给下载文件：要求下载件沿用目标文件名，
# 并登记目标，助手会从「下载」文件夹按文件名收回到原位置。
DELIVERY = ('\n\n【交付方式】优先直接写入任务中给出的目标路径；若无法写入本机文件，'
            '请以可下载文件交付，文件名必须与目标路径的文件名完全一致，'
            '用户下载后助手会自动放回对应位置。')
FULL_HEADING = '【当前项目文件（含用户手改），以本次正文为准】'
# Gemini 等桌面程序对超长单条输入直接报错：超过此字数改为任务文件作附件、输入框只放短指令（REQ-S01-70）。
ATTACH_THRESHOLD = 8000


def attachment_payload(engine, task_file, text):
    """返回 (剪贴板文本, 附件路径)；不需要附件时附件路径为空串。"""
    path = Path(task_file) if task_file else None
    if engine != 'desktop-app' or len(text) <= ATTACH_THRESHOLD or path is None or not path.is_file():
        return text, ''
    instruction = (f'请完整阅读并执行附件「{path.name}」中的任务。附件就是本次全部任务说明'
                   '（含 SKILL、规则和项目材料），请读到结尾再动手，不要只看开头。'
                   '若看不到这个附件，请先告诉我附件没有上传成功，不要凭空创作。')
    return instruction + DELIVERY, str(path)


def attachment_hint(attachment):
    """附件模式下手动操作的补充说明；同时打开任务文件所在文件夹供拖拽上传（REQ-S01-70）。"""
    if not attachment:return ''
    from contract.platform_tools import open_path
    try:open_path(Path(attachment).parent)
    except OSError:pass
    return '剪贴板里是短指令；请先把任务文件 '+str(attachment)+' 作为附件上传（已打开所在文件夹，可直接拖进对话框），再粘贴短指令。'


def deliver_desktop_app(host, finish, receipt, task_file, title, clipboard_text,
                        program, app, delivery='paste', attachment=''):
    """启动 Desktop 程序；发送入口启用时尝试粘贴，失败如实回落为手动粘贴。"""
    from contract.platform_tools import launch_windows_app
    app = str(app or '桌面模型')
    if not program:
        message = '已复制到剪贴板；未找到 '+app+' 的程序路径，请在模型管理指定 .exe 后手动粘贴并发送。'+attachment_hint(attachment)
        finish(receipt,'prepared',message,task_file=task_file); host.status.set(message)
        host.notifier.info(message,title='请手动粘贴')
        return
    launch_windows_app(program, app)
    if delivery != 'paste':
        message = '已打开 '+app+'，任务已复制到剪贴板；请切到该窗口粘贴并手动发送。'+attachment_hint(attachment)
        finish(receipt,'prepared',message,task_file=task_file); host.status.set(message)
        host.notifier.info(message,title='请粘贴并发送')
        return
    from codex_paste import paste_attachment, paste_existing
    def pasted(value):
        reason = str(value.get('reason') or '')
        if not value['ok'] and '剪贴板' not in reason: reason = '任务已复制到剪贴板；' + reason
        if not value['ok']: reason += attachment_hint(attachment)
        state = 'prepared' if value['ok'] else 'failed'
        finish(receipt,state,reason,task_file=task_file)
        host.status.set(reason)
        host.notifier.info(reason,title='请检查并发送' if value['ok'] else '请手动粘贴')
    host.status.set('正在将本次任务粘贴到 '+app+'，请检查后手动发送…')
    def attempt():
        try:
            if attachment:
                return paste_attachment(title,clipboard_text,attachment,program=program,app_name=app)
            return paste_existing(title,clipboard_text,program=program,
                                  app_name=app,deadline_seconds=45)
        except Exception as exc:
            return {'ok':False,'reason':'未能自动粘贴（%s）；任务已复制到剪贴板，请手动粘贴并发送。' % exc}
    host.async_(attempt,pasted)


def _reference(task_file):
    return (f'请读取并执行本次任务文件：{task_file}\n'
            '其中引用的 SKILL 和附件按任务需要读取，不重复加载无关内容。'
            '若无法读取本地文件，请提示启用文件访问并授权对应目录，或请用户上传文件；不要假定已读。')


def _resend_plan(launch, full):
    """剧本准备的续发计划；返回 (计划, 完整稿, 增量稿)。"""
    from orchestrator.workflow_settings import model_name
    skill_hash = ledger.digest(launch.prompt_with_settings('', launch.config, stage=launch.stage))
    from orchestrator.workflow_tasks import creative_source
    materials = ledger.snapshot(launch.project, model_name(launch.project, launch.stage),
                                creative_source(launch.followup or launch.prompt))
    plan = ledger.plan(launch.project, launch.stage, launch.config, skill_hash, materials)
    full = full + ledger.materials_block(materials, FULL_HEADING) + DELIVERY
    incremental = ledger.incremental_text(launch.followup, plan['changed'], DELIVERY)
    plan.update(skill_hash=skill_hash, materials=materials, full_chars=len(full),
                incremental_chars=len(incremental), app=launch.config.get('display_model') or '桌面模型')
    return plan, full, incremental


def prepare_native(launch, receipt, full):
    """后台线程：写任务文件、登记下载收件箱；剧本准备另附续发计划。"""
    from codex_tasks import task_file_reference
    from stage_execution_service import register_download_inbox
    plan = None
    if launch.stage == 'writing' and not launch.intake_only:
        plan, full, incremental = _resend_plan(launch, full)
        if plan['mode'] == 'choice':
            plan['incremental_file'] = str(task_file_reference(launch.project, launch.stage, incremental))
    else:
        full = full + DELIVERY
    task_file = task_file_reference(launch.project, launch.stage, full)
    try:register_download_inbox(launch.project, full)
    except (OSError, ValueError) as exc:LOGGER.warning('下载收件箱登记失败：%s', exc)
    result = {'receipt': receipt, 'prompt': _reference(task_file), 'task_file': str(task_file)}
    if plan is not None:
        result['send_plan'] = plan
    return result


def choose(launch, result, done):
    """Tk 线程：按计划完整发送、弹窗二选一或（全自动）直接完整发送。"""
    plan = result.pop('send_plan')
    host = launch.host
    def send(mode):
        if mode is None:
            message = '已取消发送：未复制、未粘贴任何内容。'
            launch.finish(result['receipt'], 'failed', message)
            host.status.set(message)
            return
        chosen = dict(result)
        if mode == 'incremental':
            chosen.update(task_file=plan['incremental_file'], prompt=_reference(plan['incremental_file']))
        done(chosen)
        # done() 已同步复制进剪贴板；自动粘贴成功与否都算已发出，下次据此比对。
        try:
            ledger.record(launch.project, launch.stage, launch.config, {
                'skill_hash': plan['skill_hash'], 'materials': plan['materials'],
                'mode': mode, 'task_file': chosen['task_file']})
        except (OSError, ValueError) as exc:
            LOGGER.warning('桌面续发台账更新失败：%s', exc)
    level = getattr(host, 'gate_level', None)
    if plan['mode'] == 'full':
        send('full')
    elif callable(level) and level() == 'auto':
        send('full')
        host.status.set('三虎全自动：续发不弹窗，已按新对话完整发送（约 {:,} 字）；'
                        '请切到 {} 检查后手动发送。'.format(plan['full_chars'], plan['app']))
    else:
        ask_send_mode(host.win, plan, send)


def ask_send_mode(parent, plan, on_result):
    """弹出续发方式选择；``on_result`` 收到 'incremental'／'full'／None（取消）。"""
    return SendChoiceDialog(parent, plan, on_result)


class SendChoiceDialog(BaseDialog):
    """续用上次对话／新对话完整发送／取消；关闭窗口与 Esc 等同取消。"""

    def __init__(self, parent, plan, on_result):
        self.choice = None
        self._on_result = on_result
        super().__init__(parent, '选择发送方式')
        names = '、'.join(dict.fromkeys(item[0] if isinstance(item, (tuple, list)) else item['name']
                                         for item in plan.get('changed') or ()))
        changes = ('自上次发送以来改动过：' + names + '。') if names else '自上次发送以来项目文件没有改动。'
        DescriptionBlock(self.content, text=(
            '上次已向 ' + str(plan.get('app') or '桌面模型') + ' 发过本阶段任务。' + changes + '\n'
            '续用上次对话：只发本次指令和改动过的文件正文，原对话须仍开着。\n'
            '新对话完整发送：重新发送 SKILL、规则和全部现有文件，请在新对话中粘贴。')).pack(fill='x')
        self.add_action('取消', self.close)
        self.add_action('新对话完整发送（约 {:,} 字）'.format(plan['full_chars']), lambda: self._pick('full'))
        self.add_action('续用上次对话（约 {:,} 字）'.format(plan['incremental_chars']),
                        lambda: self._pick('incremental'), primary=True)

    def _pick(self, mode):
        self.choice = mode
        self.close()

    def close(self):
        if self._closed:
            return
        super().close()
        callback, self._on_result = self._on_result, None
        if callback:
            callback(self.choice)
