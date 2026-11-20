"""Refresh the whole-program line coverage baseline for the new C8 modules."""
import importlib.util
import json
import sys
from pathlib import Path

PROGRAM = Path(r'D:\漫剧制作助手\.agents\worktrees\foundation-c8-updater\程序')
sys.path.insert(0, str(PROGRAM))
spec = importlib.util.spec_from_file_location(
    'coverage_report', PROGRAM / 'scripts' / 'coverage_report.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

baseline_path = PROGRAM / '维护记录' / '覆盖率基线.json'
baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
targets = list(baseline['targets'])
if 'tests.test_update_pipeline' not in targets:
    targets.append('tests.test_update_pipeline')
report = tool.measure(targets)
print('tests_ok', report['tests_ok'], 'modules', report['modules_total'],
      'covered', report['modules_covered'])
print('targets', len(report['targets']))
if not report['tests_ok']:
    print('NOT WRITING baseline')
    raise SystemExit(2)
baseline_path.write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('baseline updated')
