"""Refresh the L0/L1 branch coverage baseline with the new C8 module set."""
import importlib.util
import json
import sys
from pathlib import Path

PROGRAM = Path(r'D:\漫剧制作助手\.agents\worktrees\foundation-c8-updater\程序')
sys.path.insert(0, str(PROGRAM))
spec = importlib.util.spec_from_file_location(
    'branch_coverage_report', PROGRAM / 'scripts' / 'branch_coverage_report.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

baseline_path = PROGRAM / '维护记录' / '分支覆盖率基线.json'
floors_path = PROGRAM / '维护记录' / '分支覆盖率下限.json'
baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
targets = list(baseline['targets'])
if 'tests.test_update_pipeline' not in targets:
    targets.append('tests.test_update_pipeline')
report = tool.measure(targets)
print('tests_ok', report['tests_ok'], 'modules', report['modules_total'],
      'points', report['points_covered'], '/', report['points_total'])
new = {row['module']: row for row in report['modules']}
old_floors = json.loads(floors_path.read_text(encoding='utf-8'))['floors']
regressions = []
for name, floor in old_floors.items():
    row = new.get(name)
    if row is None:
        regressions.append((name, 'missing'))
    elif row['percent'] < floor:
        regressions.append((name, row['percent'], floor))
print('floor regressions:', regressions[:20], 'count', len(regressions))
if not report['tests_ok'] or regressions:
    print('NOT WRITING baseline')
    raise SystemExit(2)
baseline_path.write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
floors = dict(old_floors)
for name, row in new.items():
    floors.setdefault(name, row['percent'])
floors_path.write_text(json.dumps(
    {'note': json.loads(floors_path.read_text(encoding='utf-8'))['note'],
     'floors': dict(sorted(floors.items()))},
    ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('baseline updated; new modules:', [n for n in new if n not in old_floors])
