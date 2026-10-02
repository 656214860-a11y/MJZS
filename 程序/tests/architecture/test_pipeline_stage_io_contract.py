"""全流程 pipeline 的链路、输入来源和 manifest 归属契约。"""
import unittest

import pet_bus
import script_contract
import skill_registry
import stage_layout


PIPELINE_DEPENDENCIES = {
    'pipeline-script-preparation': [],
    'pipeline-script-structure': ['pipeline-script-preparation'],
    'pipeline-storyboard-draft': ['pipeline-script-structure'],
    'pipeline-assets': ['pipeline-storyboard-draft'],
    'pipeline-continuity': ['pipeline-assets'],
    'pipeline-storyboard-final': ['pipeline-continuity'],
    'pipeline-keyframe': ['pipeline-storyboard-final'],
    'pipeline-previs': ['pipeline-keyframe'],
    'pipeline-video-generation': ['pipeline-previs'],
    'pipeline-audio-subtitle': ['pipeline-storyboard-final'],
    'pipeline-editing': ['pipeline-video-generation', 'pipeline-audio-subtitle'],
    'pipeline-delivery': ['pipeline-editing'],
}

# 这些是用户在启动阶段时输入的配置事实，而不是任一 pipeline 的阶段成果。
INPUT_EXEMPTIONS = {
    'creativeBrief': '创意简报是剧本准备入口填写的创作事实。',
    'modelLock': '模型锁是剧本准备入口锁定的配置。',
    'aspectRatio': '画幅是剧本准备入口锁定的配置。',
    'dialogueFacts': '对白与时间线事实从已采用分镜读取，不另建重复产物。',
}


def _camel_from_manifest(filename):
    stem = filename.removesuffix('.json')
    words = stem.split('_')
    return words[0] + ''.join(word.title() for word in words[1:])


class PipelineStageIoContractTests(unittest.TestCase):
    def setUp(self):
        self.registry = skill_registry.default_registry()
        self.registry.scan(force=True)
        self.skills = {skill.name: skill for skill in self.registry.getAll()}
        self.stage_index = {stage: position for position, stage in enumerate(pet_bus.STAGES)}

    def test_pipeline_dependencies_match_the_single_contract_map(self):
        actual = {name: self.skills[name].dependsOn for name in PIPELINE_DEPENDENCIES}
        self.assertEqual(actual, PIPELINE_DEPENDENCIES)

    def test_pipeline_inputs_are_produced_upstream_or_are_documented_entry_facts(self):
        pipelines = [self.skills[name] for name in PIPELINE_DEPENDENCIES]
        for pipeline in pipelines:
            available = {value for other in pipelines
                         if self.stage_index[other.stage] <= self.stage_index[pipeline.stage]
                         for value in other.output}
            for value in pipeline.input:
                self.assertTrue(value in available or value in INPUT_EXEMPTIONS,
                                '%s 的输入 %s 没有上游来源或入口豁免' % (pipeline.name, value))

    def test_manifest_owners_and_pipeline_outputs_derive_from_contract_sources(self):
        layout_script_stage = stage_layout.stage_dir(script_contract.STAGE)[1]
        expected_files = set(stage_layout.stage_dir(script_contract.STAGE)[5])
        for filename, (producer, folder) in script_contract.PRODUCERS.items():
            self.assertIn(filename, expected_files)
            self.assertEqual(stage_layout.stage_dir(folder)[1], layout_script_stage)
            owner = self.skills[producer]
            semantic_output = _camel_from_manifest(filename)
            producer_pipeline = next(skill for skill in self.skills.values()
                                     if skill.name.startswith('pipeline-')
                                     and skill.stage == owner.stage)
            self.assertIn(semantic_output, producer_pipeline.output)
