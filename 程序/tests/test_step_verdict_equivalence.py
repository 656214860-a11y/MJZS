"""resume_preview 的逐步处置抽成 _step_verdict：与原 elif 链全组合对照。"""
import itertools
import unittest

import skill_orchestrator


def _legacy(index, step_index, total, scope_ok, version_ok, project_ok, digest_ok, artifact_verified):
    if not scope_ok:
        return 'verify', '检查点步骤 %d 落在当前 %d 步之外，需人工核实' % (step_index, total)
    elif index < step_index:
        return 'skip', '检查点之前的步骤：工具已跑过（工具调用完成，不等于成果已采用）'
    elif index > step_index and artifact_verified:
        return 'skip', '该阶段成果已验证，不重复执行'
    elif index > step_index:
        return 'continue', '后续步骤'
    elif not version_ok:
        return 'verify', '检查点由旧版格式写入，需人工核实'
    elif not project_ok:
        return 'verify', '检查点属于另一个项目，需人工核实'
    elif not scope_ok or not digest_ok:
        return 'verify', '这一步与现在的步骤／技能集对不上，需人工核实'
    elif artifact_verified:
        return 'skip', '该阶段成果已验证，不重复执行这一步'
    return 'continue', '从这一步续做'


class StepVerdictEquivalence(unittest.TestCase):
    def test_all_combinations(self):
        n = 0
        for index, step in itertools.product(range(1, 5), range(0, 6)):
            for flags in itertools.product((True, False), repeat=5):
                args = (index, step, 4) + flags
                self.assertEqual(skill_orchestrator._step_verdict(index, step, 4, flags[:4], flags[4]), _legacy(*args), args)
                n += 1
        self.assertEqual(n, 4 * 6 * 32)


if __name__ == '__main__':
    unittest.main()
