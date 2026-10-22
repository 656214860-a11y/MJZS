"""iter_script_documents 压平：旧实现原样内嵌，与新实现在各种目录布局上逐例对照（含惰性消费顺序）。"""
import os
import tempfile
import unittest
from pathlib import Path

import project_stages
import script_workspace_service as sws

LEGACY_SRC = r'''def _legacy_iter_script_documents(project):
    """逐项发现可见剧本文档，供 UI 在空闲批次中渐进消费。

    本函数不收集完整列表，也不导入 Tk。调用方可以在项目切换时停止消费，
    从而不会因为尚未显示的后续目录而继续提交 UI 工作。
    """
    writing_dir = project_stages.writing(project)
    if not writing_dir.is_dir():
        return
    try:
        writing_root = writing_dir.resolve()
    except OSError:
        return

    # 本地 Agent 可只更新内部工作稿；正式目录中没有同内容交付时才展示它。
    # 只探测当前阶段的固定路径，不为首屏调用递归的自然剧本检索。
    draft = writing_dir / RAW_SCRIPT_NAME
    draft_document = None
    draft_text = ''
    try:
        draft.resolve().relative_to(writing_root)
        if draft.is_file() and draft.stat().st_size:
            draft_text = draft.read_text(encoding='utf-8', errors='ignore').strip()
            if is_natural_script(draft_text):
                draft_document = ScriptDocument('script', draft, draft.stat().st_mtime, RAW_SCRIPT_NAME)
    except (OSError, ValueError):
        pass

    # 用户上传的创意是剧本准备的项目设定来源，放在该列而不是混进模型生成的版本目录。
    input_dir = writing_dir / '输入'
    if input_dir.is_dir():
        for path in input_dir.glob('故事创意_*.md'):
            if not path.is_file():
                continue
            try:
                path.resolve().relative_to(writing_root)
                yield ScriptDocument('setting', path, path.stat().st_mtime,
                                     path.relative_to(writing_dir).as_posix())
            except (OSError, ValueError):
                continue
    # 创意批次的正式布局固定为 ``创意_*``（历史项目）或
    # ``Provider/Model/创意_*``（当前模型分区）。不要在启动期用 rglob：
    # 它会把用户自行放入 writing 的任意深层资料树也扫进 Tk 首屏。下面的
    # 有界枚举同时保留两种已发布布局，并让未知深层目录保持用户按需打开时
    # 的惰性资源，而不是启动负担。
    creative_batches = []
    for first in writing_dir.iterdir():
        if not first.is_dir() or first.name == '输入':
            continue
        if first.name.startswith('创意_'):
            creative_batches.append(first)
            continue
        for second in first.iterdir():
            if not second.is_dir():
                continue
            if second.name.startswith('创意_'):
                creative_batches.append(second)
                continue
            for batch in second.iterdir():
                if batch.is_dir() and batch.name.startswith('创意_'):
                    creative_batches.append(batch)
    for category, directory in SCRIPT_CATEGORIES.items():
        for batch in creative_batches:
            folder = batch / directory
            if not folder.is_dir() or not folder.parent.name.startswith('创意_'):
                continue
            try:
                folder.resolve().relative_to(writing_root)
            except (OSError, ValueError):
                continue
            for path in folder.iterdir():
                if not path.is_file() or path.suffix.lower() not in VISIBLE_SUFFIXES:
                    continue
                try:
                    path.resolve().relative_to(writing_root)
                    modified_at = path.stat().st_mtime
                    relative_path = path.relative_to(writing_dir).as_posix()
                except (OSError, ValueError):
                    continue
                if (draft_document is not None and category == 'script'
                        and path.suffix.lower() in {'.md', '.txt'}):
                    try:
                        if path.read_text(encoding='utf-8').strip() == draft_text:
                            draft_document = None
                    except (OSError, UnicodeError):
                        pass
                yield ScriptDocument(category, path, modified_at, relative_path)
    if draft_document is not None:
        yield draft_document
'''

SCRIPT_TEXT = '第一场 咖啡馆\n小明：你好。\n小红：早。'


def _w(path, text='x', mtime=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def _writing(project):
    return project_stages.writing(project)


def _batch(project, *parts):
    return _writing(project).joinpath(*parts)


def f_none(project):
    pass


def f_empty_writing(project):
    _writing(project).mkdir(parents=True, exist_ok=True)


def f_draft_only(project):
    _w(_writing(project) / sws.RAW_SCRIPT_NAME, SCRIPT_TEXT)


def f_draft_empty(project):
    _w(_writing(project) / sws.RAW_SCRIPT_NAME, '')


def f_draft_dup_of_delivered(project):
    _w(_writing(project) / sws.RAW_SCRIPT_NAME, SCRIPT_TEXT)
    _w(_batch(project, '创意_1', '项目剧本', 'a.md'), '  ' + SCRIPT_TEXT + '\n', 100)


def f_draft_differs_from_delivered(project):
    _w(_writing(project) / sws.RAW_SCRIPT_NAME, SCRIPT_TEXT)
    _w(_batch(project, '创意_1', '项目剧本', 'a.md'), '别的内容', 100)


def f_draft_dup_but_docx_first(project):
    _w(_writing(project) / sws.RAW_SCRIPT_NAME, SCRIPT_TEXT)
    _w(_batch(project, '创意_1', '项目剧本', 'a.docx'), SCRIPT_TEXT, 100)
    _w(_batch(project, '创意_1', '项目剧本', 'b.txt'), SCRIPT_TEXT, 101)


def f_draft_dup_in_non_script_category(project):
    _w(_writing(project) / sws.RAW_SCRIPT_NAME, SCRIPT_TEXT)
    _w(_batch(project, '创意_1', '项目大纲', 'a.md'), SCRIPT_TEXT, 100)


def f_draft_bad_encoding_delivered(project):
    _w(_writing(project) / sws.RAW_SCRIPT_NAME, SCRIPT_TEXT)
    path = _batch(project, '创意_1', '项目剧本', 'a.md')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'\xff\xfe\x00bad')


