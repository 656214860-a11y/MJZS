"""无界面的阶段成果核验服务。"""
from pathlib import Path
import json
import math

import contract.pet_bus as pet_bus
from domain.idea_script_heuristic import flexible_structure_manifests


def media_output_folders(root, stage):
    """返回媒体阶段的成果目录与允许扩展名（成片后缀与导入共用 delivery_import_service 那一份）。"""
    from domain.delivery_import_service import ALLOWED_SUFFIXES
    from contract.stage_path_service import read_dirs
    video = set(ALLOWED_SUFFIXES)
    if stage == 'audio':
        return tuple(folder / '音频' for folder in read_dirs(root,'audio')), {'.mp3', '.wav', '.m4a', '.aac'}
    if stage == 'edit':
        return (*read_dirs(root, 'edit'), *(folder / '导出成片' for folder in read_dirs(root,'delivery'))), video
    if stage == 'delivery':
        return read_dirs(root,'delivery'), video
    return (), set()


def media_scope(root):
    """当前已采用分镜及内容版本；切集和改稿均使旧确认失效。"""
    from agent.core import file_hash, read
    from domain.storyboard_adoption_contract import adopted, prefs, resolve_source
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
    from contract.stage_path_service import write_dir
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


def _edit_bundle_status(path, digest):
    """剪辑成果须与同目录来源清单的成片摘要及质检结论一致；无清单的外部成片返回警告。"""
    from agent.core import read
    bundle_path = Path(path).parent / 'edit_bundle.json'
    if not bundle_path.is_file():
        return '无来源清单，须人工核对'
    try:
        bundle = read(bundle_path)
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError('剪辑来源清单无法读取，请重新导出或补齐清单') from exc
    if not isinstance(bundle, dict):
        raise ValueError('剪辑来源清单格式无效，不能确认后期剪辑完成')
    if bundle.get('master_sha256') != digest:
        raise ValueError('这不是该次剪辑登记的成片（可能是单镜文件）')
    qc = bundle.get('qc')
    if not isinstance(qc, dict):
        raise ValueError('剪辑来源清单缺少质检结论，不能确认后期剪辑完成')
    errors = qc.get('errors')
    if not isinstance(errors, list):
        raise ValueError('剪辑来源清单的质检结论格式无效，不能确认后期剪辑完成')
    if errors:
        raise ValueError('该成片的剪辑质检未通过，不能确认后期剪辑完成')
    return ''


def prepare_media_completion(root, stage, paths, *, scope=None):
    """后台技术校验并冻结待审核清单；不因导入或探测成功自动完成。"""
    from agent.core import file_hash, read
    from agent.media import probe
    from contract.platform_tools import tool_path
    root = Path(root).resolve()
    current = media_scope(root)
    if scope is not None and scope != current:
        raise ValueError('当前分镜已切换或修改，请重新选择成果')
    scope = current
    media_manifest_path(root, stage, scope)
    config = read(root / 'config.json') if (root / 'config.json').is_file() else {}
    executable = tool_path('ffprobe', configured=config.get('ffprobe'))
    if not executable:
        raise ValueError('请先配置 FFprobe，再校验媒体成果；在 config.json 设路径，见环境自检')
    outputs = []
    warnings = []
    for path in dict.fromkeys(_media_path(root, stage, value) for value in paths):
        digest = file_hash(path)
        if stage == 'edit':
            warning = _edit_bundle_status(path, digest)
            if warning and warning not in warnings:
                warnings.append(warning)
        probed = probe(path, {'ffprobe': executable})
        validation = _technical_media(stage, probed)
        if file_hash(path) != digest:
            raise ValueError('校验期间成果文件发生变化，请重试')
        outputs.append({'path': path.relative_to(root).as_posix(), 'sha256': digest,
                        'size': path.stat().st_size, 'validation': validation,
                        'has_audio': any(isinstance(item, dict) and item.get('codec_type') == 'audio'
                                         for item in probed.get('streams') or [])})
    if not outputs:
        raise ValueError('请至少选择一份本阶段媒体成果；字幕或压缩包不能替代媒体')
    if stage == 'audio':
        from domain.tts_api import audio_kind
        if not any(audio_kind(Path(output['path']).name) == 'dialogue' for output in outputs):
            raise ValueError('所选音频都不是对白音轨（只有 BGM／音效／旁白），不能代替对白配音完成核验')
    data = {'schema': 1, 'stage': stage, 'scope': scope, 'status': 'pending_review', 'outputs': outputs}
    if warnings:
        data['warnings'] = warnings
    if stage == 'delivery':
        data['qc'] = build_delivery_qc(root, outputs)
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
        if stage == 'edit':
            _edit_bundle_status(path, output.get('sha256'))
    if stage == 'delivery' and require_review:
        qc = data.get('qc')
        if (not isinstance(qc, dict) or qc.get('passed') is not True
                or qc.get('bound') != [output.get('sha256') for output in outputs]):
            raise ValueError('缺少与当前成片对应的质检通过结论，请重新校验确认')


