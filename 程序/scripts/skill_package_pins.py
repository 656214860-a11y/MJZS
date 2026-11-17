"""外部技能包完整性：登记每个第三方包的来源、固定提交与内容树哈希，漂移即报警（对应 E1）。

这些包由模型按文本执行，等于供应链：内容被改（本地误改、上游被替换）会直接改变模型行为。登记表
``维护记录/外部技能包哈希.json`` 记录每个包的来源地址、固定提交和提交对应的内容树哈希（git tree，
与换行符、检出方式无关）。

用法（程序目录下）::

    python -B scripts/skill_package_pins.py --check     # 校验；漂移即非 0
    python -B scripts/skill_package_pins.py --update    # 把当前固定提交与树哈希写入登记表（升级外部包时用）

校验口径：①登记的提交必须等于主仓库对该路径固定的提交（gitlink）；②包已检出时，HEAD、树哈希、
工作树是否被改过都必须与登记一致；③包没检出（新克隆还没初始化）只做①，不算通过也不算失败。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))
import infra.file_cache as file_cache  # noqa: E402

REGISTRY = PROGRAM / '维护记录' / '外部技能包哈希.json'


def _git(*args, cwd=PROGRAM):
    done = subprocess.run(['git', '-c', 'core.quotepath=false', *args], cwd=cwd, capture_output=True,
                          text=True, encoding='utf-8', errors='replace')
    return done.stdout.strip()


def pinned_packages(root=PROGRAM):
    """主仓库里固定为 gitlink（160000）的技能包：``{相对 程序 的路径: 固定提交}``。"""
    found = {}
    for line in _git('ls-files', '-s', '--', 'skills', cwd=root).splitlines():
        mode, sha, _stage, path = line.replace('\t', ' ').split(' ', 3)
        if mode == '160000':
            found[path.strip('"')] = sha
    return found


def checkout_state(folder):
    """已检出的包：``{head, tree, clean, source}``；没检出返回 None。"""
    folder = Path(folder)
    if not (folder / '.git').exists():
        return None
    return {'head': _git('rev-parse', 'HEAD', cwd=folder), 'tree': _git('rev-parse', 'HEAD^{tree}', cwd=folder),
            'clean': not _git('status', '--porcelain', cwd=folder), 'source': _git('remote', 'get-url', 'origin', cwd=folder)}


def verify(registry, pinned, states):
    """纯函数：返回问题列表（空即通过）。``states`` 是 ``{路径: checkout_state 结果}``。"""
    problems = []
    for path, commit in sorted(pinned.items()):
        entry = registry.get(path)
        if not entry:
            problems.append('%s：主仓库固定了这个包，但登记表里没有' % path)
            continue
        if entry.get('commit') != commit:
            problems.append('%s：登记提交 %s 与主仓库固定的 %s 不一致' % (path, str(entry.get('commit'))[:12], commit[:12]))
        state = states.get(path)
        if state is None:
            continue
        if state['head'] != entry.get('commit'):
            problems.append('%s：检出的 HEAD %s 不是登记提交' % (path, state['head'][:12]))
        elif state['tree'] != entry.get('tree'):
            problems.append('%s：内容树哈希与登记不一致' % path)
        if not state['clean']:
            problems.append('%s：工作树有未提交的改动，外部包内容被改过' % path)
    for path in sorted(set(registry) - set(pinned)):
        problems.append('%s：登记表里有，但主仓库已不再固定它' % path)
    return problems


def load_registry(path=REGISTRY):
    return file_cache.read_json(Path(path)).get('packages', {}) if Path(path).is_file() else {}


def build_registry(root=PROGRAM):
    packages = {}
    for path, commit in pinned_packages(root).items():
        state = checkout_state(Path(root) / path)
        if state is None or state['head'] != commit:
            raise RuntimeError('%s 没有检出到固定提交 %s，无法登记' % (path, commit[:12]))
        packages[path] = {'source': state['source'], 'commit': commit, 'tree': state['tree']}
    return packages


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--update', action='store_true')
    args = parser.parse_args(argv)
    if args.update:
        import json
        text = json.dumps({'说明': '外部技能包的来源、固定提交与内容树哈希；升级外部包时运行 scripts/skill_package_pins.py --update',
                           'packages': build_registry()}, ensure_ascii=False, indent=1) + '\n'
        REGISTRY.write_text(text, encoding='utf-8', newline='\n')
        sys.stdout.write('已登记 %d 个外部技能包\n' % len(build_registry()))
        return 0
    pinned = pinned_packages()
    problems = verify(load_registry(), pinned, {path: checkout_state(PROGRAM / path) for path in pinned})
    for line in problems:
        sys.stdout.write(line + '\n')
    sys.stdout.write('外部技能包 %d 个，问题 %d 个\n' % (len(pinned), len(problems)))
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
