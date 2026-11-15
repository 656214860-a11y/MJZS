# -*- coding: utf-8 -*-
"""剧本准备台账的落盘与自然稿采用撤销：从 writing_api 拆出，口径不变。

R2653：writing_api 行数超过模块棘轮上限（R2630 与快照提交把采用版本确认
基线守卫加进来后 1388 行 > 1372），按 R2400 先例把这组自包含的台账读写
原语迁到独立模块；函数体逐字保留，writing_api 以同名 import 继续转发，
writing_unconfirm 等既有 ``from writing_api import _…`` 调用点不受影响。
"""
import json

from file_cache import read_json


def _save_preparation_state(target, state, publish):
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