def confirm_media_completion(root, stage, prepared):
    """仅显式人工确认入口调用；发布前重新核对冻结版本。"""
    from agent.core import save
    _validate_media_completion(root, stage, prepared, require_review=False)
    if stage == 'delivery':
        qc = prepared.get('qc')
        if not isinstance(qc, dict) or qc.get('passed') is not True:
            problems = '；'.join((qc or {}).get('errors') or ['缺少质检结论'])
            raise ValueError('质检未通过，不能确认交付完成：' + problems)
    data = dict(prepared, status='complete', reviewed=True)
    if stage == 'delivery':
        data['commercial_status'] = 'pending'
    target = media_manifest_path(root, stage, data['scope'])
    save(target, data)
    if stage == 'delivery':
        publish_delivery_artifacts(root, data)
    return target


REPORT_NAME = 'delivery_report.md'


def delivery_record(root):
    """读取已确认且仍然有效的交付清单；未确认、被改动或质检未过都抛 ValueError。"""
    from agent.core import read
    root = Path(root).resolve()
    ok, detail = media_completion_evidence(root, 'delivery')
    if not ok:
        raise ValueError(detail)
    data = read(media_manifest_path(root, 'delivery', media_scope(root)))
    if not isinstance(data.get('qc'), dict) or data['qc'].get('passed') is not True:
        raise ValueError('交付清单没有质检通过结论，请重新校验确认')
    return data


def package_delivery(root):
    """（重新）落盘质检报告、交付摘要与文件清单，返回交付清单里的文件行。"""
    from agent.core import read
    root = Path(root).resolve()
    data = delivery_record(root)
    publish_delivery_artifacts(root, data)
    from contract.stage_path_service import write_dir
    return read(write_dir(root, 'delivery') / 'delivery_manifest.json')['files']


def publish_delivery_report(root):
    """交付报告（人读）：成片、质检结论、警告与商用状态；只陈述记录，不替人审核。"""
    from agent.core import save_text
    from contract.stage_path_service import write_dir
    root = Path(root).resolve()
    data = delivery_record(root)
    qc = data['qc']
    lines = ['# 交付报告', '', '- 集：' + str(data['scope'].get('episode')), '- 质检：通过', '- ' + commercial_status(root)[1], '',
             '## 成片']
    for output in data['outputs']:
        lines.append('- %s（%.1f 秒，sha256 %s）' % (output['path'], output['validation']['duration'], output['sha256'][:12]))
    lines += ['', '## 质检警告'] + (['- ' + item for item in qc.get('warnings') or []] or ['- 无'])
    lines += ['', '本报告只汇总确认记录；画面、对白、剧情与商用授权由人工审核。']
    target = write_dir(root, 'delivery') / REPORT_NAME
    save_text(target, '\n'.join(lines) + '\n')
    return target


