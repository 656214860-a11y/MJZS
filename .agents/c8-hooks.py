import os
for base in (r'D:\漫剧制作助手\.git\hooks',):
    try:
        print(base, sorted(os.listdir(base)))
    except Exception as exc:
        print('ERR', exc)
