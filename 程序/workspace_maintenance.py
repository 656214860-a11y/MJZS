"""历史入口：实体已迁至 ``infra.workspace_maintenance``（T10 包化）。

``import workspace_maintenance`` 返回 ``infra.workspace_maintenance`` 本体：私有名、模块级状态与
按扁平名打的 ``mock.patch`` 补丁面和包内路径完全一致；生产侧一律用包路径。
``python workspace_maintenance.py --cleanup`` 直跑时转发到实体 ``main()``（退出维护后台进程）。
门面清除轮统一改写测试导入后删除本文件。
"""
import sys as _sys
from infra import workspace_maintenance as _entity

_sys.modules[__name__] = _entity

if __name__ == '__main__':
    raise SystemExit(_entity.main())
