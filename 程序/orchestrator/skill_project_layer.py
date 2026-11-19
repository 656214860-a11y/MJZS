"""SKILL 层与阶段目录的路径口径（R3054／生命周期任务书 T5）。

``<项目>/skills/`` 随项目走、归用户所有；``skill_registry.Registry`` 经
:class:`ProjectLayerMixin` 获得按层取阶段写入目录的口径。模块级
``project_skill_root``／``project_skill_root_for`` 供引用解析、发送白名单
与面板反推项目层根；``STAGE_DIRECTORY_IDS``／``stage_from_path`` 是阶段目录
→ 阶段 id 的物理归档口径，层分派与注册表扫描共用。项目根只在打开阶段面板／
配置时注入，启动路径零扫描。
"""
import re
import time
from pathlib import Path

from infra.file_cache import read_json
from contract.stage_layout import SKILL_CONFIG_NAME

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

# ── 禁用登记（R3090／生命周期任务书 T8）────────────────────────────────
# ``data/skills/disabled_skills.json``：禁用不进 ``getAll()`` 但文件保留，
# 删除条目即恢复；内置层只读不提供禁用。键 ``user|<name>`` 全局生效，
# ``project|<项目路径>|<name>`` 只对该项目生效（项目层 SKILL 不跨项目泄漏）。
DISABLED_SKILLS_NAME = 'disabled_skills.json'


def disabled_skills_path(user_root):
    """禁用登记文件：与用户层同根（``data/skills/``），升级安装保留、扫描器不认 .json。"""
    return Path(user_root) / DISABLED_SKILLS_NAME if user_root else None


def _disabled_key(layer, name, project=''):
    if layer == 'project' and project:
        return 'project|%s|%s' % (str(Path(project).resolve()), name)
    return '%s|%s' % (layer, name)


def load_disabled(user_root):
    """禁用登记 → ``{键: 条目}``；文件缺失/损坏一律按空表（不阻塞扫描）。"""
    path = disabled_skills_path(user_root)
    if path is None or not path.is_file():
        return {}
    try:
        data = read_json(path)
    except (OSError, ValueError):
        return {}
    items = data.get('items') if isinstance(data, dict) else None
    return dict(items) if isinstance(items, dict) else {}


def disabled_stamp(user_root):
    """禁用登记文件 ``(mtime_ns, size)``；缺失或不可读返回 ``None``。

    登记文件在 ``data/skills/`` 根下，内容改写不改阶段目录组合键，
    必须单独盯——否则 ``FRESH_TTL`` 热窗口内禁用/启用不生效。
    """
    path = disabled_skills_path(user_root)
    if path is None:
        return None
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def disabled_view_entries(user_root, project_root=None):
    """本视图下禁用登记的条目原文（含 layer／project），供管理页灰显。"""
    project_key = str(Path(project_root).resolve()) if project_root else ''
    return tuple(
        dict(entry) for entry in load_disabled(user_root).values()
        if isinstance(entry, dict)
        and ((entry.get('layer') in ('builtin', 'user'))
             or (entry.get('layer') == 'project'
                 and str(entry.get('project') or '') == project_key)))


def disabled_pairs(user_root, project_root=None):
    """本注册表视图下被禁用的 ``(layer, name)`` 集合：内置／用户全局项＋本项目项。

    内置层禁用只登记、不删除文件；项目层条目只在 ``project`` 与本注册表项目根一致时生效，
    避免 A 项目禁用的 SKILL 泄漏到 B 项目视图。
    """
    project = str(Path(project_root).resolve()) if project_root else ''
    pairs = set()
    for entry in load_disabled(user_root).values():
        if not isinstance(entry, dict):
            continue
        layer, name = str(entry.get('layer') or ''), str(entry.get('name') or '')
        if not name or layer not in ('builtin', 'user', 'project'):
            continue
        owner = str(entry.get('project') or '')
        if layer == 'project' and owner != project:
            continue
        pairs.add((layer, name))
    return pairs


