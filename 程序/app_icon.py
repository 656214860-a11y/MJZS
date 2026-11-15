"""历史入口：实体已迁至 ``infra.app_icon``（T10 包化）。

``import app_icon`` 返回 ``infra.app_icon`` 本体：私有名、模块级状态与
按扁平名打的 ``mock.patch`` 补丁面和包内路径完全一致；生产侧一律用包路径。
``python app_icon.py`` 直跑时转发到实体 ``main()``（生成图标资产）。
门面清除轮统一改写测试导入后删除本文件。
"""
import sys as _sys
from infra import app_icon as _entity

_sys.modules[__name__] = _entity

if __name__ == '__main__':
    _entity.main()
