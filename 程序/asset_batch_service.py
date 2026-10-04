"""Asset-batch domain operations shared by local and Skill-backed production."""
import re
import threading
import uuid
from pathlib import Path

from file_cache import read_json
from project_context import ProjectContext

KINDS = {'CHAR': ('characters', '角色'), 'LOC': ('scenes', '场景'),
         'PROP': ('props', '道具')}


def _project_root(project=None, *, context=None):
    """项目级计划消费 L3 注入上下文；保留旧路径调用的兼容边界。"""
    if context is None:
        return Path(project).resolve()
    if not isinstance(context, ProjectContext):
        raise TypeError('资产批次计划需要由 L3 注入 ProjectContext。')
    root = context.root.resolve()
    if project is not None and Path(project).resolve() != root:
        raise ValueError('项目路径与注入的 ProjectContext 不一致。')
    return root


def _require_gateway(gateway):
    """正式资产索引只允许经 L3 注入的缓存读取与原子发布。"""
    required = ('read_json', 'publish_json', 'publish_bytes', 'file_hash', 'copy_file', 'replace_file')
    if not isinstance(gateway, dict) or any(not callable(gateway.get(name)) for name in required):
        raise TypeError('资产批处理读写需要由 L3 注入发布与读取网关。')
    return gateway


def asset_prompt(asset, kind):
    from asset_prompt_rules import positive
    from asset_reference_prompts import display_prompt
    if not positive(asset):
        raise ValueError('资产提示词不全，请回第1步（固定角色）或第2步（场景、道具）补齐。')
    from asset_reference_images import reference_instruction
    reference = reference_instruction(asset)
    return display_prompt(asset) + ('\n\n' + reference if reference else '')


def register_image(base, aid, asset, image, *, gateway=None):
    gateway = _require_gateway(gateway)
    base = Path(base).resolve()
    prefix = aid.split('_')[0]
    if not re.fullmatch(r'(CHAR|LOC|PROP)_\d{3,}', aid):
        raise ValueError('资产编号无效')
    raw = Path(image).read_bytes()
    if len(raw) < 33 or raw[12:16] != b'IHDR' or raw[-8:-4] != b'IEND':
        raise ValueError('PNG图片未保存完整')
    if not raw.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('生成结果不是PNG图片')
    registry_file = base / 'assets.json'
    registry = gateway['read_json'](registry_file) if registry_file.exists() else {}
    if not isinstance(registry, dict):
        registry = {}
    existing = registry.get(aid, {})
    if existing.get('image'):
        old = (base / existing['image']).resolve()
        if old.is_relative_to(base) and old.is_file():
            return '已有图片，跳过登记'
    planfile = base / 'assets/资产清单/assets.json'
    plan = gateway['read_json'](planfile)
    if not isinstance(plan, dict):
        raise ValueError('资产清单 assets.json 顶层必须为对象')
    current = plan.get(aid)
    from asset_reference_images import signature
    if (not current or any(current.get(k) != asset.get(k) for k in
                           ('name', 'description', 'image_prompt', 'negative_prompt', 'positive_prompt', 'prompt'))
            or current.get('reference_images', []) != asset.get('reference_images', [])
            or ('_reference_signature' in asset and signature(base, current) != asset['_reference_signature'])):
        raise ValueError('生成期间资产定义已变化，图片已保留，未自动关联')
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(asset.get('name', aid))).strip(' .')[:65]
    folder = base / 'assets' / KINDS[prefix][0]
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / (aid + '_' + name + '_' + uuid.uuid4().hex[:8] + '.png')
    # 成果先经原子替换落盘，随后才更新资产索引；UI 刷新或进程中断不会读到半张 PNG。
    gateway['publish_bytes'](dest, raw)
    registry[aid] = {**{k: v for k, v in asset.items() if k not in ('status', 'image') and not k.startswith('_')},
                     **existing, 'name': asset.get('name', aid),
                     'image': dest.relative_to(base).as_posix()}
    gateway['publish_json'](registry_file, registry)
    return '已生成并导入'


