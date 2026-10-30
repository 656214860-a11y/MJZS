# -*- coding: utf-8 -*-
"""SKILL 规范与注册表：扫描 01—13 阶段目录及阶段总入口，解析并建索引。

两层目录：内置层 ``程序/skills/``（随程序分发，升级会覆盖）与用户层
``程序/data/skills/``（「新增 SKILL」的导入目标，升级保留）。两层阶段目录同构；
同名时用户版优先，内置版只记一条软提示，删除用户版后内置版自动恢复。

用户附件（第 28 期）规定的规范：每个 SKILL 一个 Markdown 文件，YAML frontmatter 字段固定为
name／displayName／description／stage／capabilities／preferredModels／fallbackModels／tools／
dependsOn／conflictsWith／parallelizable／paid／input／output／constraints／feedback／examples。

这里只做四件事：
1. 解析——运行环境只有标准库（没有 PyYAML），所以只认规格里出现过的那几种形状：标量、
   行内列表 [a, b]、「- 条目」列表、「- 键: 值」映射列表；
2. 校验——常规 ``.skill.md`` 严格校验字段及文件名；阶段目录下的外部包以一个总入口
   受控补齐元数据，避免把包内子 SKILL 无差别铺进面板；
3. 索引——getById／getByStage／getAll；
4. 热加载——每次查询前比对「文件名＋修改时间＋大小」的指纹；用户打开阶段配置后新放入
   阶段目录的 ``.skill.md`` 或 ``SKILL.md`` 包即可出现。根目录遗留的 ``.skill.md``
   会按 frontmatter 的 stage 一次性归档到对应阶段目录；启动路径不扫描目录。
"""
import re
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

from pet_bus import STAGES, STAGE_NAMES

SKILL_SUFFIX = '.skill.md'
PACKAGE_SKILL_FILENAME = 'SKILL.md'
PACKAGE_README_FILENAMES = ('README_ZH.md', 'README.md', 'README.MD')
IMPORTED_PACKAGE_FLAG = '_imported_package'
CAPABILITIES = ('long-context', 'structured-output', 'creative-writing', 'reasoning', 'vision')
FEEDBACK_KEYS = ('onProgress', 'onError', 'onComplete')
REQUIRED = ('name', 'displayName', 'description', 'stage', 'capabilities', 'preferredModels',
            'fallbackModels', 'tools', 'dependsOn', 'conflictsWith', 'parallelizable', 'paid',
            'input', 'output', 'constraints', 'feedback', 'examples')
LIST_FIELDS = ('capabilities', 'preferredModels', 'fallbackModels', 'tools', 'dependsOn',
               'conflictsWith', 'input', 'output', 'constraints', 'examples')
BOOL_FIELDS = ('parallelizable', 'paid')

# 查询常发生在同一轮 Tk 控件建造中。两秒内目录不可能被用户连续编辑到需要
# 反复 stat；保留这个极短时间片可消除启动查询风暴，手动强制扫描仍立即生效。
FRESH_TTL_SECONDS = 2.0

# 阶段文件夹是 SKILL 的物理归档口径。前置零的编号必须与 12 阶段顺序保持一致；
# 新放入 01—12 文件夹但尚未补 frontmatter 的 SKILL 可据此立即出现在正确阶段。
STAGE_DIRECTORY_IDS = {
    '01': 'script', '02': 'script_structure', '03': 'storyboard',
    '04': 'animatic', '05': 'assets', '06': 'continuity', '07': 'final',
    '08': 'keyframe', '09': 'previs', '10': 'video',
    '11': 'audio', '12': 'edit', '13': 'delivery',
}


def default_root(program=None):
    """SKILL 目录：默认与程序同一个盘位下的 skills/（可用参数或参数覆盖，方便自检）。"""
    return Path(program or Path(__file__).resolve().parent) / 'skills'


def default_user_root(program=None):
    """用户 SKILL 目录：``程序/data/skills/``，与内置 skills/ 同构，升级安装保留。"""
    return Path(program or Path(__file__).resolve().parent) / 'data' / 'skills'


