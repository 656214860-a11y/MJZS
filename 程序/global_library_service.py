# -*- coding: utf-8 -*-
"""历史兼容门面：实体在 ``domain.global_library_service``（R3165 包化）。"""
from domain.global_library_service import (SHARED_SUB, SOURCE_MANIFEST, copy_to_library, copy_to_project)

__all__ = ['SHARED_SUB', 'SOURCE_MANIFEST', 'copy_to_library', 'copy_to_project']
