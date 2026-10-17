"""无界面的阶段成果核验服务。"""
from pathlib import Path
import math

import pet_bus


def media_output_folders(root, stage):
    """返回媒体阶段的成果目录与允许扩展名。"""
    from stage_path_service import read_dirs
    if stage == 'audio':
        return tuple(folder / '音频' for folder in read_dirs(root,'audio')), {'.mp3', '.wav', '.m4a', '.aac'}
    if stage == 'edit':
        return (*read_dirs(root, 'edit'), *(folder / '导出成片' for folder in read_dirs(root,'delivery'))), {'.mp4', '.mov', '.mkv'}
    if stage == 'delivery':
        return read_dirs(root,'delivery'), {'.mp4', '.mov', '.mkv'}
    return (), set()


def media_scope(root):
    """当前已采用分镜及内容版本；切集和改稿均使旧确认失效。"""
    from agent.core import file_hash, read
    from storyboard_adoption_contract import adopted, prefs, resolve_source
    root = Path(root).resolve()
    sources = adopted(root)
    selected = prefs(root).get('frame_json')
    source = resolve_source(root, selected) if selected else (sources[0] if len(sources) == 1 else None)
    if source is None or source not in sources:
        raise ValueError('请先选择当前已采用的分镜，再确认本集成果')
    data = read(source)
    if not isinstance(data, dict) or not data.get('shots'):
        raise ValueError('当前分镜没有可核验的镜头')
    return {'project': str(root), 'source': source.relative_to(root).as_posix(),
            'source_sha256': file_hash(source), 'episode': str(data.get('episode_id') or data.get('id') or source.stem)}


def media_manifest_path(root, stage, scope):
    from agent.core import fingerprint
    from stage_path_service import write_dir
    if stage not in ('audio', 'edit', 'delivery'):
        raise ValueError('不支持的媒体成果阶段')
    return write_dir(root, stage) / '成果确认' / (fingerprint(scope['source'])[:24] + '.json')


def _media_path(root, stage, value):
    root = Path(root).resolve()
    path = Path(value)
    path = (root / path).resolve() if not path.is_absolute() else path.resolve()
    folders, suffixes = media_output_folders(root, stage)
    if (not path.is_relative_to(root) or not any(path.is_relative_to(folder.resolve()) for folder in folders)
            or path.suffix.lower() not in suffixes or not path.is_file() or not path.stat().st_size):
        raise ValueError('请选择本项目对应阶段目录中的有效媒体文件：' + path.name)
    return path


def _technical_media(stage, data):
    """探测结果必须有真实流和有限正时长，不能把扩展名当技术验收。"""
    from agent.media import media_facts
    return media_facts('audio' if stage == 'audio' else 'video', data)


def prepare_media_completion(root, stage, paths, *, scope=None):
    """后台技术校验并冻结待审核清单；不因导入或探测成功自动完成。"""
    from agent.core import file_hash, read
    from agent.media import probe
    from platform_tools import tool_path
    root = Path(root).resolve()
    current = media_scope(root)
    if scope is not None and scope != current:
        raise ValueError('当前分镜已切换或修改，请重新选择成果')
    scope = current
    media_manifest_path(root, stage, scope)
    config = read(root / 'config.json') if (root / 'config.json').is_file() else {}
    executable = config.get('ffprobe') or tool_path('ffprobe')
    if not executable:
        raise ValueError('请先配置 FFprobe，再校验媒体成果')
    outputs = []
    for path in dict.fromkeys(_media_path(root, stage, value) for value in paths):
        digest = file_hash(path)
        validation = _technical_media(stage, probe(path, {'ffprobe': executable}))
        if file_hash(path) != digest:
            raise ValueError('校验期间成果文件发生变化，请重试')
        outputs.append({'path': path.relative_to(root).as_posix(), 'sha256': digest,
                        'size': path.stat().st_size, 'validation': validation})
    if not outputs:
        raise ValueError('请至少选择一份本阶段媒体成果；字幕或压缩包不能替代媒体')
    if stage == 'audio':
        from tts_api import audio_kind
        if not any(audio_kind(Path(output['path']).name) == 'dialogue' for output in outputs):
            raise ValueError('所选音频都不是对白音轨（只有 BGM／音效／旁白），不能代替对白配音完成核验')
    data = {'schema': 1, 'stage': stage, 'scope': scope, 'status': 'pending_review', 'outputs': outputs}
    _validate_media_completion(root, stage, data, require_review=False)
    return data


