# -*- coding: utf-8 -*-
"""SKILL 的 tools 落地表：把 frontmatter 里的工具名对到「现有子模块」的入口。

规格要求「复用现有子模块，不重写执行逻辑」，所以这张表只有两种条目：
- ready：本机就能跑完的一步（校验、对齐、版权过滤、技术质检、合片、交付报告……），
  复用 writing／storyboard_files／asset_reference_search／subtitle_timing／agent.media／
  engine／pet_report 这些已经在跑的模块；
- page：只能在页面上按的那一步（要 ComfyUI、要付费 API、要人判断）。这类不是「没实现」，
  而是归位到它本来就在的页面——编排器会把页面与按钮一并汇报，绝不假装成功。

调用约定：ready 条目都是 func(context) → dict，context 里带项目、当前分镜与用户勾选；
认不出来的工具名抛 ToolMissing，页面条目抛 ToolNeedsPage。
"""
import json
from pathlib import Path

import line_endings
from agent.core import read
from pet_bus import STAGES, STAGE_NAMES, stage_label

PAGE_TITLES = tuple('%02d %s' % (index + 1, STAGE_NAMES[stage]) for index, stage in enumerate(STAGES))
STAGE_PAGE = {stage: index for index, stage in enumerate(STAGES)}


class ToolError(Exception):
    """工具层的问题：编排器会把它记成这一步的失败原因。"""


class ToolMissing(ToolError):
    """没登记的工具名。"""


class ToolNeedsInput(ToolError):
    """还缺用户手上的东西（项目／分镜 JSON／文件）：不是做不成，是还没给。"""


class ToolNeedsPage(ToolError):
    """这一步只能在页面上按（要 GUI／付费接口／人判断）。"""

    def __init__(self, page, hint='', tool=''):
        self.page = int(page)
        self.hint = str(hint)
        self.tool = str(tool)
        super().__init__(self.message())

    def title(self):
        if 0 <= self.page < len(PAGE_TITLES):
            return PAGE_TITLES[self.page]
        return str(self.page)

    def message(self):
        return '这一步在「%s」页面上执行：%s' % (self.title(), self.hint or '页面上对应的按钮')


# ── 上下文小工具 ────────────────────────────────────────────────────────────
def project_of(context):
    project = (context or {}).get('project') or (context or {}).get('root')
    if not project:
        raise ToolNeedsInput('这一步需要先选定项目')
    return Path(project)


def episode_of(context):
    """当前分镜：直接给 dict，或给一个能读到的 JSON 路径。"""
    ctx = context or {}
    episode = ctx.get('episode')
    if isinstance(episode, dict):
        return episode
    for key in ('episode_file', 'storyboard', 'source'):
        value = ctx.get(key)
        if value and Path(value).is_file():
            return read(value)
    raise ToolNeedsInput('这一步需要当前分镜 JSON：请先在页面上选好分镜')


def shots_of(episode):
    shots = episode.get('shots') if isinstance(episode, dict) else None
    return shots if isinstance(shots, list) else []


# ── ready：本机跑得完的那几步 ───────────────────────────────────────────────
def _episode_validate(context):
    from writing import validate_episode
    episode = episode_of(context)
    ctx = context or {}
    source = ctx.get('source') or ctx.get('episode_file') or project_of(ctx) / 'episode' / 'episode.json'
    assets = ctx.get('assets')
    if assets is None and ctx.get('assets_file') and Path(ctx['assets_file']).is_file():
        assets = read(ctx['assets_file'])
    try:
        report = validate_episode(episode, source, assets)
    except ValueError as exc:
        return {'ok': False, 'errors': str(exc).split('\n'), 'warnings': []}
    return {'ok': True, 'errors': [], 'warnings': list(report.get('warnings') or []),
            'shot_count': report.get('shot_count'), 'total_seconds': report.get('total_seconds')}


def _storyboard_save(context):
    from storyboard_selection import remember_many
    ctx = context or {}
    path = ctx.get('episode_file') or ctx.get('source')
    if not path or not Path(path).is_file():
        raise ToolNeedsInput('没有可登记的 JSON：先选好这份分镜文件')
    remember_many(project_of(ctx), 'storyboard' if str(ctx.get('kind', 'storyboard')) != 'script' else 'script', [path])
    return {'ok': True, 'saved': str(Path(path).resolve())}


