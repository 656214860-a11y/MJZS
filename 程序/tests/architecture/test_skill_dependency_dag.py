"""注册 SKILL 的依赖必须是一个指向当前或上游阶段的 DAG。"""
import unittest

import pet_bus
import skill_registry


class SkillDependencyDagTests(unittest.TestCase):
    def setUp(self):
        self.registry = skill_registry.default_registry()
        self.registry.scan(force=True)
        self.skills = {skill.name: skill for skill in self.registry.getAll()}
        self.index = {stage: position for position, stage in enumerate(pet_bus.STAGES)}

    def test_dependencies_are_registered_and_never_point_downstream(self):
        for skill in self.skills.values():
            for dependency in skill.dependsOn:
                self.assertIn(dependency, self.skills, '%s -> %s' % (skill.name, dependency))
                self.assertLessEqual(self.index[self.skills[dependency].stage], self.index[skill.stage],
                                     '%s 不得依赖下游 %s' % (skill.name, dependency))

    def test_dependency_graph_is_acyclic(self):
        pending = {name: set(skill.dependsOn) for name, skill in self.skills.items()}
        resolved = set()
        while pending:
            ready = {name for name, dependencies in pending.items() if dependencies <= resolved}
            self.assertTrue(ready, 'SKILL 依赖图存在环：%s' % sorted(pending))
            resolved.update(ready)
            for name in ready:
                pending.pop(name)