def _validate_media_completion(root, stage, data, *, require_review=True):
    from agent.core import file_hash
    if (not isinstance(data, dict) or data.get('schema') != 1 or data.get('stage') != stage
            or data.get('scope') != media_scope(root)):
        raise ValueError('成果确认与当前项目、集或采用分镜版本不一致，请重新校验确认')
    if require_review and (data.get('status') != 'complete' or data.get('reviewed') is not True):
        raise ValueError('媒体已校验，仍待您确认本集内容和完整性')
    outputs = data.get('outputs')
    if not isinstance(outputs, list) or not outputs:
        raise ValueError('成果清单缺少必要媒体')
    for output in outputs:
        if not isinstance(output, dict) or not isinstance(output.get('validation'), dict):
            raise ValueError('成果清单格式错误')
        path = _media_path(root, stage, output['path'])
        validation = output.get('validation') or {}
        duration = float(validation.get('duration', 0))
        if (validation.get('passed') is not True or validation.get('kind') != ('audio' if stage == 'audio' else 'video')
                or not math.isfinite(duration) or duration <= 0):
            raise ValueError('成果清单缺少有效技术校验结果')
        if path.stat().st_size != output.get('size') or file_hash(path) != output.get('sha256'):
            raise ValueError('成果文件已替换或修改，请重新校验确认：' + path.name)


def confirm_media_completion(root, stage, prepared):
    """仅显式人工确认入口调用；发布前重新核对冻结版本。"""
    from agent.core import save
    _validate_media_completion(root, stage, prepared, require_review=False)
    data = dict(prepared, status='complete', reviewed=True)
    if stage == 'delivery':
        data['commercial_status'] = 'pending'
    target = media_manifest_path(root, stage, data['scope'])
    save(target, data)
    return target


COMMERCIAL_CATEGORIES = ('script', 'reference', 'image', 'video', 'music', 'font', 'voice')


def publish_imported_media(target, source, validate, kind):
    """保留导入副本的实际摘要和来源；记录不代表使用许可。"""
    from agent.core import copy_file_new, file_hash, save
    result = copy_file_new(target, source, validate)
    target = Path(target)
    save(target.with_name(target.name + '.source.json'), {
        'schema': 1, 'kind': kind, 'source': str(Path(source).resolve()),
        'imported_file': target.name, 'sha256': file_hash(target), 'rights_status': 'unknown'})
    return result