def f_inputs(project):
    _w(_writing(project) / '输入' / '故事创意_a.md', 'a', 50)
    _w(_writing(project) / '输入' / '故事创意_b.md', 'b', 60)
    _w(_writing(project) / '输入' / '其它.md', 'c', 70)
    (_writing(project) / '输入' / '故事创意_dir.md').mkdir(parents=True, exist_ok=True)


def f_three_layouts(project):
    for rank, parts in enumerate((('创意_1',), ('P', '创意_2'), ('P', 'M', '创意_3'), ('P', 'M', 'X', '创意_4'))):
        for category, folder in sws.SCRIPT_CATEGORIES.items():
            _w(_batch(project, *parts, folder, '%s_%d.md' % (category, rank)), category, 100 + rank)


def f_suffixes_and_dirs(project):
    base = _batch(project, '创意_1', '项目设定')
    for name in ('a.md', 'b.TXT', 'c.docx', 'd.pdf', 'e', 'f.MD'):
        _w(base / name, name, 10)
    (base / 'sub.md').mkdir(parents=True, exist_ok=True)


def f_input_dir_skipped_as_batch(project):
    _w(_writing(project) / '输入' / '创意_hidden' / '项目设定' / 'a.md', 'a', 10)
    _w(_writing(project) / '其它目录' / '创意_ok' / '项目设定' / 'a.md', 'a', 11)
    _w(_writing(project) / 'file_at_top.md', 'top', 12)


def f_batch_named_like_file(project):
    _w(_writing(project) / '创意_file', 'not a dir', 12)
    _w(_writing(project) / 'P' / '创意_file', 'not a dir either', 12)


def f_category_is_file(project):
    _w(_batch(project, '创意_1', '项目设定'), 'file instead of dir', 12)


def f_symlink_escape(project):
    outside = Path(tempfile.mkdtemp())
    try:
        _w(outside / 'evil.md', 'evil', 12)
        target = _batch(project, '创意_1', '项目设定')
        target.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(str(outside), str(target), target_is_directory=True)
    except (OSError, NotImplementedError):
        raise unittest.SkipTest('no symlink privilege')


def f_file_symlink_escape(project):
    outside = Path(tempfile.mkdtemp())
    try:
        evil = _w(outside / 'evil.md', 'evil', 12)
        _w(_batch(project, '创意_1', '项目设定', 'ok.md'), 'ok', 13)
        os.symlink(str(evil), str(_batch(project, '创意_1', '项目设定', 'link.md')))
    except (OSError, NotImplementedError):
        raise unittest.SkipTest('no symlink privilege')


def f_writing_is_file(project):
    target = _writing(project)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('file', encoding='utf-8')


FIXTURES = [value for key, value in sorted(globals().items()) if key.startswith('f_')]


def _rows(documents):
    return [(d.category, str(d.path), d.modified_at, d.relative_path) for d in documents]


class IterScriptDocumentsEquivalence(unittest.TestCase):
    def setUp(self):
        namespace = dict(vars(sws))
        exec(compile(LEGACY_SRC, 'legacy_iter_script_documents', 'exec'), namespace)
        self.legacy = namespace['_legacy_iter_script_documents']

    def test_every_layout_matches_the_legacy_result(self):
        total = ran = 0
        raw_drafts = 0
        for fixture in FIXTURES:
            with tempfile.TemporaryDirectory() as td:
                project = Path(td) / 'p'
                project.mkdir()
                try:
                    fixture(project)
                except unittest.SkipTest:
                    continue
                old = _rows(self.legacy(project))
                new = _rows(sws.iter_script_documents(project))
                self.assertEqual(new, old, fixture.__name__)
                ran += 1
                total += len(new)
                raw_drafts += any(Path(row[1]).name == sws.RAW_SCRIPT_NAME for row in new)
        self.assertGreater(ran, 14)
        self.assertGreater(total, 25)   # 对照不能是空对空
        self.assertGreater(raw_drafts, 2)  # 内部工作稿既出现过也被去重过

    def test_consumption_is_lazy_in_the_same_way(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'p'
            project.mkdir()
            f_three_layouts(project)
            f_inputs(project)
            f_draft_only(project)
            old_it, new_it = self.legacy(project), sws.iter_script_documents(project)
            for _ in range(5):
                self.assertEqual(_rows([next(new_it)]), _rows([next(old_it)]))
            self.assertEqual(_rows(new_it), _rows(old_it))


if __name__ == '__main__':
    unittest.main()
