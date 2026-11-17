# -*- coding: utf-8 -*-
"""B节门面删除批处理：删除指定包的扁平门面并同步三份基线/台账。

用法：
  python retire_facades.py --package contract --dry-run
  python retire_facades.py --package contract --apply

每批动作：
  1. 删除 顶层 <name>.py 门面（facade_map.json 中 entities 属于该包的项）
  2. 覆盖率基线.json：删对应行，modules_total 同步（covered>0 的行会报警——门面应全为0）
  3. 类型检查基线.json：若有条目则删除，total 重算
  4. 架构统一基数.json 第一项：若名字在 adopters/exempt_items/scope_audit_pending
     且属于 L2 登记（经 tests.architecture._layers.LAYERS 判定），移入
     historical_name_audit_pending（实体仍在包内，登记名保留追溯）
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PROG = os.path.abspath(os.path.join(ROOT, '..', '..', '..'))
FMAP = os.path.join(ROOT, 'facade_map.json')
COV = os.path.join(PROG, '维护记录', '覆盖率基线.json')
TYP = os.path.join(PROG, '维护记录', '类型检查基线.json')
LEDGER = os.path.join(PROG, '维护记录', '架构统一基数.json')

sys.path.insert(0, PROG)
from tests.architecture._layers import LAYERS  # noqa: E402


def facades_of_package(pkg):
    fm = json.load(open(FMAP, encoding='utf-8'))
    return {n: e for n, e in fm['entities'].items()
            if e != '?' and e.split('.')[0] == pkg}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--package', required=True,
                    choices=['contract', 'infra', 'domain', 'ui', 'orchestrator'])
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    fac = facades_of_package(args.package)
    print(f'package={args.package} facades={len(fac)}')
    l2 = sorted(n for n in fac if LAYERS.get(n) == 2)
    print(f'  L2-registered (需历史名迁移): {len(l2)} {l2}')

    # 1) 覆盖率基线
    cov = json.load(open(COV, encoding='utf-8'))
    cov_names = {f['module'] for f in cov['modules']}
    missing_cov = [n for n in fac if n + '.py' not in cov_names]
    hit_cov = [n for n in fac if n + '.py' in cov_names]
    covered_hits = [m['module'] for m in cov['modules']
                    if m['module'] in {n + '.py' for n in fac}
                    and (m.get('covered') or 0) > 0]
    print(f'  coverage rows: {len(hit_cov)} hit, {len(missing_cov)} absent,'
          f' covered>0: {covered_hits}')

    # 2) 类型检查基线
    typ = json.load(open(TYP, encoding='utf-8'))
    typ_hits = [n + '.py' for n in fac if n + '.py' in typ['modules']]
    print(f'  typecheck rows: {len(typ_hits)} {typ_hits}')

    # 3) 架构统一基数 第一项
    led = json.load(open(LEDGER, encoding='utf-8'))
    s1 = led['第一项']
    active = set(s1['adopters']) | set(s1['exempt_items']) | set(s1['scope_audit_pending'])
    move = [n for n in l2 if n in active]
    already = [n for n in l2 if n in set(s1['historical_name_audit_pending'])
               | set(s1['historical_name_audited'])]
    print(f'  ledger 第一项: move-to-historical={len(move)} {move}')
    print(f'  ledger already-historical: {already}')

    if args.dry_run or not args.apply:
        return

    # apply
    for n in fac:
        p = os.path.join(PROG, n + '.py')
        if os.path.isfile(p):
            os.remove(p)
            print('  deleted', n + '.py')
        else:
            print('  MISSING', n + '.py')

    drop = {n + '.py' for n in fac}
    cov['modules'] = [m for m in cov['modules'] if m['module'] not in drop]
    cov['modules_total'] = len(cov['modules'])
    cov['modules_covered'] = sum(1 for m in cov['modules']
                                 if (m.get('covered') or 0) > 0)
    json.dump(cov, open(COV, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(COV, 'a', encoding='utf-8').write('\n')

    for k in list(typ['modules']):
        if k in drop:
            del typ['modules'][k]
    typ['total'] = sum(typ['modules'].values())
    json.dump(typ, open(TYP, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(TYP, 'a', encoding='utf-8').write('\n')

    hist = s1['historical_name_audit_pending']
    for n in move:
        for grp in ('adopters', 'exempt_items', 'scope_audit_pending'):
            if n in s1[grp]:
                s1[grp].remove(n)
        if n not in hist and n not in s1['historical_name_audited']:
            hist.append(n)
    if 'exempt_items' in s1:
        s1['exempt_count'] = len(s1['exempt_items'])
    json.dump(led, open(LEDGER, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    open(LEDGER, 'a', encoding='utf-8').write('\n')
    print('applied')


if __name__ == '__main__':
    main()