def skill_roots(program=None):
    """引用允许落在的 SKILL 根目录（内置层、用户层），均为 resolve 后的绝对路径。"""
    return (default_root(program).resolve(), default_user_root(program).resolve())


def resolve_reference(source, relative, program=None):
    """解析 SKILL 正文里的相对引用。

    用户层与内置层同构：用户层 SKILL 引用 ``../00全流程SKILL/…`` 这类内置共享资料时，
    用户层没有该文件就退回内置层同一相对位置；两层都没有时返回原解析结果，由调用方报缺失。
    """
    target = (Path(source).parent / relative).resolve()
    builtin, user = skill_roots(program)
    if not target.exists() and target.is_relative_to(user):
        fallback = builtin / target.relative_to(user)
        if fallback.exists():
            return fallback
    return target


def stage_id(value):
    """阶段名 → 阶段 id：中英文都收（frontmatter 可写中文名，程序使用阶段 id）。"""
    text = str(value or '').strip()
    if text in STAGES:
        return text
    for sid in STAGES:
        if STAGE_NAMES.get(sid) == text:
            return sid
    return ''


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


def imported_package_meta(source_meta, body, package, source):
    """为阶段目录下的外部 SKILL 包建立一个受控总入口元数据。

    外部 ``SKILL.md`` 多为 Codex/Claude 的轻量格式，不满足本程序的完整 frontmatter
    契约；这里不信任其执行字段，仅复用可读名称/简介和正文，其余字段采用稳定默认值。
    """
    source_meta = source_meta or {}
    title = (str(source_meta.get('displayName', '') or '').strip() or
             markdown_heading(body) or package.name)
    description = (str(source_meta.get('description', '') or '').strip() or
                   markdown_summary(body) or
                   '外部 SKILL 包总入口：%s' % title)
    return {
        'name': str(source_meta.get('name', '') or '').strip() or package.name,
        'displayName': title,
        'description': description,
        'stage': stage_from_path(source),
        'capabilities': ['creative-writing'],
        'preferredModels': [],
        'fallbackModels': [],
        'tools': [],
        'dependsOn': [],
        'conflictsWith': [],
        'parallelizable': False,
        'paid': False,
        'input': [],
        'output': [],
        'constraints': ['这是外部 SKILL 包的总入口，不自动展开其内部子 SKILL。'],
        'feedback': [],
        'examples': [],
        IMPORTED_PACKAGE_FLAG: True,
    }


def scalar(text):
    """一个 frontmatter 标量：去引号、认布尔与整数，其余按字符串。"""
    value = str(text).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('\'', '"'):
        value = value[1:-1]
    low = value.lower()
    if low in ('true', 'yes'):
        return True
    if low in ('false', 'no'):
        return False
    if low in ('null', '~', ''):
        return ''
    if low.lstrip('-').isdigit():
        return int(low)
    return value


def inline_list(text):
    """[a, b, c] → [a, b, c]；[] → []；认不出来就返回 None（交给调用方当标量处理）。"""
    body = str(text).strip()
    if not (body.startswith('[') and body.endswith(']')):
        return None
    inner = body[1:-1].strip()
    if not inner:
        return []
    return [scalar(item) for item in inner.split(',') if item.strip() != '']


def split_pair(line):
    """一行里的 key: value；没有冒号（或冒号在引号里）时返回 None。"""
    text = line.strip()
    if text.startswith('- '):
        text = text[2:].strip()
    quote = ''
    for index, char in enumerate(text):
        if quote:
            if char == quote:
                quote = ''
            continue
        if char in ('\'', '"'):
            quote = char
            continue
        if char == ':':
            return text[:index].strip(), text[index + 1:].strip()
    return None


def list_pair(text):
    """「- 键: 值」里的键必须是个标识符（onProgress 那样）。

    示例行里也有冒号——`- 用户："…" → batchGenerate({ scope: 'missing' })` 的那个冒号在
    花括号里，前面还夹着中文与空格，按标识符一卡就不会被误当成映射。
    """
    pair = split_pair(text)
    if pair is None:
        return None
    return pair if re.match(r'^[A-Za-z_][A-Za-z0-9_\-]*$', pair[0]) else None