def _commercial_inventory(root, scope, outputs):
    """只预填可追溯文件，不推断授权，也不扫描无关项目文件。"""
    from agent.core import file_hash, read
    from storyboard_catalog_service import board_source_script
    from project_context_factory import project_context
    root = Path(root).resolve()
    categories = {key: {'items': [], 'unused_reason': ''} for key in COMMERCIAL_CATEGORIES}
    warnings, seen = [], set()

    def add(category, path, expected=None):
        path = Path(path).resolve()
        if not path.is_relative_to(root) or not path.is_file() or not path.stat().st_size:
            warnings.append('来源缺失、为空或越出项目：' + str(path))
            return
        digest = file_hash(path)
        if expected is not None and expected != digest:
            warnings.append('来源版本已改变：' + str(path))
        key = (category, path)
        if key in seen:
            return
        seen.add(key)
        origin = ''
        receipt_path = path.with_name(path.name + '.source.json')
        if receipt_path.is_file():
            receipt = read(receipt_path)
            if (not isinstance(receipt, dict) or receipt.get('sha256') != digest
                    or receipt.get('imported_file') != path.name):
                warnings.append('导入来源记录与当前素材不一致：' + str(path))
            elif isinstance(receipt.get('source'), str):
                origin = '外部导入：' + receipt['source']
        categories[category]['items'].append({
            'path': path.relative_to(root).as_posix(), 'sha256': digest,
            'source': origin, 'rights_holder': '', 'license': '',
            'commercial_allowed': False, 'derivative_allowed': False, 'obligations_fulfilled': False,
            'authorization': {'path': '', 'sha256': ''}})

    board = root / scope['source']
    link = read(board).get('source_script')
    if link and isinstance(link, str):
        script = board_source_script(project_context(root), board)
        if script is not None:
            add('script', script)
        else:
            warnings.append('采用分镜的剧本来源无法解析')
    elif link is None or link == '':
        add('script', board)
    else:
        warnings.append('采用分镜的剧本来源格式无效')
    for output in outputs:
        path = (root / output['path']).resolve()
        add('video', path, output['sha256'])
        bundle_path = path.parent / 'edit_bundle.json'
        if not bundle_path.is_file():
            warnings.append('成片无来源清单，须人工补齐镜头及其他采用素材：' + output['path'])
            continue
        bundle = read(bundle_path)
        if not isinstance(bundle, dict):
            warnings.append('成片来源清单格式无效：' + output['path'])
            continue
        for field, category in (('manifest', 'video'), ('fonts', 'font'), ('references', 'reference')):
            rows = bundle.get(field, [])
            if not isinstance(rows, list):
                warnings.append('来源清单格式无效：' + field)
                continue
            for row in rows:
                source = row.get('source' if field == 'manifest' else 'path') if isinstance(row, dict) else None
                if not isinstance(source, str) or not source.strip():
                    warnings.append('来源清单缺少路径，须人工补齐：' + field)
                    continue
                row_category = row.get('category', 'reference') if field == 'references' else category
                if field == 'references' and row_category not in ('reference', 'image'):
                    warnings.append('参考来源类别无效')
                    continue
                add(row_category, path.parent / source, row.get('sha256'))
        if (path.parent / 'font.ttc').is_file():
            add('font', path.parent / 'font.ttc')
    return categories, warnings


def commercial_template(root):
    """生成待填写清单，不把技术检查或空声明当作授权。"""
    from agent.core import read
    scope = media_scope(root)
    data = read(media_manifest_path(root, 'delivery', scope))
    _validate_media_completion(root, 'delivery', data)
    categories, warnings = _commercial_inventory(root, scope, data['outputs'])
    return {'schema': 1, 'scope': scope, 'outputs': data['outputs'],
            'inventory_reviewer': '', 'inventory_complete': False,
            'categories': categories, 'inventory_warnings': warnings,
            'content_review': {key: {'status': 'pending', 'reviewer': '', 'evidence': ''}
                               for key in ('infringement', 'nsfw', 'sensitive')}}


