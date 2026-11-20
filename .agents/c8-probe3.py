import os, sys
base = r'D:\漫剧制作助手'
for p in [r'D:\漫剧制作助手\.agents\worktrees\dsh-68d604fa-4983\运行环境',
          r'D:\漫剧制作助手\.agents\worktrees\foundation-c8-updater\运行环境',
          r'D:\漫剧制作助手\运行环境',
          r'D:\漫剧制作助手\.agents\worktrees\foundation-c8-updater']:
    print('PATH', p.encode('unicode_escape').decode())
    try:
        print('  exists', os.path.exists(p), 'islink', os.path.islink(p), 'isdir', os.path.isdir(p))
        if os.path.islink(p):
            print('  target', os.readlink(p).encode('unicode_escape').decode())
        print('  entries', [e.encode('unicode_escape').decode() for e in sorted(os.listdir(p))[:12]])
    except Exception as e:
        print('  ERR', type(e).__name__, e)
d = r'D:\漫剧制作助手\.agents\worktrees\dsh-68d604fa-4983\运行环境\Python\Lib\site-packages'
print('site-packages exists', os.path.isdir(d))
print('sp entries', [e for e in sorted(os.listdir(d))[:40]] if os.path.isdir(d) else None)
