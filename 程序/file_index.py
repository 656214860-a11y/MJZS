# -*- coding: utf-8 -*-
"""历史兼容门面：实体在 ``infra.file_index``（R3093 包化）。"""
from infra.file_index import (AUDIO_SUFFIXES, CONFIRM_DIR_NAME, DELIVERY_MANIFEST, GLOBAL_INDEX_NAME,
                              IMAGE_SUFFIXES, INDEX_DIR_NAME, INDEX_NAME, SKIP_DIRS, VIDEO_SUFFIXES, build,
                              build_global, ensure, global_index_path, global_rows, index_path, kind_of, kinds,
                              published_paths, read, read_global, rebuild, rebuild_global, rows, search,
                              search_global, stage_of, summary, update)

__all__ = ['AUDIO_SUFFIXES', 'CONFIRM_DIR_NAME', 'DELIVERY_MANIFEST', 'GLOBAL_INDEX_NAME', 'IMAGE_SUFFIXES',
           'INDEX_DIR_NAME', 'INDEX_NAME', 'SKIP_DIRS', 'VIDEO_SUFFIXES', 'build', 'build_global', 'ensure',
           'global_index_path', 'global_rows', 'index_path', 'kind_of', 'kinds', 'published_paths', 'read',
           'read_global', 'rebuild', 'rebuild_global', 'rows', 'search', 'search_global', 'stage_of', 'summary',
           'update']
