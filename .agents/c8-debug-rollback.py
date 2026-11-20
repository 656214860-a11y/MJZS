import sys, os, tempfile, traceback
from pathlib import Path
sys.path.insert(0, r'D:\漫剧制作助手\.agents\worktrees\foundation-c8-updater\程序')
from tests import test_update_pipeline as T

case = T.RollbackTests('test_replace_failure_restores_old_files')
case.setUp()
try:
    case.publish('0.9')
    source = case.source('0.8')
    release = source.check()
    archive = source.download(release)
    calls = {'count': 0}
    def flaky(move_source, move_target):
        calls['count'] += 1
        print('MOVE', calls['count'], move_source, '->', move_target)
        if calls['count'] == 2:
            raise OSError('injected')
        move_target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(move_source, move_target)
    try:
        T.update_installer.install_archive(archive, case.install_root, version='0.9', mover=flaky)
    except Exception as exc:
        print('raised', type(exc).__name__, exc)
    print('root files', sorted(p.relative_to(case.install_root).as_posix() for p in case.install_root.rglob('*') if p.is_file()))
finally:
    case.tmp.cleanup()
