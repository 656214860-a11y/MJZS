"""项目接续索引的 L3 发布与提示词编排入口。"""


def workflow_context_gateway():
    """为 L2 项目接续索引装配唯一的正式 JSON 发布器。"""
    from agent.core import save
    return {'publish_json': save}


def request_stage_instruction(project, stage, data=None):
    """刷新项目接续索引并返回当前阶段提示词。"""
    from domain.workflow_context import request_instruction
    result = request_instruction(project, stage, data,
                                 publish=workflow_context_gateway()['publish_json'])
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def publish_writing_context(project, stage, data=None):
    """为直接剧本 API 回复刷新完整项目接续索引。"""
    from domain.workflow_context import instruction
    result = instruction(project, stage, data,
                         publish=workflow_context_gateway()['publish_json'])
    if not result.ok:
        raise ValueError(result.reason)
    return result.data
