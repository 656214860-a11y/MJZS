"""无 Tk 的初步分镜文件表状态、刷新与回收编排。"""
from __future__ import annotations

from pathlib import Path

from stage_execution_service import storyboard_catalog as catalog, storyboard_produced_scripts as produced_scripts, storyboard_resolve_source as resolve_source
from storyboard_recycle_service import (
    latest_recycle_batch, recycle_files, recycle_plan, restore_latest_recycled_files,
)
from storyboard_selection import adopted, prune_invalid_adoptions, remember_many, selected_many, summary


class StoryboardPageController:
    """保持文件表的领域状态；Tk 页面只负责呈现和确认交互。"""

    KINDS = ('script', 'storyboard')

    def __init__(self, project):
        self.project = Path(project).resolve()
        self.catalogs = {kind: [] for kind in self.KINDS}
        self.selections = {kind: list(selected_many(self.project, kind)) for kind in self.KINDS}
        self.completed_scripts = set()

    def prune_invalid_adoptions(self):
        return prune_invalid_adoptions(self.project)

    def adopted(self):
        return set(adopted(self.project))

    def summary(self):
        return summary(self.project)

    def resolve(self, values):
        return [resolve_source(self.project, value) for value in values]

    def selection(self, kind):
        self._check_kind(kind)
        return list(self.selections[kind])

    def action_selection(self, kind, highlighted=()):
        """勾选优先；未勾选时使用页面传入的高亮行。"""
        selected = self.selection(kind)
        return selected or self.resolve(highlighted)

    def choose(self, kind, paths):
        self._check_kind(kind)
        chosen = list(dict.fromkeys(Path(path).resolve() for path in paths))
        remember_many(self.project, kind, chosen)
        self.selections[kind] = chosen
        return chosen

    def refresh_catalogs(self):
        return {kind: catalog(self.project, kind) for kind in self.KINDS}

    def apply_catalogs(self, catalogs):
        """应用完整扫描结果，并保持可用的表格选择。"""
        boards = list(catalogs['storyboard'])
        scripts = list(catalogs['script'])
        self.catalogs = {'script': scripts, 'storyboard': boards}
        self.completed_scripts = produced_scripts(self.project, boards)
        used = self.adopted()
        for kind, entries in self.catalogs.items():
            if kind == 'script':
                current = [entry['path'] for entry in entries if not entry.get('done')]
            else:
                current = [path for path in self.selection(kind) if path not in used]
            for path in current:
                if not any(entry['path'] == path for entry in entries):
                    entries.append({
                        'path': path,
                        'title': path.stem + (' · 已制作分镜' if kind == 'script' and path in self.completed_scripts else ''),
                        'created': path.stat().st_mtime,
                        'done': kind == 'script' and path in self.completed_scripts,
                    })
            self.choose(kind, current)
        return self.catalogs

    def control_states(self, scripts, boards):
        used = self.adopted()
        return {
            'agent': bool(any(path not in self.completed_scripts for path in scripts)
                          or any(path not in used for path in boards)),
            'adopt': bool(any(path not in used for path in boards)),
            'remove': bool(any(path in used for path in boards)),
            'delete_script': not any(path in self.completed_scripts for path in scripts),
            'delete_storyboard': not any(path in used for path in boards),
        }

    def removable(self, kind, path):
        path = Path(path).resolve()
        if kind == 'script' and path in self.completed_scripts:
            raise ValueError('这一份剧本已经制作成分镜，取消制作后才能删除')
        if kind == 'storyboard' and path in self.adopted():
            raise ValueError('这一份分镜已被采用，先「手动取消采用」再删除')
        return path

    def recycle_targets(self, kind, paths):
        sources = [self.removable(kind, path) for path in paths]
        targets = [target for source in sources for target in recycle_plan(self.project, kind, source)]
        return sources, list(dict.fromkeys(targets))

    def recycle(self, kind, paths):
        sources, _targets = self.recycle_targets(kind, paths)
        return recycle_files(self.project, kind, sources)

    def latest_recycle_batch(self):
        return latest_recycle_batch(self.project)

    def restore_latest(self):
        return restore_latest_recycled_files(self.project)

    def _check_kind(self, kind):
        if kind not in self.KINDS:
            raise ValueError('文件类型无效')
