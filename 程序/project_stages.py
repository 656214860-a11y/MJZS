"""历史入口：实体已迁至 ``contract.project_stages``（T10 包化）。

测试与未改写的消费方仍按扁平名导入；生产侧一律用包路径。
门面清除轮统一改写测试导入后删除本文件。

R3093（任务书 P0，Q15）：原 ``STAGES`` 字典（键拼写与 ``pet_bus.STAGES`` 不同）已删除，
改为 ``stage_dirs()``；门面不再转发 ``Path``——需要 ``Path`` 的调用方自己
``from pathlib import Path``，不要把 ``pathlib`` 名字当成阶段契约的一部分。
"""
from contract.project_stages import (
    assets,
    audio,
    delivery,
    editing,
    exports,
    stage,
    stage_dirs,
    storyboard,
    structure,
    subtitles,
    writing,
)

__all__ = ['assets', 'audio', 'delivery', 'editing', 'exports', 'stage', 'stage_dirs', 'storyboard',
           'structure', 'subtitles', 'writing']
