import re
p = r'D:\漫剧制作助手\.agents\worktrees\foundation-integration-final\程序\logs\v2_arch.log'
lines = open(p, encoding='utf-8', errors='replace').read().splitlines()
out = []
for i, l in enumerate(lines):
    if l.startswith('FAIL:') or l.startswith('ERROR:'):
        out.append('### ' + l[:120])
        j = i + 1
        cnt = 0
        while j < len(lines) and cnt < 10:
            t = lines[j]
            if t.startswith('=====') or t.startswith('FAIL:') or t.startswith('ERROR:'):
                break
            if t.strip():
                out.append('    ' + t[:240])
                cnt += 1
            j += 1
open(r'D:\漫剧制作助手\.agents\tmp-pip-probe\arch_failures.txt', 'w', encoding='utf-8').write('\n'.join(out))
print(len(out))
