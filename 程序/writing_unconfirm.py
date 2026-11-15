# -*- coding: utf-8 -*-
"""剧本准备阶段确认与取消：把磁盘文件设为/取消该阶段定稿，只改确认台账、不删文件。

``confirm_preparation_document``（设为定稿）与 ``unconfirm_preparation_document``
（取消确认）是一对对称的台账操作：写台账复用 ``writing_api._save_preparation_state``，
读复用 ``file_cache.read_json``，不另立第二入口。两函数此前分别在 writing_api 与
writing_unconfirm，R2400 起为收窄 writing_api 体积合入本模块。
"""
import hashlib
import json
import re
from pathlib import Path

from file_cache import read_json
from writing_api import (PREPARATION_STAGES, _complete_brief, _confirmed_prefix,
                         _preparation_brief_hash, _promote_revision,
                         _save_preparation_state_guarded, _working_documents)


def confirm_preparation_document(project, stage, path, *, publish):
    """把磁盘上的当前文件登记为该阶段的确认输出；只重算正文指纹，不改文件本体。"""
    if not callable(publish):
        raise TypeError('剧本准备阶段需要 L3 注入发布器')
    brief = _complete_brief(project)
    if brief is None:
        raise ValueError('请先完成项目创作信息')
    if stage not in PREPARATION_STAGES:
        raise ValueError('请选择项目设定、剧本大纲或角色卡')
    from contract.stage_path_service import write_dir
    folder = write_dir(project, 'script').resolve()
    target = folder / 'preparation_state.json'
    chosen = Path(path).resolve()
    if not chosen.is_file():
        raise ValueError('请选择一份已保存的阶段文件')
    if not chosen.is_relative_to(folder):
        raise ValueError('确认文件必须位于当前剧本准备目录内')
    text = chosen.read_text(encoding='utf-8')
    if not text.strip():
        raise ValueError('文件内容为空，不能作为确认输出')
    fingerprint = hashlib.sha256(json.dumps(brief['brief'], ensure_ascii=False,
                                            sort_keys=True).encode('utf-8')).hexdigest()
    state = read_json(target)
    brief_changed = isinstance(state, dict) and _preparation_brief_hash(state) != fingerprint
    if not isinstance(state, dict) or brief_changed:
        # 简报变化让旧确认记录整体失效，需按序重确认；保留重置以允许从「项目设定」重新开始。
        state = {'version': 1, 'brief_hash': fingerprint, 'documents': []}
    index = PREPARATION_STAGES.index(stage)
    try:
        documents = _working_documents(state)
    except (KeyError, TypeError):
        raise ValueError('剧本准备重写记录无效')
    if not isinstance(documents, list):
        raise ValueError('剧本准备阶段记录无效，不能确认输出')
    prefix = _confirmed_prefix(documents, index)
    if prefix is None and isinstance(state.get('revision'), dict):
        # 进行中的重写草稿（revision.documents）未推进到目标阶段时，显式「设为定稿」
        # 回到采用版本（顶层 documents）操作，而不是误报前置未确认——采用版本里
        # 前置阶段可能已确认（revision 只保留了重写起点之前的较短前缀）。
        adopted = state.get('documents')
        if isinstance(adopted, list):
            prefix = _confirmed_prefix(adopted, index)
            if prefix is not None:
                documents = adopted
                state.pop('revision', None)
                state.pop('pending_restart', None)
    if prefix is None:
        if brief_changed:
            raise ValueError('创作简报已变化，前置确认已失效；请先重设为「项目设定」定稿，'
                             '再确认「剧本大纲」「角色卡」')
        missing = [PREPARATION_STAGES[position] for position in range(index)
                   if position >= len(documents)
                   or not (isinstance(documents[position], dict)
                           and documents[position].get('confirmed') is True)]
        raise ValueError('「' + stage + '」之前还有阶段未确认（' + '、'.join(missing)
                         + '）；请先依次把这些阶段设为定稿，再设「' + stage + '」')
    invalidated = tuple(PREPARATION_STAGES[position]
                        for position, doc in enumerate(documents[index + 1:], start=index + 1)
                        if isinstance(doc, dict) and doc.get('confirmed') is True)
    document = {'stage': stage, 'path': chosen.relative_to(folder).as_posix(),
                'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(), 'confirmed': True}
    # REQ-S01-89：确认本阶段后，其后未确认的并行草稿记录保留；已确认下游照旧作废。
    state.get('revision', state)['documents'] = prefix + [document] + [
        doc for doc in documents[index + 1:]
        if isinstance(doc, dict) and doc.get('confirmed') is not True]
    revision = state.get('revision')
    # 重写稿确认到三阶段齐全才切换采用版本；中途确认仍留在 revision，
    # 与聊天「推进才采用」同口径，避免采用版本与自然稿采用记录错位。
    promoted = (isinstance(revision, dict)
                and len(revision.get('documents') or ()) == len(PREPARATION_STAGES)
                and _promote_revision(state, project, target, publish))
    if not promoted:
        # 放弃重写回到采用版本（rebound）、重确认同阶段换文件等都会改采用版本；
        # 基线守卫只在确认基线实际变化且存在有效采用时撤销自然稿采用。
        _save_preparation_state_guarded(project, target, state, publish)
    return invalidated


def preparation_confirmed_stages(project):
    """只读：当前已确认的①②③阶段名元组（采用状态），供菜单判断「取消已确认」是否可用。"""
    from contract.stage_path_service import write_dir
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

    与 ``confirm_preparation_document`` 对称：被取消阶段之后已确认的阶段
    一并取消确认，阶段指针回到该阶段，使其成为当前待确认阶段；原稿与重写草稿的文件
    本体都保留。返回一并取消的下游阶段元组；该阶段未确认或不存在时是空操作，返回空
    元组、不报错。"""
    if not callable(publish):
        raise TypeError('剧本准备阶段需要 L3 注入发布器')
    if stage not in PREPARATION_STAGES:
        raise ValueError('请选择项目设定、剧本大纲或角色卡')
    from contract.stage_path_service import write_dir
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
    _save_preparation_state_guarded(project, target, state, publish)
    return invalidated


_HEADING = re.compile(r'^#{1,6}\s')


def adoption_sections(text):
    """REQ-S01-88：待采用稿分段——markdown 标题分段（标题前导文自成一段）；无标题按空行分段。

    返回 [{'title', 'text'}]，title 供勾选列表展示。"""
    lines = str(text or '').splitlines()
    heads = [index for index, line in enumerate(lines) if _HEADING.match(line)]
    sections = []
    if heads:
        bounds = heads + [len(lines)]
        if heads[0] > 0 and '\n'.join(lines[:heads[0]]).strip():
            bounds = [0] + bounds
        for position in range(len(bounds) - 1):
            body = '\n'.join(lines[bounds[position]:bounds[position + 1]]).strip('\n')
            if body.strip():
                sections.append({'title': body.splitlines()[0].strip(), 'text': body})
    else:
        for chunk in re.split(r'\n\s*\n', str(text or '')):
            if chunk.strip():
                sections.append({'title': chunk.strip().splitlines()[0].strip(),
                                 'text': chunk.strip()})
    return sections


def apply_partial_adoption(project, stage, path, keep, *, publish):
    """REQ-S01-88：只保留所选段落；台账命中的记录写 partial_adoption 标记。

    已确认稿被截写等同取消该阶段确认：同 unconfirm 口径截断其后记录，确认基线
    收窄时既有守卫自动撤销自然稿采用；待确认草稿只改标记与文件，指纹按既有
    待确认重绑口径在下次装载时更新。文件不在台账登记时只做截写。全选为不操作。"""
    if not callable(publish):
        raise TypeError('剧本准备阶段需要 L3 注入发布器')
    if stage not in PREPARATION_STAGES:
        raise ValueError('请选择项目设定、剧本大纲或角色卡')
    from stage_path_service import write_dir
    folder = write_dir(project, 'script').resolve()
    target = folder / 'preparation_state.json'
    chosen = Path(path).resolve()
    if not chosen.is_relative_to(folder):
        raise ValueError('采用文件必须位于当前剧本准备目录内')
    text = chosen.read_text(encoding='utf-8') if chosen.is_file() else ''
    sections = adoption_sections(text)
    if len(sections) < 2:
        raise ValueError('稿件不足两段，无需按段落采用')
    keep = sorted(set(int(index) for index in keep))
    if not keep or keep[0] < 0 or keep[-1] >= len(sections):
        raise ValueError('请选择要采用的段落')
    if keep == list(range(len(sections))):
        return {'kept': keep, 'total': len(sections), 'changed': False}
    kept_text = '\n\n'.join(sections[index]['text'] for index in keep).strip() + '\n'
    publish(chosen, kept_text, lambda value: bool(str(value).strip()), lambda _target: None)
    state = read_json(target) if target.is_file() else None
    if not isinstance(state, dict):
        return {'kept': keep, 'total': len(sections), 'changed': True}
    relative = chosen.relative_to(folder).as_posix()
    box = state['revision'] if isinstance(state.get('revision'), dict) else state
    documents = box.get('documents') if isinstance(box, dict) else None
    if isinstance(documents, list):
        index = next((position for position, document in enumerate(documents)
                      if isinstance(document, dict) and document.get('stage') == stage
                      and document.get('path') == relative), None)
        if index is not None:
            document = dict(documents[index],
                            partial_adoption={'kept': keep, 'total': len(sections)})
            if document.get('confirmed') is True:
                box['documents'] = documents[:index] + [dict(document, confirmed=False)]
            else:
                box['documents'] = documents[:index] + [document] + documents[index + 1:]
            _save_preparation_state_guarded(project, target, state, publish)
    return {'kept': keep, 'total': len(sections), 'changed': True}
