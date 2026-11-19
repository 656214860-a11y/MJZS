"""历史入口：实体已迁至 ``infra.storage_maintenance``（T10 包化）。

``import storage_maintenance`` 返回 ``infra.storage_maintenance`` 本体：私有名、模块级状态与
按扁平名打的 ``mock.patch`` 补丁面和包内路径完全一致；生产侧一律用包路径。
``python storage_maintenance.py --cleanup`` 仅保留给旧版外部调用并转发到实体 ``main()``；
生产自启动已经使用 ``python -m infra.storage_maintenance --cleanup``。待扁平导入／补丁面
兼容窗口结束且发布清单不再承诺旧入口后，门面清除轮才可删除本文件。
"""
import sys as _sys
from infra import storage_maintenance as _entity

_sys.modules[__name__] = _entity

if __name__ == '__main__' and '--cleanup' in _sys.argv:
    _entity.main()
