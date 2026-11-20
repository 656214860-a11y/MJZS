import shutil, sys, traceback, os
from pathlib import Path
program = Path(r'D:\漫剧制作助手\.agents\worktrees\foundation-c8-updater\程序').resolve()
names = ['剧本锻造', '编剧技能集']
base = program / 'skills' / '01 剧本准备SKILL'
for name in names:
    path = base / name
    path.mkdir(parents=True, exist_ok=True)
    print('ensured', path, 'entries', os.listdir(path))

removed = []
for p in sorted(program.glob('tmp*')):
    if not p.is_dir() or not p.name.startswith('tmp'):
        continue
    if p.resolve().parent != program:
        print('skip', p)
        continue
    try:
        shutil.rmtree(p)
        removed.append(p.name)
    except Exception as exc:
        print('FAILED', p.name, type(exc).__name__, exc)
print('removed', len(removed))
