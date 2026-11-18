"""Production-model names shared by stage orchestration, frame generation and asset batches.

Keeping these facts outside either caller prevents the configuration layer and
the frame UI/service from importing one another merely to compare a label.
"""

LOCAL_KEYFRAME_MODEL = '本地 FLUX.2 Klein（ComfyUI）'
SEEDREAM_KEYFRAME_MODEL = 'Seedream 5.0 Pro'
KEYFRAME_MODELS = (LOCAL_KEYFRAME_MODEL, SEEDREAM_KEYFRAME_MODEL)


# 第 1647 轮：资产批量生成的后端名同样是被两处比较的事实（L2 asset_batch_service 解析当前模型、
# L4 cloud_assets 认节点类型与参考图张数上限），按本模块既有口径下沉到 L0，
# 让领域服务不必为了比一个字符串反向依赖 UI 层。
ASSET_LOCAL_MODEL = '本地 FLUX.2 Klein / 自定义工作流'
ASSET_CLOUD_MODELS = ('Seedream 5.0 Pro', 'Nano Banana Pro', 'GPT Image 2')
# 轮 6B（D7）：节点类型与参考图上限是按模型名寻址的命名映射，
# 与 ASSET_CLOUD_MODELS 的有序元组解耦——元组顺序只服务于 UI 选项排序，
# 往中间插一个模型不再按位置错位既有条目；键集必须与元组一致（有测试守卫）。
ASSET_CLOUD_NODE_TYPES = {
    'Seedream 5.0 Pro': 'ByteDanceSeedreamNode',
    'Nano Banana Pro': 'GeminiImage2Node',
    'GPT Image 2': 'OpenAIGPTImage1',
}
ASSET_CLOUD_REFERENCE_LIMITS = {
    'Seedream 5.0 Pro': 10,
    'Nano Banana Pro': 14,
    'GPT Image 2': 16,
}