def _structure_script(context):
    """读取已确认原稿并复用剧本契约生成结构化 Markdown。"""
    from script_contract import RAW_SCRIPT_NAME, structure_script
    from stage_path_service import read_dirs
    root = project_of(context)
    source = next((folder / RAW_SCRIPT_NAME for folder in read_dirs(root, 'script')
                   if (folder / RAW_SCRIPT_NAME).is_file()), None)
    if source is None:
        raise ToolNeedsInput('未找到已确认的剧本原稿：请先完成并确认剧本准备阶段')
    content = structure_script(source.read_text(encoding='utf-8-sig'))
    return {'ok': True, 'characters': content.count('## 角色'), 'text': content}


def _write_structured_script(context):
    """将已确认原稿原子写入唯一的结构化剧本目标。"""
    from script_contract import write_structured_script
    try:
        target = write_structured_script(project_of(context))
    except ValueError as exc:
        raise ToolNeedsInput(str(exc))
    return {'ok': True, 'path': str(target)}


def _review_structured_script(context):
    """Run the Editor review against the same canonical source as Writer."""
    from script_contract import review_structured_script
    rendered = _structure_script(context)
    root = project_of(context)
    from script_contract import resolve_script_source
    source = resolve_script_source(root)
    if source is None:
        raise ToolNeedsInput('未找到已确认的自然剧本：请先完成剧本准备阶段')
    return review_structured_script(source.read_text(encoding='utf-8-sig'), rendered['text'])


def _revise_structured_script(context):
    """Let Writer regenerate from Editor feedback without writing a partial file."""
    from script_contract import revise_structured_script, resolve_script_source
    rendered = _structure_script(context)
    root = project_of(context)
    source = resolve_script_source(root)
    if source is None:
        raise ToolNeedsInput('未找到已确认的自然剧本：请先完成剧本准备阶段')
    review = _review_structured_script(context)
    text = revise_structured_script(source.read_text(encoding='utf-8-sig'), review.get('feedback') or ())
    return {'ok': True, 'text': text, 'revised': not bool(review.get('approved')),
            'characters': rendered.get('characters', 0)}


def _recon_request(project):
    """用户在 input/recon_request.json 里写下的采风请求（有就用，没有返回空表）。"""
    from file_cache import read_json
    from recon_service import stage_paths
    try:
        value = read_json(stage_paths(project)['input'] / 'recon_request.json')
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _recon_topic(project):
    """热点速成只借「故事题材」这一个方向词起手；梗概等原创内容不出去。"""
    from idea_brief_form import brief_creation_values
    from project_context_factory import project_context
    try:
        values = brief_creation_values(project_context(project))
    except (OSError, ValueError, TypeError):
        # 简报读不出来就不推断方向：宁可让采风停在「还缺输入」，也不拿废话去搜。
        return ''
    return str((values or {}).get('故事题材') or '').strip()


def _recon_target(context, project, material_source):
    """对标对象从哪来：本次上下文 → 采风请求文件 → ④ 用简报题材方向。"""
    raw = (context or {}).get('recon_target')
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        return {'name': raw.strip()}
    request = _recon_request(project)
    if request and (request.get('name') or request.get('topic')):
        request.setdefault('material_source', material_source)
        return request
    if material_source == '热点速成':
        topic = _recon_topic(project)
        if topic:
            return {'type': 'topic', 'topic': topic,
                    'question': '这个题材最近有哪些能用的结构'}
    return {}


def _recon_card(context):
    """素材采风：③④ 才激活；把对标对象的公开情报抓回来装成《对标情报卡》。"""
    from recon_service import MATERIAL_SOURCES, collect, save_card, summary
    import stage_config
    ctx = context or {}
    project = project_of(ctx)
    lock = stage_config.workflow_lock(project) or {}
    material_source = str(ctx.get('material_source') or lock.get('material_source') or '').strip()
    if material_source not in MATERIAL_SOURCES:
        return {'ok': True, 'skipped': True,
                'reason': '素材来源是「%s」，只有对标爆款／热点速成才采风' % (material_source or '未选')}
    target = _recon_target(ctx, project, material_source)
    if not target:
        raise ToolNeedsInput('采风需要先给出对标对象：在阶段配置选对标爆款并写明剧名，'
                             '或在阶段 input/recon_request.json 里写下 name／topic')
    card = collect(target, material_source, transport=ctx.get('transport'),
                   headers=ctx.get('headers'), pause=ctx.get('pause'),
                   program=ctx.get('program'))
    saved = save_card(project, card, save=ctx.get('save'), save_text=ctx.get('save_text'))
    return {'ok': True, 'card': saved['card'], 'doc': saved['doc'],
            'sources': len(card.get('sources') or ()), 'problems': saved['problems'],
            'summary': summary(card), 'not_found': card.get('not_found'),
            'budget': card.get('budget')}


