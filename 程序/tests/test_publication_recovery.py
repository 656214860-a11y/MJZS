"""Process-death coverage for durable artifact/index publication."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent import core, publication
import file_cache


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
