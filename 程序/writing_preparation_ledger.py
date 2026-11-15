# -*- coding: utf-8 -*-
"""剧本准备台账的落盘与自然稿采用撤销：从 writing_api 拆出，口径不变。

R2653：writing_api 行数超过模块棘轮上限（R2630 与快照提交把采用版本确认
基线守卫加进来后 1388 行 > 1372），按 R2400 先例把这组自包含的台账读写
原语迁到独立模块；函数体逐字保留，writing_api 以同名 import 继续转发，
writing_unconfirm 等既有 ``from writing_api import _…`` 调用点不受影响。
"""
import json
from datetime import datetime

from file_cache import read_json


def _snapshot_basis(state):
    """采用稿（顶层 documents）中已确认内容的 {(阶段, sha256)} 集合——快照触发判据。

    重写稿（revision）不计：重写启动时前缀会重绑到用户编辑后正文的新 sha，
    那不是新的定稿事件；重写稿确认后由提升一步进采用稿，那时再打快照。"""
    if not isinstance(state, dict):
        return frozenset()
    return frozenset((document.get('stage'), document.get('sha256'))
                     for document in state.get('documents') or ()
                     if isinstance(document, dict) and document.get('confirmed') is True)


def _record_confirmation_snapshots(target, state, publish):
    """REQ-S01-87：本次写入新增的已确认文档，把正文快照到「确认快照/」并入台账。

    挂在统一写口上：右键设为定稿、聊天推进、重写提升、取消后重确认共用。
    同 (stage, sha256) 不重复快照；快照历史随台账在简报变化时保留。"""
    old = read_json(target) if target.is_file() else None
    fresh = _snapshot_basis(state) - _snapshot_basis(old)
    if not fresh:
        return
    folder = target.parent
    snapshots = list(state.get('snapshots') or [])
    known = {(item.get('stage'), item.get('sha256'))
             for item in snapshots if isinstance(item, dict)}
    seen = set()
    for document in state.get('documents') or ():
        if not isinstance(document, dict):
            continue
        key = (document.get('stage'), document.get('sha256'))
        if key not in fresh or key in known or key in seen:
            continue
        path = document.get('path')
        if not isinstance(path, str) or not path:
            continue
        source = folder / path
        try:
            text = source.read_text(encoding='utf-8') if source.is_file() else ''
        except OSError:
            continue
        if not text.strip():
            continue
        seen.add(key)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        snapshot = folder / '确认快照' / ('%s_%s_%s.md' % (
            document['stage'], stamp, document['sha256'][:8]))
        try:
            relative = snapshot.relative_to(folder).as_posix()
        except ValueError:
            continue
        publish(snapshot, text if text.endswith('\n') else text + '\n',
                lambda value: bool(str(value).strip()), lambda _target: None)
        snapshots.append({'stage': document['stage'], 'path': path,
                          'sha256': document['sha256'], 'snapshot': relative,
                          'confirmed_at': datetime.now().isoformat(timespec='seconds')})
    if snapshots:
        state['snapshots'] = snapshots


def _save_preparation_state(target, state, publish):
    _record_confirmation_snapshots(target, state, publish)
    payload = json.dumps(state, ensure_ascii=False, indent=2) + '\n'
    publish(target, payload, lambda value: value == payload, lambda _target: None)


def _revoke_natural_script_adoption(project, target, state, publish):
    """采用版本变化后撤销自然稿采用：先落采用记录失效，再回写阶段台账。"""
    from script_contract import natural_script_selection_path
    payload = json.dumps({'path': '', 'sha256': '',
                          'reason': '前置阶段已更新，请重新生成或明确采用自然剧本'}, ensure_ascii=False)
    publish(natural_script_selection_path(project), payload,
            lambda value: value == payload,
            lambda _target: _save_preparation_state(target, state, publish))


def _confirmed_basis(state):
    """采用版本里已确认内容的 {(阶段, sha256)} 集合——自然稿采用的依据基线。"""
    documents = state.get('documents') if isinstance(state, dict) else None
    if not isinstance(documents, list):
        return frozenset()
    return frozenset((document.get('stage'), document.get('sha256'))
                     for document in documents
                     if isinstance(document, dict) and document.get('confirmed') is True)


def _save_preparation_state_guarded(project, target, state, publish):
    """写阶段台账；采用版本确认基线变化且存在有效自然稿采用时先撤销采用。

    覆盖非重写确认路径的基线变化：「取消已确认」、简报变化后重确认、菜单/聊天
    直接改写采用版本。与 ``_promote_revision`` 的重写切换同口径；基线未变或
    没有有效采用时直接保存，不给从未采用过的项目写多余的失效记录。"""
    from script_contract import natural_script_selection_path
    old = read_json(target) if target.is_file() else None
    if _confirmed_basis(old) != _confirmed_basis(state):
        selection = natural_script_selection_path(project)
        adopted = read_json(selection) if selection.is_file() else None
        if isinstance(adopted, dict) and adopted.get('path'):
            _revoke_natural_script_adoption(project, target, state, publish)
            return
    _save_preparation_state(target, state, publish)


def _promote_revision(state, project, target, publish):
    """revision 存在时把它切换为采用版本并撤销自然稿采用（与推进确认同口径）。

    聊天 advancing、右键「设为定稿」确认完整重写稿、三阶段齐全的遗留 revision
    都由调用方判定时机；revision.documents 可以带未确认尾稿。返回是否发生切换。"""
    revision = state.get('revision')
    documents = revision.get('documents') if isinstance(revision, dict) else None
    if not (isinstance(documents, list) and documents):
        return False
    state.pop('revision')
    state['documents'] = documents
    state['brief_hash'] = revision.get('brief_hash', state.get('brief_hash'))
    _revoke_natural_script_adoption(project, target, state, publish)
    return True
