# -*- coding: utf-8 -*-
"""B节门面迁移 codemod：把测试/脚本里的扁平门面引用改写为包路径。

用法：
  python migrate_facades.py --dry-run   # 只报告
  python migrate_facades.py --apply     # 写盘

改写规则（AST 定位 + 文本拼接）：
  import NAME [as X]            -> from PKG import NAME [as X]
  import A, NAME [as X]         -> import A + from PKG import NAME [as X]
  from NAME import a, b         -> from PKG.NAME import a, b
  'NAME' / 'NAME.attr' 字符串   -> 'PKG.NAME' / 'PKG.NAME.attr'
    仅限模块引用语境：patch( / patch.object( / patch.dict( / patch.multiple(
    的字符串实参、import_module( / __import__( 的实参、sys.modules[...] 下标
    与 .get(...) 实参、'NAME' in sys.modules 比较。
  其余等于门面名的裸字符串只记录不改写（review 列表）。
"""
import argparse
import ast
import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
PROG = os.path.abspath(os.path.join(ROOT, '..', '..', '..'))  # 程序/
FMAP_PATH = os.path.join(ROOT, 'facade_map.json')
OUT_PATH = os.path.join(ROOT, 'migrate_report.json')

FACADES = {}  # name -> (entity_dotted, package_dotted)


def load_facades():
    raw = json.load(open(FMAP_PATH, encoding='utf-8'))
    for name, ent in raw['entities'].items():
        if ent == '?' or '.' not in ent:
            continue
        FACADES[name] = (ent, ent.rsplit('.', 1)[0])


def iter_py():
    skip_dirs = {'__pycache__', '.git', 'voice_asr_venv', 'data', 'logs',
                 'private', 'episode', '维护记录', '升级备份'}
    for dirpath, dirnames, filenames in os.walk(PROG):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            if not fn.endswith('.py'):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, PROG).replace('\\', '/')
            if '/' not in rel and os.path.basename(rel)[:-3] in FACADES:
                continue  # 门面文件自身
            yield p, rel


def seg_lines(lines, node):
    return lines[node.lineno - 1:node.end_lineno]


def line_indent(line):
    return line[:len(line) - len(line.lstrip())]


def collect_import_edits(tree, lines, edits, review):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            hits = [a for a in node.names if a.name in FACADES]
            if not hits:
                continue
            seg = seg_lines(lines, node)
            indent = line_indent(seg[0])
            kept = [a for a in node.names if a.name not in FACADES]
            new_lines = []
            if kept:
                parts = [a.name + (' as ' + a.asname if a.asname else '')
                         for a in kept]
                new_lines.append(indent + 'import ' + ', '.join(parts))
            for a in hits:
                ent, pkg = FACADES[a.name]
                mod_name = ent.rsplit('.', 1)[1]
                new_lines.append(
                    indent + f'from {pkg} import {mod_name}'
                    + (' as ' + a.asname if a.asname else ''))
            edits.append(('block', node.lineno, node.end_lineno,
                          '\n'.join(new_lines)))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module in FACADES:
                ent, _ = FACADES[node.module]
                seg = '\n'.join(seg_lines(lines, node))
                m = re.search(r'from\s+' + re.escape(node.module) + r'\b', seg)
                if not m:
                    review.append(('importfrom-nomatch', node.lineno,
                                   node.module))
                    continue
                new_seg = seg[:m.start()] + 'from ' + ent + seg[m.end():]
                edits.append(('block', node.lineno, node.end_lineno, new_seg))