def validate_commercial_evidence(root, evidence):
    """核验声明、文件摘要及人工审查证据；不判断授权文件法律效力。"""
    from agent.core import file_hash, read
    root = Path(root).resolve()
    scope = media_scope(root)
    data = read(media_manifest_path(root, 'delivery', scope))
    _validate_media_completion(root, 'delivery', data)
    if not isinstance(evidence, dict) or evidence.get('schema') != 1 or evidence.get('scope') != scope:
        raise ValueError('商用资料不属于当前采用分镜版本')
    if evidence.get('outputs') != data['outputs']:
        raise ValueError('商用审查对应成片已改变，请重新审查')
    def nonempty(value):
        return isinstance(value, str) and bool(value.strip())
    def frozen_file(item):
        if not isinstance(item, dict) or not nonempty(item.get('path')):
            raise ValueError('授权资料或素材缺少本地文件')
        path = (root / item['path']).resolve()
        if not path.is_relative_to(root) or not path.is_file() or not path.stat().st_size:
            raise ValueError('授权资料或素材必须位于本项目且非空')
        if file_hash(path) != item.get('sha256'):
            raise ValueError('授权资料或素材摘要不一致，请重新审查')
        receipt_path = path.with_name(path.name + '.source.json')
        if receipt_path.is_file():
            receipt = read(receipt_path)
            if (not isinstance(receipt, dict) or receipt.get('sha256') != item.get('sha256')
                    or receipt.get('imported_file') != path.name):
                raise ValueError('导入来源记录与素材不一致，请恢复导入版本或重新导入')
    if evidence.get('inventory_complete') is not True or not nonempty(evidence.get('inventory_reviewer')):
        raise ValueError('需由审核人确认清单覆盖成片全部采用素材和参考来源')
    categories = evidence.get('categories')
    if not isinstance(categories, dict) or set(categories) != set(COMMERCIAL_CATEGORIES):
        raise ValueError('必须逐类核对剧本、参考、图像、视频、音乐、字体和声音')
    for category, group in categories.items():
        if not isinstance(group, dict) or not isinstance(group.get('items'), list):
            raise ValueError('素材清单格式错误：' + category)
        if not group['items']:
            if category in ('script', 'video') or not nonempty(group.get('unused_reason')):
                raise ValueError('缺少素材或未使用说明：' + category)
        for item in group['items']:
            frozen_file(item)
            if (not nonempty(item.get('source')) or not nonempty(item.get('rights_holder'))
                    or not nonempty(item.get('license')) or item.get('commercial_allowed') is not True
                    or item.get('derivative_allowed') is not True or item.get('obligations_fulfilled') is not True):
                raise ValueError('授权范围或履约记录不完整：' + category)
            frozen_file(item.get('authorization'))
    # 来源剧本沿用分镜目录的解析规则；不能拿其他作品的授权代替。
    from storyboard_catalog_service import board_source_script
    from project_context_factory import project_context
    board_path = root / scope['source']
    source_value = read(board_path).get('source_script')
    if source_value is not None and not isinstance(source_value, str):
        raise ValueError('采用分镜的剧本来源无效，请补齐来源')
    script_path = board_source_script(project_context(root), board_path) if source_value else board_path
    if (script_path is None or not script_path.is_relative_to(root)
            or not script_path.is_file() or not script_path.stat().st_size):
        raise ValueError('采用分镜的剧本来源缺失或不在项目内')
    scripts = {(root / item['path']).resolve(): item['sha256']
               for item in categories['script']['items']}
    if scripts.get(script_path) != file_hash(script_path):
        raise ValueError('剧本授权清单未覆盖当前分镜实际来源')
    declared = {(root / item['path']).resolve(): item['sha256']
                for item in categories['video']['items']}
    known_hashes = set(declared.values())
    for output in data['outputs']:
        path = (root / output['path']).resolve()
        if declared.get(path) != output['sha256']:
            raise ValueError('视频授权清单未覆盖实际交付成片')
        bundle_path = path.parent / 'edit_bundle.json'
        if bundle_path.exists():
            bundle = read(bundle_path)
            if (not isinstance(bundle, dict) or bundle.get('master') != path.name
                    or bundle.get('master_sha256') != output['sha256']):
                raise ValueError('成片来源清单与交付文件不一致')
            rows = bundle.get('manifest')
            if not isinstance(rows, list) or not rows:
                raise ValueError('成片来源清单为空或无效')
            if any(not isinstance(row, dict) or not row.get('sha256')
                   or row['sha256'] not in known_hashes for row in rows):
                raise ValueError('授权清单未覆盖成片已登记的镜头来源')
            for row in rows:
                if 'source' not in row:  # 旧版清单仅有摘要，仍限定视频类别。
                    continue
                if not isinstance(row['source'], str) or not row['source'].strip():
                    raise ValueError('成片镜头来源路径无效')
                source = (path.parent / row['source']).resolve()
                if (not source.is_relative_to(root) or not source.is_file()
                        or declared.get(source) != row['sha256']
                        or file_hash(source) != row['sha256']):
                    raise ValueError('视频授权未覆盖成片实际镜头来源版本')
            references = bundle.get('references', [])
            if not isinstance(references, list):
                raise ValueError('成片参考来源清单无效')
            for reference in references:
                if (not isinstance(reference, dict) or not isinstance(reference.get('path'), str)
                        or not reference['path'].strip()):
                    raise ValueError('成片参考来源清单无效')
                category = reference.get('category', 'reference')
                if category not in ('reference', 'image'):
                    raise ValueError('成片参考来源类别无效')
                declared_references = {(root / item['path']).resolve(): item['sha256']
                                       for item in categories[category]['items']}
                reference_path = (path.parent / reference['path']).resolve()
                if (not reference_path.is_relative_to(root) or not reference_path.is_file()
                        or declared_references.get(reference_path) != reference.get('sha256')
                        or file_hash(reference_path) != reference.get('sha256')):
                    raise ValueError('参考授权未覆盖镜头生成时采用的素材版本')
            fonts = bundle.get('fonts', [])
            if not isinstance(fonts, list):
                raise ValueError('成片字体来源清单无效')
            # 兼容旧成片：已有叠字字体副本也不能声明为未使用。
            local_font = path.parent / 'font.ttc'
            if local_font.is_file():
                fonts = [*fonts, {'path': 'font.ttc', 'sha256': file_hash(local_font)}]
            declared_fonts = {(root / item['path']).resolve(): item['sha256']
                              for item in categories['font']['items']}
            for font in fonts:
                if not isinstance(font, dict) or not isinstance(font.get('path'), str):
                    raise ValueError('成片字体来源清单无效')
                font_path = (path.parent / font['path']).resolve()
                if (not font_path.is_relative_to(path.parent) or not font_path.is_file()
                        or declared_fonts.get(font_path) != font.get('sha256')
                        or file_hash(font_path) != font.get('sha256')):
                    raise ValueError('字体授权未覆盖成片实际使用的字体版本')
    reviews = evidence.get('content_review')
    if not isinstance(reviews, dict):
        raise ValueError('缺少内容审查记录')
    for key in ('infringement', 'nsfw', 'sensitive'):
        review = reviews.get(key)
        if (not isinstance(review, dict) or review.get('status') != 'cleared'
                or not nonempty(review.get('reviewer')) or not nonempty(review.get('evidence'))):
            raise ValueError('内容风险未完成审核：' + key)
    return True