def _copyright_filter(context):
    """版权过滤与来源记录：复用参考图搜索那份许可表（CC0／CC-BY 优先，不明就拦掉）。"""
    from asset_reference_search import normalize, copyright_decision
    ctx = context or {}
    allow_cc0 = ctx.get('allowCC0', True)
    allow_ccby = ctx.get('allowCCBY', True)
    kept, blocked = [], []
    for item in ctx.get('candidates') or ():
        if not isinstance(item, dict):
            blocked.append({'item': item, 'reason': '候选不是一条记录'})
            continue
        entry = normalize(item)
        reason, obligations = copyright_decision(entry)
        if reason:
            blocked.append({'item': entry, 'reason': reason})
            continue
        label = entry['license']
        low = label.lower()
        is_cc0 = 'cc0' in low or '公有领域' in label or 'public domain' in low
        is_ccby = 'cc by' in low or 'cc-by' in low or '署名' in label
        if is_cc0 and not allow_cc0:
            blocked.append({'item': entry, 'reason': '按设置不允许 CC0'})
            continue
        if is_ccby and not allow_ccby:
            blocked.append({'item': entry, 'reason': '按设置不允许 CC-BY'})
            continue
        entry['obligations'] = obligations
        kept.append(entry)
    return {'ok': True, 'filtered': kept, 'blocked': blocked,
            'licenses': sorted({entry['license'] for entry in kept})}


def _subtitle_align(context):
    from subtitle_timing import timed_entries
    episode = episode_of(context)
    entries, estimated = timed_entries(episode)
    return {'ok': True, 'entries': [{'shot': sid, 'speaker': speaker, 'text': text,
                                     'start': start, 'end': end}
                                    for sid, speaker, text, start, end in entries],
            'estimated': bool(estimated), 'count': len(entries)}


def _subtitle_generate(context):
    from subtitle_timing import srt_rows
    ctx = context or {}
    rows, estimated = srt_rows(episode_of(ctx))
    text = '\n'.join(rows)
    written = ''
    target = ctx.get('subtitle_file') or ctx.get('output')
    if target:
        # 第 7 轮：字幕正文来自用户与模型，最容易夹带落单的 \r；写入改走「写入即校验行尾」，
        # 已有的字幕文件按它自己的换行符回写，新建的按 Windows 文本惯例给 CRLF。
        from subtitle_export_controller import publish_stage_srt_text
        result = publish_stage_srt_text(target, text)
        if not result.ok:
            raise ValueError(result.reason)
        written = str(result.data)
    return {'ok': True, 'rows': len(rows), 'estimated': bool(estimated),
            'subtitle_file': written, 'text': text if not written else ''}


def _subtitle_sync(context):
    """音画同步检查：每句字幕都要落在对应镜头的时长里，串行不重叠。"""
    from subtitle_timing import timed_entries
    episode = episode_of(context)
    durations = {}
    for shot in shots_of(episode):
        try:
            durations[str(shot.get('id'))] = float(shot.get('duration') or 0)
        except (TypeError, ValueError):
            continue
    entries, estimated = timed_entries(episode)
    issues = []
    offset = 0.0
    spans = {sid: (offset, offset + durations.get(sid, 0.0)) for sid in durations}
    for sid, _speaker, text, start, end in entries:
        window = spans.get(sid)
        if window is None:
            issues.append('%s：字幕没有对应的镜头' % sid)
            continue
        if start < window[0] - 0.01 or end > window[1] + 0.01:
            issues.append('%s：字幕 %.2f–%.2f 秒超出本镜 %.2f–%.2f 秒' % (sid, start, end, window[0], window[1]))
    for sid, (start, end) in spans.items():
        offset = end
    return {'ok': not issues, 'issues': issues, 'entries': len(entries), 'estimated': bool(estimated)}


