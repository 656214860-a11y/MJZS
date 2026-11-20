import shutil
from pathlib import Path
program = Path(r'D:\漫剧制作助手\.agents\worktrees\foundation-c8-updater\程序').resolve()
removed = 0
for p in sorted(program.glob('tmp*')):
    if not p.is_dir() or not p.name.startswith('tmp'):
        continue
    if p.resolve().parent != program:
        raise SystemExit('refusing: %s' % p)
    shutil.rmtree(p)
    removed += 1
print('removed', removed)