def _attr_chain(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return '.'.join(reversed(parts))
    return None


def rewrite_val(v):
    for name in sorted(FACADES, key=len, reverse=True):
        if v == name:
            return name, FACADES[name][0]
        if v.startswith(name + '.'):
            return name, FACADES[name][0] + v[len(name):]
    return None, None


def collect_string_edits(tree, edits, review):
    replacements = []  # (constant_node, oldval, newval)

    class V(ast.NodeVisitor):
        def _maybe(self, node, allow_bare=True):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                old, new = rewrite_val(node.value)
                if new and (allow_bare or node.value != old):
                    replacements.append((node, node.value, new))

        def visit_Call(self, node):
            chain = _attr_chain(node.func) or ''
            last = chain.split('.')[-1] if chain else ''
            is_patch_family = last in ('patch', 'object', 'dict', 'multiple')
            is_loader = last in ('import_module', '__import__', 'reload')
            if last == 'dict' and len(node.args) >= 2:
                d = node.args[1]
                if isinstance(d, ast.Dict):
                    for k in d.keys:
                        if isinstance(k, ast.Constant) and isinstance(k.value, str):
                            old, new = rewrite_val(k.value)
                            if new and k.value in FACADES:
                                replacements.append((k, k.value, new))
            for arg in node.args:
                if isinstance(arg, ast.Constant):
                    if is_patch_family or is_loader:
                        self._maybe(arg)
                elif isinstance(arg, (ast.List, ast.Tuple)) and is_patch_family:
                    for el in arg.elts:
                        if isinstance(el, ast.Constant):
                            self._maybe(el)
            self.generic_visit(node)

        def visit_Subscript(self, node):
            if _attr_chain(node.value) == 'sys.modules':
                self._maybe(node.slice)
            self.generic_visit(node)

        def visit_Compare(self, node):
            has_modules = (_attr_chain(node.left) == 'sys.modules' or
                           any(_attr_chain(c) == 'sys.modules'
                               for c in node.comparators))
            if has_modules:
                self._maybe(node.left)
                for c in node.comparators:
                    self._maybe(c)
            self.generic_visit(node)

        def visit_Constant(self, node):
            if isinstance(node.value, str) and node.value in FACADES:
                review.append(('bare-str', node.lineno, node.value))

    V().visit(tree)
    for node, old, new in replacements:
        edits.append(('str', node.lineno, node.col_offset,
                      node.end_col_offset, old, new))


def rewrite_source(src, edits):
    lines = src.split('\n')
    block_lines = set()
    for e in edits:
        if e[0] == 'block':
            block_lines.update(range(e[1], e[2] + 1))

    # 1) 行内字符串替换：在字面量源文本中定位旧值并替换（保留引号/前缀/三引号）
    inline = {}
    for e in edits:
        if e[0] == 'str':
            _, ln, col, ecol, old, new = e
            if ln in block_lines:
                continue
            inline.setdefault(ln, []).append((col, ecol, old, new))
    for ln, items in inline.items():
        line = lines[ln - 1]
        for col, ecol, old, new in sorted(items, key=lambda x: -x[0]):
            seg = line[col:ecol]
            idx = seg.find(old)
            if idx < 0:
                continue  # 找不到原文（转义差异）→ 跳过，review 已覆盖
            line = line[:col + idx] + new + line[col + idx + len(old):]
        lines[ln - 1] = line

    # 2) 块替换（按起始行倒序）
    for e in sorted((e for e in edits if e[0] == 'block'),
                    key=lambda x: -x[1]):
        _, s, en, txt = e
        lines[s - 1:en] = txt.split('\n')
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    load_facades()

    report = {'files': {}, 'review': [], 'errors': []}
    nfiles = 0
    for path, rel in iter_py():
        try:
            src = open(path, encoding='utf-8').read()
            tree = ast.parse(src)
        except Exception as e:
            report['errors'].append((rel, str(e)[:200]))
            continue
        edits, review = [], []
        collect_import_edits(tree, src.split('\n'), edits, review)
        collect_string_edits(tree, edits, review)
        if not edits and not review:
            continue
        nfiles += 1
        report['files'][rel] = {
            'blocks': sum(1 for e in edits if e[0] == 'block'),
            'strs': sum(1 for e in edits if e[0] == 'str'),
        }
        report['review'].extend([(rel,) + tuple(r) for r in review])
        if args.apply:
            new_src = rewrite_source(src, edits)
            try:
                ast.parse(new_src)
            except SyntaxError as e:
                report['errors'].append((rel, f'post-rewrite syntax: {e}'))
                continue
            open(path, 'w', encoding='utf-8', newline='').write(new_src)
    report['nfiles'] = nfiles
    json.dump(report, open(OUT_PATH, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('files touched:', nfiles,
          '| review items:', len(report['review']),
          '| errors:', len(report['errors']))
    for e in report['errors'][:10]:
        print(' ERR', e)


if __name__ == '__main__':
    main()
