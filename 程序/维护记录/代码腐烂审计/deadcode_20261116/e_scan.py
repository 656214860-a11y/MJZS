# -*- coding: utf-8 -*-
"""E节补扫：符号级死代码 + 死测试 + 脚本甄别（只读，不改源码）。
E1a 活文件未用 import；E1b 顶层 def/class 定义点外零词边界命中；
E2 skip台账孤儿；E4 scripts 引用计数。产出 e_scan.json。
"""
import ast, json, re, glob, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # 程序/
OUT = os.path.join(ROOT, '维护记录', '代码腐烂审计', 'deadcode_20261116', 'e_scan.json')

LIVE = set()
d = json.load(open(os.path.join(ROOT, '维护记录', '代码腐烂审计', 'deadcode_20261116', 'scan1.json'), encoding='utf-8'))
for k, v in d['nodes'].items():
    if isinstance(v, dict) and v.get('tier') == 'LIVE':
        LIVE.add(k[:-3] if k.endswith('.py') else k)

# ---------- 收集全仓文本（词边界复核用），排除自身/缓存/数据 ----------
SKIP_DIRS = {'__pycache__', 'data', 'logs', 'private', '维护记录', '升级备份', '.git', 'episode'}
corpus = {}  # relpath -> text
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [x for x in dirnames if x not in SKIP_DIRS and not x.startswith('.')]
    for fn in filenames:
        if not fn.endswith('.py'):
            continue
        p = os.path.join(dirpath, fn)
        rel = os.path.relpath(p, ROOT).replace('\\', '/')
        try:
            corpus[rel] = open(p, encoding='utf-8').read()
        except Exception:
            pass
ALLTEXT = '\n'.join(corpus.values())

def word_hits(name):
    return len(re.findall(r'(?<![\w.])' + re.escape(name) + r'(?![\w(])', ALLTEXT))

# ---------- E1a 未用 import ----------
unused_imports = []
for rel, text in corpus.items():
    mod = rel[:-3].replace('/', '.')
    if mod not in LIVE and not rel.endswith('.pyw'):
        continue  # 只查生产 LIVE 文件（.pyw 入口也查）
    try:
        tree = ast.parse(text)
    except SyntaxError:
        continue
    imported = {}   # local name -> lineno
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                local = (a.asname or a.name).split('.')[0]
                imported.setdefault(local, node.lineno)
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name == '*':
                    continue
                imported.setdefault(a.asname or a.name, node.lineno)
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            pass
    # 属性根名也算使用
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            n = node
            while isinstance(n, ast.Attribute):
                n = n.value
            if isinstance(n, ast.Name):
                used.add(n.id)
    # __all__ / 字符串引用兜底：名字作为字符串出现也算疑似再导出
    for name, ln in imported.items():
        if name in used:
            continue
        if name in ('annotations',):
            continue
        if re.search(r'["\']' + re.escape(name) + r'["\']', text):
            continue  # 可能再导出/patch面
        unused_imports.append({'file': rel, 'line': ln, 'name': name})

# ---------- E1b 顶层 def/class 定义点外零命中 ----------
dead_syms = []
for rel, text in corpus.items():
    mod = rel[:-3].replace('/', '.')
    if mod not in LIVE:
        continue
    try:
        tree = ast.parse(text)
    except SyntaxError:
        continue
    # 文件自身除定义行外的命中数：粗算=全仓命中数-本文件内命中数
    own = len(re.findall(r'(?<![\w.])(?:def|class)\s+', text))  # 占位不用
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
            if name.startswith('_') and not name.startswith('__'):
                continue  # 私有名常态
            hits = word_hits(name)
            # 本文件命中至少含定义处1次+可能内部递归/引用
            own_hits = len(re.findall(r'(?<![\w.])' + re.escape(name) + r'(?![\w(])', text))
            if hits - own_hits <= 0:
                dead_syms.append({'file': rel, 'line': node.lineno, 'kind': type(node).__name__, 'name': name,
                                  'repo_hits': hits, 'own_hits': own_hits})

# ---------- E2 skip 台账孤儿：台账条目对应的测试文件/skip点仍在？ ----------
ledger_path = os.path.join(ROOT, '维护记录', 'skip台账.json')
skip_orphans = []
if os.path.exists(ledger_path):
    try:
        led = json.load(open(ledger_path, encoding='utf-8'))
        items = led if isinstance(led, list) else led.get('items', led.get('entries', []))
        for it in items:
            tf = it.get('test_file') or it.get('file') or ''
            if tf and tf.replace('/', '\\') not in [k.replace('/', '\\') for k in corpus]:
                skip_orphans.append({'entry': str(it)[:120], 'missing_file': tf})
    except Exception as e:
        skip_orphans.append({'error': str(e)})

# ---------- E4 scripts 引用计数 ----------
scripts = {}
for p in glob.glob(os.path.join(ROOT, 'scripts', '*.py')):
    name = os.path.basename(p)[:-3]
    hits = word_hits(name)
    scripts[name] = {'lines': text.count('\n') if False else sum(1 for _ in open(p, encoding='utf-8', errors='ignore')), 'repo_word_hits': hits}

result = {
    'live_files': len(LIVE), 'corpus_files': len(corpus),
    'E1a_unused_imports': unused_imports,
    'E1a_count': len(unused_imports),
    'E1b_dead_syms': dead_syms,
    'E1b_count': len(dead_syms),
    'E2_skip_orphans': skip_orphans,
    'E4_scripts': scripts,
}
json.dump(result, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('E1a unused imports:', len(unused_imports))
print('E1b dead syms:', len(dead_syms))
print('E2 skip orphans:', len(skip_orphans))
print('E4 scripts:', len(scripts))
print('->', OUT)
