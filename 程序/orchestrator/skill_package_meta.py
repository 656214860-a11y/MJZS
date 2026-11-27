# -*- coding: utf-8 -*-
"""外部 SKILL 包受控元数据（R3097／生命周期任务书 T9）。

从 ``skill_registry`` 拆出（模块行数棘轮）：``imported_package_meta`` 及其依赖的
``markdown_heading``／``markdown_summary``／``IMPORTED_PACKAGE_FLAG`` 本属注册表，
现集中在本模块；``skill_registry`` 原样 re-export，调用方路径不变。
阶段判定 ``stage_from_path`` 的唯一权威在 ``skill_project_layer``（L3 同层引用，
无循环）。
"""
import re

from pathlib import Path

from orchestrator.skill_project_layer import stage_from_path

IMPORTED_PACKAGE_FLAG = '_imported_package'
PACKAGE_ROOT_KEY = '_package_root'
COMPOSITE_SUITE_FLAG = '_composite_suite'
PRIMARY_SUBSKILL_KEY = '_primary_subskill'
_PRIMARY_SUBDIR_HINTS = (
    'director', 'orchestrator', 'master', 'router', 'controller',
    '总控', '主控', 'main', 'core',
)


def detect_composite_suite_entry(package):
    """识别复合技能套装（根无 SKILL.md，但含 ≥2 个并列子目录各含 SKILL.md）。

    命中返回 ``(主入口 SKILL.md 路径, 主入口子目录名)``；普通单根包或非套装返回 ``None``。
    主入口优先级：目录名含总控/director 等特征 → 根 README 标示 L0/总控指向的子目录 → 首个子目录。
    """
    package = Path(package)
    try:
        if not package.is_dir() or (package / 'SKILL.md').is_file():
            return None
        children = sorted(
            (child for child in package.iterdir()
             if child.is_dir() and not child.name.startswith('.')
             and child.name != '__pycache__' and (child / 'SKILL.md').is_file()),
            key=lambda p: p.name.casefold(),
        )
    except OSError:
        return None
    if len(children) < 2:
        return None
    for child in children:
        lower = child.name.casefold()
        if any(hint in lower for hint in _PRIMARY_SUBDIR_HINTS):
            return child / 'SKILL.md', child.name
    for readme_name in ('README.md', 'README.MD', 'readme.md'):
        readme = package / readme_name
        if readme.is_file():
            try:
                text = readme.read_text(encoding='utf-8-sig')[:16000]
            except (OSError, UnicodeError):
                text = ''
            for child in children:
                if re.search(r'(?:L0|总控|主入口|router)[^\n]{0,60}' + re.escape(child.name),
                             text, flags=re.IGNORECASE):
                    return child / 'SKILL.md', child.name
            break
    return children[0] / 'SKILL.md', children[0].name


def unwrap_package_container(root):
    """剥离仓库压缩包常见的单层顶壳目录（如 GitHub codeload 解出的 ``repo-main/``）。"""
    current = Path(root)
    for _ in range(2):
        try:
            entries = [p for p in current.iterdir()
                       if not p.name.startswith('.') and p.name != '__pycache__']
        except OSError:
            break
        if any(p.is_file() and (p.name.casefold() == 'skill.md' or p.name.endswith('.skill.md'))
               for p in entries):
            break
        dirs = [p for p in entries if p.is_dir()]
        files = [p for p in entries if p.is_file()]
        if len(dirs) == 1 and not files:
            current = dirs[0]
            continue
        break
    return current


def detect_stage_free_suite(root, *, parse_fn, stage_id_fn, valid_stages):
    """检测剥壳后的目录是否为“无显式 01-13 阶段声明的多子技能复合总包”；命中返回 ``(package_root, primary_entry)``。"""
    effective = unwrap_package_container(Path(root))
    composite = detect_composite_suite_entry(effective)
    if composite is None:
        return None
    primary_entry, _primary_name = composite
    stages_set = set(valid_stages or ())
    for child in sorted(effective.iterdir(), key=lambda p: p.name.casefold()):
        if not child.is_dir() or child.name.startswith('.'):
            continue
        skill_md = child / 'SKILL.md'
        if not skill_md.is_file():
            continue
        if stage_from_path(skill_md):
            return None
        try:
            meta, _ = parse_fn(skill_md.read_text(encoding='utf-8-sig'), source=str(skill_md))
        except (OSError, UnicodeError):
            meta = {}
        if stage_id_fn(meta.get('stage', '')) in stages_set:
            return None
    return effective, primary_entry