def parse(text, source=''):
    """解析一份 .skill.md：返回 (meta, body)。frontmatter 缺了开头的 --- 就当空表。"""
    raw = str(text).lstrip('\ufeff').replace('\r\n', '\n').replace('\r', '\n')
    lines = raw.split('\n')
    if not lines or lines[0].strip() != '---':
        return {}, raw
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == '---':
            end = index
            break
    if end is None:
        return {}, ''
    meta, entries, block, pending, fold = {}, [], None, None, ' '
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            pair = split_pair(line)
            if pair is None:
                continue
            key, value = pair
            items = inline_list(value)
            # 与 skill_notes.reading_text 识别同一组块标量指示符，避免简介丢失。
            if value in ('>', '>-', '>+', '|', '|-', '|+'):
                block, pending, fold = str, '', ('\n' if value.startswith('|') else ' ')
                meta[key] = pending
            elif value == '':
                block = list if key in LIST_FIELDS or key == 'feedback' else str
                pending = [] if block is list else ''
                fold = ' '
                meta[key] = pending
            elif items is not None:
                meta[key] = items
                pending, block = None, None
            else:
                meta[key] = scalar(value)
                pending, block = None, None
            entries.append(key)
            continue
        if pending is None:
            continue
        if block is list:
            if line.strip().startswith('- '):
                rest = line.strip()[2:].strip()
                pair = list_pair(rest)
                if pair is not None:
                    pending.append({pair[0]: scalar(pair[1])})
                else:
                    pending.append(scalar(rest))
                continue
            if pending and isinstance(pending[-1], dict):
                pair = list_pair(line)
                if pair is not None:
                    pending[-1][pair[0]] = scalar(pair[1])
                    continue
            continue
        pending = (str(pending) + fold + line.strip()).strip()
        meta[entries[-1]] = pending
    body = '\n'.join(lines[end + 1:]).strip()
    return meta, body


class Skill:
    """一个 SKILL：frontmatter 的字段原样挂成属性，取值统一在 get()／列表字段上兜底。"""

    def __init__(self, meta, body='', path=None, layer=''):
        self.meta = dict(meta)
        self.body = body
        self.path = Path(path) if path else None
        # 'builtin'＝程序 skills/，'user'＝data/skills/；注册表外直接构造的为空串。
        self.layer = layer

    def get(self, key, default=None):
        value = self.meta.get(key, default)
        return default if value is None else value

    @property
    def name(self):
        return str(self.get('name', ''))

    @property
    def displayName(self):
        return str(self.get('displayName', ''))

    @property
    def description(self):
        return str(self.get('description', ''))

    @property
    def stage(self):
        # 01—12 分类是阶段配置的归档依据；根目录或资料包仍保留 frontmatter 兼容。
        return stage_from_path(self.path) or stage_id(self.get('stage', ''))

    @property
    def capabilities(self):
        return list(self.get('capabilities', []) or [])

    @property
    def preferredModels(self):
        return list(self.get('preferredModels', []) or [])

    @property
    def fallbackModels(self):
        return list(self.get('fallbackModels', []) or [])

    @property
    def tools(self):
        return list(self.get('tools', []) or [])

    @property
    def dependsOn(self):
        return list(self.get('dependsOn', []) or [])

    @property
    def conflictsWith(self):
        return list(self.get('conflictsWith', []) or [])

    @property
    def input(self):
        return list(self.get('input', []) or [])

    @property
    def output(self):
        return list(self.get('output', []) or [])

    @property
    def constraints(self):
        return list(self.get('constraints', []) or [])

    @property
    def examples(self):
        return list(self.get('examples', []) or [])

    @property
    def feedback(self):
        return list(self.get('feedback', []) or [])

    @property
    def parallelizable(self):
        return bool(self.get('parallelizable', False))

    @property
    def paid(self):
        return bool(self.get('paid', False))

    @property
    def deprecated(self):
        """旧 SKILL 的兼容标记：仍可从旧项目配置读到，但不再作为新项目默认项。"""
        return bool(self.get('deprecated', False))

    @property
    def replacedBy(self):
        """被合并后的主 SKILL id；空值表示这不是兼容别名。"""
        return str(self.get('replacedBy', '') or '').strip()

    def feedback_kinds(self):
        """onProgress／onError／onComplete 里声明了哪几个。"""
        return tuple(key for item in self.feedback if isinstance(item, dict)
                     for key in item if key in FEEDBACK_KEYS)

    def __repr__(self):
        return 'Skill(%s @ %s)' % (self.name, self.stage)


