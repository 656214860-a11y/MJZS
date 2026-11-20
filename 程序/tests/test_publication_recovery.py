"""Process-death coverage for durable artifact/index publication."""
import errno
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent import core, publication
import infra.file_cache as file_cache


SCRIPT = r'''
import os, sys
from pathlib import Path
from agent import core, publication
from stage_execution_service import publish_stage_bundle
root = Path(sys.argv[1])
publication.ROOT = root / 'transactions'
point = sys.argv[2]
replace = core.replace
write = publication._write
commit = publication._commit
discard = publication._discard
os_replace = os.replace
def crash_recovery(source, target):
    os_replace(source, target)
    if point == 'recovering' and str(source).endswith('.recover'):
        os._exit(77)
os.replace = crash_recovery
def crash_replace(source, target):
    replace(source, target)
    if Path(target).name == point:
        os._exit(77)
def crash_write(folder, record):
    write(folder, record)
    if record['state'] == point:
        os._exit(77)
def crash_commit(folder):
    commit(folder)
    if point == 'committed':
        os._exit(77)
def crash_discard(folder):
    if point == 'cleanup':
        (folder/'0').unlink(missing_ok=True)
        os._exit(77)
    discard(folder)
core.replace = crash_replace
publication._write = crash_write
publication._commit = crash_commit
publication._discard = crash_discard
def update_index():
    core.save(root/'index.json', {'v':2})
    if point in ('rolled_back', 'recovering'):
        raise RuntimeError('rollback injection')
publish_stage_bundle({root/'first.json': b'{"v":2}', root/'second.json': b'{"v":2}'},
                     lambda _: True, update_index)
'''


