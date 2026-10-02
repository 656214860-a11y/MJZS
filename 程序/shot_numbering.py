# -*- coding: utf-8 -*-
"""按集号顺序重排镜头编号，并同步项目内的编号引用。

批量分镜任务可能按完成顺序而不是剧本顺序编号（例如 EP002 得到 SH032-SH050，
EP003 反而占了 SH017-SH031）。本模块按集号升序重新分配连续编号，并把项目里
以镜头编号命名的文件、目录以及文本里的编号引用一起改写；只改编号，不动镜头
内容、资产、对白和任务状态。

命令行：
    python shot_numbering.py <项目目录>          # 预演，只打印计划
    python shot_numbering.py <项目目录> --apply  # 执行，改写前自动备份
"""
import json
from file_cache import read_json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from agent.core import save_bytes

ID_PATTERN = re.compile(r'SH\d{3,}')
SKIP_PARTS = (('工作流任务', '回收站'), ('工作流任务', '升级备份'))
TEXT_SUFFIXES = frozenset({'.json', '.jsonl', '.txt', '.md', '.py', '.srt', '.csv',
                           '.log', '.yaml', '.yml', '.ini', '.cfg', '.xml', '.html'})
SIZE_LIMIT = 8 * 1024 * 1024


def _read_json(path):
    data = read_json(path)
    if not isinstance(data, dict):
        raise ValueError(Path(path).name + ' 不是 JSON 对象')
    return data


def episode_number(data, path, fallback=0):
    """集号优先取 episode_id（EP002），其次取文件名（EP002 / 第02集），最后用传入顺序。"""
    for value in (data.get('episode_id'), Path(path).name):
        text = str(value or '')
        match = re.search(r'EP\s*0*(\d+)', text) or re.search(r'第\s*0*(\d+)\s*集', text)
        if match:
            return int(match.group(1))
    return fallback


def storyboard_order(paths):
    """按集号升序返回 [(path, data)]。"""
    rows = []
    for index, path in enumerate(paths):
        path = Path(path)
        data = _read_json(path)
        rows.append((episode_number(data, path, index), index, path, data))
    rows.sort(key=lambda row: (row[0], row[1]))
    return [(row[2], row[3]) for row in rows]


def build_mapping(ordered):
    """按集号顺序连续编号，返回 {旧编号: 新编号}；编号本来正确的镜头不收录。

    同一个旧编号在两处需要不同去向时必须直接报错。改写是按编号做的（项目里的
    文件、目录名和文本引用都只有编号可依据），所以「同一编号出现在不止一集」时
    无从分辨某处引用属于哪一集：照做就会把别集的同名编号一起改掉，两集最后得到
    重复编号，而且改写正好落在备份之后、无法整体回滚。宁可拒绝，让用户先让各集
    编号全局唯一。
    """
    mapping = {}
    seen = {}
    counter = 1
    for path, data in ordered:
        shots = data.get('shots')
        if not isinstance(shots, list) or not shots:
            raise ValueError(Path(path).name + ' 缺少非空 shots 数组')
        for shot in shots:
            old = str(shot.get('id') or '')
            if not ID_PATTERN.fullmatch(old):
                raise ValueError(Path(path).name + ' 的镜头编号格式错误：' + (old or '空'))
            new = 'SH%03d' % counter
            counter += 1
            if old in seen and seen[old][0] != new:
                was, name = seen[old]
                raise ValueError(
                    '编号冲突：%s 在「%s」要改成 %s，在「%s」却要改成 %s。同一编号出现在多份分镜里'
                    '（各集都从 SH001 重新编号，或目录里留了同一集的多份副本）；按编号重排会把两处一起'
                    '改掉，已停止。请先让各集编号全局唯一（取消采用或删除多余副本）再重排。'
                    % (old, name, was, Path(path).name, new))
            seen[old] = (new, Path(path).name)
            if old != new:
                mapping[old] = new
    return mapping


def renumber_text(text, mapping):
    return ID_PATTERN.sub(lambda match: mapping.get(match.group(0), match.group(0)), text)


def adopted_storyboards(project):
    from storyboard_selection import adopted
    return adopted(project)


def _skipped(project, path):
    try:
        parts = path.relative_to(project).parts
    except ValueError:
        return True
    return any(parts[:len(skip)] == skip for skip in SKIP_PARTS)


def _text(path):
    """可改写的文本返回 (text, encoding)，否则返回 (None, None)。"""
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return None, None
    try:
        if path.stat().st_size > SIZE_LIMIT:
            return None, None
        raw = path.read_bytes()
    except OSError:
        return None, None
    if b'\x00' in raw:
        return None, None
    for encoding in ('utf-8', 'gbk'):
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        if encoding == 'utf-8' and text.startswith('\ufeff'):
            return text[1:], 'utf-8-sig'
        return text, encoding
    return None, None


