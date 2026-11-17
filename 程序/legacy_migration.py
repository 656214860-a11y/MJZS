# -*- coding: utf-8 -*-
"""兼容入口：完整迁移与引用重写已统一在事务 apply 内完成。"""
from orchestrator.legacy_migration import (
    ASSETS_MANIFEST_NAME, BACKUP_DIR_NAME, CONFIRM_DIR_NAME, REPORT_NAME,
    MigrationError, apply, mapping_of, plan, report, rollback, target_relpath,
)

__all__ = ['ASSETS_MANIFEST_NAME', 'BACKUP_DIR_NAME', 'CONFIRM_DIR_NAME', 'REPORT_NAME',
           'MigrationError', 'apply', 'mapping_of', 'plan', 'report', 'rollback', 'target_relpath']