def _media_check(context):
    """技术质检：PNG 走头尾校验＋尺寸，视频走 ffprobe 的时长／音轨／分辨率。"""
    from agent import media
    ctx = context or {}
    targets, missing = [], []
    for item in ctx.get('targets') or ():
        path = Path(str(item))
        if not path.is_file():
            missing.append(str(path))
            continue
        targets.append(path)
    if not targets:
        episode = None
        try:
            episode = episode_of(ctx)
        except ToolError:
            episode = None
        project = Path(ctx['project']) if ctx.get('project') else None
        for shot in shots_of(episode or {}):
            name = str(shot.get('frame') or '')
            if not name or project is None:
                continue
            path = project / name
            if path.is_file():
                targets.append(path)
            else:
                missing.append(str(path))
    problems, checked = [], []
    for path in targets:
        if path.suffix.lower() == '.png':
            if not media.png_complete(path):
                problems.append('%s：PNG 未写完整' % path.name)
                continue
            try:
                width, height = media.png_size(path)
            except ValueError as exc:
                problems.append('%s：%s' % (path.name, exc))
                continue
            checked.append({'file': path.name, 'width': width, 'height': height})
            if min(width, height) < 512:
                problems.append('%s：分辨率 %d×%d 偏小（小于 512）' % (path.name, width, height))
            continue
        cfg = ctx.get('ffprobe_config')
        if not cfg:
            checked.append({'file': path.name, 'note': '非 PNG，未配置 ffprobe，跳过'})
            continue
        try:
            report = media.check(str(path), float(ctx.get('duration') or 0), cfg)
        except Exception as exc:
            problems.append('%s：%s' % (path.name, exc))
            continue
        checked.append({'file': path.name, 'duration': report.get('duration')})
        problems.extend('%s：%s' % (path.name, item) for item in report.get('errors') or ())
    return {'ok': not problems, 'checked': checked, 'issues': problems, 'missing': missing,
            'lowQuality': problems}


def _video_poll(context):
    """本地视频进度：复用 local_video 的清单（待提交／在跑／跳过），不提交任何任务。"""
    from local_video import auto_plan
    ctx = context or {}
    project = project_of(ctx)
    source = ctx.get('episode_file') or ctx.get('source')
    if not source:
        raise ToolNeedsInput('没有当前分镜：先在页面上选好分镜')
    submit, poll, skipped = auto_plan(project, source, studio=ctx.get('studio'))
    return {'ok': True, 'submitted': sorted(submit), 'running': sorted(poll),
            'skipped': [{'shot': sid, 'why': why} for sid, why in skipped]}


def _edit_compose(context):
    """合片：直接把镜头清单交给 engine.Studio.assemble，参数与页面上的完全一致。"""
    ctx = context or {}
    project = project_of(ctx)
    source = ctx.get('episode_file') or ctx.get('source')
    if not source:
        raise ToolNeedsInput('没有当前分镜：先在页面上选好分镜')
    from local_video import open_studio
    studio = ctx.get('studio') or open_studio(project, episode_file=source)
    done = studio.assemble(ctx.get('shot_ids'), skip_unready=bool(ctx.get('skip_unready', True)))
    return {'ok': True, 'result': done if isinstance(done, dict) else {'path': str(done)}}


def _delivery_report(context):
    """交付报告：pet_report.daily 归一 + 建议 + 落盘，含 Token／成本／命中率。"""
    import pet_report
    ctx = context or {}
    project = project_of(ctx)
    data, path = pet_report.daily(project, progress=ctx.get('progress'), ledger=ctx.get('ledger'),
                                  failures=ctx.get('failures'), notices=ctx.get('notices'),
                                  budget=ctx.get('budget'), stages=ctx.get('stages'),
                                  counts=ctx.get('counts'), timings=ctx.get('timings'))
    return {'ok': True, 'report': str(path), 'day': data.get('day'), 'data': data}


def _delivery_manifest(context):
    """交付清单：把这一轮各步的结果写成 manifest.json，路径与文件名都在里面。"""
    ctx = context or {}
    project = project_of(ctx)
    target = Path(ctx.get('manifest') or (project / '工作流任务' / 'SKILL' / '交付清单.json'))
    files = []
    for item in ctx.get('files') or ():
        path = Path(str(item))
        files.append({'path': str(path), 'exists': path.is_file(),
                      'size': path.stat().st_size if path.is_file() else 0})
    payload = {'project': str(project), 'stage_results': ctx.get('results') or [],
               'files': files, 'generated_by': 'delivery.exportManifest'}
    line_endings.write_text(target, json.dumps(payload, ensure_ascii=False, indent=2))
    return {'ok': True, 'manifest': str(target), 'files': files}


