"""L3 交接、写作准备与连贯性网关：交接包、创意稿、自动标记与连贯性清单入口装配。

自 stage_execution_service 拆出；那边按原名重新导出，旧调用点与测试补丁点不变。
"""
from pathlib import Path
from orchestrator.project_context_factory import project_context
from contract.stage_path_service import write_dir
from orchestrator.stage_publication import publish_stage_bundle
from orchestrator.stage_publication import publish_stage_text
from orchestrator.stage_write_preparation_service import prepare_legacy_stage_path
import file_cache
import json
from orchestrator.stage_gate_gateways import video_lifecycle_gateway


def mark_stage_video_deleted(source, sid, versions):
    from domain.video_lifecycle_service import mark_video_deleted
    result = mark_video_deleted(prepare_legacy_stage_path(source), sid, versions, gateway=video_lifecycle_gateway())
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def save_stage_video_options(source, sid, selected, generate_audio, is_local):
    from domain.video_lifecycle_service import save_video_options
    result = save_video_options(prepare_legacy_stage_path(source), sid, selected, generate_audio, is_local,
                              gateway=video_lifecycle_gateway())
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def save_stage_white_model_upload(source, sid, enabled):
    from domain.video_lifecycle_service import save_white_model_upload
    result = save_white_model_upload(prepare_legacy_stage_path(source), sid, enabled, gateway=video_lifecycle_gateway())
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def save_stage_editing_checklist(project, text):
    """剪辑清单保存编排：保留用户清空清单的既有语义。"""
    from domain.edit_service import save_editing_checklist

    def publish_checklist(target, value):
        return publish_stage_text(
            target, value, lambda _value: True, lambda _target: None, allow_empty=True)

    result = save_editing_checklist(project, text, publish=publish_checklist,
                                    context=project_context(project))
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def publish_handoff_bundle(project, name, artifacts, *, auto=False, summary=None):
    """交接包发布编排：L3 负责目录切换、字节发布、可校验清单登记与旧自动包回收。"""
    root = Path(project).resolve()
    edit_dir = write_dir(root, 'edit')
    final = edit_dir / str(name)
    if final.parent != edit_dir:
        raise ValueError('交接包目标越界。')
    if auto and final.exists() and not (final / '交接包标记.json').is_file():
        raise ValueError('已有同名目录且不是自动生成的交接包，请先改名或移走：' + str(final))
    staging = edit_dir / '自动交接包.生成中'
    output = staging if auto else final
    if auto and staging.exists():
        from storage_maintenance import recycle_paths
        recycle_paths(root, [staging], '清理未完成自动交接包')
    payload = {}
    for item in artifacts:
        filename = str(item['name'])
        target = output / filename
        if target.parent != output:
            raise ValueError('交接包文件名越界。')
        data = item.get('data')
        if data is None:
            data = Path(item['source']).read_bytes()
        payload[target] = bytes(data)
    from domain.handoff_service import BUNDLE_MANIFEST_NAME, build_bundle_manifest
    manifest = build_bundle_manifest(summary, [{'name': Path(target).name, 'data': data}
                                               for target, data in payload.items()])
    payload[output / BUNDLE_MANIFEST_NAME] = json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8')
    publish_stage_bundle(payload, lambda _items: True, lambda: None)
    if auto:
        if final.exists():
            from storage_maintenance import recycle_paths
            if not recycle_paths(root, [final], '更新自动交接包'):
                raise ValueError('旧自动交接包未能移入回收站，已保留原包')
        staging.replace(final)
    return final


def publish_writing_preparation(project, name, artifacts):
    """剧本准备工作区发布编排：L3 定位阶段目录并原子发布完整成果包。"""
    root = Path(project).resolve()
    script_dir = write_dir(root, 'script')
    output = script_dir / str(name)
    if output.parent != script_dir:
        raise ValueError('剧本准备工作区目标越界。')
    payload = {}
    for item in artifacts:
        target = output / str(item['name'])
        if not target.is_relative_to(output):
            raise ValueError('剧本准备工作区文件名越界。')
        data = item.get('data')
        if data is None:
            data = Path(item['source']).read_bytes()
        payload[target] = bytes(data)
    publish_stage_bundle(payload, lambda _items: True, lambda: None)
    return output


def publish_idea_creative(project, artifacts):
    """创意文件发布编排：L3 定位剧本阶段并原子发布分类成果。"""
    root = Path(project).resolve()
    script_dir = write_dir(root, 'script')
    payload = {}
    published = {}
    directories = set()
    for item in artifacts:
        name = str(item['name']).replace('\\', '/')
        target = script_dir.joinpath(*name.split('/'))
        try:
            target.resolve().relative_to(script_dir.resolve())
        except (OSError, ValueError) as exc:
            raise ValueError('创意文件目标越界。') from exc
        data = item.get('data')
        if data is None:
            data = Path(item['source']).read_bytes()
        payload[target] = bytes(data)
        published[name] = target
        for directory in item.get('directories', ()):
            folder = script_dir.joinpath(*str(directory).replace('\\', '/').split('/'))
            try:
                folder.resolve().relative_to(script_dir.resolve())
            except (OSError, ValueError) as exc:
                raise ValueError('创意分类目录越界。') from exc
            directories.add(folder)
    publish_stage_bundle(payload, lambda _items: True, lambda: None)
    for folder in directories:
        folder.mkdir(parents=True, exist_ok=True)
    return published


