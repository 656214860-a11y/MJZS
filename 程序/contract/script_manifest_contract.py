"""剧本 manifest 的不可变文件契约。

阶段目录和剧本校验都需要这些名称，因此不能由其中一方反向导入另一方。
"""
from __future__ import annotations

import contract.asset_contract as asset_contract

MANIFESTS = ('character_manifest.json', 'scene_manifest.json', 'prop_manifest.json',
             'scene_breakdown.json', 'emotion_curve.json')
# 资产三类的唯一源是 asset_contract.KINDS（H4）；scene_breakdown／emotion_curve
# 只服务剧本产出，不属于资产类别，接在资产三类后面保持原有顺序。
MANIFEST_KINDS = asset_contract.KINDS + ('scene_breakdown', 'emotion_curve')
MANIFEST_OF_KIND = dict(zip(MANIFEST_KINDS, MANIFESTS))
KIND_OF_MANIFEST = dict(zip(MANIFESTS, MANIFEST_KINDS))
HEADER = ('manifest', 'kind', 'items')
STAGE_OUTPUTS = MANIFESTS
# 每份 manifest 落在哪个阶段目录（REQ-S02-25）：键是状态机阶段 id，值是该阶段 output/ 下的文件。
STAGE_MANIFESTS = {
    'script': ('emotion_curve.json',),
    'script_structure': ('character_manifest.json', 'scene_manifest.json', 'prop_manifest.json'),
    'storyboard': ('scene_breakdown.json',),
}
STRUCTURE_MANIFESTS = STAGE_MANIFESTS['script_structure']