def _delivery_validate(context):
    """质检：核验成片已确认且质检结论通过（依据成果确认清单里的可复核事实，不采信模型文字）。"""
    import stage_completion_service as service
    project = project_of(context or {})
    try:
        record = service.delivery_record(project)
    except ValueError as exc:
        return {'ok': False, 'problems': [str(exc)]}
    qc = record['qc']
    return {'ok': True, 'outputs': [item['path'] for item in record['outputs']], 'warnings': list(qc.get('warnings') or [])}


def _delivery_package(context):
    """打包交付：落盘质检报告、交付摘要和带摘要的文件清单；质检未通过时拒绝。"""
    import stage_completion_service as service
    project = project_of(context or {})
    try:
        files = service.package_delivery(project)
    except ValueError as exc:
        return {'ok': False, 'problems': [str(exc)]}
    return {'ok': True, 'files': files}


def _continuity_ledger(context):
    """连贯性台账：按当前分镜与资产清单现场算一份，落 03_continuity/output（本机跑得完）。"""
    import continuity_ledger
    ctx = context or {}
    project = project_of(ctx)
    episode = episode_of(ctx)
    assets = ctx.get('assets')
    if assets is None and ctx.get('assets_file') and Path(ctx['assets_file']).is_file():
        assets = read(ctx['assets_file'])
    ledger = continuity_ledger.build(shots_of(episode), assets if isinstance(assets, dict) else {})
    path = continuity_ledger.write(project, ledger)
    summary = ledger.get('summary') or {}
    return {'ok': bool(summary.get('ok')), 'ledger': str(path), 'summary': summary,
            'problems': list(summary.get('problems') or [])}


def platform_spec(name):
    """导出规范表：页面上的导出与编排器共用 edit_export 的那一份。"""
    from edit_export import platform_spec as table
    try:
        spec = table(name)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    if spec.get('key') == 'custom':
        spec.pop('key')
    return spec


def _export(context):
    """导出这一步的平台参数：真正的转码在 09 页面上按（这里给出目标规格并记账）。"""
    ctx = context or {}
    platform = ctx.get('platform') or 'custom'
    spec = platform_spec(platform)
    custom = ctx.get('customParams') if isinstance(ctx.get('customParams'), dict) else {}
    spec.update({key: custom[key] for key in ('width', 'height', 'fps', 'bitrate') if key in custom})
    return {'ok': True, 'platform': platform, 'spec': spec,
            'note': '转码在「' + stage_label('edit') + '」页面上按对应平台的导出按钮执行（Studio.export_platform）'}