def import_asset_image(base, project_root, aid, source, requirements, *, gateway=None):
    """Import a user-selected asset image and publish its registry pointer safely."""
    gateway = _require_gateway(gateway)
    base = Path(base).resolve()
    project_root = Path(project_root).resolve()
    aid = str(aid or '').strip()
    match = re.fullmatch(r'(CHAR|LOC|PROP)_\d{3,}', aid)
    if not match:
        raise ValueError('资产ID格式错误')
    source = Path(source).resolve()
    if not source.is_file():
        raise ValueError('请选择存在的图片文件')
    suffix = source.suffix.lower()
    if suffix not in ('.png', '.jpg', '.jpeg', '.webp'):
        raise ValueError('请选择 PNG、JPG、JPEG 或 WEBP 图片')
    kind = KINDS[match.group(1)][0]
    registry_file = base / 'assets.json'
    registry = gateway['read_json'](registry_file)
    if not isinstance(registry, dict):
        raise ValueError('资产登记表格式错误')
    requirements = requirements if isinstance(requirements, dict) else {}
    requirement = requirements.get(aid, {})
    existing = registry.get(aid, {})
    name = requirement.get('name') or existing.get('name') or aid
    folder = (base / 'assets' / kind).resolve()
    if not folder.is_relative_to(base):
        raise ValueError('资产导入目录越界')
    renamed = source.with_name(aid + suffix)
    dest = (folder / (aid + suffix)).resolve()
    if renamed != source and renamed.exists() and renamed != dest:
        raise ValueError('原图目录已有同名文件：' + str(renamed) + '。请先移走该文件后再导入。')
    original_hash = gateway['file_hash'](source)
    old_dest = dest.read_bytes() if dest.is_file() else None
    old_registry = registry_file.read_bytes()
    temporary = dest.with_name(dest.stem + '_' + uuid.uuid4().hex + '.importing')
    try:
        if source != dest:
            folder.mkdir(parents=True, exist_ok=True)
            gateway['copy_file'](source, temporary)
            if gateway['file_hash'](temporary) != original_hash:
                raise ValueError('图片复制校验失败，原图已保留')
            if dest.exists():
                backup = folder / '历史版本'
                backup.mkdir(exist_ok=True)
                gateway['copy_file'](dest, backup / (dest.stem + '_' + uuid.uuid4().hex[:8] + dest.suffix))
            gateway['replace_file'](temporary, dest)
        updated = dict(registry)
        updated[aid] = {'name': name, 'image': dest.relative_to(base).as_posix(),
                        'description': requirement.get('description', name)}
        gateway['publish_json'](registry_file, updated)
    except Exception:
        if old_dest is None:
            if dest.is_file():
                from storage_maintenance import recycle_paths
                if not recycle_paths(project_root, (dest,), '资产导入索引失败回收'):
                    raise OSError('资产索引发布失败，且新导入图片未能安全回收')
        else:
            gateway['publish_bytes'](dest, old_dest)
        if registry_file.read_bytes() != old_registry:
            gateway['publish_bytes'](registry_file, old_registry)
        raise
    finally:
        if temporary.exists():
            from file_cache import remove_temporary_file
            remove_temporary_file(temporary)
    result = '已登记 ' + aid + ' · 图片已按资产编号命名'
    if source != renamed:
        try:
            if gateway['file_hash'](source) != original_hash:
                raise ValueError('原图在导入时被修改')
            if renamed == dest:
                from storage_maintenance import recycle_paths
                if recycle_paths(project_root, [source], '导入资产后的原始副本'):
                    result += '；原始副本已移入回收站'
                else:
                    result += '；原始副本已保留'
            else:
                source.rename(renamed)
        except (OSError, ValueError) as exc:
            result = '资产已导入，但原图未能改名：' + str(exc)
    return kind, result


