# -*- coding: utf-8 -*-
"""剧本阶段提供给 Claude 的受控项目文件工具。"""
from pathlib import Path

from stage_path_service import write_dir

PROJECT_CONTEXT_FILES=('data/项目接续.json',)
MAX_READ_CHARS=60000


def definitions():
    """返回 Anthropic Messages API 的工具声明。"""
    return [
        {'name':'list_project_writing_files', 'description':'列出当前项目的剧本文档与项目接续 JSON。',
         'input_schema':{'type':'object','properties':{}}},
        {'name':'read_project_writing_file', 'description':'读取当前项目的剧本文档或项目接续 JSON。path 必须先由列表工具返回。',
         'input_schema':{'type':'object','properties':{'path':{'type':'string','description':'相对项目根目录的路径'}},'required':['path']}},
        {'name':'write_project_writing_file', 'description':'保存本轮剧本成果。仅可写 01剧本准备/ 下文件；历史 writing/ 路径会自动迁移到当前目录。项目接续 JSON 仅可读取。',
         'input_schema':{'type':'object','properties':{'path':{'type':'string','description':'相对项目根目录的目标路径'},'content':{'type':'string','description':'完整文本内容'}},'required':['path','content']}},
    ]


def _project_relative(root, raw):
    target=(root/raw).resolve()
    try:return target,target.relative_to(root).as_posix()
    except ValueError:raise ValueError('文件路径超出当前项目')


def _path(project, value, writing_only=False):
    """解析受控路径；旧 writing/ 只读，新写始终进入当前阶段目录。"""
    root=Path(project).resolve();raw=str(value or '').replace('\\','/').strip()
    if not raw or Path(raw).is_absolute():raise ValueError('文件路径必须是项目内的相对路径')
    current=write_dir(root,'script').resolve();legacy=(root/'writing').resolve()
    if raw.startswith('writing/') or raw.startswith('01剧本准备/'):
        tail=raw.split('/',1)[1] if '/' in raw else ''
        if not tail:raise ValueError('请指定剧本阶段内的文件')
        target,_relative=_project_relative(current,tail)
        if writing_only:return target,target.relative_to(root).as_posix()
        old,_old_relative=_project_relative(legacy,tail)
        # 同名时当前阶段优先；只有历史文件存在时才回退读取。
        if not target.exists() and old.is_file():target=old
        return target,target.relative_to(root).as_posix()
    target,relative=_project_relative(root,raw)
    if relative in PROJECT_CONTEXT_FILES and not writing_only:return target,relative
    raise ValueError('该路径不在剧本工作流授权范围内')


def list_files(project):
    root=Path(project).resolve();items=[];current=write_dir(root,'script');legacy=root/'writing'
    for folder in (current,legacy):
        if folder.is_dir():
            for file in sorted(folder.rglob('*')):
                if file.is_file() and file.suffix.lower() in ('.md','.json','.txt'):
                    relative=file.relative_to(root).as_posix()
                    if relative not in items:items.append(relative)
    for relative in PROJECT_CONTEXT_FILES:
        if (root/relative).is_file():items.append(relative)
    return items[:200]


def read_file(project, path):
    target,relative=_path(project,path)
    if not target.is_file():raise ValueError('文件不存在：'+relative)
    text=target.read_text(encoding='utf-8-sig')
    if len(text)>MAX_READ_CHARS:text=text[:MAX_READ_CHARS]+'\n[内容过长，已截断]'
    return {'path':relative,'content':text}


def write_file(project, path, content, *, publish=None):
    target,relative=_path(project,path,writing_only=True);text=str(content or '')
    if not text.strip():
        raise ValueError('剧本正文不能为空')
    if not callable(publish):
        raise TypeError('剧本成果工具需要 L3 注入发布器')
    publish(target, text, lambda value: bool(value.strip()), lambda _target: None)
    return {'path':relative,'saved_chars':len(text)}


def execute(project, name, payload, *, publish=None):
    args=payload if isinstance(payload,dict) else {}
    if name=='list_project_writing_files':return {'files':list_files(project)}
    if name=='read_project_writing_file':return read_file(project,args.get('path'))
    if name=='write_project_writing_file':
        if not callable(publish):
            raise TypeError('剧本成果工具需要 L3 注入发布器')
        return write_file(project,args.get('path'),args.get('content'),publish=publish)
    raise ValueError('未授权的项目工具：'+str(name))
