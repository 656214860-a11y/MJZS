from pathlib import Path
import subprocess

PROGRAM = Path(r'D:\漫剧制作助手\.agents\worktrees\foundation-integration-final\程序')
ROOT = PROGRAM.parent
import sys
sys.path.insert(0, str(PROGRAM / '维护记录' / '基准脚本'))
import round_evidence

result = PROGRAM / 'tasks_round' / 'tasks_round_3897_result.md'
result.write_text(
    '# R3897 — 任务书状态回填（整合候选与 C8 接收后的真实进度）\n\n'
    '## 三问\n\n'
    '1. **类型**：文档/状态接续轮（§3.6 类），只改任务书状态，不改源码。\n'
    '2. **测试**：文档轮按 AGENTS §5 不跑 smoke/selftest；本轮无代码改动，不新增绿色凭据。\n'
    '3. **欠账**：把 R3895/R3896 的真实接收状态、两处已知红、剩余 4 条反向依赖边与未完成项写回任务书 §11.5 及对应条目，避免下轮误判为已完成。\n\n'
    '## 变更\n\n'
    '- 任务书新增 §11.5：整合分支折叠（`4a532515`，基线 master `bcbf337e`，备份引用）、C6 三车道接收、反向依赖 15→12、C8 接收（`4cdaa20c`）、两处已知红（状态页轮次/分支覆盖基线受 GUI 队列 ACL 阻塞）、最终未完成清单。\n'
    '- C8 条目更新为「python-tuf 替代 tufup」的真实实现与验证状态（四态未混填：已实现/已验证/已合入整合分支/未发布）。\n'
    '- C6 条目补记三车道接收与严格闭包，明确生产 bootstrap 装配点仍未做。\n'
    '- 全局「反向依赖豁免额度」条目改为目标 8/当前 12/动态 2，并写清剩余 4 条，未上调额度。\n\n'
    '## 未完成\n\n'
    '任务书其余条目与最终验收（安全全量、分发构建、C3 真实跨屏、C6 生产装配点、真实发布链路、任务完成文件、master 接收）仍未完成；目标保持执行中，不生成总任务完成文件。\n',
    encoding='utf-8')

target = round_evidence.write_evidence(3897, [], root=ROOT)
print('evidence=', target, 'judge=', round_evidence.judge(3897))
print('stamp=', round_evidence.stamp_result(result, 3897))
for item in (target, result, PROGRAM / 'tasks_round' / '架构地基加固任务书.md'):
    print('add', item.name, subprocess.run(['git', 'add', '--', str(item)], cwd=str(ROOT)).returncode)
