"""注册 SKILL 的依赖必须是一个指向当前或上游阶段的 DAG。"""
import tempfile
import unittest
from pathlib import Path

import pet_bus
import skill_registry


def dependency_problems(skills, index):
    """返回依赖图问题；生产注册表和新增技能注入都复用同一判据。"""
    problems=[]
    for skill in skills.values():
        for dependency in skill.dependsOn:
            if dependency not in skills:
                problems.append('%s -> %s 未注册' % (skill.name, dependency))
            elif index[skills[dependency].stage] > index[skill.stage]:
                problems.append('%s 不得依赖下游 %s' % (skill.name, dependency))
    pending={name:set(skill.dependsOn) for name,skill in skills.items()}
    resolved=set()
    while pending:
        ready={name for name, dependencies in pending.items() if dependencies <= resolved}
        if not ready:
            problems.append('SKILL 依赖图存在环：%s' % sorted(pending))
            break
        resolved.update(ready)
        for name in ready:
            pending.pop(name)
    return problems


class SkillDependencyDagTests(unittest.TestCase):
    def setUp(self):
        self.registry = skill_registry.default_registry()
        self.registry.scan(force=True)
        self.skills = {skill.name: skill for skill in self.registry.getAll()}
        self.index = {stage: position for position, stage in enumerate(pet_bus.STAGES)}

    def test_dependencies_are_registered_and_never_point_downstream(self):
        self.assertEqual(dependency_problems(self.skills,self.index),[])

    def test_dependency_graph_is_acyclic(self):
        self.assertEqual(dependency_problems(self.skills,self.index),[])

    def test_new_skills_are_checked_by_the_same_registry_gate(self):
        """R813：以后新增技能也必须经过缺依赖、下游与环三类门禁。"""
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self._write_skill(root,'01 剧本','upstream',[])
            self._write_skill(root,'02 剧本结构','new-skill',['upstream'])
            registry=skill_registry.Registry(root);registry.scan(force=True)
            skills={skill.name:skill for skill in registry.getAll()}
            self.assertEqual(dependency_problems(skills,self.index),[])
            self._write_skill(root,'02 剧本结构','missing',['not-registered'])
            self._write_skill(root,'01 剧本','downstream',['new-skill'])
            self._write_skill(root,'01 剧本','cycle-a',['cycle-b'])
            self._write_skill(root,'01 剧本','cycle-b',['cycle-a'])
            registry.scan(force=True);skills={skill.name:skill for skill in registry.getAll()}
            problems=dependency_problems(skills,self.index)
            self.assertTrue(any('未注册' in problem for problem in problems))
            self.assertTrue(any('下游' in problem for problem in problems))
            self.assertTrue(any('存在环' in problem for problem in problems))

    @staticmethod
    def _write_skill(root, directory, name, depends_on):
        target=root/directory/(name+'.skill.md');target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text('''---
name: {name}
displayName: {name}
description: test
stage: {stage}
capabilities: [creative-writing]
preferredModels: []
fallbackModels: []
tools: []
dependsOn: [{depends_on}]
conflictsWith: []
parallelizable: false
paid: false
input: []
output: []
constraints: []
feedback: []
examples: []
---
'''.format(name=name,stage=skill_registry.stage_from_path(target),depends_on=', '.join(depends_on)),encoding='utf-8')
