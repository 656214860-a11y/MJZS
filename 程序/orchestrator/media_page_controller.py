"""无 Tk 的制作后段页（首帧／连贯性／视频／配音／后期／交付）状态与决策（R1983 J3）。

从 ``desktop_media_pages.MediaPagesMixin`` 下沉：就绪签名、首帧批次可否派发的判据、连贯性清单的
表格行、剪映查找候选、字幕状态文案、交接包选版、交付页逐镜状态行、视频工作区解析。方法体与原
Mixin 逐字等价；读文件的口子由调用方注入（``read_json`` 等），本模块不持有 Tk 控件、不写项目数据。
"""
from __future__ import annotations

import os
from pathlib import Path

from engine import adopted_edit_version, adoption_summary, review_label


def summary_text(summary):
    """连贯性清单的一句结论；页头与生成播报共用，数字出自同一份台账。"""
    summary = summary or {}
    return '镜头 %s 个 · 批次 %s 组 · %s' % (
        summary.get('shots', 0), summary.get('batches', 0), '全部通过' if summary.get('ok') else '有待办')


def edit_ready_signature(studio):
    """整集「已验收」状态签名。

    必须带上分镜文件：两份分镜的镜头编号与版本完全相同时，只比镜头状态会让第二集沿用第一集的签名。
    """
    state = studio.state()
    return (str(studio.episode_path), tuple(
        (shot['id'], tuple((v.get('version'), v.get('review'), v.get('qc_pass'), v.get('state'))
                           for v in state['shots'].get(shot['id']) or []))
        for shot in studio.episode['shots']))


def keyframe_batch_verdict(pending, busy, missing_settings, blockers, skip_summary, check_settings=False):
    """「现在能不能补首帧」的判据：返回 (reason, warn)；reason 为空串＝可以立刻派发。

    ``busy``／``missing_settings``／``blockers`` 都是调用方注入的回调，保持原来的短路与惰性求值：
    有任务在跑就不查设置，设置没问题才去做逐镜检查。``skip_summary`` 由 L4 注入（local_video 的归并文案）。
    """
    if busy():
        return '已有制作任务在跑，等这一轮结束再补', False
    if check_settings:
        missing = missing_settings()
        if missing:
            return '本地 ComfyUI 还没配好（缺 ' + '、'.join(missing) + '），可到「首帧制作」窗口保存设置', True
    # 整批镜头都会被引擎逐镜跳过时批次只会白跑，这种批次不派发，用引擎自己的逐镜检查给出原因。
    try:
        blocked = blockers()
    except (OSError, ValueError) as exc:
        return str(exc), True
    if len(blocked) == len(pending):
        return str(len(pending)) + ' 镜都无法生成：' + skip_summary(blocked), True
    return '', True


def ledger_shots(episode):
    """从分镜 JSON 取镜头列表；形状不对就当没有镜头。"""
    if isinstance(episode, dict) and isinstance(episode.get('shots'), list):
        return episode['shots']
    return []


def build_ledger(read_episode, read_assets):
    """现场算一份连贯性台账（只读，不落盘）：读不出分镜或资产清单时按空处理。"""
    from continuity_ledger import build
    try:
        shots = ledger_shots(read_episode())
    except (ValueError, OSError):
        shots = []
    try:
        assets = dict(read_assets())
    except (ValueError, OSError, TypeError, AttributeError, KeyError):
        assets = {}
    return build(shots, assets)


def continuity_folder(project):
    """连贯性阶段落盘的目录（03_continuity/output）。"""
    import contract.stage_layout as stage_layout
    return stage_layout.paths(project, '03_continuity')['output']


def batch_rows(ledger):
    """「批次与冻结锚点」表的行。"""
    return [(block.get('batch_id') or '', '、'.join(block.get('shot_ids') or []) or '—',
             block.get('seconds') or 0,
             '；'.join('%s %s：%s' % (entry.get('kind') or '', entry.get('id') or '', entry.get('anchor') or '')
                      for entry in block.get('frozen_anchors') or []) or '—')
            for block in (ledger.get('batches') or [])]


def check_rows(ledger):
    """「跨批次与三元组校验」表的行（三元组、跨批次、参考图裁决、锚点漂移依次排列）。"""
    checks = []
    for row in ledger.get('triplets') or []:
        checks.append(('三元组', row.get('batch_id') or '', '一致' if row.get('ok') else '不一致',
                       row.get('detail') or ''))
    for row in ledger.get('cross_batch') or []:
        checks.append(('跨批次', row.get('id') or row.get('kind') or '', '一致' if row.get('ok') else '不一致',
                       row.get('detail') or ''))
    for row in ledger.get('conflicts') or []:
        checks.append(('参考图裁决', row.get('shot_id') or row.get('batch_id') or '', row.get('kind') or '',
                       (row.get('resolution') or '')
                       + (('；理由：' + str(row.get('reason'))) if row.get('reason') else '')))
    for row in ledger.get('drift') or []:
        checks.append(('锚点漂移', row.get('id') or '', '漂移' if not row.get('ok') else '一致',
                       row.get('detail') or ''))
    return checks


def issue_table_rows(issue_rows):
    """「问题闭环」表的行。"""
    return [(row.get('id') or '', row.get('kind_label') or '', row.get('severity') or '',
             row.get('state_label') or '',
             '、'.join([str(item) for item in (row.get('shots') or []) + (row.get('assets') or [])]) or '—',
             row.get('evidence') or row.get('detail') or '')
            for row in issue_rows]