def validate_skill(skill, known=()):
    """单个 SKILL 的字段问题（不牵扯别的 SKILL 的那几条）。"""
    out, meta = [], skill.meta
    for key in REQUIRED:
        if key not in meta:
            out.append('%s：缺字段 %s' % (skill.name or skill.path, key))
    for key in LIST_FIELDS:
        if key in meta and not isinstance(meta[key], list):
            out.append('%s：%s 应当是列表' % (skill.name or skill.path, key))
    for key in BOOL_FIELDS:
        if key in meta and not isinstance(meta[key], bool):
            out.append('%s：%s 应当是 true／false' % (skill.name or skill.path, key))
    for value in skill.capabilities:
        if value not in CAPABILITIES:
            out.append('%s：capabilities 里有没登记的能力 %s' % (skill.name, value))
    stage = skill.stage
    if not stage:
        out.append('%s：stage 认不出（%s）' % (skill.name or skill.path, meta.get('stage')))
    folder_stage = stage_from_path(skill.path)
    declared_stage = stage_id(meta.get('stage', ''))
    if folder_stage and declared_stage and folder_stage != declared_stage:
        out.append('%s：阶段目录与 frontmatter stage 不一致' % skill.name)
    for item in skill.feedback:
        if not isinstance(item, dict):
            out.append('%s：feedback 每一项都是「- 键: 值」' % skill.name)
            continue
        for key in item:
            if key not in FEEDBACK_KEYS:
                out.append('%s：feedback 里有没登记的键 %s' % (skill.name, key))
    for value in skill.preferredModels + skill.fallbackModels:
        if not isinstance(value, str) or not value.strip():
            out.append('%s：模型名不能为空' % skill.name)
    if (skill.name and skill.path is not None and
            not skill.get(IMPORTED_PACKAGE_FLAG, False)):
        stem = skill.path.name
        if stem.endswith(SKILL_SUFFIX):
            stem = stem[:-len(SKILL_SUFFIX)]
        if stem != skill.name:
            out.append('%s：name 与文件名不一致（文件叫 %s）' % (skill.name, stem))
    for other in skill.dependsOn:
        if other == skill.name:
            out.append('%s：不能依赖自己' % skill.name)
    for other in skill.conflictsWith:
        if other == skill.name:
            out.append('%s：不能和自己冲突' % skill.name)
        elif known and other not in known:
            out.append('%s：冲突里的 %s 不存在' % (skill.name, other))
    for other in set(skill.dependsOn) & set(skill.conflictsWith):
        out.append('%s：既依赖又冲突（%s）' % (skill.name, other))
    return out


REFERENCE_SUFFIXES = ('.md', '.txt')

# 行内链接：可选尖括号包裹、可选标题；只做文本解析，不碰文件系统。
_LINK_RE = re.compile(r'\]\(\s*(<[^>]+>|[^)]+)\s*\)')