def commercial_evidence_path(root):
    scope = media_scope(root)
    return media_manifest_path(root, 'delivery', scope).with_suffix('.commercial.json')


def create_commercial_template(root):
    from agent.core import save
    target = commercial_evidence_path(root).with_suffix('.pending.json')
    if target.exists():
        raise ValueError('待填资料已存在，请保留已填写内容：' + str(target))
    save(target, commercial_template(root))
    return target


def confirm_commercial_evidence(root, evidence):
    from agent.core import save
    validate_commercial_evidence(root, evidence)
    target = commercial_evidence_path(root)
    save(target, evidence)
    return target


def commercial_delivery_status(root):
    from agent.core import read
    try:
        validate_commercial_evidence(root, read(commercial_evidence_path(root)))
        return True, '商用资料核验通过（依据人工授权与内容审核记录）'
    except (ValueError, OSError, KeyError, TypeError) as error:
        return False, '商用交付待核验：' + str(error)


def media_completion_evidence(root, stage):
    from agent.core import read
    scope = media_scope(root)
    target = media_manifest_path(root, stage, scope)
    if not target.is_file():
        return False, '已导入或生成的文件尚未确认；请点击“校验并确认本阶段成果”'
    _validate_media_completion(root, stage, read(target))
    return True, ''


def completion_evidence(root, stage, video_ready=None):
    """返回阶段是否已有可复核成果及未通过原因。"""
    try:
        root = Path(root) if root else None
    except (TypeError, ValueError):
        return False, '项目路径无效，不能确认阶段完成'
    if root is None:
        return True, ''
    if not root.is_dir():
        return False, '项目目录不存在，不能确认阶段完成'
    stage = str(stage or '')
    try:
        if stage in ('audio', 'edit', 'delivery'):
            return media_completion_evidence(root, stage)
        if stage in ('script', 'script_structure'):
            from skill_orchestrator import verified_stage_output
            ok = verified_stage_output(root, stage)
            return ok, '没有找到可读取的%s成果' % pet_bus.STAGE_NAMES.get(stage, stage)
        if stage == 'animatic':
            from animatic_service import evidence
            return evidence(root)
        if stage == 'storyboard':
            from stage_parallel import _adopted
            from storyboard_selection import draft_problems
            if not any(shots for _source, shots in _adopted(root)):
                return False, '还没有已采用且含镜头的分镜 JSON'
            problems = draft_problems(root)
            return not problems, '；'.join(problems[:2])
        checks = {'assets': 'assets_locked', 'continuity': 'ledger_ready', 'final': 'batches_ready',
                  'keyframe': 'frames_ready', 'previs': 'previs_ready'}
        if stage in checks:
            import stage_parallel
            result = getattr(stage_parallel, checks[stage])(root)
            return bool(result.get('ok') and result.get('started')), str(result.get('detail') or '阶段成果尚未通过校验')
        if stage == 'video' and callable(video_ready):
            digest, _waiting = video_ready()
            return bool(digest), '没有全部下载、质检并验收的视频镜头'
        folders, suffixes = media_output_folders(root, stage)
        if not folders and stage in pet_bus.STAGES:
            from project_stages import stage as stage_dir
            folders = (stage_dir(root, stage),)
        for folder in folders:
            if folder.is_dir():
                for path in folder.rglob('*'):
                    if path.is_file() and path.suffix.lower() in suffixes and path.stat().st_size:
                        return True, ''
        return False, '没有找到可核验的%s成果文件' % pet_bus.STAGE_NAMES.get(stage, stage)
    except (OSError, TypeError, ValueError, KeyError, ImportError) as exc:
        return False, '成果校验失败：%s' % exc


