import subprocess
out = subprocess.run(['git','status','--porcelain','-z'],capture_output=True).stdout.decode('utf-8','replace')
raw = [e for e in out.split('\0') if e]
paths=[]
i=0
while i < len(raw):
    e = raw[i]
    code, p = e[:2], e[3:]
    i += 1
    if 'R' in code or 'C' in code:
        i += 1  # skip old-path record
    if p.startswith('程序/skills/') or p=='程序/project_status.md':
        continue
    paths.append(p)
print(len(paths),'files to stage')
for j in range(0,len(paths),60):
    chunk=paths[j:j+60]
    r=subprocess.run(['git','add','--']+chunk,capture_output=True,text=True)
    if r.returncode:
        print('ADD FAIL',r.stderr[:500]); break
else:
    print('staged ok')
staged=subprocess.run(['git','diff','--cached','--name-only'],capture_output=True,text=True).stdout.splitlines()
bad=[s for s in staged if 'project_status' in s or '/skills/' in s.replace(chr(92),'/')]
print('staged total',len(staged),'bad',bad[:5])