def open_issues(issue_rows):
    return [item for item in issue_rows if item.get('state') == 'open']


def editor_candidates(saved, environ=None):
    """剪映专业版可能的安装位置，按优先级排列：用户保存的路径最先。"""
    environ = os.environ if environ is None else environ
    candidates = [Path(saved)] if saved else []
    local = Path(environ.get('LOCALAPPDATA', ''))
    candidates.extend([
        local / 'JianyingPro/JianyingPro.exe',
        local / 'Programs/JianyingPro/JianyingPro.exe',
        Path(environ.get('ProgramFiles', 'C:/Program Files')) / 'JianyingPro/JianyingPro.exe',
        Path(environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'JianyingPro/JianyingPro.exe',
    ])
    candidates.extend(sorted((local / 'JianyingPro/Apps').glob('*/JianyingPro.exe'), reverse=True))
    for drive in 'CDEFG':
        candidates.append(Path(f'{drive}:/JianyingPro/JianyingPro.exe'))
    return candidates


def subtitle_status(report):
    """字幕导出后的状态文案：按校准报告说清是否校准、还有几句没校准。"""
    if not isinstance(report, dict):
        return '字幕时间按镜头时长估算，属草稿，请在剪映中听校。' if report else '字幕时间已按分镜时间生成。'
    pending = report.get('uncalibrated') or []
    if pending:
        basis = '句长' if report.get('mode') == 'length' else '镜头时长'
        return '字幕时间暂按%s估算，还有 %d 句未按实际配音校准，导出前请先听校。' % (basis, len(pending))
    return '字幕时间已按实际配音／作者标注校准，共 %d 句。' % report.get('calibrated', 0)


def handoff_rows(project, studio):
    """交接包要收的 (镜头, 采用版) 列表。

    与自动粗剪／成片同一口径：``engine.adopted_edit_version`` 是唯一选版规则。取不到采用版的镜头
    如实不进包，由清单声明缺镜；不退回未验收版，也不把缺失／被替换的文件塞进交接包。
    """
    state = studio.state()
    rows = []
    for shot in studio.episode['shots']:
        version, _reason = adopted_edit_version(state['shots'].get(shot['id']), project)
        if version is not None and version.get('file'):
            rows.append((shot, version))
    return rows


def dialogue_availability(read_entries):
    """配音页的对白可用性：返回 (有无对白, 不可用原因)；读不出来时把原因带回去而不是静默禁用。"""
    try:
        entries, _estimated = read_entries()
    except (ValueError, OSError, TypeError) as exc:
        return False, '对白无法读取，配音生成与字幕导出暂不可用：' + str(exc)
    if not entries:
        return False, '当前分镜没有对白，配音生成与字幕导出暂不可用。'
    return True, ''


def delivery_lines(project, studio, labels, status_next):
    """交付页逐镜状态行；采用列与真实成片来源同一版（最新版失败但旧版通过时显示旧版）。

    ``labels``／``status_next`` 是 L4 ``video_progress`` 的状态文案，由调用方注入。
    """
    state = studio.state()
    lines = []
    for shot in studio.episode['shots']:
        summary = adoption_summary(project, state['shots'][shot['id']])
        version = summary['source']
        status = labels.get(version.get('state'), version.get('state') or '未提交')
        qc = {True: '通过', False: '未通过'}.get(version.get('qc_pass'), '未检查')
        review = review_label(version)
        if summary['adopted'] is not None:
            adopted_text = 'v%s' % summary['adopted']['version']
            if not summary['latest_is_adopted'] and summary['latest']:
                adopted_text += '；最新 v%s 未采用' % summary['latest'].get('version')
            step = ''
        else:
            adopted_text = '无' if not summary['reason_text'] else '无（%s）' % summary['reason_text']
            step = status_next(version)
        lines.append(f'{shot["id"]}  {shot["title"]}  | 状态 {status} | 技术QC {qc} | 验收 {review} | 采用 {adopted_text}'
                     + (' | 下一步 ' + step if step else ''))
    return lines


def resolve_video_root(project, mode, prefs):
    """视频页读哪个目录：线上模式且偏好里记着的云端任务目录有效就用它，否则用项目根。"""
    project = Path(project)
    video_root = project
    if mode == 'cloud' and prefs.get('cloud_video_workspace'):
        candidate = (project / prefs['cloud_video_workspace']).resolve()
        if candidate.is_relative_to((project / 'cloud_video').resolve()) and (candidate / 'config.json').is_file():
            video_root = candidate
    return video_root


def apply_video_workspace(project, prefs, folder):
    """把云端任务目录写进偏好字典（folder 为 None 即清除）；目录不在项目内就拒绝。"""
    if folder is None:
        prefs.pop('cloud_video_workspace', None)
        return prefs
    folder = Path(folder).resolve()
    if not folder.is_relative_to((Path(project) / 'cloud_video').resolve()):
        raise ValueError('云端任务目录不在当前项目内')
    prefs['cloud_video_workspace'] = folder.relative_to(Path(project).resolve()).as_posix()
    return prefs


def frame_checks_key(merged, stored_key, source):
    """首帧勾选表的钥匙：「全部分镜」合成一张表时认页面记着的钥匙，否则按来源文件。"""
    if merged:
        return stored_key or str(Path(source).resolve())
    return str(Path(source).resolve())
