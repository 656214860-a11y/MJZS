import sys
from pathlib import Path

PROGRAM = Path(r'D:\漫剧制作助手\.agents\worktrees\foundation-integration-final\程序')
ROOT = PROGRAM.parent
sys.path.insert(0, str(PROGRAM))
sys.path.insert(0, str(PROGRAM / '维护记录' / '基准脚本'))
sys.path.insert(0, str(PROGRAM / 'scripts'))
import round_evidence

keywords = ['stage_extension', 'stage_task_owner', 'test_skill_tools',
            'test_dynamic_import_registry', 'test_confirm_gates',
            'test_content_extraction_owner']
target = round_evidence.write_evidence(3895, keywords, root=ROOT)
print('evidence=', target, flush=True)
print('judge=', round_evidence.judge(3895), flush=True)
result = PROGRAM / 'tasks_round' / 'tasks_round_3895_result.md'
print('stamp=', round_evidence.stamp_result(result, 3895), flush=True)
import subprocess
print('add1=', subprocess.run(['git', 'add', '--', str(target)], cwd=str(ROOT)).returncode, flush=True)
print('add2=', subprocess.run(['git', 'add', '--', str(result)], cwd=str(ROOT)).returncode, flush=True)