def clean_suite_name(root, hint=''):
    """为复合套装或仓库推导干净的安装目录名（如 ``manju-laoli-skill``）。"""
    raw = str(hint or '').strip()
    if raw:
        raw = raw.split('@', 1)[0].rstrip('/\\')
        raw = raw.rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
        if raw.lower().endswith('.git'):
            raw = raw[:-4]
        if raw.lower().endswith('.zip'):
            raw = raw[:-4]
    if not raw or raw.startswith('.仓库克隆-') or raw.startswith('.压缩包解压-'):
        raw = Path(root).name
    raw = re.sub(r'-(?:HEAD|main|master)$', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', raw).strip(' .')
    return (raw or 'skill-suite')[:80]


def package_root_of(skill):
    """返回技能包的真实根目录（复合套装返回总包根而非 L0 子目录）。"""
    if skill is None:
        return None
    stored = getattr(skill, 'get', lambda *_a: '')(PACKAGE_ROOT_KEY, '')
    if stored:
        return Path(stored)
    path = getattr(skill, 'path', None)
    return Path(path).parent if path is not None else None


def markdown_heading(body):
    """取 Markdown 首个一级标题，供无 frontmatter 的外部包显示。"""
    match = re.search(r'^\s*#\s+(.+?)\s*$', str(body or ''), flags=re.MULTILINE)
    return match.group(1).strip() if match else ''


def markdown_summary(body):
    """取 Markdown 的首句说明；外部资料没有简介时也能在面板里说明来源。"""
    for line in str(body or '').splitlines():
        text = line.strip()
        if text and not text.startswith(('#', '---', '```', '-', '*')):
            return text[:160]
    return ''


def _external_list(meta, *keys):
    """frontmatter 可选字段 → 扁平字符串列表：内联表、块列表与单值都认。"""
    for key in keys:
        value = (meta or {}).get(key)
        if value in (None, ''):
            continue
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()]
    return []


def imported_package_meta(source_meta, body, package, source, known_tools=()):
    """为阶段目录下的外部 SKILL 包建立一个受控总入口元数据。

    外部 ``SKILL.md`` 多为 Codex/Claude 的轻量格式，不满足本程序的完整 frontmatter
    契约；这里不信任其执行字段，仅复用可读名称/简介和正文，其余字段采用稳定默认值。
    T9：``license``／``compatibility`` 原样保留进 meta 供说明区展示；``allowed-tools``
    只把 ``known_tools``（内置层声明的工具名集）里的名字映射进 ``tools``，其余进
    ``constraints`` 提示——不硬猜、不放宽 17 字段契约。
    """
    source_meta = source_meta or {}
    title = (str(source_meta.get('displayName', '') or '').strip() or
             markdown_heading(body) or package.name)
    description = (str(source_meta.get('description', '') or '').strip() or
                   markdown_summary(body) or
                   '外部 SKILL 包总入口：%s' % title)
    constraints = ['这是外部 SKILL 包的总入口，不自动展开其内部子 SKILL。']
    allowed = _external_list(source_meta, 'allowed-tools', 'allowed_tools')
    known = {str(tool) for tool in known_tools or ()}
    mapped = [tool for tool in allowed if tool in known]
    unmapped = [tool for tool in allowed if tool not in known]
    if unmapped:
        constraints.append('外部包声明 allowed-tools：%s；本应用无对应工具，仅作提示不映射。'
                           % '、'.join(unmapped))
    try:
        composite = Path(source).resolve().parent != Path(package).resolve()
    except OSError:
        composite = Path(source).parent != Path(package)
    pkg_name = package.name if composite else (str(source_meta.get('name', '') or '').strip() or package.name)
    meta = {
        'name': pkg_name,
        'displayName': title,
        'description': description,
        'stage': stage_from_path(source),
        'capabilities': ['creative-writing'],
        'preferredModels': [],
        'fallbackModels': [],
        'tools': mapped,
        'dependsOn': [],
        'conflictsWith': [],
        'parallelizable': False,
        'paid': False,
        'input': [],
        'output': [],
        'constraints': constraints,
        'feedback': [],
        'examples': [],
        IMPORTED_PACKAGE_FLAG: True,
        PACKAGE_ROOT_KEY: str(package),
    }
    if composite:
        meta[COMPOSITE_SUITE_FLAG] = True
        meta[PRIMARY_SUBSKILL_KEY] = Path(source).parent.name
    for key in ('license', 'compatibility'):
        value = source_meta.get(key)
        if value not in (None, ''):
            meta[key] = value if isinstance(value, (list, tuple)) else str(value)
    return meta