class PublicationRecoveryTests(unittest.TestCase):
    def test_recovery_preserves_edits_after_process_death(self):
        for edit in ('in-place', 'same-size-and-mtime', 'replace', 'delete', 'new-target'):
            with self.subTest(edit=edit), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / 'first.json'
                with patch.object(publication, 'ROOT', root / 'transactions'):
                    if edit != 'new-target':
                        core.save_text(target, 'old')
                    result = subprocess.run(
                        [sys.executable, '-B', '-c', SCRIPT, str(root), target.name],
                        capture_output=True, timeout=15,
                        cwd=Path(__file__).resolve().parents[1],
                    )
                    self.assertEqual(result.returncode, 77, result.stderr.decode(errors='replace'))
                    edited = b'edited'
                    if edit == 'same-size-and-mtime':
                        before = target.stat()
                        edited = b'{"v":3}'
                        target.write_bytes(edited)
                        os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
                        self.assertEqual(target.stat().st_size, before.st_size)
                        self.assertEqual(target.stat().st_mtime_ns, before.st_mtime_ns)
                    elif edit == 'replace':
                        replacement = root / 'editor.tmp'
                        replacement.write_bytes(b'edited')
                        os.replace(replacement, target)
                    elif edit == 'delete':
                        target.unlink()
                    else:
                        target.write_bytes(b'edited')
                    with self.assertLogs(publication.__name__, level='WARNING'):
                        publication.recover_pending()
                        if edit == 'delete':
                            self.assertFalse(target.exists())
                        else:
                            self.assertEqual(target.read_bytes(), edited)
                    self.assertFalse(any(path.is_dir() for path in publication.ROOT.iterdir()))

    def test_bundle_faults_leave_original_and_clean_temporary_files(self):
        from stage_execution_service import publish_stage_bundle

        for fault in ('partial-write', 'disk-full', 'permission', 'replace'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / 'first.json'
                real_replace = os.replace
                real_fsync = os.fsync
                with patch.object(publication, 'ROOT', root / 'transactions'):
                    core.save_text(target, 'old')
                    original_inode = target.stat().st_ino
                    def replace(source, destination):
                        if Path(destination) == target and not str(source).endswith('.recover'):
                            if fault == 'permission':
                                raise PermissionError(errno.EACCES, fault)
                            if fault == 'replace':
                                raise OSError(errno.EIO, fault)
                        real_replace(source, destination)

                    def fsync(fd):
                        if fault == 'partial-write':
                            os.ftruncate(fd, 1)
                            raise OSError(errno.EIO, fault)
                        if fault == 'disk-full':
                            raise OSError(errno.ENOSPC, fault)
                        real_fsync(fd)

                    with patch('os.replace', side_effect=replace), patch('os.fsync', side_effect=fsync):
                        with self.assertRaisesRegex(OSError, fault):
                            publish_stage_bundle({target: b'new'}, lambda _: True, lambda: None)
                    self.assertEqual(target.read_bytes(), b'old')
                    self.assertEqual(target.stat().st_ino, original_inode)
                    self.assertEqual(set(root.iterdir()), {target, publication.ROOT})
                    self.assertFalse(any(path.is_dir() for path in publication.ROOT.iterdir()))

    def test_recovery_retry_after_replace_failure_preserves_later_edit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'artifact.md'
            with patch.object(publication, 'ROOT', root / 'transactions'):
                core.save_text(target, 'old')
                real_replace = os.replace

                def replace(source, destination):
                    if str(source).endswith('.recover'):
                        raise OSError(errno.EACCES, 'recovery replace denied')
                    real_replace(source, destination)

                with patch('os.replace', side_effect=replace):
                    with self.assertRaisesRegex(OSError, 'recovery replace denied') as raised:
                        with publication.transaction():
                            core.save_text(target, 'first attempt')
                            core.save_text(target, 'second attempt')
                            raise ValueError('index failure')
                self.assertEqual(str(raised.exception.__context__), 'index failure')
                self.assertEqual(target.read_bytes(), b'second attempt')
                self.assertEqual(list(root.glob('*.recover')), [])
                self.assertEqual(len(list(publication.ROOT.glob('*/journal.json'))), 1)
                target.write_bytes(b'user edit')
                with self.assertLogs(publication.__name__, level='WARNING'):
                    publication.recover_pending()
                self.assertEqual(target.read_bytes(), b'user edit')
                self.assertEqual(list(publication.ROOT.glob('*/journal.json')), [])

    def test_recovery_rechecks_target_after_copying_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'artifact.md'
            copy = publication._copy

            def copy_with_edit(source, destination):
                copy(source, destination)
                if str(destination).endswith('.recover'):
                    target.write_bytes(b'user edit during recovery')

            with patch.object(publication, 'ROOT', root / 'transactions'):
                core.save_text(target, 'old')
                with patch.object(publication, '_copy', side_effect=copy_with_edit):
                    with self.assertLogs(publication.__name__, level='WARNING'):
                        with self.assertRaisesRegex(ValueError, 'index failure'):
                            with publication.transaction():
                                core.save_text(target, 'new')
                                raise ValueError('index failure')
                self.assertEqual(target.read_bytes(), b'user edit during recovery')
                self.assertEqual(list(root.glob('*.recover')), [])

    def test_same_transaction_replacement_does_not_adopt_an_external_edit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'artifact.md'
            with patch.object(publication, 'ROOT', root / 'transactions'):
                core.save_text(target, 'old')
                with self.assertLogs(publication.__name__, level='WARNING'):
                    with self.assertRaisesRegex(RuntimeError, '在发布期间已被修改'):
                        with publication.transaction():
                            core.save_text(target, 'first attempt')
                            target.write_bytes(b'user edit')
                            core.save_text(target, 'second attempt')
                self.assertEqual(target.read_bytes(), b'user edit')
                self.assertEqual(set(root.iterdir()), {target, publication.ROOT})

    def test_death_at_every_target_index_commit_and_cleanup(self):
        for point in ('first.json', 'second.json', 'index.json', 'committed', 'cleanup', 'rolled_back', 'recovering'):
            with self.subTest(point=point), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with patch.object(publication, 'ROOT', root/'transactions'):
                    core.save(root/'first.json', {'v':1})
                    core.save(root/'index.json', {'v':1})
                    file_cache.read_json(root/'first.json')
                    result = subprocess.run([sys.executable, '-B', '-c', SCRIPT, str(root), point],
                                            capture_output=True, timeout=15,
                                            cwd=Path(__file__).resolve().parents[1])
                    self.assertEqual(result.returncode, 77, result.stderr.decode(errors='replace'))
                    committed = point in ('committed', 'cleanup')
                    expected = {'v':2 if committed else 1}
                    self.assertEqual(file_cache.read_json(root/'first.json'), expected)
                    self.assertEqual(core.read(root/'index.json'), expected)
                    self.assertEqual((root/'second.json').exists(), committed)
                    publication.recover_pending()
                    self.assertEqual(core.read(root/'first.json'), expected)
                    self.assertFalse(any(p.is_dir() for p in publication.ROOT.iterdir()))

    def test_index_exception_rolls_back_index_and_new_artifact(self):
        from stage_execution_service import publish_stage_text
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(publication, 'ROOT', root/'transactions'):
                core.save(root/'index.json', {'v':1})
                def update(_):
                    core.save(root/'index.json', {'v':2})
                    raise RuntimeError('index failed')
                with self.assertRaisesRegex(RuntimeError, 'index failed'):
                    publish_stage_text(root/'new.md', 'new', lambda _: True, update)
                self.assertFalse((root/'new.md').exists())
                self.assertEqual(core.read(root/'index.json'), {'v':1})

    def test_corrupt_journal_blocks_read_without_touching_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(publication, 'ROOT', root/'transactions'):
                core.save(root/'first.json', {'v':1})
                # 手工摆坏日志不经过 access()：拿住进程内的发布锁到用例收尾，免得别的线程读写时把还没写日志的目录清掉。
                publication._LOCK.acquire()
                self.addCleanup(publication._LOCK.release)
                folder = publication.ROOT / ('a'*32)
                folder.mkdir()
                (folder/'journal.json').write_text('{broken', encoding='utf-8')
                with self.assertRaisesRegex(RuntimeError, '日志损坏'):
                    file_cache.read_json(root/'first.json')
                self.assertEqual((root/'first.json').read_text(encoding='utf-8').strip(), '{\n  "v": 1\n}')

    def test_caught_nested_failure_cannot_commit_partial_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(publication, 'ROOT', root/'transactions'):
                core.save(root/'first.json', {'v':1})
                with self.assertRaisesRegex(RuntimeError, '嵌套发布失败'):
                    with publication.transaction():
                        try:
                            with publication.transaction():
                                core.save(root/'first.json', {'v':2})
                                raise ValueError('inner failed')
                        except ValueError:
                            pass
                self.assertEqual(core.read(root/'first.json'), {'v':1})

    def test_reader_waits_for_live_process_instead_of_recovering_it(self):
        writer_script = r'''
import sys,time
from pathlib import Path
from agent import core,publication
root=Path(sys.argv[1]); publication.ROOT=root/'transactions'
with publication.transaction():
    core.save(root/'first.json', {'v':2})
    print('ready',flush=True)
    deadline=time.monotonic()+10
    while not (root/'release').exists():
        if time.monotonic()>deadline: raise RuntimeError('test release missing')
        time.sleep(.01)
'''
        reader_script = r'''
import sys
from pathlib import Path
from agent import core,publication
root=Path(sys.argv[1]); publication.ROOT=root/'transactions'
print(core.read(root/'first.json')['v'],flush=True)
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(publication, 'ROOT', root/'transactions'):
                core.save(root/'first.json', {'v':1})
                cwd = Path(__file__).resolve().parents[1]
                writer = subprocess.Popen([sys.executable, '-B', '-c', writer_script, str(root)],
                                          cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                reader = None
                try:
                    self.assertEqual(writer.stdout.readline().strip(), b'ready')
                    reader = subprocess.Popen([sys.executable, '-B', '-c', reader_script, str(root)],
                                              cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    with self.assertRaises(subprocess.TimeoutExpired):
                        reader.communicate(timeout=.3)
                    (root/'release').touch()
                    output, error = reader.communicate(timeout=15)
                    self.assertEqual(reader.returncode, 0, error)
                    self.assertEqual(output.strip(), b'2')
                    self.assertEqual(writer.wait(timeout=15), 0)
                finally:
                    (root/'release').touch()
                    for process in (writer, reader):
                        if process is not None:
                            if process.poll() is None:
                                process.kill()
                            process.communicate(timeout=15)

    def test_managed_recycle_recovers_only_moves_owned_by_the_transaction(self):
        from stage_execution_service import recover_stage_publications

        script = """
import os, sys
from pathlib import Path
from agent import core, publication
from infra import storage_maintenance as storage
root = Path(sys.argv[1])
publication.ROOT = root / 'transactions'
point = sys.argv[2]
move = storage.move_planned
def crash_after_move(record, root, batch, **kwargs):
    move(record, root, batch, **kwargs)
    if point in ('after-ledger', 'delete-after-retry'):
        return
    os._exit(77)
def after_moves(_):
    core.save(root/'ledger.json', {'v': 2})
    os._exit(77)
storage.move_planned = crash_after_move
storage.recycle_paths(root, [root/'first.skill.md', root/'second.skill.md'], 'test',
                      after_moves=after_moves)
"""
        for change in ('none', 'replacement', 'directory', 'edit-unmoved',
                       'delete-unmoved', 'edit-recycled', 'retry', 'after-ledger',
                       'delete-after-retry'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                first = root / 'first.skill.md'
                second = root / 'second.skill.md'
                first.write_bytes(b'old')
                second.write_bytes(b'second')
                ledger = root / 'ledger.json'
                ledger.write_text('{"v":1}', encoding='utf-8')
                child = subprocess.run([sys.executable, '-c', script, str(root), change],
                                       cwd=str(Path(__file__).resolve().parents[1]),
                                       capture_output=True, timeout=30)
                self.assertEqual(child.returncode, 77, child.stderr.decode(errors='replace'))
                if change == 'replacement':
                    first.write_bytes(b'new')
                if change == 'directory':
                    first.mkdir()
                if change == 'delete-unmoved':
                    second.unlink()
                if change == 'edit-unmoved':
                    second.write_bytes(b'edited')
                if change == 'edit-recycled':
                    archived = next(root.rglob('first.skill.md'))
                    self.assertNotEqual(archived, first)
                    archived.write_bytes(b'edited')
                with patch.object(publication, 'ROOT', root / 'transactions'):
                    if change in ('retry', 'delete-after-retry'):
                        rename = Path.rename

                        def fail_first(source, target):
                            if target == first:
                                raise PermissionError(errno.EACCES, 'restore')
                            return rename(source, target)

                        with patch.object(Path, 'rename', fail_first):
                            with self.assertRaises(PermissionError):
                                publication.recover_pending()
                        self.assertFalse(first.exists())
                        self.assertTrue(any(publication.ROOT.glob('*/journal.json')))
                        if change == 'delete-after-retry':
                            second.unlink()
                    recover_stage_publications()
                    recover_stage_publications()
                if change == 'directory':
                    self.assertTrue(first.is_dir())
                elif change == 'edit-recycled':
                    self.assertFalse(first.exists())
                    self.assertEqual(archived.read_bytes(), b'edited')
                else:
                    self.assertEqual(first.read_bytes(), b'new' if change == 'replacement' else b'old')
                self.assertEqual(second.exists(), change not in ('delete-unmoved', 'delete-after-retry'))
                self.assertEqual(ledger.read_text(encoding='utf-8'), '{"v":1}')
                if change == 'edit-unmoved':
                    self.assertEqual(second.read_bytes(), b'edited')

    def test_managed_recycle_rolls_back_files_and_ledger(self):
        from infra import storage_maintenance as storage

        for issue in ('second-move', 'ledger-enospc', 'ledger-replace', 'manifest-replace'):
            with self.subTest(issue=issue), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                paths = [root / name for name in ('first.skill.md', 'second.skill.md')]
                for path in paths:
                    path.write_bytes(path.name.encode())
                ledger = root / 'ledger.json'
                ledger.write_text('{"v":1}', encoding='utf-8')
                rename = Path.rename
                replace = os.replace

                def fail_rename(path, destination):
                    if issue == 'second-move' and path == paths[1]:
                        raise PermissionError(errno.EACCES, issue)
                    return rename(path, destination)

                def fail_replace(source, destination):
                    destination = Path(destination)
                    if destination == ledger and issue.startswith('ledger-'):
                        code = errno.ENOSPC if issue.endswith('enospc') else errno.EIO
                        raise OSError(code, issue)
                    if (destination.name == storage.MANIFEST_NAME and issue == 'manifest-replace'
                            and b'"committed"' in Path(source).read_bytes()):
                        raise OSError(errno.EIO, issue)
                    return replace(source, destination)

                with (patch.object(publication, 'ROOT', root / 'transactions'),
                      patch.object(Path, 'rename', fail_rename),
                      patch.object(os, 'replace', fail_replace)):
                    with self.assertRaisesRegex(OSError, issue):
                        storage.recycle_paths(root, paths, 'test',
                                              after_moves=lambda _: core.save(ledger, {'v': 2}))
                    publication.recover_pending()
                self.assertEqual(ledger.read_text(encoding='utf-8'), '{"v":1}')
                self.assertEqual([p.read_bytes() for p in paths], [p.name.encode() for p in paths])