def rename_asset(base, aid, old_name, new_name, *, gateway=None):
    """Rename an asset in its plan and registered-image index as one recoverable change."""
    gateway = _require_gateway(gateway)
    base = Path(base).resolve()
    aid = str(aid or '').strip()
    name = str(new_name or '').strip()
    if not aid:
        raise ValueError('资产编号不能为空')
    if not name:
        raise ValueError('资产名称不能为空')
    plan_file = base / 'assets/资产清单/assets.json'
    registry_file = base / 'assets.json'
    plan = gateway['read_json'](plan_file)
    if not isinstance(plan, dict):
        raise ValueError('资产清单 assets.json 顶层必须为对象')
    registry = gateway['read_json'](registry_file) if registry_file.is_file() else {}
    if not isinstance(registry, dict):
        registry = {}
    plan_entry = dict(plan.get(aid, {}))
    aliases = list(plan_entry.get('aliases', []))
    if old_name not in aliases:
        aliases.append(old_name)
    plan_entry.update(name=name, aliases=aliases)
    updated_plan = dict(plan)
    updated_plan[aid] = plan_entry
    updated_registry = dict(registry)
    if aid in updated_registry:
        updated_registry[aid] = {**updated_registry[aid], 'name': name}
    previous = ((plan_file, plan_file.read_bytes()),
                (registry_file, registry_file.read_bytes() if registry_file.is_file() else None))
    try:
        gateway['publish_json'](plan_file, updated_plan)
        if aid in updated_registry:
            gateway['publish_json'](registry_file, updated_registry)
    except Exception:
        for path, raw in previous:
            if raw is not None:
                gateway['publish_bytes'](path, raw)
        raise
    return plan_entry


def remove_asset_image(base, aid, *, gateway=None):
    """Recycle one registered asset image, then clear its index with recovery on failure."""
    gateway = _require_gateway(gateway)
    base = Path(base).resolve()
    assets_file = base / 'assets.json'
    assets = gateway['read_json'](assets_file)
    if not isinstance(assets, dict):
        raise ValueError('资产登记表格式错误')
    entry = assets.get(aid, {})
    image = entry.get('image')
    if not image:
        raise ValueError('该资产尚未导入图片')
    path = (base / image).resolve()
    if not path.is_relative_to(base):
        raise ValueError('资产路径越界')
    if not path.is_file():
        raise ValueError('图片文件已不存在，请刷新列表')
    from storage_maintenance import recycle_paths, restore_latest_recycled_path
    if not recycle_paths(base, (path,), '删除资产图片'):
        raise OSError('图片未能安全移入项目回收站')
    updated = dict(assets)
    updated[aid] = {key: value for key, value in entry.items() if key != 'image'}
    try:
        gateway['publish_json'](assets_file, updated)
    except Exception as exc:
        try:
            restore_latest_recycled_path(base, path)
        except Exception as restore_exc:
            raise OSError('资产索引写入失败，且图片恢复失败：' + str(restore_exc)) from exc
        raise
    return path


def restore_asset_image(base, aid, *, gateway=None):
    """Restore one asset image and register it, recycling it again if indexing fails."""
    gateway = _require_gateway(gateway)
    base = Path(base).resolve()
    assets_file = base / 'assets.json'
    assets = gateway['read_json'](assets_file)
    if not isinstance(assets, dict):
        raise ValueError('资产登记表格式错误')
    entry = assets.get(aid, {})
    if entry.get('image'):
        raise ValueError(aid + ' 已有导入图片，无需恢复')
    prefix = str(aid).split('_', 1)[0]
    kind = KINDS.get(prefix)
    if kind is None:
        raise ValueError('资产ID格式错误，无法确定恢复目录')
    folder = (base / 'assets' / kind[0]).resolve()
    if not folder.is_relative_to(base):
        raise ValueError('资产恢复目录越界')
    from storage_maintenance import recycle_paths, restore_latest_recycled_child
    restored = []
    try:
        restored = restore_latest_recycled_child(
            base, folder, aid, ('.png', '.jpg', '.jpeg', '.webp'))
        if len(restored) != 1:
            raise OSError('恢复结果异常')
        dest = restored[0]
        updated = dict(assets)
        updated[aid] = {**entry, 'image': dest.relative_to(base).as_posix()}
        gateway['publish_json'](assets_file, updated)
    except Exception as exc:
        if restored:
            try:
                recycle_paths(base, restored, '资产图片恢复后索引失败回收')
            except Exception as rollback_exc:
                raise OSError('资产索引写入失败，且恢复图片回收失败：' + str(rollback_exc)) from exc
        raise
    return dest