def disabled_names(user_root, project_root=None):
    """本注册表视图下被禁用的 SKILL 名集合（管理页展示用，不分层）。"""
    return {name for _, name in disabled_pairs(user_root, project_root)}


def set_disabled(user_root, layer, name, project='', disabled=True, path='', save=None):
    """写禁用登记（读改写）；``save`` 注入正式 JSON 写入口，缺省用 ``agent.core.save``。

    返回写后的条目 dict；``disabled=False`` 时摘除条目（幂等）。内置层只登记禁用。
    ``path`` 记录条目文件位置，供已禁用 SKILL 的重命名／编辑／删除定位。
    """
    if layer not in ('builtin', 'user', 'project'):
        raise ValueError('未知 SKILL 层，不能禁用')
    name = str(name or '').strip()
    if not name:
        raise ValueError('SKILL 名不能为空')
    file_path = disabled_skills_path(user_root)
    if file_path is None:
        raise ValueError('没有用户层目录，无法登记禁用')
    if save is None:
        from agent.core import save as _save
        save = _save
    items = load_disabled(user_root)
    key = _disabled_key(layer, name, project)
    if disabled:
        items[key] = {'layer': layer, 'name': name,
                      'project': str(Path(project).resolve()) if project else '',
                      'path': str(path or ''),
                      'disabled_at': time.strftime('%Y-%m-%d %H:%M:%S')}
    else:
        items.pop(key, None)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    save(file_path, {'version': 1, 'items': items})
    return items.get(key)


def rename_disabled(user_root, old_name, new_name, layer='', project='', new_path=''):
    """禁用登记随 SKILL 改名同步：匹配旧名（可选限定层与项目）的条目换名并改写路径。

    返回是否有条目被改写；无匹配时不动文件。``layer``/``project`` 为空表示不限，
    避免同名跨层条目被误改。
    """
    items = load_disabled(user_root)
    changed = False
    for key, entry in list(items.items()):
        if not isinstance(entry, dict) or str(entry.get('name') or '') != old_name:
            continue
        entry_layer = str(entry.get('layer') or '')
        entry_project = str(entry.get('project') or '')
        if layer and entry_layer != layer:
            continue
        if project and entry_project != str(Path(project).resolve()):
            continue
        updated = dict(entry)
        updated['name'] = new_name
        if new_path:
            updated['path'] = str(new_path)
        items.pop(key)
        items[_disabled_key(entry_layer, new_name, entry_project)] = updated
        changed = True
    if changed:
        file_path = disabled_skills_path(user_root)
        if file_path is not None:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            from agent.core import save as _save
            _save(file_path, {'version': 1, 'items': items})
    return changed


class ProjectLayerMixin:
    """Registry 的按层阶段目录口径：``scope`` ∈ ``'project'``／``'user'``。

    依赖宿主提供 ``_stage_directory_for``／``_stage_directories``／``user_root``／
    ``project_skills``／``_fresh``／``_disabled_pairs``／``_disabled_entries``；
    项目层缺位时 ``'project'`` 一律返回 None，调用方退回用户层。
    """

    def disabled_names(self):
        """本视图下被禁用的 SKILL 名集合（不进 ``getAll()``，文件仍在盘上）。"""
        self._fresh()
        return {name for _, name in self._disabled_pairs}

    def disabled_entries(self):
        """本视图下禁用登记的原始条目（含 layer／project），供管理页灰显。"""
        self._fresh()
        return [dict(entry) for entry in self._disabled_entries]

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


def scan_residue(program, *, package_source):
    """管理通道：注入唯一阶段判定与调用方已有的包定位器，避免注册表环依赖。"""
    from domain import skill_residue_service
    return skill_residue_service.scan_residue(
        program, stage_from_path=stage_from_path, package_source=package_source)


def dispose_residue(program, names, *, package_source):
    """L3 组装回收发布器；L2 不反向依赖注册表或自行写回收凭据。"""
    from domain import skill_residue_service
    from infra.storage_maintenance import recycle_paths
    return skill_residue_service.dispose_residue(
        program, names, stage_from_path=stage_from_path,
        package_source=package_source, publisher=recycle_paths)