READY = {
    'script_contract.structure_script': (_structure_script, 'script_contract.structure_script：解析已确认原稿'),
    'script_contract.review_structured_script': (_review_structured_script,
                                                  'script_contract.review_structured_script：规则校验提取完整性（未调用模型）'),
    'script_contract.revise_structured_script': (_revise_structured_script,
                                                  'script_contract.revise_structured_script：按审校反馈用本地规则重提取'),
    'script_contract.write_structured_script': (_write_structured_script,
                                                'script_contract.write_structured_script：原子写入结构化剧本'),
    'script.validate': (_episode_validate, 'writing.validate_episode：交付 JSON 契约校验'),
    'storyboard.validate': (_episode_validate, 'writing.validate_episode：镜头链契约校验'),
    'storyboard.validatePrompt': (_episode_validate, 'writing.validate_episode：提示词随 JSON 一起校验'),
    'storyboard.save': (_storyboard_save, 'storyboard_files.remember：登记这份分镜'),
    'asset.copyrightFilter': (_copyright_filter, 'asset_reference_search 的许可表：CC0／CC-BY 优先'),
    'subtitle.align': (_subtitle_align, 'subtitle_timing.timed_entries：逐句对齐'),
    'subtitle.generate': (_subtitle_generate, 'subtitle_timing.srt_rows：生成 SRT'),
    'subtitle.syncCheck': (_subtitle_sync, '字幕落在本镜时长内、串行不重叠'),
    'firstframe.qualityCheck': (_media_check, 'agent.media：PNG 完整性＋尺寸'),
    'video.qualityCheck': (_media_check, 'agent.media.check：时长／音轨／分辨率'),
    'qa.visualCheck': (_media_check, 'agent.media.check：画面技术项'),
    'qa.audioCheck': (_media_check, 'agent.media.check：音轨技术项'),
    'qa.subtitleCheck': (_subtitle_sync, '字幕与镜头时长的一致性'),
    'video.pollStatus': (_video_poll, 'local_video.auto_plan：待提交／在跑／跳过'),
    'edit.compose': (_edit_compose, 'engine.Studio.assemble：按页面同一套参数合片'),
    'delivery.generateReport': (_delivery_report, 'pet_report.daily：耗时／成本／重试／Token'),
    'delivery.exportManifest': (_delivery_manifest, '写出交付清单 manifest.json'),
    'delivery.validate': (_delivery_validate, 'stage_completion_service.delivery_record：成片已确认且质检通过'),
    'delivery.package': (_delivery_package, 'stage_completion_service.package_delivery：质检报告与交付清单'),
    'continuity.buildLedger': (_continuity_ledger, 'continuity_ledger.build：现场算一份台账并落盘'),
    'edit.exportDouyin': (_export, 'platform_spec：抖音 1080×1920 / 8M'),
    'edit.exportBilibili': (_export, 'platform_spec：B站 1920×1080 / 12M'),
    'edit.exportYouTube': (_export, 'platform_spec：YouTube 3840×2160 / 45M'),
    'edit.exportCustom': (_export, 'platform_spec：自定义参数'),
    'recon.card': (_recon_card, 'recon_service：③④ 采风，检索公开情报并落《对标情报卡》'),
}

# 只能在页面上按的那几步：页序号按 STAGES 的顺序（与左侧导航一一对应）。
from pet_bus import STAGES, STAGE_NAMES
_SCRIPT, _SCRIPT_STRUCTURE, _STORYBOARD, _ANIMATIC, _ASSETS, _CONTINUITY, _FINAL, _KEYFRAME, _PREVIS, _VIDEO, _AUDIO, _EDIT, _DELIVERY = map(STAGES.index, STAGES)
PAGES = {
    'animatic.generate': (_ANIMATIC, '生成分镜预演'),
    'animatic.validate': (_ANIMATIC, '确认预演（SG-B）'),
    'script.generate': (_SCRIPT, '剧本创作'),
    'script.save': (_SCRIPT, '保存剧本'),
    'script.extractCharacters': (_ASSETS, '从剧本提取角色／场景／道具'),
    'script.extractScenes': (_ASSETS, '从剧本提取角色／场景／道具'),
    'script.extractProps': (_ASSETS, '从剧本提取角色／场景／道具'),
    'storyboard.generate': (_STORYBOARD, '分镜创作'),
    'storyboard.pacingCheck': (_STORYBOARD, '分镜提示词生成／节奏检查'),
    'storyboard.continuityCheck': (_STORYBOARD, '连续性检查'),
    'storyboard.renderPrompt': (_FINAL, '生成提示词'),
    'storyboard.lockConsistency': (_FINAL, '一致性锁定'),
    'storyboard.checkDrift': (_FINAL, '检查漂移'),
    'asset.startAutoFill': (_ASSETS, '自动补资产'),
    'asset.retry': (_ASSETS, '重试失败项'),
    'asset.pause': (_ASSETS, '暂停自动补资产'),
    'asset.resume': (_ASSETS, '继续自动补资产'),
    'asset.importAssets': (_ASSETS, '导入资产'),
    'firstframe.batchGenerate': (_KEYFRAME, '手动制作首帧'),
    'firstframe.retry': (_KEYFRAME, '重试失败项'),
    'whitemodel.buildScene': (_PREVIS, '开始制作'),
    'whitemodel.placeActors': (_PREVIS, '白模搭景'),
    'whitemodel.setCamera': (_PREVIS, '镜头机位'),
    'whitemodel.recordCamera': (_PREVIS, '录制运镜'),
    'whitemodel.recordMotion': (_PREVIS, '录制动作'),
    'whitemodel.validateRhythm': (_PREVIS, '节奏检查'),
    'video.batchSubmit': (_VIDEO, '提交生成'),
    'video.retry': (_VIDEO, '重试失败项'),
    'video.pause': (_VIDEO, '暂停'),
    'video.resume': (_VIDEO, '继续'),
    'voice.synthesize': (_AUDIO, '一键生成配音'),
    'voice.qualityCheck': (_AUDIO, '试听检查'),
    'voice.retry': (_AUDIO, '重新生成这一句'),
    'edit.addTransition': (_EDIT, '转场'),
    'edit.addSFX': (_EDIT, '音效'),
    'continuity.resolveConflict': (_CONTINUITY, '参考图裁决（每条选一个）'),
    'continuity.freezeAnchors': (_CONTINUITY, '手动生成连贯性清单'),
    'continuity.checkCrossBatch': (_CONTINUITY, '跨批次与三元组校验表'),
    'continuity.checkTriplets': (_CONTINUITY, '跨批次与三元组校验表'),
    'continuity.auditDrift': (_CONTINUITY, '锚点漂移（校验表里那一行）'),
    'edit.addBGM': (_EDIT, '背景音乐'),
    'qa.styleCheck': (_DELIVERY, '风格检查'),
    'qa.complianceCheck': (_DELIVERY, '合规检查'),
    'delivery.archive': (_DELIVERY, '打包交付'),
    'asset.plan': (_ASSETS, '生成资产计划'),
    'asset.validate': (_ASSETS, '校验资产计划'),
    'continuity.audit': (_CONTINUITY, '连贯性审计'),
    'continuity.validate': (_CONTINUITY, '校验连贯性清单'),
    'storyboard.finalize': (_FINAL, '分镜定稿'),
    'keyframe.generate': (_KEYFRAME, '手动制作首帧'),
    'keyframe.validate': (_KEYFRAME, '校验首帧'),
    'previs.generate': (_PREVIS, '开始制作'),
    'previs.validate': (_PREVIS, '校验白模预演'),
    'video.submit': (_VIDEO, '提交生成'),
    'video.validate': (_VIDEO, '校验生成视频'),
    'audio.synthesize': (_AUDIO, '一键生成配音'),
    'subtitle.export': (_AUDIO, '导出字幕'),
    'audio.validate': (_AUDIO, '校验配音与字幕'),
    'edit.assemble': (_EDIT, '自动合成'),
    'edit.validate': (_EDIT, '校验后期合成'),
}