def reference_targets(text):
    """Markdown 行内链接的目标，按出现顺序返回。

    kind 区分：markdown（可内联的 .md／.txt 文档引用）、other（图片、脚本等资源或工具）、
    remote（带协议或主机名的外部地址）、anchor（纯锚点）。path 为未解析的相对路径。
    """
    out = []
    for match in _LINK_RE.finditer(text or ''):
        link = match.group(1).strip()
        if link.startswith('<'):
            link = link[1:-1]
        else:
            link = re.sub(r'''\s+["'][^"']*["']\s*$''', '', link)
        parts = urlsplit(link.replace('\\', '/'))
        if parts.scheme or parts.netloc:
            out.append({'raw': link, 'kind': 'remote', 'path': None})
            continue
        if not parts.path:
            out.append({'raw': link, 'kind': 'anchor', 'path': None})
            continue
        relative = Path(unquote(parts.path))
        kind = 'markdown' if relative.suffix.lower() in REFERENCE_SUFFIXES else 'other'
        out.append({'raw': link, 'kind': kind, 'path': relative, 'fragment': parts.fragment,
                    'start': match.start()})
    return out


def classify_dependencies(skill, known=()):
    """把 dependsOn 拆成两类：在册的技能依赖，与未在册的外部子模块／步骤。

    规格里的 asset-auto-fill 就依赖 asset-search／asset-rank／asset-dedupe／asset-candidate-wall
    这几步子模块（不是 SKILL），所以「外部」不算错误，只如实列出。
    """
    registered, external = [], []
    for other in skill.dependsOn:
        if other == skill.name:
            continue
        (registered if other in known else external).append(other)
    return {'skill': registered, 'external': external}


def dependency_report(skill, known=()):
    """一个 SKILL 的依赖面：技能依赖、外部子模块／步骤、可执行工具（tools 字段）。"""
    kinds = classify_dependencies(skill, known)
    return {'skill': kinds['skill'], 'external': kinds['external'],
            'tools': [str(item) for item in skill.tools]}


def external_references(skill, known=()):
    """dependsOn 里不在注册表里的名字（子模块／外部步骤）：不算错，只如实列出。"""
    return classify_dependencies(skill, known)['external']