def emit_verified_completion(root, stage, text, emit, video_ready=None, before_emit=None):
    """核验成果后才通过受控事件出口标记阶段完成。"""
    ok, detail = completion_evidence(root, stage, video_ready)
    if not ok:
        return False, detail, None
    if stage in ('keyframe', 'previs'):
        try:
            publish_stage_manifest(root, stage)
        except (OSError, ValueError) as exc:
            return False, '阶段输出清单写入失败：%s' % exc, None
    if callable(before_emit):
        before_emit()
    return True, '', emit('stage.completed', stage=str(stage or ''), text=text)


def publish_stage_manifest(root, stage):
    """核验通过后落盘阶段输出清单（stage_layout 契约名 frames.json／previs.json）；清单是回执，不是完成证据。"""
    from datetime import datetime
    from agent.core import save
    from project_context_factory import project_context
    from stage_parallel import _adopted
    from stage_path_service import write_dir
    root = Path(root)
    stamp = datetime.now().isoformat(timespec='seconds')
    if stage == 'keyframe':
        from storyboard_paths import media_root
        episodes = []
        for source, shots in _adopted(root):
            base = media_root(source).resolve()
            rows = []
            for shot in shots:
                evidence = shot.get('frame_evidence')
                image = evidence.get('image') if isinstance(evidence, dict) else None
                rows.append({'id': shot.get('id'), 'frame': shot.get('frame'),
                             'deleted': bool(shot.get('frame_deleted')),
                             'sha256': image.get('sha256') if isinstance(image, dict) else None})
            episodes.append({'source': str(source), 'media_root': str(base), 'shots': rows})
        target = write_dir(root, 'keyframe') / 'output' / 'frames.json'
        save(target, {'schema': 1, 'stage': 'keyframe', 'generated_at': stamp, 'episodes': episodes})
        return target
    import white_model_service as wm
    from previs_routing import decisions_for
    context = project_context(root)
    required = {}
    for source, shots in _adopted(root):
        decisions = decisions_for(context, source, shots)
        for sid, item in decisions.items():
            if item.get('level') in ('complex', 'medium'):
                required[sid] = item['level']
                try:
                    wm.sync_project_copy(context, sid, source, publish=save)
                except (OSError, ValueError):
                    import app_logging
                    app_logging.swallowed('预演项目内副本未写入')
    index = wm.read_project_index(context)
    index.update(stage='previs', generated_at=stamp, required=required)
    target = wm.project_index_path(context, write=True)
    save(target, index)
    return target
