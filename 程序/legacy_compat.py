# -*- coding: utf-8 -*-
"""仅供旧项目读取的兼容门面。

业务模块不得各自捕获 ``ImportError`` 后猜测旧布局；需要兼容历史项目时统一经本模块
读取。新写入路径不应使用这里的函数。计划在 2027-03-31 与旧目录只读兼容一起移除。
"""
from pathlib import Path


RETIRE_AFTER = '2027-03-31'

# 历史兼容入口唯一清单。调用方由架构门禁从生产 AST 反查；未来若某入口没有
# 生产调用，仍须显式登记空元组，以便 P3-2 据此安全淘汰。
FACADE_MANIFEST = {
    'resolved_storyboard_alias': {
        'owner': 'legacy_compat', 'callers': ('engine',), 'retire_after': RETIRE_AFTER,
    },
    'canonical_stage_name': {
        'owner': 'legacy_compat', 'callers': ('confirm_gates',), 'retire_after': RETIRE_AFTER,
    },
    'optional_workflow_model_name': {
        'owner': 'legacy_compat', 'callers': ('local_previs',), 'retire_after': RETIRE_AFTER,
    },
    'optional_model_identity': {
        'owner': 'legacy_compat', 'callers': ('idea_document_paths',), 'retire_after': RETIRE_AFTER,
    },
    'optional_asset_counts': {
        'owner': 'legacy_compat', 'callers': ('pet_ui_support',), 'retire_after': RETIRE_AFTER,
    },
}


def resolved_storyboard_alias(project, path):
    """将历史分镜别名解析为当前文件；映射组件不可用时保留原路径只读尝试。"""
    candidate = Path(path)
    try:
        from storyboard_storage import resolved_alias
    except ImportError:
        return candidate
    return Path(resolved_alias(Path(project), candidate))


def canonical_stage_name(value):
    """将历史阶段标识转换为当前显示目录名；未知值原样返回。"""
    text = str(value or '').strip().rstrip('/\\')
    try:
        from contract.stage_layout import stage_dir
    except ImportError:
        return text
    row = stage_dir(text)
    return row[0] if row is not None else text


def optional_workflow_model_name(project, stage):
    """读取可选工作流模型名；运行环境缺少设置模块时保持页面可用。

    这是历史／可选组件边界的唯一 ImportError 容错点。调用方只消费空字符串，不能在 UI
    模块自行猜默认模型或打印导入异常。
    """
    try:
        from workflow_settings import model_name
    except ImportError:
        return ''
    try:
        return str(model_name(project, stage) or '')
    except (OSError, ValueError):
        return ''


def optional_model_identity(label, program):
    """返回可选模型池中的 Provider／显示名；缺失模型池时保留调用方输入。

    这是历史安装缺少 ``model_pool`` 时唯一的容错边界。页面和创作服务不能各自
    捕获 ImportError 后再猜目录归属；写入方仍会把空 Provider 落在自己的明确兜底目录。
    """
    shown = str(label or '').strip()
    try:
        import model_pool
        records = model_pool.pool(program=Path(program))
        model_id = model_pool.id_of_label(shown, model_pool.options(records, with_auto=False))
        record = records.get(model_id, {})
        provider = model_pool.provider_name(model_id, record)
        shown = str(record.get('label') or shown or model_id).strip()
        return str(provider or '').strip(), shown
    except (ImportError, AttributeError, TypeError, OSError, ValueError):
        return '', shown


def optional_asset_counts(base, read_json):
    """返回资产登记数和就绪图片数；历史安装缺少资产状态服务时安全降级。"""
    try:
        from asset_batch_state_service import ready_asset_ids
        root = Path(base)
        ready = len(ready_asset_ids(root))
        registry = read_json(root / 'assets.json')
        return (len(registry) if isinstance(registry, dict) else 0), ready
    except (ImportError, AttributeError, TypeError, OSError, ValueError, KeyError):
        return 0, 0