class Registry:
    """SKILL 注册表：扫目录 → 解析 → 校验 → 建索引；查询前自动热加载。"""

    def __init__(self, root=None, clock=time.time, user_root=None):
        self.root = Path(root) if root else default_root()
        # 不给 root 时用户层跟随程序目录；显式给 root（自检临时目录）时只有给了 user_root 才有用户层。
        self.user_root = (Path(user_root) if user_root else
                          (default_user_root() if root is None else None))
        self.clock = clock
        self._skills = {}
        self._problems = []
        self._warnings = []
        self._fingerprint = None
        # 根目录、阶段目录和阶段下的总入口目录都未变时，文件清单与其指纹才可复用。
        # 常规查询只 stat 两层目录，不重新 rglob 整棵 skills 树。
        self._directory_mtime_ns = None
        self._child_directory_mtimes = None
        self._directory_cache_key = None
        self._file_records = None
        self._root_migration_problems = ()
        self._root_manifests_migrated = False
        self._fingerprint_cache = None
        self._fingerprint_checked_at = 0.0
        self._fresh_checked_at = 0.0

    # ── 扫描 ────────────────────────────────────────────────────────────────
    def _layers(self):
        """``(根目录, 层名)``，用户层在前；用户层目录不存在时照常跳过。"""
        layers = [(self.root, 'builtin')]
        if self.user_root is not None:
            layers.insert(0, (self.user_root, 'user'))
        return tuple(layers)

    def _stage_directories(self, root=None):
        """只返回 SKILL 根目录下直接对应 01—13 的目录，不猜测其他资料目录。"""
        root = self.root if root is None else root
        try:
            entries = sorted(root.iterdir(), key=lambda path: str(path))
        except OSError:
            return ()
        return tuple(path for path in entries
                     if path.is_dir() and stage_from_path(path / '__stage_probe__'))

    def _stage_directory_for(self, sid):
        """返回阶段 id 对应的物理归档目录；缺目录时不猜测也不新建。"""
        return next((path for path in self._stage_directories()
                     if stage_from_path(path / '__stage_probe__') == sid), None)

    def user_stage_directory_for(self, sid):
        """「新增 SKILL」的写入目录：用户层同名阶段目录（不存在时由导入方新建）。

        目录名沿用内置阶段目录，保证两层同构；没有用户层的注册表（自检临时目录）退回内置目录。
        """
        builtin = self._stage_directory_for(sid)
        if builtin is None or self.user_root is None:
            return builtin
        existing = next((path for path in self._stage_directories(self.user_root)
                         if stage_from_path(path / '__stage_probe__') == sid), None)
        return existing or self.user_root / builtin.name

    def _migrate_root_manifests(self):
        """把 skills 根目录的旧 .skill.md 移入其 frontmatter 指定的阶段目录。

        这是打开阶段配置后的懒迁移：只枚举根目录的一层文件，绝不触碰 00 全流程包、
        其他资料包或用户项目。没有合法 stage、目标目录或同名目标时保留原文件并报明原因。
        """
        problems = []
        try:
            paths = sorted(self.root.glob('*' + SKILL_SUFFIX), key=lambda path: str(path))
        except OSError:
            self._root_migration_problems = ()
            return
        for path in paths:
            try:
                meta, _ = parse(path.read_text(encoding='utf-8-sig'), source=str(path))
            except (OSError, UnicodeError) as exc:
                problems.append('%s：根目录遗留 SKILL 读不出来（%s）' % (path.name, exc))
                continue
            sid = stage_id(meta.get('stage', ''))
            if not sid:
                problems.append('%s：根目录遗留 SKILL 没有可识别的阶段 stage，未自动归档' % path.name)
                continue
            target_dir = self._stage_directory_for(sid)
            if target_dir is None:
                problems.append('%s：阶段 %s 没有对应目录，未自动归档' % (path.name, sid))
                continue
            target = target_dir / path.name
            if target.exists():
                problems.append('%s：目标 %s 已存在，未覆盖也未自动归档' %
                                (path.name, target.name))
                continue
            try:
                path.replace(target)
            except OSError as exc:
                problems.append('%s：自动归档失败（%s）' % (path.name, exc))
        self._root_migration_problems = tuple(problems)

    @staticmethod
    def _package_source(package, include_readme=True):
        """一个外部包只认其根部 SKILL.md；集合包可退回根部 README 总说明。"""
        candidates = [package / PACKAGE_SKILL_FILENAME]
        if include_readme:
            candidates.extend(package / name for name in PACKAGE_README_FILENAMES)
        for path in candidates:
            try:
                if path.is_file():
                    return path
            except OSError:
                continue
        return None

    def _package_sources(self, root=None):
        """发现阶段目录的一层外部包，永远不递归枚举包内子 SKILL。"""
        sources = []
        for stage_dir in self._stage_directories(root):
            direct_source = self._package_source(stage_dir, include_readme=False)
            if direct_source is not None:
                sources.append((direct_source, stage_dir))
            try:
                entries = sorted(stage_dir.iterdir(), key=lambda path: str(path))
            except OSError:
                continue
            for package in entries:
                try:
                    if not package.is_dir() or package.name.startswith('.'):
                        continue
                except OSError:
                    continue
                source = self._package_source(package)
                if source is not None:
                    sources.append((source, package))
        return tuple(sources)

    def _manifest_sources(self, root=None):
        """返回阶段目录直系的常规 ``.skill.md`` 文件。

        常规清单的归档口径就是阶段目录本身；子目录是外部包，只认由
        :meth:`_package_sources` 读取的包根 ``SKILL.md``。因此这里不能递归，
        启动时也不会为阶段配置的默认值扫描整个 SKILL 树。
        """
        sources = []
        for stage_dir in self._stage_directories(root):
            try:
                entries = tuple(stage_dir.iterdir())
            except OSError:
                continue
            for path in sorted(entries, key=lambda item: str(item)):
                try:
                    if not path.is_file() or not path.name.endswith(SKILL_SUFFIX):
                        continue
                except OSError:
                    continue
                sources.append(path)
        return tuple(sources)

    def _file_cache_key(self):
        """返回根目录、阶段目录和总入口目录的 mtime 键，不递归枚举 SKILL 文件。"""
        try:
            directory_mtime_ns = self.root.stat().st_mtime_ns
        except OSError:
            return None, ()

        children = []
        user_directories = ()
        if self.user_root is not None:
            try:
                children.append((str(self.user_root), self.user_root.stat().st_mtime_ns))
                user_directories = self._stage_directories(self.user_root)
            except OSError:
                pass
        for path in (*user_directories, *self._stage_directories()):
            try:
                children.append((str(path), path.stat().st_mtime_ns))
                for package in sorted(path.iterdir(), key=lambda item: str(item)):
                    if package.is_dir():
                        children.append((str(package), package.stat().st_mtime_ns))
                    elif package.is_file() and package.name.endswith(SKILL_SUFFIX):
                        stat = package.stat()
                        children.append((str(package), stat.st_mtime_ns, stat.st_size))
            except OSError:
                continue
        return directory_mtime_ns, tuple(children)

    def _refresh_file_cache(self, force=False):
        """目录变更时才重建 ``(path, mtime, size, source, package)`` 的内存清单。"""
        # 根目录旧清单的迁移是有副作用的维护动作，不能藏在每一次查询里。
        # 首次建表和面板的 scan(force=True) 仍保留原有迁移机会。
        if force or not self._root_manifests_migrated:
            self._migrate_root_manifests()
            self._root_manifests_migrated = True
        directory_mtime_ns, child_directory_mtimes = self._file_cache_key()
        cache_key = (directory_mtime_ns, child_directory_mtimes)

        if (self._file_records is not None and
                cache_key == self._directory_cache_key):
            return

        records = []
        if directory_mtime_ns is not None:
            for root, layer in self._layers():
                for path in self._manifest_sources(root):
                    try:
                        stat = path.stat()
                    except OSError:
                        continue
                    records.append((path, int(stat.st_mtime), int(stat.st_size),
                                    'manifest', None, layer))
                for path, package in self._package_sources(root):
                    try:
                        stat = path.stat()
                    except OSError:
                        continue
                    records.append((path, int(stat.st_mtime), int(stat.st_size),
                                    'package', package, layer))
        self._directory_mtime_ns = directory_mtime_ns
        self._child_directory_mtimes = child_directory_mtimes
        self._directory_cache_key = cache_key
        self._file_records = tuple(records)

    def files(self):
        self._refresh_file_cache()
        return [record[0] for record in self._file_records]

    def fingerprint(self, force=False):
        """返回文件指纹；热查询时间片内绝不重新枚举目录或拼接元组。"""
        now = time.monotonic()
        if (not force and self._fingerprint_cache is not None and
                now - self._fingerprint_checked_at < FRESH_TTL_SECONDS):
            return self._fingerprint_cache
        self._refresh_file_cache(force=force)
        stamp = tuple((str(path), mtime, size, source, str(package or ''), layer)
                      for path, mtime, size, source, package, layer in self._file_records)
        self._fingerprint_cache = stamp
        self._fingerprint_checked_at = now
        return stamp

    def scan(self, force=False):
        """重新读一遍目录。没变化（指纹相同）且不是 force 时直接返回缓存。"""
        stamp = self.fingerprint(force=force)
        if not force and stamp == self._fingerprint:
            return self
        skills, problems, warnings = {}, list(self._root_migration_problems), []
        records = sorted(self._file_records,
                         key=lambda item: (item[5] != 'user', item[3] != 'manifest', str(item[0])))
        for path, _, _, source_kind, package, layer in records:
            try:
                meta, body = parse(path.read_text(encoding='utf-8-sig'), source=str(path))
            except (OSError, UnicodeError) as exc:
                problems.append('%s：读不出来（%s）' % (path.name, exc))
                continue
            if source_kind == 'package':
                meta = imported_package_meta(meta, body, package, path)
            shadow = skills.get(str(meta.get('name') or ''))
            if layer == 'builtin' and shadow is not None and shadow.layer == 'user':
                warnings.append('%s：用户版 %s 覆盖内置版（删除用户版后恢复内置版）' %
                                (shadow.name, shadow.path))
                continue
            if source_kind == 'package':
                base_name = meta['name']
                suffix = 2
                while meta['name'] in skills:
                    meta['name'] = 'package-%s-%d' % (base_name, suffix)
                    suffix += 1
            skill = Skill(meta, body, path, layer=layer)
            if not skill.name:
                problems.append('%s：frontmatter 里没有 name' % path.name)
                continue
            if skill.name in skills:
                problems.append('%s：与 %s 重名' % (path.name, skills[skill.name].path.name))
                continue
            skills[skill.name] = skill
        known = set(skills)
        for name in sorted(skills):
            problems.extend(validate_skill(skills[name], known))
            warnings.extend('%s：依赖 %s（子模块／外部步骤，不在注册表里）' % (name, other)
                            for other in external_references(skills[name], known))
        self._skills, self._problems, self._fingerprint = skills, problems, stamp
        self._warnings = warnings
        return self

    def _fresh(self):
        now = time.monotonic()
        if now - self._fresh_checked_at < FRESH_TTL_SECONDS:
            return self
        self._fresh_checked_at = now
        if self.fingerprint() != self._fingerprint:
            self.scan()
        return self

    # ── 查询 ────────────────────────────────────────────────────────────────
    def getAll(self):
        """全部 SKILL：先按阶段顺序，同阶段按文件名（发现顺序稳定，界面勾选框不跳）。"""
        self._fresh()
        order = {sid: index for index, sid in enumerate(STAGES)}
        return sorted(self._skills.values(),
                      key=lambda skill: (order.get(skill.stage, len(STAGES)), skill.name))

    def getById(self, sid):
        self._fresh()
        return self._skills.get(str(sid or ''))

    get = getById

    def canonical_id(self, sid):
        """把历史 SKILL id 归到当前主 SKILL，防止一次执行重复扣费。

        文件和旧配置都保留；只有登记了 ``deprecated + replacedBy`` 的兼容项才会重定向。
        多跳别名或错误配置会安全停止在最后一个可识别 id，不让解析陷入循环。
        """
        self._fresh()
        name, seen = str(sid or '').strip(), set()
        while name and name not in seen:
            seen.add(name)
            item = self._skills.get(name)
            target = item.replacedBy if item is not None and item.deprecated else ''
            if not target or target not in self._skills:
                break
            name = target
        return name

    def getByStage(self, stage):
        """一个阶段下的 SKILL（阶段可写 id 或中文名）。"""
        sid = stage_id(stage)
        return [skill for skill in self.getAll() if skill.stage == sid]

    def stages(self):
        """目录里真正有 SKILL 的阶段（按阶段顺序）。"""
        have = {skill.stage for skill in self.getAll()}
        return tuple(sid for sid in STAGES if sid in have)

    def problems(self):
        """硬问题：字段缺失、名字不符、阶段认不出、自依赖、又依赖又冲突。"""
        self._fresh()
        return list(self._problems)

    def warnings(self):
        """软提示：依赖指向子模块／外部步骤（不在注册表里）的那种。"""
        self._fresh()
        return list(self._warnings)

    def count(self):
        self._fresh()
        return len(self._skills)


_DEFAULTS = {}


def default_registry(program=None):
    """进程内默认注册表（界面与编排器共用一份，免得各扫一遍目录）。

    第 44 期：缓存**按目录分开**。原先只留「最后用到的那一份」——谁先拿一个别处的
    目录（自检里喂的临时 program，或换过安装位置的老进程）调一次，之后所有不带参数
    的 default_registry()（＝程序目录）都会拿到那一份空的：界面勾选框、阶段默认值、
    编排器找 SKILL 全跟着一起空。分开缓存之后，喂临时目录只影响那个临时目录。
    """
    root = default_root(program)
    key = str(root)
    if key not in _DEFAULTS:
        _DEFAULTS[key] = Registry(root, user_root=default_user_root(program))
    return _DEFAULTS[key]