def save_automatic_assemble_marker(project, digest, master, completed_at):
    """自动粗剪完成标记：L3 定位阶段目录并注入原子发布器。"""
    from domain.edit_service import AUTOMATIC_ASSEMBLE_MARKER_NAME, save_automatic_assemble_marker as save_marker
    target = write_dir(Path(project), 'edit') / AUTOMATIC_ASSEMBLE_MARKER_NAME

    def publish_marker(path, payload):
        return publish_stage_text(
            path, json.dumps(payload, ensure_ascii=False, sort_keys=True),
            lambda text: isinstance(json.loads(text), dict), lambda _target: None)

    result = save_marker(target, digest, master, completed_at, publish=publish_marker)
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def save_automatic_handoff_marker(project, digest, folder, shot_count):
    """自动交接完成标记：L3 定位阶段目录并注入原子发布器。"""
    from domain.handoff_service import AUTOMATIC_HANDOFF_MARKER_NAME, save_automatic_handoff_marker as save_marker
    target = write_dir(Path(project), 'edit') / AUTOMATIC_HANDOFF_MARKER_NAME

    def publish_marker(path, payload):
        return publish_stage_text(
            path, json.dumps(payload, ensure_ascii=False, sort_keys=True),
            lambda text: isinstance(json.loads(text), dict), lambda _target: None)

    result = save_marker(target, digest, folder, shot_count, publish=publish_marker)
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def verify_handoff_bundle(folder):
    """离线校验一个已解包的交接包：读清单、按清单核对每个文件，只读不改。"""
    from domain.handoff_service import BUNDLE_MANIFEST_NAME, verify_manifest
    folder = Path(folder).resolve()
    manifest_path = folder / BUNDLE_MANIFEST_NAME
    if not manifest_path.is_file():
        return {'ok': False, 'problems': ['缺少交接包清单，无法离线校验：' + BUNDLE_MANIFEST_NAME],
                'missing': [], 'count': 0, 'label': ''}
    try:
        manifest = file_cache.read_json(manifest_path)
    except (OSError, ValueError):
        manifest = None
    if manifest is None:
        return {'ok': False, 'problems': ['交接包清单读不出来或格式坏了'], 'missing': [], 'count': 0, 'label': ''}

    def probe(name):
        path = (folder / str(name)).resolve()
        if not path.is_relative_to(folder):
            raise OSError('交接包条目越界：' + str(name))
        if not path.is_file():
            raise OSError('交接包文件缺失：' + str(name))
        return path.stat().st_size, file_cache.file_digest(path)
    return verify_manifest(manifest, probe)


def storyboard_adoption_impact(project, paths):
    """L3 注入项目上下文：候选分镜相对已采用分镜的只读影响预览。"""
    from domain.storyboard_catalog_service import adoption_impact
    return adoption_impact(project_context(project), paths)


def asset_impact(project, aid, *, episode_dir=''):
    """L3 门面：资产变更影响视图（只读）。"""
    from domain.asset_plan import asset_impact as _impact
    return _impact(project, aid, episode_dir=episode_dir)


def continuity_issue_report(project, ledger=None):
    """L3 门面：连贯性问题闭环视图（只读，不落盘）。"""
    from continuity_ledger import issues, merge_issues, read_issues
    from continuity_ledger import read as read_ledger
    data = ledger if isinstance(ledger, dict) and ledger else read_ledger(project)
    _register, rows = merge_issues(read_issues(project), issues(data))
    return rows


def sync_continuity_issues(project, ledger=None):
    """L3 门面：算一遍问题并落盘 03_continuity/output/continuity_issues.json。"""
    from agent.core import save
    from continuity_ledger import read as read_ledger
    from continuity_ledger import sync_issues
    data = ledger if isinstance(ledger, dict) and ledger else read_ledger(project)
    return sync_issues(project, data, publish=save)


def decide_continuity_issue(project, issue_id, decision, reason='', by='人工'):
    """L3 门面：记一条问题的处理决定（忽略必须写理由）。"""
    from agent.core import save
    from continuity_ledger import decide_issue
    return decide_issue(project, issue_id, decision, reason, by=by, publish=save)


def publish_response_archive(project, text):
    """把模型已返回的可见正文归档到 01剧本准备/responses/，返回归档路径。

    只归档，不登记为阶段成果，也不改变采用状态；取消、迟到返回或格式不合格的
    正文同样留副本，供用户对照「原始响应已保存」。空正文不建文件。
    """
    from datetime import datetime
    from uuid import uuid4
    from contract.stage_path_service import write_dir
    value = str(text or '').replace('\r\n', '\n')
    if not value.strip():
        return ''
    target = write_dir(project, 'script') / 'responses' / (
        datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '_' + uuid4().hex + '.txt')
    publish_stage_text(target, value, lambda published: published == value, lambda _target: None)
    return str(target)


def import_downloaded_creatives(context, provider='', model='', backups=None):
    """L3 编排：从本机「下载」文件夹收回桌面 Agent 窗口给出的同项目创作文件并发布。"""
    from domain.idea_chat import import_downloaded_documents
    from contract.platform_tools import downloads_directory
    return import_downloaded_documents(context, downloads_directory(), provider=provider, model=model,
                                       publish=publish_idea_creative, backups=backups)
