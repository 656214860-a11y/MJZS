"""Stable, Tk-free facade for storyboard catalog and selection callers.

Callers outside the page import this module.  New implementations live in the
catalog/selection services; this facade is retained for compatibility until the
2027-03-31 legacy project-path retirement.
"""
from storyboard_catalog_service import (
    IGNORED, default_source, resolve_source, catalog, produced_scripts,
    produced_episodes, board_source_script, file_order, check_adoptable,
)
from storyboard_selection import remember_many, selected_many, sync_structured_script


def remember(project, kind, path):
    return remember_many(project, kind, [path] if path else [])
