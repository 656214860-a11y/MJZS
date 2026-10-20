"""REQ-S11 测试锚定：配音阶段默认技能与兼容层的关系。"""
import unittest

import workflow_settings


class ReqS11AnchorTests(unittest.TestCase):
    def test_req_s11_32_legacy_audio_default_is_empty_and_stage_preset_is_authoritative(self):
        """REQ-S11-32：旧 FLOWS 的 audio 默认保持空串，阶段预设默认 pipeline-audio-subtitle。"""
        self.assertEqual(workflow_settings.DEFAULT_SKILLS['audio'], '')
        preset = workflow_settings.BUILTIN_WORKFLOW_PRESETS['AIGC全流程']['stage_skills']['audio']
        self.assertEqual(preset, ['pipeline-audio-subtitle'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