def build_delivery_qc(root, outputs):
    """交付质检结论：只依据可复核的事实（技术校验、剪辑质检、来源清单），人工审核仍在确认环节。"""
    from agent.core import file_hash, read
    root = Path(root).resolve()
    errors, warnings, rows = [], [], []
    for output in outputs:
        path = (root / output['path']).resolve()
        checks = ['技术校验通过（视频流、时长、画面尺寸）']
        if output.get('has_audio') is False:
            warnings.append(path.name + ' 没有音轨')
        bundle_path = path.parent / 'edit_bundle.json'
        if bundle_path.is_file():
            bundle = read(bundle_path)
            if (not isinstance(bundle, dict) or bundle.get('master') != path.name
                    or bundle.get('master_sha256') != file_hash(path)):
                errors.append(path.name + ' 与剪辑来源清单不一致')
            else:
                checks.append('与剪辑来源清单一致')
                qc = bundle.get('qc') if isinstance(bundle.get('qc'), dict) else {}
                for message in qc.get('errors') or []:
                    errors.append(path.name + ' 剪辑质检：' + str(message))
                skipped = (bundle.get('coverage') or {}).get('skipped') or []
                if skipped:
                    warnings.append(path.name + ' 粗剪跳过了 %d 个未就绪镜头' % len(skipped))
        else:
            warnings.append(path.name + ' 没有剪辑来源清单（外部导入成片），来源须人工核对')
        rows.append({'path': output['path'], 'sha256': output['sha256'], 'checks': checks})
    return {'passed': not errors, 'errors': errors, 'warnings': warnings, 'outputs': rows,
            'bound': [output['sha256'] for output in outputs]}


def publish_delivery_artifacts(root, data):
    """交付确认后落盘本阶段声明的产物：质检报告、交付摘要和带摘要的文件清单。"""
    import time
    from agent.core import file_hash, save
    from contract.stage_path_service import write_dir
    root = Path(root).resolve()
    folder = write_dir(root, 'delivery')
    now = time.time()
    save(folder / 'qc_report.json', {'schema': 1, 'scope': data['scope'], 'qc': data['qc'], 'confirmed_at': now})
    save(folder / 'delivery.json', {'schema': 1, 'scope': data['scope'],
                                    'outputs': [{'path': item['path'], 'sha256': item['sha256']}
                                                for item in data['outputs']],
                                    'qc_passed': True, 'commercial_status': data['commercial_status'],
                                    'confirmed_at': now})
    files = [{'path': item['path'], 'sha256': item['sha256'], 'role': 'master'} for item in data['outputs']]
    for name in ('qc_report.json', 'delivery.json', REPORT_NAME):
        if not (folder / name).is_file():
            continue
        files.append({'path': (folder / name).relative_to(root).as_posix(),
                      'sha256': file_hash(folder / name), 'role': 'record'})
    save(folder / 'delivery_manifest.json', {'schema': 1, 'scope': data['scope'], 'files': files})


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


def _commercial_script(root, scope):
    """采用分镜的剧本来源；返回 (路径, 待填警告, 核验错误)。"""
    from agent.core import read
    from domain.storyboard_catalog_service import board_source_script
    from orchestrator.project_context_factory import project_context
    root = Path(root).resolve()
    board = root / scope['source']
    link = read(board).get('source_script')
    if link is not None and not isinstance(link, str):
        return None, '采用分镜的剧本来源格式无效', '采用分镜的剧本来源无效，请补齐来源'
    script = board_source_script(project_context(root), board) if link else board
    if (script is not None and script.is_relative_to(root)
            and script.is_file() and script.stat().st_size):
        return script.resolve(), '', ''
    if link:
        return None, '采用分镜的剧本来源无法解析', '采用分镜的剧本来源缺失或不在项目内'
    return None, '', '采用分镜的剧本来源缺失或不在项目内'


def _commercial_inventory(root, scope, outputs):
    """只盘点已登记来源边，不推断授权，也不扫描无关项目文件。"""
    from domain.commercial_inventory_service import collect_inventory
    script, warning, _error = _commercial_script(root, scope)
    return collect_inventory(root, scope, outputs, script_path=script, script_warning=warning)


