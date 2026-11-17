# -*- coding: utf-8 -*-
"""历史兼容门面：实体在 ``contract.file_naming``（R3093 包化）。"""
from contract.file_naming import (DEFAULT_KIND, KINDS, MAX_NAME, MAX_PATH, RESERVED_NAMES, TEMPLATES,
                                  check_path, generate_name, kind_from_suffix, legacy_scheme, parse,
                                  sanitize_part, validate)

__all__ = ['DEFAULT_KIND', 'KINDS', 'MAX_NAME', 'MAX_PATH', 'RESERVED_NAMES', 'TEMPLATES', 'check_path',
           'generate_name', 'kind_from_suffix', 'legacy_scheme', 'parse', 'sanitize_part', 'validate']
