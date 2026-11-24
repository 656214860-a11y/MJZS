# -*- coding: utf-8 -*-
"""剧本准备台账的落盘与草稿位次路由：从 writing_api 拆出。

台账怎么变都不动自然剧本的采用记录（REQ-S01-14）：设定、大纲、角色卡和自然剧本
四份文档各管各的，生成或更新其中一份不撤销另一份的采用。

R2653：writing_api 行数超过模块棘轮上限（R2630 与快照提交把采用版本确认
基线守卫加进来后 1388 行 > 1372），按 R2400 先例把这组自包含的台账读写
原语迁到独立模块；函数体逐字保留，writing_api 以同名 import 继续转发，
writing_unconfirm 等既有 ``from writing_api import _…`` 调用点不受影响。
"""
import json
import re
from datetime import datetime

from infra.file_cache import read_json

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


def _document_stage_index(document):
    """台账记录对应的阶段位次；阶段名不在 PREPARATION_STAGES 时返回 None。"""
    stage = document.get('stage') if isinstance(document, dict) else None
    return PREPARATION_STAGES.index(stage) if stage in PREPARATION_STAGES else None


def _document_for_stage(documents, stage):
    """按阶段名查台账记录（LOST-04：documents 不再要求与阶段位次对齐）。"""
    index = PREPARATION_STAGES.index(stage)
    for position, document in enumerate(documents):
        if _document_stage_index(document) == index:
            return position, document
    return None, None


def _confirmed_prefix(documents, index):
    """该阶段之前的各阶段记录必须齐全且都已确认；满足时返回这段前缀，否则 None。

    LOST-04：documents 按阶段名查而不再按下标对位——任意顺序生成的稀疏
    台账（如只有角色卡）同样适用；前缀按 PREPARATION_STAGES 顺序返回。"""
    prefix = []
    for position in range(index):
        stage = PREPARATION_STAGES[position]
        found = next((doc for doc in documents
                      if isinstance(doc, dict) and doc.get('stage') == stage), None)
        if found is None or found.get('confirmed') is not True:
            return None
        prefix.append(found)
    return prefix


# REQ-S01-89：首行以确认/推进词开头的消息，点名阶段视为交给模型的推进请求。
_PREPARATION_ADVANCE_LEAD = tuple(word.casefold() for word in (
    '确认', '确定', '好的', '好', '可以', '行', '嗯', '通过', '同意',
    'ok', 'okay', 'yes', '继续'))


def _preparation_work_index(documents, message):
    """本轮处理的阶段位次（LOST-04：四份文档任意顺序、任意组合生成）。

    默认优先处理阶段序里最早的未确认草稿（REQ-S01-89：继续手头稿件），
    没有草稿时取 PREPARATION_STAGES 顺序里第一个尚无已确认记录的阶段；
    三阶段全部确认才返回 len(PREPARATION_STAGES) 进入自然剧本。
    点名别的阶段仍按点名走。"""
    drafts = sorted((doc for doc in documents
                     if isinstance(doc, dict) and doc.get('confirmed') is not True
                     and _document_stage_index(doc) is not None),
                    key=_document_stage_index)
    if drafts:
        default = PREPARATION_STAGES.index(drafts[0]['stage'])
    else:
        default = next((position for position, stage in enumerate(PREPARATION_STAGES)
                        if not any(isinstance(doc, dict) and doc.get('stage') == stage
                                   and doc.get('confirmed') is True for doc in documents)),
                       len(PREPARATION_STAGES))
    first = str(message or '').strip().split('\n', 1)[0].strip()
    lead = first.casefold().startswith(_PREPARATION_ADVANCE_LEAD)
    stage = None if lead else _preparation_stage_alias(first)
    if lead or stage is None:
        # 「确认，输出角色卡」一类：确认词领衔时点名是交给模型的推进请求，
        # 不做草稿路由（REQ-S01-89；确认与推进由模型语义判定）。
        return default
    position = PREPARATION_STAGES.index(stage)
    _slot, document = _document_for_stage(documents, stage)
    if document is None or document.get('confirmed') is not True:
        return position
    return default


def _preparation_draft_is_parallel(project, requested):
    """REQ-S01-89：重写口令指向未确认并行草稿时按重起草处理，不走采用稿重写。

    台账不是 dict 或缺 ``documents`` 列表时按非并行处理，交给
    ``_preparation_state`` 的「记录无效」校验给出原口径报错。"""
    from contract.stage_path_service import write_dir
    target = write_dir(project, 'script') / 'preparation_state.json'
    early = read_json(target) if target.is_file() else None
    box = early.get('revision') if isinstance(early, dict) else None
    if not isinstance(box, dict):
        box = early
    documents = box.get('documents') if isinstance(box, dict) else None
    if not isinstance(documents, list):
        return False
    _slot, document = _document_for_stage(documents, requested)
    return (isinstance(document, dict)
            and document.get('confirmed') is not True
            and _confirmed_prefix(documents, PREPARATION_STAGES.index(requested)) is None)


def _save_preparation_state_guarded(project, target, state, publish):
    """采用版本的台账写口：取消已确认、重确认、菜单或聊天改写采用版本都经这里。

    只写台账，不动自然剧本的采用记录（REQ-S01-14）；``project`` 留着是为了各调用点
    的签名不变。"""
    _save_preparation_state(target, state, publish)


