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
