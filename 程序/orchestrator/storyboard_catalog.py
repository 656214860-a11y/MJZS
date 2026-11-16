"""Stable, Tk-free facade for storyboard catalog and selection callers.

Callers outside the page import this module.  New implementations live in the
catalog/selection services; this facade is retained for compatibility until the
2027-03-31 legacy project-path retirement.
"""
from domain.storyboard_catalog_service import IGNORED, file_order, check_adoptable
from stage_execution_service import (
    storyboard_board_source_script as board_source_script, storyboard_catalog as catalog,
    storyboard_default_source as default_source, storyboard_produced_episodes as produced_episodes,
    storyboard_produced_scripts as produced_scripts, storyboard_resolve_source as resolve_source,
)
from storyboard_selection import remember_many, selected_many, sync_structured_script


def remember(project, kind, path):
    return remember_many(project, kind, [path] if path else [])