def commercial_template(root):
    """生成待填写清单，不把技术检查或空声明当作授权。"""
    from agent.core import read
    scope = media_scope(root)
    data = read(media_manifest_path(root, 'delivery', scope))
    _validate_media_completion(root, 'delivery', data)
    inventory = _commercial_inventory(root, scope, data['outputs'])
    return {'schema': 1, 'scope': scope, 'outputs': data['outputs'],
            'inventory_reviewer': '', 'inventory_complete': False,
            'categories': inventory['categories'], 'inventory_warnings': inventory['warnings'],
            'inventory_trace': {'requirements': inventory['requirements'],
                                'trace_gaps': inventory['trace_gaps']},
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
            raise ValueError('授权凭据或素材摘要不一致，请重新审查')
        receipt_path = path.with_name(path.name + '.source.json')
        snapshot = item.get('source_receipt')
        if isinstance(snapshot, dict) and nonempty(snapshot.get('path')):
            expected_receipt = (root / snapshot['path']).resolve()
            if expected_receipt != receipt_path or not expected_receipt.is_relative_to(root):
                raise ValueError('导入来源记录路径无效，请恢复导入版本或重新导入')
            if not expected_receipt.is_file():
                raise ValueError('导入来源记录缺失，请恢复导入版本或重新导入')
            if file_hash(expected_receipt) != snapshot.get('sha256'):
                raise ValueError('导入来源记录已改变，请恢复导入版本或重新导入')
        if receipt_path.is_file():
            try:
                receipt = read(receipt_path)
            except (OSError, ValueError, TypeError):
                raise ValueError('导入来源记录无法读取，请恢复导入版本或重新导入') from None
            if (not isinstance(receipt, dict) or receipt.get('sha256') != item.get('sha256')
                    or receipt.get('imported_file') != path.name):
                raise ValueError('导入来源记录与素材不一致，请恢复导入版本或重新导入')
            declared_source = item.get('source')
            if (nonempty(declared_source) and declared_source.startswith('外部导入：')
                    and declared_source != '外部导入：' + str(receipt.get('source') or '')):
                raise ValueError('导入来源记录已改变，请恢复导入版本或重新导入')
        elif nonempty(item.get('source')) and item['source'].startswith('外部导入：'):
            raise ValueError('导入来源记录缺失，请恢复导入版本或重新导入')
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
    script_path, _script_warning, script_error = _commercial_script(root, scope)
    if script_error:
        raise ValueError(script_error)
    scripts = {(root / item['path']).resolve(): item['sha256']
               for item in categories['script']['items']}
    if scripts.get(script_path) != file_hash(script_path):
        raise ValueError('剧本授权清单未覆盖当前分镜实际来源')
    _validate_commercial_coverage(root, scope, data, categories, script_path)
    reviews = evidence.get('content_review')
    if not isinstance(reviews, dict):
        raise ValueError('缺少内容审查记录')
    for key in ('infringement', 'nsfw', 'sensitive'):
        review = reviews.get(key)
        if (not isinstance(review, dict) or review.get('status') != 'cleared'
                or not nonempty(review.get('reviewer')) or not nonempty(review.get('evidence'))):
            raise ValueError('内容风险未完成审核：' + key)
    return True


def _commercial_declared(root, categories):
    return {category: {(root / item['path']).resolve(): item['sha256']
                       for item in group['items']}
            for category, group in categories.items()}


def _commercial_requirement_path(root, value):
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _commercial_requirement_error(requirement):
    """缺项提示必须落到可行动的文件、摘要或来源边；保留原类别提示作前缀。"""
    error = requirement.get('error') or '授权清单未覆盖实际采用素材'
    path = str(requirement.get('path') or '')
    if path:
        return error + '：' + path
    sha256 = str(requirement.get('sha256') or '')
    edge = str(requirement.get('edge') or '')
    if sha256:
        detail = 'sha256 ' + sha256[:12]
        if edge:
            detail += '（' + edge + '）'
        return error + '：' + detail
    if edge:
        return error + '：' + edge
    return error


def _validate_commercial_requirement(root, requirement, declared):
    from agent.core import file_hash
    root = Path(root).resolve()
    kind = requirement.get('kind')
    error = _commercial_requirement_error(requirement)
    if kind == 'structural' or str(kind).startswith('invalid_'):
        raise ValueError(error)
    category = requirement.get('category')
    sha256 = str(requirement.get('sha256') or '')
    rows = declared.get(category, {})
    if kind == 'shot_hash':
        if not sha256 or sha256 not in rows.values():
            raise ValueError(error)
        return
    if not requirement.get('path'):
        raise ValueError(error)
    path = _commercial_requirement_path(root, requirement['path'])
    base = _commercial_requirement_path(root, requirement['base']) if requirement.get('base') else root
    if (not path.is_relative_to(root) or not path.is_relative_to(base) or not path.is_file()
            or rows.get(path) != sha256 or file_hash(path) != sha256):
        raise ValueError(error)


def _validate_commercial_coverage(root, scope, data, categories, script_path):
    """按同一份递归盘点 requirements 核验；多项缺失一次列出，不用首项吞掉其余缺项。"""
    from domain.commercial_inventory_service import collect_inventory
    inventory = collect_inventory(root, scope, data['outputs'], script_path=script_path)
    declared = _commercial_declared(root, categories)
    errors = []
    for requirement in inventory['requirements']:
        try:
            _validate_commercial_requirement(root, requirement, declared)
        except ValueError as exc:
            message = str(exc)
            if message not in errors:
                errors.append(message)
    if errors:
        raise ValueError('；'.join(errors))


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
    from agent.core import read, save
    validate_commercial_evidence(root, evidence)
    target = commercial_evidence_path(root)
    save(target, evidence)
    manifest = media_manifest_path(root, 'delivery', media_scope(root))
    data = read(manifest)
    data['commercial_status'] = 'verified'
    save(manifest, data)
    return target


def commercial_status(root):
    """交付页常驻显示的商用状态：none 未确认成片、pending 待核验、verified 已核验（依据人工授权记录）。"""
    from agent.core import read
    try:
        data = read(media_manifest_path(root, 'delivery', media_scope(root)))
        _validate_media_completion(root, 'delivery', data)
    except (ValueError, OSError, KeyError, TypeError):
        return 'none', '商用状态：尚未确认交付成片'
    ok, text = commercial_delivery_status(root)
    return ('verified', text) if ok else ('pending', text)


def commercial_trace_summary(root):
    """交付页只读盘点提示：对已有待填/已核验资料比对当前文件，不写盘。"""
    from agent.core import read
    root = Path(root).resolve()
    try:
        scope = media_scope(root)
        data = read(media_manifest_path(root, 'delivery', scope))
        _validate_media_completion(root, 'delivery', data)
    except (ValueError, OSError, KeyError, TypeError):
        return '商用素材盘点：确认交付成片后，生成待填资料以显示遗漏、来源变更与人工补录'
    final = commercial_evidence_path(root)
    candidates = (final.with_suffix('.pending.json'), final)
    evidence = None
    for candidate in candidates:
        if candidate.is_file():
            try:
                evidence = read(candidate)
            except (OSError, ValueError, TypeError) as exc:
                return '商用素材盘点：资料文件无法读取，请保留原文件并人工核对：' + candidate.name
            break
    if not isinstance(evidence, dict):
        return '商用素材盘点：生成商用待填资料后显示遗漏、来源变更与人工补录'
    script, warning, _error = _commercial_script(root, scope)
    from domain.commercial_inventory_service import collect_inventory, review_inventory, review_text
    inventory = collect_inventory(root, scope, data['outputs'], script_path=script, script_warning=warning)
    return review_text(review_inventory(root, inventory, evidence))


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


def preparation_progress(project):
    """只读：报告剧本准备四份文档各自的落盘与确认现状（LOST-04 后不再是卡点判据）。

    用户 11-22 23:12 第 1 条取消了「项目大纲→设定→角色卡→自然剧本」先后链：
    四份文档相互独立、任意顺序生成，三份阶段稿是可选参考，剧本阶段完成只认
    已采用的自然剧本（``completion_evidence`` 的 script 分支）。本函数保留给
    监控与诊断展示各文档现状，不再输出会阻塞推进的 ``blocked``。

    返回 dict：
      blocked —— 恒为空串（四文档互不设卡，保留键位兼容旧消费方）；
      missing —— 恒为 False（同上）；
      confirmed —— 台账中已确认的阶段稿份数（0~3，不要求连号）；
      stages —— 三个阶段各自的 (阶段名, 文件在否, 已确认否)，互不影响；
      applicable —— 四阶段确认流程是否适用（存在已确认简报）；False 时
                    confirmed==3 仅表示门禁不适用，与「未开始」区分；
      script —— 自然稿采用状态：'已采用'／'需重新采用'／'待采用'（报告级，
                完成核验仍以 resolve_script_source 为准）；
      script_quality —— 采用稿的质检状态表（`writing_quality.REPORTS` 键→status），
                未生成报告为 None；采用稿质检有 fail/invalid 项时 next_actions
                指向重新生成或修订后重新采用；
      next_actions —— 按自然稿采用状态推导的下一步动作建议元组。
    """
    from infra.file_cache import read_json
    from contract.stage_path_service import write_dir
    from writing_api import PREPARATION_STAGES
    folder = write_dir(project, 'script').resolve()
    brief = folder / 'brief_complete.json'
    if not brief.is_file() and not (Path(project) / 'writing' / 'brief_complete.json').is_file():
        return {'blocked': '', 'missing': False, 'confirmed': len(PREPARATION_STAGES),
                'stages': (), 'applicable': False,
                'script': _script_adoption_state(project),
                'script_quality': _adopted_script_quality(project),
                'next_actions': ('完成项目创作信息',)}
    target = folder / 'preparation_state.json'
    try:
        state = read_json(target) if target.is_file() else None
    except (OSError, ValueError):
        state = None
    working = state.get('revision', state) if isinstance(state, dict) else None
    documents = working.get('documents') if isinstance(working, dict) else None
    documents = documents if isinstance(documents, list) else []
    stages = []
    confirmed = 0
    for stage in PREPARATION_STAGES:
        document = next((doc for doc in documents
                         if isinstance(doc, dict) and doc.get('stage') == stage), None)
        present = False
        if document is not None and isinstance(document.get('path'), str) and document['path']:
            try:
                resolved = (folder / document['path']).resolve()
                present = resolved.is_relative_to(folder) and resolved.is_file()
            except (OSError, ValueError):
                present = False
        ok = document is not None and document.get('confirmed') is True
        stages.append((stage, present, ok))
        confirmed += int(ok)
    script = _script_adoption_state(project)
    quality = _adopted_script_quality(project) if script == '已采用' else None
    if script == '需重新采用':
        actions = ('重新生成或明确采用自然剧本',)
    elif script == '待采用':
        actions = ('生成自然剧本并明确采用',)
    elif quality is not None and any(
            status in ('fail', 'invalid') for status in quality.values()):
        actions = ('采用的自然剧本辅助质检未通过，请重新生成或修订后重新采用',)
    else:
        actions = ()
    return {'blocked': '', 'missing': False, 'confirmed': confirmed,
            'stages': tuple(stages), 'applicable': True, 'script': script,
            'script_quality': quality, 'next_actions': actions}


def _script_adoption_state(project):
    """自然稿采用状态（报告级）：'已采用'／'需重新采用'／'待采用'。

    只读 selection 记录与文件存在性；sha 等完整核验由 resolve_script_source
    在完成核验时执行，这里不重复。"""
    from infra.file_cache import read_json
    from contract.script_contract import natural_script_selection_path
    selection = natural_script_selection_path(project)
    record = read_json(selection) if selection.is_file() else None
    if isinstance(record, dict) and record.get('reason') and not record.get('path'):
        return '需重新采用'
    if (isinstance(record, dict) and record.get('path')
            and (Path(project) / str(record['path'])).is_file()):
        return '已采用'
    return '待采用'


def _adopted_script_quality(project):
    """当前采用稿的质检状态表；无采用稿或未生成报告返回 None（报告级只读）。"""
    try:
        from contract.script_contract import resolve_script_source
        from contract.stage_path_service import write_dir
        from domain.writing_quality import adopted_quality
        source = resolve_script_source(project)
        return adopted_quality(source, write_dir(project, 'script') / 'quality') if source else None
    except (ImportError, OSError, TypeError, ValueError):
        return None


def edit_ready_for_project(root):
    """无界面／无 ``Studio`` 的成片就绪核验：返回 ``(成片指纹, 未就绪原因列表)``。

    与 ``Studio.auto_edit_ready`` 同一选版口径（REQ-S10-22）：``episode_file_of``
    解析当前镜头 JSON、只读 ``data/state.json``、逐镜走 ``adopted_edit_version``
    （与 ``auto_edit_ready`` 共用的 ``engine.edit_ready_rows`` 内核）；不建
    ``Studio``，不写 ``config.json``／``state.json``。找不到镜头 JSON、读不动
    或没有任何已采用版本时返回 ``(None, 原因)``，由完成核验判未完成。
    """
    from agent.core import read_json
    from orchestrator.engine import episode_file_of, edit_ready_rows
    root = Path(root).resolve()
    cfg = read_json(root / 'config.json', {})
    if not isinstance(cfg, dict):
        cfg = {}
    episode_path = episode_file_of(root, cfg)
    if not episode_path.is_file():
        return None, ['找不到镜头 JSON（episode.json）']
    episode = read_json(episode_path, {})
    shots = (episode.get('shots') if isinstance(episode, dict) else None) or []
    state = read_json(root / 'data' / 'state.json', {})
    state_shots = state.get('shots') if isinstance(state, dict) else None
    return edit_ready_rows(root, shots, state_shots or {})


def completion_evidence(root, stage, video_ready=None):
    """返回阶段是否已有可复核成果及未通过原因。"""
    try:
        root = Path(root) if root else None
    except (TypeError, ValueError):
        return False, '项目路径无效，不能确认阶段完成'
    if root is None:
        # REQ-S13-54：无项目＝空项目＝未完成。旧口径「root 为空直接通过」是为兼容
        # 轻量宿主的完成判定开了后门，会让空项目被当成已完成、自动链空转推进。
        return False, '未打开项目，无法核验阶段成果'
    if not root.is_dir():
        return False, '项目目录不存在，不能确认阶段完成'
    stage = str(stage or '')
    try:
        if stage in ('audio', 'edit', 'delivery'):
            return media_completion_evidence(root, stage)
        if stage in ('script', 'script_structure'):
            import contract.script_contract as script_contract
            # LOST-04（用户 11-22 23:12 第 1 条）：项目设定／剧本大纲／角色卡／自然剧本
            # 四份文档相互独立、任意顺序生成；剧本阶段完成只认至少一份已采用的自然剧本
            # （resolve_script_source），其余三份是可选参考，不再串行卡点。
            source = (script_contract.resolve_script_source(root) if stage == 'script'
                      else script_contract.structured_script_path(root))
            ok = (source is not None) if stage == 'script' else script_contract.is_structured_script(source)
            if ok and stage == 'script':
                # REQ-S01-22：采用稿存在质检报告时，fail/invalid 项硬卡完成核验。
                from contract.stage_path_service import write_dir
                from domain.writing_quality import adopted_quality, REPORTS, QUALITY_BLOCKING
                statuses = adopted_quality(source, write_dir(root, 'script') / 'quality')
                if statuses is not None:
                    blocked = [key for key in REPORTS if statuses.get(key) in QUALITY_BLOCKING]
                    if blocked:
                        return False, ('采用的自然剧本辅助质检未通过（'
                                       + '、'.join(REPORTS[key][0] for key in blocked)
                                       + '）；请重新生成或修订后重新采用')
            if ok and stage == 'script_structure':
                problems = script_contract.structure_manifest_problems(root, source)  # R2178 J16：与编排器同一判据
                if problems:
                    return False, '剧本结构清单未通过核验：' + problems[0]
            return ok, '没有找到可读取的%s成果' % pet_bus.STAGE_NAMES.get(stage, stage)
        if stage == 'animatic':
            from domain.animatic_service import evidence
            return evidence(root)
        if stage == 'storyboard':
            from orchestrator.stage_parallel import _adopted
            from orchestrator.storyboard_selection import draft_problems
            if not any(shots for _source, shots in _adopted(root)):
                return False, '还没有已采用且含镜头的分镜 JSON'
            problems = draft_problems(root)
            return not problems, '；'.join(problems[:2])
        checks = {'assets': 'assets_locked', 'continuity': 'ledger_ready', 'final': 'batches_ready',
                  'keyframe': 'frames_ready', 'previs': 'previs_ready'}
        if stage in checks:
            import orchestrator.stage_parallel as stage_parallel
            result = getattr(stage_parallel, checks[stage])(root)
            return bool(result.get('ok') and result.get('started')), str(result.get('detail') or '阶段成果尚未通过校验')
        if stage == 'video':
            if callable(video_ready):
                digest, _waiting = video_ready()
                return bool(digest), '没有全部下载、质检并验收的视频镜头'
            # REQ-S10-22／DES-S10-22：无回调（L3 无界面、轻量宿主）时按同一选版口径
            # 只读核验，不再退化为「目录里有任意媒体文件即算完成」。
            digest, waiting = edit_ready_for_project(root)
            if digest:
                return True, ''
            return False, '；'.join(str(item) for item in (waiting or ['没有全部下载、质检并验收的视频镜头']))
        folders, suffixes = media_output_folders(root, stage)
        if not folders and stage in pet_bus.STAGES:
            from contract.project_stages import stage as stage_dir
            folders = (stage_dir(root, stage),)
        for folder in folders:
            if folder.is_dir():
                for path in folder.rglob('*'):
                    if path.is_file() and path.suffix.lower() in suffixes and path.stat().st_size:
                        return True, ''
        return False, '没有找到可核验的%s成果文件' % pet_bus.STAGE_NAMES.get(stage, stage)
    except (OSError, TypeError, ValueError, KeyError, ImportError) as exc:
        return False, '成果校验失败：%s' % exc


def _sync_flexible_manifests(script_contract, root, text):
    from agent.core import read, save_text
    flex = flexible_structure_manifests(script_contract, text)
    if not any(item.get('items') for item in flex.values()):
        return False, '', False
    folder = script_contract.structure_manifest_dir(root)
    if not script_contract.structure_manifest_problems(root):
        same = all(
            sorted(str(x.get('name') or '') for x in script_contract.items_of(read(folder / name)))
            == sorted(x['name'] for x in data['items'])
            for name, data in flex.items()
        )
        if same:
            return True, '', False
    for name, data in flex.items():
        save_text(folder / name, json.dumps(data, ensure_ascii=False, indent=2))
    if not script_contract.structure_manifest_problems(root):
        return True, '已按当前结构剧本补全清单', True
    return False, '', False


def storyboard_send_readiness(project):
    """初步分镜发送门禁（REQ-S03-55）：有可用结构稿即可发送，不复用 S02 完成核验。

    返回 ``(可发送, 说明, 已自动补清单)``。唯一拦截情形是没有可用结构稿；
    三份清单有问题时先按当前结构稿派生补写一次（先严格格式、再兼容模型变体标题／列表／表格），
    补得上就放行并说明，补不出（如模型按集写的稿没有可派生名单）也只给说明、不拦截。
    ``completion_evidence`` 的判定不受影响。
    """
    try:
        root = Path(project) if project else None
    except (TypeError, ValueError):
        root = None
    blocked_note = '还没有可用的结构剧本，请先到「剧本结构」页确认一份结构剧本，再回来发送'
    if root is None or not root.is_dir():
        return False, blocked_note, False
    import contract.script_contract as script_contract
    try:
        candidates = script_contract.structured_script_paths(root)
    except (OSError, TypeError, ValueError):
        candidates = ()
    source = candidates[0] if candidates else None
    if source is None or not script_contract.is_structured_script(source):
        return False, blocked_note, False
    problems = script_contract.structure_manifest_problems(root, source)
    if not problems:
        return True, '', False
    try:
        text = Path(source).read_text(encoding='utf-8-sig', errors='replace')
        derived = script_contract.structure_manifests(text)
        if any(manifest.get('items') for manifest in derived.values()):
            script_contract.write_structure_manifests(root, text)
            problems = script_contract.structure_manifest_problems(root, source)
            if not problems:
                return True, '已按当前结构剧本补全清单', True
        ok, note, filled = _sync_flexible_manifests(script_contract, root, text)
        if ok:
            return True, note, filled
    except (OSError, TypeError, ValueError, KeyError, ImportError):
        pass
    # 有可用结构剧本即直接放行分镜制作，不再输出「未能自动生成」类报错文案误报红字。
    return True, '', False


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
    from orchestrator.project_context_factory import project_context
    from orchestrator.stage_parallel import _adopted
    from contract.stage_path_service import write_dir
    root = Path(root)
    stamp = datetime.now().isoformat(timespec='seconds')
    if stage == 'keyframe':
        from contract.storyboard_paths import media_root
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
    import domain.white_model_service as wm
    from domain.previs_routing import decisions_for
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
                    import infra.app_logging as app_logging
                    app_logging.swallowed('预演项目内副本未写入')
    index = wm.read_project_index(context)
    index.update(stage='previs', generated_at=stamp, required=required)
    target = wm.project_index_path(context, write=True)
    save(target, index)
    return target
