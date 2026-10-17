"""交付阶段的最终成片导入。"""
import logging
import uuid
from pathlib import Path

from project_context import ProjectContext
from service_contract import SystemError, UserError, success
from agent.media import MediaValidationError


ALLOWED_SUFFIXES = frozenset({'.mp4', '.mov', '.mkv'})
LOGGER = logging.getLogger(__name__)


def import_final_master(context, source, publish=None):
    """校验并发布成片，统一以 ``ServiceResult`` 返回结果。"""
    if not isinstance(context, ProjectContext):
        raise TypeError('最终成片导入需要由 L3 注入 ProjectContext。')
    if not callable(publish):
        raise TypeError('最终成片发布需要由 L3 注入发布器。')
    source = Path(source)
    try:
        if source.suffix.lower() not in ALLOWED_SUFFIXES:
            return UserError('请选择 MP4、MOV 或 MKV 成片文件')
        if not source.is_file() or not source.stat().st_size:
            return UserError('成片文件为空，请选择有效文件')
        target_dir = context.stage_resolver('delivery')
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / (source.stem + '_' + uuid.uuid4().hex[:6] + source.suffix)
        publish(target, source)
    except MediaValidationError as exc:
        return UserError(str(exc))
    except (OSError, ValueError) as exc:
        LOGGER.exception('最终成片发布失败')
        return SystemError(str(exc))
    return success(target)
