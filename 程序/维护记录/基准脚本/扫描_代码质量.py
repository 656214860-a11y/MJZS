# -*- coding: utf-8 -*-
"""代码扫描：死代码／未用 import／重复块／大文件（第 58 期附件「代码扫描」一节）。"""
import ast, io, json, os, re, sys
from pathlib import Path
PROG = Path(r'D:\漫剧制作助手\程序')
os.chdir(str(PROG))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

files = sorted(p for p in PROG.glob('*.py'))
prod = [p for p in files if not p.name.startswith('test_')]
tests = [p for p in files if p.name.startswith('test_')]
texts = {p: io.open(p, encoding='utf-8', errors='replace').read() for p in files}
all_src = '\n'.join(texts[p] for p in files)
prod_src = '\n'.join(texts[p] for p in prod)
test_src = '\n'.join(texts[p] for p in tests)

report = {}

# 1) 文件大小
sizes = sorted(((len(t.split('\n')), p.name) for p, t in texts.items()), reverse=True)
report['files'] = {'count': len(files), 'lines': sum(n for n, _ in sizes),
                   'over_500': [[n, name] for n, name in sizes if n > 500],
                   'prod_over_500': [[n, name] for n, name in sizes if n > 500 and not name.startswith('test_')],
                   'top': [[n, name] for n, name in sizes[:12]]}

# 2) 未用 import
unused = []
for p in files:
    try:
        tree = ast.parse(texts[p])
    except SyntaxError as exc:
        unused.append([p.name, '<parse error>', str(exc)])
        continue
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [(a.asname or a.name.split('.')[0]) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [(a.asname or a.name) for a in node.names if a.name != '*']
        if not names:
            continue
        body = texts[p]
        for name in names:
            hits = len(re.findall(r'\b%s\b' % re.escape(name), body))
            declared = len(re.findall(r'\b%s\b' % re.escape(name), ast.get_source_segment(body, node) or ''))
            if hits - declared <= 0:
                unused.append([p.name, name, 'line %d' % node.lineno])
report['unused_imports'] = unused

# 3) 顶层 def/class 的引用计数
defs = []
for p in prod:
    try:
        tree = ast.parse(texts[p])
    except SyntaxError:
        continue
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs.append((p.name, node.name, node.lineno))
dead = []
for name, symbol, line in defs:
    pat = re.compile(r'\b%s\b' % re.escape(symbol))
    prod_hits = len(pat.findall(prod_src))
    all_hits = len(pat.findall(all_src))
    if prod_hits <= 1:
        dead.append([name, symbol, 'line %d' % line, prod_hits, all_hits])
report['top_level_symbols'] = len(defs)
report['never_used_in_program'] = dead

# 4) 重复代码块（同文件内 6 行窗口，去掉空白与纯注释行）
def normalize(lines):
    out = []
    for line in lines:
        text = line.strip()
        if not text or text.startswith('#'):
            continue
        out.append(re.sub(r'\s+', ' ', text))
    return out

dupes = []
for p in prod:
    norm = normalize(texts[p].split('\n'))
    windows = {}
    for i in range(len(norm) - 5):
        key = '\n'.join(norm[i:i + 6])
        windows.setdefault(key, []).append(i)
    for key, spots in windows.items():
        if len(spots) > 1:
            dupes.append([p.name, len(spots), key.split('\n')[0][:90]])
dupes.sort(key=lambda row: -row[1])
report['duplicate_blocks'] = dupes[:25]
report['duplicate_block_count'] = len(dupes)

# 5) 注释掉的代码
commented = []
pat = re.compile(r'^\s*#\s*(import |from |def |class |self\.|return |if |for |while |try:|except )')
for p in files:
    lines = texts[p].split('\n')
    run = 0
    for i, line in enumerate(lines):
        if pat.match(line):
            run += 1
            if run == 3:
                commented.append([p.name, 'line %d' % (i - 1)])
        else:
            run = 0
report['commented_code_blocks'] = commented

json.dump(report, io.open(str(Path(__file__).resolve().parent / '扫描结果_代码质量.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('files', report['files']['count'], 'lines', report['files']['lines'])
print('over500', report['files']['over_500'])
print('prod over500', report['files']['prod_over_500'])
print('unused imports', len(unused))
for row in unused[:30]:
    print('   ', row)
print('top level symbols', len(defs), 'never used in program', len(dead))
for row in dead[:30]:
    print('   ', row)
print('duplicate block count', len(dupes))
for row in dupes[:12]:
    print('   ', row)
print('commented code blocks', len(commented))
for row in commented[:20]:
    print('   ', row)