def image_ready(base, aid, registry=None):
    base = Path(base).resolve()
    if registry is None:
        file = base / 'assets.json'
        registry = read_json(file) if file.is_file() else {}
    asset = registry.get(aid, {}) if isinstance(registry, dict) else {}
    path = (base / asset.get('image', '')).resolve()
    return bool(asset.get('image') and path.is_relative_to(base) and path.is_file())


def batch_complete(base, aids):
    """Whether all requested assets are registered and present on disk."""
    base = Path(base).resolve()
    file = base / 'assets.json'
    registry = read_json(file) if file.is_file() else {}
    return all(image_ready(base, aid, registry=registry) for aid in aids)


def automatic_plan(project, base, sources, settings, scope='adopted', *, gateway=None, context=None):
    """Return independently generatable assets without constructing any Tk UI."""
    from asset_plan import _sync_plan
    from asset_prompt_rules import issues
    from prop_assets import requires_asset

    project = _project_root(project, context=context)
    base = Path(base)
    rows = _sync_plan(project, base, sources, scope=scope, gateway=gateway, context=context)
    ready = []
    skipped = []
    for aid, asset in rows.items():
        kind = aid.split('_')[0]
        if kind not in KINDS:
            continue
        if not settings.get(kind, kind != 'PROP'):
            continue
        if not requires_asset(aid, asset):
            continue
        if asset.get('status') == '已导入' or image_ready(base, aid):
            continue
        problems = issues(aid, asset)
        if problems:
            skipped.append((aid, '、'.join(problems)))
            continue
        ready.append((aid, asset))
    return ready, skipped


def auto_settings(project=None, *, context=None):
    """Return persisted unattended asset-batch settings without constructing UI."""
    from project_settings import read_prefs
    prefs = read_prefs(_project_root(project, context=context) / 'ui_settings.json')
    saved = prefs.get('asset_batch', {})
    return dict(saved) if isinstance(saved, dict) else {}


def current_model(project=None, *, context=None):
    """Resolve the asset model from the same stage configuration as execution."""
    from cloud_assets import LOCAL, MODELS
    from stage_model_value import value as configured_value
    try:
        value = configured_value(_project_root(project, context=context), 'assets')
    except (OSError, ValueError, TypeError, KeyError):
        value = ''
    choices = [LOCAL, *MODELS]
    if value in choices:
        return value
    if value not in choices:
        legacy = str(auto_settings(project, context=context).get('backend') or '').strip()
        if legacy in choices:
            return legacy
    return LOCAL


def unattended_plan(project, base, sources, scope='adopted', *, gateway=None, context=None):
    """Build an unattended plan together with its persisted batch settings."""
    project = _project_root(project, context=context)
    saved = auto_settings(project, context=context)
    if not saved:
        raise ValueError('请先打开一次「批量资产」窗口并保存生图设置，再开启无人值守自动补资产')
    ready, skipped = automatic_plan(project, base, sources, saved, scope,
                                    gateway=gateway, context=context)
    return ready, skipped, saved


def unattended_signature(missing, saved):
    """返回自动资产批次的稳定去重键，设置变化会触发新一轮计划。"""
    return (tuple(asset_id for asset_id, _item in missing),
            tuple(sorted((key, str(value)) for key, value in saved.items())))


def unattended_retry_decision(signature, previous_signature, attempts, retry_limit):
    """计算自动资产批次的去重、重试上限及派发决定，不读写台账。"""
    if signature == previous_signature:
        return {'action': 'skip'}
    if attempts >= retry_limit:
        return {'action': 'stop', 'signature': signature}
    return {'action': 'dispatch', 'signature': signature}
