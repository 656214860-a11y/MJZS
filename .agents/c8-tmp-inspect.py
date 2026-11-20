import os
from pathlib import Path
program = Path(r'D:\漫剧制作助手\.agents\worktrees\foundation-c8-updater\程序')
for p in sorted(program.glob('tmp*')):
    if not p.is_dir():
        continue
    sample = []
    for root, dirs, files in os.walk(p):
        rel = os.path.relpath(root, p)
        for d in dirs[:3]:
            sample.append(os.path.join(rel, d))
        for f in files[:3]:
            sample.append(os.path.join(rel, f))
        if len(sample) > 8:
            break
    print(p.name, len(sample), sample[:8])
