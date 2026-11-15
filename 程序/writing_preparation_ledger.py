# -*- coding: utf-8 -*-
"""剧本准备台账的落盘、自然稿采用撤销与草稿位次路由：从 writing_api 拆出，口径不变。

R2653：writing_api 行数超过模块棘轮上限（R2630 与快照提交把采用版本确认
基线守卫加进来后 1388 行 > 1372），按 R2400 先例把这组自包含的台账读写
原语迁到独立模块；函数体逐字保留，writing_api 以同名 import 继续转发，
writing_unconfirm 等既有 ``from writing_api import _…`` 调用点不受影响。
"""
import json
from datetime import datetime

from file_cache import read_json

PREPARATION_STAGES = ('项目设定', '剧本大纲', '角色卡')


_PREPARATION_STAGE_WORDS = (
    ('项目设定', ('项目设定', '设定')),
    ('剧本大纲', ('剧本大纲', '大纲', '纲要')),
    ('角色卡', ('角色卡', '人物设定（角色卡）', '人物设定', '人物卡')),
)


def _preparation_stage_alias(text):
    """原话点名的最长阶段别名对应的阶段；未点名阶段返回 None。"""
    found = None
    for stage, words in _PREPARATION_STAGE_WORDS:
        for word in words:
            if word in text and (found is None or len(word) > found[0]):
                found = (len(word), stage)
    return None if found is None else found[1]


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


def _working_documents(state):
    """重新创作的草稿与当前采用版本分开，确认前不替换采用版本。"""
    return state.get('revision', state)['documents']


def _confirmed_prefix(documents, index):
    """该阶段之前的记录必须齐全且都已确认；满足时返回这段前缀，否则 None。"""
    prefix = documents[:index]
    if len(prefix) != index or any(not isinstance(doc, dict) or doc.get('confirmed') is not True
                                   for doc in prefix):
        return None
    return prefix


# REQ-S01-89：首行以确认/推进词开头的消息，点名阶段视为交给模型的推进请求。
_PREPARATION_ADVANCE_LEAD = tuple(word.casefold() for word in (
    '确认', '确定', '好的', '好', '可以', '行', '嗯', '通过', '同意',
    'ok', 'okay', 'yes', '继续'))


def _preparation_work_index(documents, message):
    """REQ-S01-89：本轮处理的阶段位次。

    原话点名未确认草稿→修订该位；点名紧邻未起草阶段→追加并行草稿位；点名更远的
    未起草阶段→报错；点名已确认阶段或未点名→首个未确认位，全已确认则追加位。"""
    default = next((position for position, doc in enumerate(documents)
                    if not isinstance(doc, dict) or doc.get('confirmed') is not True),
                   len(documents))
    first = str(message or '').strip().split('\n', 1)[0].strip()
    if first.casefold().startswith(_PREPARATION_ADVANCE_LEAD):
        # 「确认，输出角色卡」一类：确认词领衔时点名是交给模型的推进请求，
        # 不做草稿路由（REQ-S01-89；确认与推进由模型语义判定）。
        return default
    stage = _preparation_stage_alias(first)
    if stage is None:
        return default
    position = PREPARATION_STAGES.index(stage)
    if position > len(documents):
        raise ValueError('「' + stage + '」之前还有阶段未起草；请先起草「'
                         + PREPARATION_STAGES[len(documents)] + '」')
    if position == len(documents):
        return position
    document = documents[position]
    if isinstance(document, dict) and document.get('confirmed') is not True:
        return position
    return default


def _preparation_draft_is_parallel(project, requested):
    """REQ-S01-89：重写口令指向未确认并行草稿时按重起草处理，不走采用稿重写。"""
    from stage_path_service import write_dir
    target = write_dir(project, 'script') / 'preparation_state.json'
    early = read_json(target) if target.is_file() else None
    documents = _working_documents(early) if isinstance(early, dict) else []
    position = PREPARATION_STAGES.index(requested)
    return (position < len(documents) and isinstance(documents[position], dict)
            and documents[position].get('confirmed') is not True
            and _confirmed_prefix(documents, position) is None)


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