def _preparation_document(text, title):
    """只规范单份当前阶段文件的说明前缀及显式待确认尾节。"""
    headings = list(re.finditer(r'^# ([^\n]+)\n', text, re.MULTILINE))
    if len(headings) != 1 or headings[0].group(1).strip() != title:
        return ''
    document = text[headings[0].start():]
    if document.endswith('待确认'):
        return document
    # 保留尾节里的问题与确认说明，只补统一结束标记；不凭空推断缺失标记。
    sections = list(re.finditer(r'^#{2,6} (.+)$', document, re.MULTILINE))
    if sections and sections[-1].group(1).strip() == '待确认':
        return document + '\n\n待确认'
    return ''


def _select_preparation_document(raw, titles, index, next_index):
    """在允许的位次范围内挑出模型回复里第一份合规格的阶段稿；返回 (位次, 正文)。"""
    selected = None
    text = ''
    for candidate in range(index, min(next_index, 2) + 1):
        document_text = _preparation_document(raw, titles[candidate])
        if document_text:
            selected, text = candidate, document_text
            break
    return selected, text


def _confirm_stage_document(documents, stage):
    """把台账中该阶段记录标为已确认；记录不存在时不动。"""
    _slot, document = _document_for_stage(documents, stage)
    if document is not None:
        document['confirmed'] = True


def _upsert_stage_document(documents, stage_index, stage, document):
    """按阶段名对位写入：同阶段原位替换，否则按 PREPARATION_STAGES 顺序插入。

    LOST-04：稀疏台账（任意顺序生成）始终保持阶段序，便于下标与阶段名互查。"""
    slot, _existing = _document_for_stage(documents, stage)
    if slot is None:
        insert_at = len(documents)
        for position, doc in enumerate(documents):
            doc_index = _document_stage_index(doc)
            if doc_index is not None and doc_index > stage_index:
                insert_at = position
                break
        documents.insert(insert_at, document)
    else:
        documents[slot] = document


def _preparation_texts_map(documents, texts):
    """documents 与 texts 平行列表 → {阶段名: 正文}；稀疏台账下不再按下标对位。

    只收已确认记录——进入自然剧本时交给模型的「已确认阶段文件」不含未确认草稿。"""
    return {doc['stage']: text for doc, text in zip(documents, texts)
            if isinstance(doc, dict) and doc.get('confirmed') is True}


def _preparation_brief_hash(state):
    revision = state.get('revision')
    return (revision.get('brief_hash', state.get('brief_hash'))
            if isinstance(revision, dict) else state.get('brief_hash'))


_PREPARATION_STAGE_ALT = '|'.join(sorted(
    (word for _stage, words in _PREPARATION_STAGE_WORDS for word in words), key=len, reverse=True))
_PREPARATION_BACK = re.compile(
    r'(?:请)?(?:把|将)?(?:回到|返回|退回|重新回到|重回|切回)\s*(?:'
    + _PREPARATION_STAGE_ALT + r')\s*(?:阶段)?\s*'
    + r'(?:重新创作|重新写|重写|重新生成|重新输出|重做|重来|再来|从头写)?'
    + r'\s*(?:一遍|一次)?')
_PREPARATION_REWRITE = re.compile(
    r'(?:请)?(?:把|将)?(?:' + _PREPARATION_STAGE_ALT
    + r')\s*(?:阶段)?\s*(?:要|需要|需|得|全部|整个|从头)?\s*'
    + r'(?:推翻|推倒|重写|重做|重来|重新写|重新创作|重新生成|重新输出)'
    + r'\s*(?:一遍|一次|重来|重新来)?')
# REQ-S01-12：回退重写的二次确认只认明确词，与询问文案「回复“确认”即从该阶段重写」
# 一致；随口应答（好／继续／ok 等）按保持现状处理。阶段推进不依赖本表，由模型按语义判断。
_PREPARATION_AFFIRMATIVE = frozenset(
    word.casefold() for word in ('确认', '确定', '确认重写', '重写', 'yes'))


def _preparation_rollback(stage, documents):
    """返回回退到该阶段会失效的已确认阶段清单；目标不合法或无下游确认时返回 None。

    此处只列出原采用阶段；重写所需前置正文由重写入口单独校验。"""
    if stage not in PREPARATION_STAGES:
        return None
    index = PREPARATION_STAGES.index(stage)
    if _confirmed_prefix(documents, index) is None:
        return None
    invalidated = [name for name in PREPARATION_STAGES[index:]
                   if any(isinstance(doc, dict) and doc.get('stage') == name
                          and doc.get('confirmed') is True for doc in documents)]
    return invalidated or None


def _preparation_natural_requested(message):
    """LOST-04：用户原话点名自然剧本且未点名前三阶段时，直接进入阶段④生成。"""
    first = str(message or '').strip().split('\n', 1)[0]
    return (any(word in first for word in ('自然剧本', '项目剧本'))
            and _preparation_stage_alias(first) is None)


def _promote_revision(state, project, target, publish):
    """revision 存在时把它切换为采用版本并写台账；不动自然剧本的采用记录（REQ-S01-14）。

    聊天 advancing、右键「设为定稿」确认完整重写稿、三阶段齐全的遗留 revision
    都由调用方判定时机；revision.documents 可以带未确认尾稿。返回是否发生切换。"""
    revision = state.get('revision')
    documents = revision.get('documents') if isinstance(revision, dict) else None
    if not (isinstance(documents, list) and documents):
        return False
    state.pop('revision')
    state['documents'] = documents
    state['brief_hash'] = revision.get('brief_hash', state.get('brief_hash'))
    _save_preparation_state_guarded(project, target, state, publish)
    return True
