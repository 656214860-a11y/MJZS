# -*- coding: utf-8 -*-
"""历史入口：实体在 ``ui.ui_status_bus``（T10 包化同款）。生产侧用包路径导入。"""
import sys as _sys
from ui import ui_status_bus as _entity

_sys.modules[__name__] = _entity
