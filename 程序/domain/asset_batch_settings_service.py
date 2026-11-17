"""Asset-batch preference updates shared by the interactive UI paths."""
import logging
from pathlib import Path

from infra.project_settings import read_prefs
from contract.service_contract import SystemError, UserError, success

LOGGER = logging.getLogger('asset_batch_settings_service')


def _read_settings(path, publish):
    if not callable(publish):
        raise TypeError('资产批量设置发布必须由 L3 注入。')
    try:
        return success(read_prefs(path))
    except (OSError, ValueError):
        LOGGER.exception('资产批量设置读取失败')
        return SystemError('项目设置无法读取，请保留原文件并检查 ui_settings.json 后重试。')


def _publish_settings(path, prefs, updated, publish):
    try:
        publish(path, prefs)
    except OSError:
        LOGGER.exception('资产批量设置保存失败')
        return SystemError('资产批量设置保存失败，请检查文件权限和磁盘空间后重试。')
    return success(updated)


def _saved_settings(prefs):
    saved = prefs.get('asset_batch', {})
    return dict(saved) if isinstance(saved, dict) else {}


def save_settings(project, options, categories=None, restored_model_id=None, *, publish):
    """Merge validated batch settings without overwriting unrelated project prefs."""
    if not isinstance(options, dict):
        return UserError('资产批量设置必须为对象')
    if categories is not None and not isinstance(categories, dict):
        return UserError('资产类别设置必须为对象')
    path = Path(project) / 'ui_settings.json'
    result = _read_settings(path, publish)
    if not result.ok:
        return result
    prefs = result.data
    saved = _saved_settings(prefs)
    updated = {**saved, **options}
    if categories is not None:
        updated.update(categories)
    deleted = saved.get('deleted_models', [])
    if not isinstance(deleted, list):
        deleted = []
    if restored_model_id:
        deleted = [item for item in deleted if item != restored_model_id]
    updated['deleted_models'] = deleted
    prefs['asset_batch'] = updated
    return _publish_settings(path, prefs, updated, publish)


def remove_model(project, url, model, model_id, *, publish):
    """Hide one detected model while keeping its local ComfyUI file untouched."""
    path = Path(project) / 'ui_settings.json'
    result = _read_settings(path, publish)
    if not result.ok:
        return result
    prefs = result.data
    updated = _saved_settings(prefs)
    deleted = updated.get('deleted_models', [])
    if not isinstance(deleted, list):
        deleted = []
    updated['deleted_models'] = list(dict.fromkeys([*deleted, model_id]))
    if (str(updated.get('url', '')).rstrip('/') == str(url).strip().rstrip('/')) and updated.get('model') == model:
        updated['model'] = ''
    prefs['asset_batch'] = updated
    return _publish_settings(path, prefs, updated, publish)
