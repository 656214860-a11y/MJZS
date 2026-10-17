"""剧本 manifest 的不可变文件契约。

阶段目录和剧本校验都需要这些名称，因此不能由其中一方反向导入另一方。
"""
from __future__ import annotations

MANIFESTS = ('character_manifest.json', 'scene_manifest.json', 'prop_manifest.json',
             'scene_breakdown.json', 'emotion_curve.json')
KINDS = ('character', 'scene', 'prop', 'scene_breakdown', 'emotion_curve')
MANIFEST_OF_KIND = dict(zip(KINDS, MANIFESTS))
KIND_OF_MANIFEST = dict(zip(MANIFESTS, KINDS))
HEADER = ('manifest', 'kind', 'items')
STAGE_OUTPUTS = MANIFESTS
# 每份 manifest 落在哪个阶段目录（REQ-S02-25）：键是状态机阶段 id，值是该阶段 output/ 下的文件。
STAGE_MANIFESTS = {
    'script': ('emotion_curve.json',),
    'script_structure': ('character_manifest.json', 'scene_manifest.json', 'prop_manifest.json'),
    'storyboard': ('scene_breakdown.json',),
}
STRUCTURE_MANIFESTS = STAGE_MANIFESTS['script_structure']
