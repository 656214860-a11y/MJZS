# -*- coding: utf-8 -*-
"""E1a v2：未用 import 候选——加跨文件消费者复核。
修正 v1 两处失效：
1) LIVE 匹配：节点键 'a/b/c.py' → 模块名 'a.b.c'（v1 只匹配了顶层文件，子目录实体全漏）；
2) 再导出复核：候选名若被任一文件 `from <mod> import <名>`／`from <mod> import *`／
   `<mod>.<名>`／`import <mod> as <别名>`+`<别名>.<名>` 消费 → 保留。
排除 facade=True 文件（B 节迁移对象，避免重复改写）。
产出 e1a_v2.json: {file: [names]}
"""
import ast, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
AUD = os.path.join(ROOT, '维护记录', '代码腐烂审计', 'deadcode_20261116')

scan1 = json.load(open(os.path.join(AUD, 'scan1.json'), encoding='utf-8'))
nodes = scan1['nodes']
LIVE_MODS = {}   # modname -> relpath
for k, v in nodes.items():
    if isinstance(v, dict) and v.get('tier') == 'LIVE' and k.endswith('.py') and not v.get('facade'):
        rel = k.replace('\\', '/')
        mod = rel[:-3].replace('/', '.')
        LIVE_MODS[mod] = rel

# ---------- 全仓 .py 语料（含 tests/scripts，消费者面） ----------
SKIP_DIRS = {'__pycache__', 'data', 'logs', 'private', '维护记录', '升级备份', '.git', 'episode', 'voice_asr_venv'}
corpus = {}
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [x for x in dirnames if x not in SKIP_DIRS and not x.startswith('.')]
    for fn in filenames:
        if fn.endswith('.py'):
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, ROOT).replace('\\', '/')
            try:
                corpus[rel] = open(p, encoding='utf-8').read()
            except Exception:
                pass
ALLTEXT = '\n'.join(corpus.values())

def modname_of(rel):
    return rel[:-3].replace('/', '.')

def resolve_from(module, level, cur_mod):
    """把 from X import 的 module+level 解析成绝对模块名。
    level=1 → 当前包；level=L → 上溯 L-1 级。__init__.py 的部件末位是 __init__，
    parts[:-1] 恰为其所代表包，公式统一。"""
    if not level:
        return module or ''
    parts = cur_mod.split('.')
    pkg_chain = parts[:-1]
    if level > 1:
        up = level - 1
        pkg_chain = pkg_chain[:len(pkg_chain) - up] if len(pkg_chain) >= up else []
    return '.'.join(pkg_chain + ([module] if module else []))

EXISTING_MODS = set(LIVE_MODS) | {modname_of(r) for r in corpus if r.endswith('.py')}

# ---------- 消费者索引 ----------
from_imports = {}     # modname -> set(names)
star_mods = set()
alias_map = []        # (file_rel, alias, modname)
for rel, text in corpus.items():
    cur = modname_of(rel)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = resolve_from(node.module or '', node.level or 0, cur)
            if node.module == '__future__':
                continue
            for a in node.names:
                if a.name == '*':
                    star_mods.add(mod)
                    continue
                from_imports.setdefault(mod, set()).add(a.name)
                # from pkg import submod 且 submod 是真实模块 → 绑定的是模块别名
                full = mod + '.' + a.name
                if full in EXISTING_MODS:
                    alias_map.append((rel, a.asname or a.name, full))
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.asname:
                    alias_map.append((rel, a.asname, a.name))
                else:
                    alias_map.append((rel, a.name.split('.')[0], a.name))

# 属性使用：modname.NAME 全文正则（按候选模块惰性做）
attr_cache = {}
def attrs_used(modname):
    if modname in attr_cache:
        return attr_cache[modname]
    pat = re.compile(r'(?<![\w.])' + re.escape(modname) + r'\.(\w+)')
    s = set(pat.findall(ALLTEXT))
    attr_cache[modname] = s
    return s

# 别名属性使用：alias.NAME（限该别名所在文件）
alias_attrs = {}
for rel, alias, modname in alias_map:
    text = corpus[rel]
    pat = re.compile(r'(?<![\w.])' + re.escape(alias) + r'\.(\w+)')
    for m in pat.findall(text):
        alias_attrs.setdefault(modname, set()).add(m)

def name_needed(modname, name):
    if name in from_imports.get(modname, ()):
        return True
    if modname in star_mods:
        return True
    if name in attrs_used(modname):
        return True
    if name in alias_attrs.get(modname, ()):
        return True
    return False

# ---------- 候选生成（仅 LIVE 非门面实体文件） ----------
WORD = lambda n: re.compile(r'(?<![\w])' + re.escape(n) + r'(?![\w])')
result = {}
for modname, rel in sorted(LIVE_MODS.items()):
    p = os.path.join(ROOT, rel.replace('/', os.sep))
    if not os.path.exists(p):
        continue
    text = corpus.get(rel)
    if text is None:
        continue
    try:
        tree = ast.parse(text)
    except SyntaxError:
        continue
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    if not imports:
        continue
    # rest = 屏蔽所有 import 段（段级，保住同行 `;` 兄弟语句）后的文本
    lines = text.splitlines(keepends=True)
    starts = []
    pos = 0
    for l in lines:
        starts.append(pos)
        pos += len(l)
    def to_char(lineno, byte_col):
        line = lines[lineno - 1]
        return starts[lineno - 1] + len(line.encode('utf-8')[:byte_col].decode('utf-8'))
    rest_chars = list(text)
    for n in imports:
        s = to_char(n.lineno, n.col_offset)
        e = to_char(n.end_lineno or n.lineno, n.end_col_offset)
        rest_chars[s:e] = ' ' * (e - s)
    rest = ''.join(rest_chars)
    dead = []
    for n in imports:
        is_from = isinstance(n, ast.ImportFrom)
        if is_from and n.module == '__future__':
            continue
        for a in n.names:
            if a.name == '*':
                continue
            local = (a.asname or a.name) if is_from else (a.asname or a.name).split('.')[0]
            if local in ('annotations',):
                continue
            if WORD(local).search(rest):
                continue
            if "'" + local + "'" in text or '"' + local + '"' in text:
                continue
            # 跨文件消费者复核：导出名 = 本地绑定名（asname 优先；
            # 平铺 import a.b.c 再导出的是根名 a）
            if is_from:
                exported = a.asname or a.name
            else:
                exported = a.asname or a.name.split('.')[0]
            if name_needed(modname, exported):
                continue
            dead.append({'line': n.lineno, 'name': local,
                         'raw': a.name + (' as ' + a.asname if a.asname else '')})
    if dead:
        result[rel] = dead

out = os.path.join(AUD, 'e1a_v2.json')
json.dump(result, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
total = sum(len(v) for v in result.values())
print('files:', len(result), 'names:', total)
for rel, ds in list(result.items())[:10]:
    print(' ', rel, len(ds))
print('->', out)
