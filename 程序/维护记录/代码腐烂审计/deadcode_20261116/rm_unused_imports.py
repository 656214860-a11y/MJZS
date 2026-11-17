# -*- coding: utf-8 -*-
"""E1a 清理 v2：删除 LIVE 生产文件中的未用 import（AST 段级手术）。
v1 行级手术有 `import x; foo()` 同行多语句误删 bug，已废弃。
本版：
- 判定：别名本地名在「屏蔽所有 import 段（col_offset..end_col_offset）后的文本」词边界零命中；
- 改写：整节点全删 → 段替换为 `pass`（保块结构、保同行 `;` 兄弟语句与行尾注释）；
  部分删 → 段替换为重建的 import 语句（行尾注释在段外，自动保留）；
- 多行 from-import 逐名删：dead 名独占一行→删该行段；否则整节点重建为单行；
- 每文件改写后 ast.parse+compile 校验，失败整文件跳过。
用法: python rm_unused_imports.py [--apply]
输入: e1a_v2.json {file: [{line,name,raw}]}
"""
import ast, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SCAN = os.path.join(ROOT, '维护记录', '代码腐烂审计', 'deadcode_20261116', 'e1a_v2.json')
APPLY = '--apply' in sys.argv

data = json.load(open(SCAN, encoding='utf-8'))
by_file = {rel: {x['name'] for x in items} for rel, items in data.items()}
WORD = lambda n: re.compile(r'(?<![\w])' + re.escape(n) + r'(?![\w])')


def seg_span(lines, starts, node):
    """返回 (start_char, end_char) 绝对字符偏移。col_offset 为 UTF-8 字节偏移。"""
    l1, l2 = node.lineno, node.end_lineno or node.lineno
    c1, c2 = node.col_offset, node.end_col_offset
    def to_char(lineno, byte_col):
        line = lines[lineno - 1]
        return starts[lineno - 1] + len(line.encode('utf-8')[:byte_col].decode('utf-8'))
    return to_char(l1, c1), to_char(l2, c2)


def alias_local(a, is_from):
    return (a.asname or a.name) if is_from else (a.asname or a.name).split('.')[0]


def alias_text(a):
    return a.name + (' as ' + a.asname if a.asname else '')


def process(path, wanted):
    text = open(path, encoding='utf-8').read()
    lines = text.splitlines(keepends=True)
    starts = []
    _pos = 0
    for _l in lines:
        starts.append(_pos)
        _pos += len(_l)
    line_end = [s + len(l) for s, l in zip(starts, lines)]  # 含换行的行尾偏移
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None, [], ['parse_fail']
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    if not imports:
        return None, [], []
    parents = {}
    for node in ast.walk(tree):
        for c in ast.iter_child_nodes(node):
            parents[c] = node

    def suite_of(par, node):
        for attr in ('body', 'orelse', 'finalbody'):
            lst = getattr(par, attr, None)
            if isinstance(lst, list) and node in lst:
                return lst
        return getattr(par, 'body', [])

    # rest = 屏蔽所有 import 段后的文本
    edits_mask = []
    for n in imports:
        s, e = seg_span(lines, starts, n)
        edits_mask.append((s, e))
    rest_chars = list(text)
    for s, e in sorted(edits_mask, reverse=True):
        rest_chars[s:e] = ' ' * (e - s)
    rest = ''.join(rest_chars)

    edits = []   # (start, end, replacement)
    removed = []
    for n in imports:
        is_from = isinstance(n, ast.ImportFrom)
        if is_from and n.module == '__future__':
            continue
        dead, alive = [], []
        for a in n.names:
            local = alias_local(a, is_from)
            if local == '*' or local not in wanted or WORD(local).search(rest):
                alive.append(a)
            else:
                dead.append(a)
        if not dead:
            continue
        s, e = seg_span(lines, starts, n)
        if len(dead) == len(n.names):
            # 独占整行且父块删后仍非空 → 删整行（含换行）；否则段替换 pass
            l1, l2 = n.lineno, n.end_lineno or n.lineno
            line_start = starts[l1 - 1]
            end_pos = line_end[l2 - 1]
            prefix_ok = text[line_start:s].strip() == ''
            suffix = text[e:end_pos]
            suffix_ok = suffix.strip() == '' or suffix.lstrip().startswith('#')
            par = parents.get(n)
            suite = suite_of(par, n) if par is not None else []
            block_ok = par is None or isinstance(par, ast.Module) or len(suite) > 1
            if prefix_ok and suffix_ok and block_ok:
                edits.append((line_start, end_pos, ''))
            else:
                edits.append((s, e, 'pass'))
            removed += [alias_local(a, is_from) for a in dead]
            continue
        # 部分删除：整段重建为单行（多行 from-import 同样合法折叠）
        kept = ', '.join(alias_text(a) for a in alive)
        if is_from:
            mod = ('.' * (n.level or 0)) + (n.module or '')
            new = f'from {mod} import {kept}'
        else:
            new = f'import {kept}'
        edits.append((s, e, new))
        removed += [alias_local(a, is_from) for a in dead]
    if not removed:
        return None, [], []
    new_text = text
    for s, e, rep in sorted(edits, key=lambda x: -x[0]):
        new_text = new_text[:s] + rep + new_text[e:]
    try:
        ast.parse(new_text)
        compile(new_text, path, 'exec')
    except SyntaxError:
        return None, [], ['rewrite_fail']
    return new_text, removed, []


changed, skipped, total = [], [], 0
for rel, wanted in sorted(by_file.items()):
    p = os.path.join(ROOT, rel.replace('/', os.sep))
    if not os.path.exists(p):
        skipped.append((rel, 'missing')); continue
    new_text, removed, errs = process(p, wanted)
    if errs:
        skipped.append((rel, ','.join(errs))); continue
    if new_text is None:
        continue
    total += len(removed)
    changed.append((rel, len(removed)))
    if APPLY:
        open(p, 'w', encoding='utf-8', newline='').write(new_text)

print(('APPLIED' if APPLY else 'DRY-RUN'), 'files:', len(changed), 'names:', total)
for rel, c in changed:
    print('  ', rel, c)
if skipped:
    print('SKIPPED:', skipped[:20])
