# -*- coding: utf-8 -*-
"""历史兼容门面：实体在 ``orchestrator.legacy_migration``（R3125 包化）。"""
from orchestrator.legacy_migration import (ASSETS_MANIFEST_NAME, BACKUP_DIR_NAME, CONFIRM_DIR_NAME,
                                           REPORT_NAME, apply, mapping_of, plan, repoint_manifests, report,
                                           rewrite_absolute_manifests, target_relpath)

__all__ = ['ASSETS_MANIFEST_NAME', 'BACKUP_DIR_NAME', 'CONFIRM_DIR_NAME', 'REPORT_NAME', 'apply', 'mapping_of',
           'plan', 'repoint_manifests', 'report', 'rewrite_absolute_manifests', 'target_relpath']
