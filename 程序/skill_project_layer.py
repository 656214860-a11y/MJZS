"""SKILL 层与阶段目录的路径口径（R3054／生命周期任务书 T5）。

``<项目>/skills/`` 随项目走、归用户所有；``skill_registry.Registry`` 经
:class:`ProjectLayerMixin` 获得按层取阶段写入目录的口径。模块级
``project_skill_root``／``project_skill_root_for`` 供引用解析、发送白名单
与面板反推项目层根；``STAGE_DIRECTORY_IDS``／``stage_from_path`` 是阶段目录
→ 阶段 id 的物理归档口径，层分派与注册表扫描共用。项目根只在打开阶段面板／
配置时注入，启动路径零扫描。
"""
import re
from pathlib import Path

from stage_layout import SKILL_CONFIG_NAME

# 阶段文件夹是 SKILL 的物理归档口径。前置零的编号必须与 12 阶段顺序保持一致；
# 新放入 01—12 文件夹但尚未补 frontmatter 的 SKILL 可据此立即出现在正确阶段。
STAGE_DIRECTORY_IDS = {
    '01': 'script', '02': 'script_structure', '03': 'storyboard',
    '04': 'animatic', '05': 'assets', '06': 'continuity', '07': 'final',
    '08': 'keyframe', '09': 'previs', '10': 'video',
    '11': 'audio', '12': 'edit', '13': 'delivery',
}


def stage_from_path(path):
    """从 ``01…12`` 阶段目录推断阶段；非阶段资料目录不作猜测。"""
    candidate = Path(path) if path else None
    if candidate is None:
        return ''
    for parent in candidate.parents:
        match = re.match(r'^(\d{2})(?:\s|\D|$)', parent.name)
        if match:
            return STAGE_DIRECTORY_IDS.get(match.group(1), '')
    return ''


def project_skill_root(project):
    """项目级 SKILL 目录：``<项目>/skills/``（项目根与 ``skill_config.json`` 同级）。"""
    return Path(project) / 'skills' if project else None


def project_skill_root_for(path):
    """从 SKILL 文件路径反推项目层根：祖先名为 ``skills`` 且其父级是项目根
    （含 ``skill_config.json``）才算；程序内 skills 树与自检临时目录不误判。"""
    candidate = Path(path) if path else None
    if candidate is None:
        return None
    for parent in candidate.parents:
        if parent.name != 'skills':
            continue
        if (parent.parent / SKILL_CONFIG_NAME).is_file():
            return parent.resolve()
    return None


# 层名 → 中文层名（遮蔽警告与界面展示共用同一措辞）。
LAYER_LABELS = {'project': '项目版', 'user': '用户版', 'builtin': '内置版'}
# 层名 → 优先级名次（小者优先）：scan 排序与遮蔽判定共用。
LAYER_ORDER = {'project': 0, 'user': 1, 'builtin': 2}


class ProjectLayerMixin:
    """Registry 的按层阶段目录口径：``scope`` ∈ ``'project'``／``'user'``。

    依赖宿主提供 ``_stage_directory_for``／``_stage_directories``／``user_root``／
    ``project_skills``；项目层缺位时 ``'project'`` 一律返回 None，调用方退回用户层。
    """

    def project_stage_directory_for(self, sid):
        """项目层写入目录：``<项目>/skills/<同名阶段目录>``；没有项目层返回 None。"""
        return self._layer_stage_directory_for(sid, 'project')

    def stage_directory_for(self, sid, scope='user'):
        """按层取阶段写入目录：``scope`` ∈ ``'project'``／``'user'``。"""
        if scope == 'project':
            return self.project_stage_directory_for(sid)
        if scope == 'user':
            return self.user_stage_directory_for(sid)
        raise ValueError('未知的 SKILL 导入层：%s' % scope)

    def _layer_stage_directory_for(self, sid, layer):
        builtin = self._stage_directory_for(sid)
        root = {'user': self.user_root, 'project': self.project_skills}.get(layer)
        if builtin is None or root is None:
            return builtin if layer == 'user' else None
        existing = next((path for path in self._stage_directories(root)
                         if stage_from_path(path / '__stage_probe__') == sid), None)
        return existing or root / builtin.name
