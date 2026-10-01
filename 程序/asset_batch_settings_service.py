"""Asset-batch preference updates shared by the interactive UI paths."""
from pathlib import Path

from agent.core import save
from project_settings import read_prefs


def _saved_settings(prefs):
    saved = prefs.get('asset_batch', {})
    return dict(saved) if isinstance(saved, dict) else {}


def save_settings(project, options, categories=None, restored_model_id=None):
    """Merge validated batch settings without overwriting unrelated project prefs."""
    if not isinstance(options, dict):
        raise ValueError('资产批量设置必须为对象')
    if categories is not None and not isinstance(categories, dict):
        raise ValueError('资产类别设置必须为对象')
    path = Path(project) / 'ui_settings.json'
    prefs = read_prefs(path)
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
    save(path, prefs)
    return updated


def remove_model(project, url, model, model_id):
    """Hide one detected model while keeping its local ComfyUI file untouched."""
    path = Path(project) / 'ui_settings.json'
    prefs = read_prefs(path)
    updated = _saved_settings(prefs)
    deleted = updated.get('deleted_models', [])
    if not isinstance(deleted, list):
        deleted = []
    updated['deleted_models'] = list(dict.fromkeys([*deleted, model_id]))
    if (str(updated.get('url', '')).rstrip('/') == str(url).strip().rstrip('/')) and updated.get('model') == model:
        updated['model'] = ''
    prefs['asset_batch'] = updated
    save(path, prefs)
    return updated