def collect(project, mapping):
    """只读预检：返回 (需要改写内容的文件, 需要改名的文件或目录)。"""
    project = Path(project).resolve()
    contents = []
    renames = []
    for root, dirs, files in os.walk(project):
        base = Path(root)
        if _skipped(project, base):
            dirs[:] = []
            continue
        dirs[:] = [name for name in dirs if not _skipped(project, base / name)]
        for name in dirs + files:
            if renumber_text(name, mapping) != name:
                renames.append(base / name)
        for name in files:
            path = base / name
            text, encoding = _text(path)
            if text is not None and renumber_text(text, mapping) != text:
                contents.append(path)
    return contents, renames


def _backup(project, paths, stamp):
    root = project / '工作流任务' / '升级备份' / (stamp + '_镜头编号重排')
    for path in paths:
        for file in ([path] if path.is_file() else sorted(path.rglob('*'))):
            if not file.is_file():
                continue
            target = root / file.relative_to(project)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
    return root


def _apply_renames(project, mapping):
    """先改成临时名再改成目标名，避免两个编号互换时互相覆盖。"""
    def walk(current):
        pending = []
        for child in sorted(current.iterdir(), key=lambda item: item.name):
            if _skipped(project, child):
                continue
            new_name = renumber_text(child.name, mapping)
            if new_name == child.name:
                if child.is_dir():
                    walk(child)
                continue
            temp = child.with_name(child.name + '.rn' + uuid4().hex[:8])
            child.rename(temp)
            pending.append((temp, new_name))
        for temp, new_name in pending:
            if temp.is_dir():
                walk(temp)
            temp.rename(temp.with_name(new_name))
    walk(project)


def renumber(project, storyboards=None, *, apply=False, log=print):
    """按集号顺序重排镜头编号；apply=False 时只预演，不改动项目。"""
    project = Path(project).resolve()
    ordered = storyboard_order(storyboards if storyboards is not None else adopted_storyboards(project))
    mapping = build_mapping(ordered)
    contents, renames = collect(project, mapping)
    result = {'project': project, 'ordered': ordered, 'mapping': mapping,
              'contents': contents, 'renames': renames, 'backup': None}
    log('按集号顺序：' + '、'.join('%s(%s)' % (data.get('episode_id'), Path(path).name) for path, data in ordered))
    log('需改编号 %d 个镜头；需改写文本 %d 个；需改名 %d 项' % (len(mapping), len(contents), len(renames)))
    if not mapping:
        log('编号已经连续，无需改动')
        return result
    if not apply:
        for old in sorted(mapping):
            log('  %s -> %s' % (old, mapping[old]))
        return result
    result['backup'] = _backup(project, list(dict.fromkeys(contents + renames)),
                              datetime.now().strftime('%Y%m%d_%H%M%S'))
    for path in contents:
        text, encoding = _text(path)
        save_bytes(path, renumber_text(text, mapping).encode(encoding))
    _apply_renames(project, mapping)
    log('备份：' + str(result['backup']))
    return result


def verify(project, storyboards=None):
    """重排后自检：返回问题列表，空列表表示编号连续。"""
    project = Path(project).resolve()
    problems = []
    expected = 1
    for path, data in storyboard_order(storyboards if storyboards is not None else adopted_storyboards(project)):
        ids = [str(shot.get('id') or '') for shot in data.get('shots') or []]
        numbers = [int(sid[2:]) for sid in ids if ID_PATTERN.fullmatch(sid)]
        if len(numbers) != len(ids):
            problems.append(Path(path).name + ' 存在非标准镜头编号')
        if numbers != list(range(expected, expected + len(numbers))):
            span = (ids[0] + '..' + ids[-1]) if ids else '空'
            problems.append('%s 编号不连续：%s，本应从 SH%03d 起' % (Path(path).name, span, expected))
        expected += len(numbers)
    return problems


def main(argv=None):
    import sys
    args = list(sys.argv[1:] if argv is None else argv)
    values = [value for value in args if not value.startswith('-')]
    if not values:
        print('用法：python shot_numbering.py <项目目录> [--apply]')
        return 2
    try:
        result = renumber(values[0], apply='--apply' in args)
    except (OSError, ValueError) as error:
        print('重排失败：' + str(error))
        return 1
    if '--apply' in args:
        problems = verify(values[0])
        print('自检：' + ('编号连续' if not problems else '；'.join(problems)))
        again = renumber(values[0], apply=False, log=lambda *a: None)
        print('复查：%d 个镜头待改编号、%d 个文件待改写、%d 项待改名（全为 0 表示已完成）'
              % (len(again['mapping']), len(again['contents']), len(again['renames'])))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
