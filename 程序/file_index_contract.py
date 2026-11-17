# -*- coding: utf-8 -*-
"""历史兼容门面：实体在 ``contract.file_index_contract``（R3093 包化）。"""
from contract.file_index_contract import (FIELDS, INDEX_VERSION, ORIGIN_MODEL, ORIGIN_SYSTEM, ORIGIN_USER,
                                          ORIGINS, STATUSES, STATUS_ARCHIVED, STATUS_DRAFT, STATUS_PUBLISHED,
                                          FileRow)

__all__ = ['FIELDS', 'INDEX_VERSION', 'ORIGIN_MODEL', 'ORIGIN_SYSTEM', 'ORIGIN_USER', 'ORIGINS', 'STATUSES',
           'STATUS_ARCHIVED', 'STATUS_DRAFT', 'STATUS_PUBLISHED', 'FileRow']
