"""无 Tk 的分镜定稿预览、编辑与镜头导航控制器。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from file_cache import read_json, read_text
from stage_execution_service import save_edited_stage_storyboard
from storyboard_selection import remember_final_view
from storyboard_storage import resolved_alias


def storyboard_lifecycle_gateway():
    """定稿退役的别名发布能力仅由 L3 注入。"""
    from agent.core import save
    return {'publish_json': save}


def retire_stage_storyboard(project, source, target, expected):
    """定稿后退役工作分镜：由 L3 注入别名发布器并保留回收站事务。"""
    from storyboard_lifecycle import retire
    return retire(project, source, target, expected,
                  publish=storyboard_lifecycle_gateway()['publish_json'])


def finalize_stage_storyboard(project, episode_dir, source):
    """桌面定稿入口：完成发布后才允许经 L3 退役工作分镜。"""
    from storyboard_final import finalize
    from stage_execution_service import asset_plan_gateway
    return finalize(project, episode_dir, source, retire_working=retire_stage_storyboard,
                    gateway=asset_plan_gateway())


@dataclass(frozen=True)
class FinalPreview:
    path: Path
    text: str
    data: dict | None


class FinalStoryboardController:
    """保存页面无关的定稿预览、编辑和导航状态。"""

    def __init__(self, project):
        self.project = Path(project).resolve()
        self.preview: FinalPreview | None = None
        self.shot_ids: tuple[str, ...] = ()
        self.selected_shot: str | None = None

    def display_name(self, path) -> str:
        try:
            return Path(path).resolve().relative_to(self.project).as_posix()
        except ValueError:
            return str(path)

    def live_path(self, path=None) -> Path:
        target = Path(path or self.active_path()).resolve()
        try:
            return Path(resolved_alias(self.project, target))
        except (OSError, ValueError):
            return target

    def active_path(self) -> Path:
        if self.preview is None:
            raise ValueError('尚未选择 JSON')
        return self.preview.path

    def is_edited(self, text: str) -> bool:
        return self.preview is not None and text != self.preview.text

    def clear(self) -> None:
        self.preview = None
        self.shot_ids = ()
        self.selected_shot = None

    def load(self, path) -> FinalPreview:
        target = self.live_path(path)
        try:
            data = read_json(target)
        except (OSError, ValueError):
            data = None
        if isinstance(data, dict):
            text = json.dumps(data, ensure_ascii=False, indent=2)
        else:
            try:
                text = read_text(target, encoding='utf-8-sig', errors='replace')
            except OSError:
                text = '（无法读取此文件）'
        return self.apply_preview(FinalPreview(target, text, data))

    def apply_preview(self, preview: FinalPreview) -> FinalPreview:
        """接收已在后台读好的预览；这里只更新页面无关的选择状态。"""
        self.preview = preview
        self.set_navigation(preview.data)
        return preview

    def choose(self, path, load=True) -> tuple[FinalPreview | None, str]:
        """记录选择；大文件视图可先记录、再由后台读取后调用 ``apply_preview``。"""
        target = Path(path).resolve()
        remember_final_view(self.project, target)
        if not load:
            return None, f'已选：{self.display_name(target)} · 正在加载预览'
        preview = self.load(target)
        missing = preview.data.get('missing_assets') if isinstance(preview.data, dict) else None
        state = (f'待补齐 {len(missing)} 项资产' if missing else
                 ('已生成分镜定稿' if (target.parent / 'assets.json').is_file() else '分镜初稿'))
        return preview, f'已选：{self.display_name(target)} · {state}'

    def save_edited(self, text: str) -> FinalPreview:
        path = self.live_path()
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise ValueError('改完的文字不是一份合法 JSON：' + str(exc)) from exc
        save_edited_stage_storyboard(path, data)
        return self.load(path)

    def set_navigation(self, data) -> tuple[str, ...]:
        shots = data.get('shots', []) if isinstance(data, dict) else []
        self.shot_ids = tuple(str(shot.get('id')) for shot in shots
                              if isinstance(shot, dict) and shot.get('id'))
        self.selected_shot = None
        return self.shot_ids

    def select_shot(self, shot_id) -> str:
        shot_id = str(shot_id)
        if shot_id not in self.shot_ids:
            raise ValueError('镜头不在当前分镜中')
        self.selected_shot = shot_id
        return shot_id
