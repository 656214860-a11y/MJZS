# -*- coding: utf-8 -*-
"""取消剧本准备阶段确认：把准备流程回退到该阶段，只改确认台账、不删文件。

与 ``writing_api.confirm_preparation_document`` 对称的台账操作：写台账复用
``writing_api._save_preparation_state``，读复用 ``file_cache.read_json``，不另立第二入口。
"""
from file_cache import read_json
from writing_api import PREPARATION_STAGES, _save_preparation_state


def preparation_confirmed_stages(project):
    """只读：当前已确认的①②③阶段名元组（采用状态），供菜单判断「取消已确认」是否可用。"""
    from stage_path_service import write_dir
    target = write_dir(project, 'script') / 'preparation_state.json'
    state = read_json(target) if target.is_file() else None
    if not isinstance(state, dict):
        return ()
    documents = state.get('documents')
    if not isinstance(documents, list):
        return ()
    return tuple(document['stage'] for document in documents
                 if isinstance(document, dict) and document.get('confirmed') is True
                 and document.get('stage') in PREPARATION_STAGES)


def unconfirm_preparation_document(project, stage, *, publish):
    """取消某阶段的确认并把准备流程回退到该阶段；只改确认台账，不删改任何文件。

    与 ``writing_api.confirm_preparation_document`` 对称：被取消阶段之后已确认的阶段
    一并取消确认，阶段指针回到该阶段，使其成为当前待确认阶段；原稿与重写草稿的文件
    本体都保留。返回一并取消的下游阶段元组；该阶段未确认或不存在时是空操作，返回空
    元组、不报错。"""
    if not callable(publish):
        raise TypeError('剧本准备阶段需要 L3 注入发布器')
    if stage not in PREPARATION_STAGES:
        raise ValueError('请选择项目设定、剧本大纲或角色卡')
    from stage_path_service import write_dir
    target = write_dir(project, 'script') / 'preparation_state.json'
    state = read_json(target) if target.is_file() else None
    if state is None:
        return ()
    if not isinstance(state, dict):
        raise ValueError('剧本准备阶段记录无效，不能取消确认')
    documents = state.get('documents')
    if not isinstance(documents, list):
        raise ValueError('剧本准备阶段记录无效，不能取消确认')
    index = PREPARATION_STAGES.index(stage)
    if index >= len(documents):
        return ()
    document = documents[index]
    if not isinstance(document, dict) or document.get('confirmed') is not True:
        return ()
    invalidated = tuple(PREPARATION_STAGES[position]
                        for position, doc in enumerate(documents[index + 1:], start=index + 1)
                        if isinstance(doc, dict) and doc.get('confirmed') is True)
    state['documents'] = documents[:index] + [dict(document, confirmed=False)]
    state.pop('revision', None)
    state.pop('pending_restart', None)
    _save_preparation_state(target, state, publish)
    return invalidated