# 页号与显示名均随阶段权威源顺延，动作说明保持原有语义。
PAGES = {tool: (page, '%02d %s → %s' % (page + 1, STAGE_NAMES[STAGES[page]], hint.split('→', 1)[-1].strip()))
         for tool, (page, hint) in PAGES.items()}

_INJECTED = {}


def register(name, func, note=''):
    """把一个实现挂进表里（也用于自检注入替身）。"""
    READY[str(name)] = (func, note)
    return func


def injected(context):
    """上下文里可以直接带一套 tools 替身，方便自检与离线跑。"""
    tools = (context or {}).get('tools')
    return tools if isinstance(tools, dict) else {}


def status_of(name):
    """ready／page／missing——面板与编排器都按这个口径说话。"""
    tool = str(name or '')
    if tool in _INJECTED:
        return 'ready'
    if tool in READY:
        return 'ready'
    if tool in PAGES:
        return 'page'
    return 'missing'


def ready_names():
    return sorted(READY)


def page_names():
    return sorted(PAGES)


def missing(names):
    """这一批工具里既没实现又没有页面去处的（正常应当是空的）。"""
    return [str(name) for name in names or () if status_of(name) == 'missing']


def call(name, context=None):
    """跑一步工具：返回结果 dict；页面条目抛 ToolNeedsPage，没登记的抛 ToolMissing。"""
    tool = str(name or '')
    ctx = context or {}
    custom = injected(ctx)
    if tool in custom:
        func = custom[tool]
        if callable(func):
            result = func(ctx)
            return result if isinstance(result, dict) else {'ok': True, 'value': result}
        return {'ok': True, 'value': func}
    if tool in READY:
        func, note = READY[tool]
        result = func(ctx)
        result = result if isinstance(result, dict) else {'ok': True, 'value': result}
        result.setdefault('tool', tool)
        result.setdefault('note', note)
        return result
    if tool in PAGES:
        page, hint = PAGES[tool]
        raise ToolNeedsPage(page, hint, tool)
    raise ToolMissing('没登记的工具：' + tool)
