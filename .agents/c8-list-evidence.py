import os
base = r'D:\漫剧制作助手\.git\foundation-update-admission-r3844'
for root, dirs, files in os.walk(base):
    rel = os.path.relpath(root, base)
    for f in files:
        p = os.path.join(root, f)
        print(os.path.getsize(p), os.path.join(rel, f).encode('unicode_escape').decode())
