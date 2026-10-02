# -*- coding: utf-8 -*-
"""剧本阶段产出契约（第 70 期任务 5／6／7）：五类 manifest 的字段、字段化物理特征与 ID 唯一性。

附件《剧本阶段SKILL审计命令》里，任务 1～4 是审计、任务 5～7 是「缺什么补什么」。这一份把要补的
东西落成能跑、能验的代码，不再只是报告里的一段话：

- 任务 5：剧本阶段要产出五类 JSON —— character_manifest／scene_manifest／prop_manifest／
  scene_breakdown／emotion_curve。`MANIFESTS` 是这五个文件名，`STAGE_OUTPUTS` 交给
  `stage_layout.STAGES` 的 00_script 那一段，`manifest()` 把条目收成一份带抬头的文件
  （抬头三件：manifest／kind／items）。
- 任务 6：character_manifest.json 里每个角色的 physical_features 必须是字段化的五件：
  skin_tone／hair／eyes／distinctive_marks／body_type。整句自然语言交给 `field_features()` 拆字段，
  认不出来的片段留在 raw 里（原文不丢）。
- 任务 7：所有 manifest 里的 ID 必须唯一。`duplicate_ids()` 报重复、`reassign_ids()` 重发号、
  `unique_ids()` 是验收口径；`completeness()` 是产出完整性那一份报告（交付物 5）。
- 任务 1～4 的审计表也做成数据：`manifest_rows()` 从真注册表读 SKILL 的名称／路径／输入／输出，
  `audit_rows()` 给每个 SKILL 一个类别与处理动作。报告与代码同源，不会各说各的。
- 任务 3 的收口（第 8 轮）：「重叠」的台词润色与「支撑」的世界观设定不删文件、并回正稿的
  相应那一段，产物归属与落点由 `support_rows()` 发出、`merge_problems()` 体检。

口径跟 `asset_contract` 一致——**只补不改**：normalize 只补缺的键与缺的编号，已有的值一个都不动，
老 JSON 少这几个键照旧读得出来。

五类 manifest 的产出者（`PRODUCERS` 是唯一口径）：

| manifest | 产出 SKILL | 这一步在哪一阶段 |
|:---|:---|:---|
| character_manifest.json／scene_manifest.json／prop_manifest.json | script-character-extraction（角色与设定提取） | 剧本结构 |
| emotion_curve.json | script-emotion-curve（情绪曲线标注） | 剧本准备 |
| scene_breakdown.json | storyboard-scene-breakdown（场次拆分） | 初步分镜 |

场次拆分那个 SKILL 归在「初步分镜」，产物按契约落在 00_script/output（剧本阶段自己再核对一遍），
所以它也算剧本阶段的产出——`PRODUCERS` 里照实写，别归错。
"""
import json
from agent.core import read
import re
import hashlib
from datetime import datetime
from pathlib import Path
from script_manifest_contract import (HEADER, KIND_OF_MANIFEST, KINDS, MANIFEST_OF_KIND,
                                      MANIFESTS, STAGE_OUTPUTS)

# ── 五类产出（任务 5）─────────────────────────────────────────────────────────

# 剧本结构阶段的唯一输入／输出契约。原稿永远只读；结构化稿独立放入
# project/02剧本结构/结构剧本/：结构剧本独立为项目工作阶段，
# 不再和剧本准备阶段的自然剧本混在 writing 目录。
RAW_SCRIPT_NAME = 'script_raw.md'
STRUCTURED_SCRIPT_NAME = 'script.md'  # 旧版兼容名；新生成文件使用 stage_file_name().
STRUCTURED_SCRIPT_DIR = '结构剧本'
STRUCTURED_STAGE_DIR = '02剧本结构'
_SCENE_LINE = re.compile(r'(?m)^\s*(?:#{1,6}\s*)?((?:第[一二三四五六七八九十百零〇\d]+[集幕]|(?:场景|场次|scene)\s*[一二三四五六七八九十\d]+)[^\n]*)')
_DIALOGUE_LINE = re.compile(r'^\s*([^\s：:]{1,16})[：:]\s*(.+)$')
_EXCLUDED_SPEAKERS = frozenset(('场景', '场次', '时间', '地点', '旁白', '动作', '情绪', '角色', '人物', '道具'))
_EMOTIONS = ('愤怒', '悲伤', '紧张', '恐惧', '喜悦', '开心', '惊讶', '平静', '焦虑', '愧疚', '决绝')
_CLOTHING = ('衣', '衫', '裙', '裤', '鞋', '外套', '风衣', '校服', '制服')
_PROP_DECLARATION = re.compile(r'(?:道具|物品)[：:]?\s*([^，。；\n]{1,30})')
_DIMENSION = re.compile(r'\d+(?:\.\d+)?\s*(?:厘米|公分|cm|CM|米|m)')

# 剧本准备与剧本结构的边界必须可执行，不能只写在提示词中。这里故意只拦截
# 明确属于结构阶段的版式，普通剧本中的“场景”“镜头”等叙事用语不会被误伤。
_NATURAL_SCRIPT_FORBIDDEN = (
    ('结构化剧本', '结构化剧本标题'), ('角色档案', '角色档案'), ('场景档案', '场景档案'),
    ('道具档案', '道具档案'), ('分场剧本', '分场剧本'), ('镜头编号', '镜头编号'),
    ('镜头表', '镜头表'), ('分镜表', '分镜表'), ('首帧提示词', '首帧提示词'),
    ('视频提示词', '视频提示词'), ('```json', 'JSON 代码块'), ('"source_script"', '分镜 JSON'),
)


def natural_script_violations(text):
    """返回剧本准备阶段不允许落盘的结构化产物特征。"""
    value = str(text or '').strip()
    if not value:
        return ('空正文',)
    violations = []
    if value.startswith(('{', '[')):
        violations.append('JSON 正文')
    folded = value.casefold()
    for needle, label in _NATURAL_SCRIPT_FORBIDDEN:
        if needle.casefold() in folded and label not in violations:
            violations.append(label)
    if re.search(r'(?m)^\s*\|.+\|\s*$', value):
        violations.append('字段表格')
    return tuple(violations)


def require_natural_script(text):
    """剧本准备的保存闸门：只接收自然语言剧本原稿。"""
    violations = natural_script_violations(text)
    if violations:
        raise ValueError('剧本准备阶段只接受完整自然语言剧本；检测到结构化内容：' + '、'.join(violations))
    return str(text or '').strip()


def save_natural_script(path, text):
    """原子保存用户手改的自然剧本，拒绝写入结构化阶段正文。"""
    path = Path(path)
    if path.suffix.lower() != '.md':
        raise ValueError('自然剧本必须保存为 Markdown 文件。')
    value = require_natural_script(text)
    from agent.core import save_text
    save_text(path, value + '\n')
    return path


def is_natural_script(text):
    """供列表与兼容读取使用；文件名已是剧本时只排除明确的错阶段内容。"""
    return not natural_script_violations(text)


def _unique(values):
    """按首次出现顺序去重；结构化结果要稳定，不能因重复台词产生重复档案。"""
    return tuple(dict.fromkeys(value for value in values if value))


def _scene_blocks(raw):
    """按原稿场次标题切块；没有场次标题的原稿也保留为一场，绝不丢正文。"""
    hits = list(_SCENE_LINE.finditer(raw))
    if not hits:
        return (('场次 01', raw.strip()),)
    blocks = []
    if raw[:hits[0].start()].strip():
        blocks.append(('场次 01', raw[:hits[0].start()].strip()))
    offset = len(blocks)
    for position, match in enumerate(hits):
        # 用原始命中位置确定下一场开头，标题本身也留在正文里，便于追溯。
        next_start = hits[position + 1].start() if position + 1 < len(hits) else len(raw)
        index = offset + position + 1
        blocks.append((match.group(1).strip() or '场次 %02d' % index, raw[match.start():next_start].strip()))
    return tuple(blocks)


def _speakers(text):
    return _unique(match.group(1).strip() for line in text.splitlines()
                   for match in [_DIALOGUE_LINE.match(line)] if match and match.group(1).strip() not in _EXCLUDED_SPEAKERS)


def _first_sentence(text, words):
    for line in text.splitlines():
        clean = line.strip('-* #\t')
        if clean and any(word in clean for word in words):
            return clean[:100]
    return '待确认（原稿未明确）'


def natural_script_paths(project):
    """返回全部用户可见自然剧本，明确排除 HOLLMWOOD 的内部副本。"""
    from stage_path_service import read_dirs
    project = Path(project)
    # 新项目只写 01剧本准备；这里保留旧 writing 的只读兼容，方便打开历史项目，
    # 但绝不在旧目录创建副本。
    roots = read_dirs(project, 'script')
    ignored = {STRUCTURED_SCRIPT_NAME, 'brief_raw.md', 'brief_creation.md', '聊天记录.md'}
    candidates = []
    for priority, writing in enumerate(roots):
      if not writing.is_dir():
        continue
      for path in writing.rglob('*.md'):
        relative = path.relative_to(writing)
        # `script_raw.md` 是四角色协作的内部工作副本，不在自然剧本列表显示，
        # 更不能优先盖过已经按用户命名保存的正式自然剧本。
        if (not path.is_file() or path.name in ignored or path.name == RAW_SCRIPT_NAME
                or STRUCTURED_SCRIPT_DIR in relative.parts):
            continue
        name = path.name.lower()
        # 四段式命名里“剧本准备”是阶段名，不能因此把项目设定或大纲误认成自然剧本。
        if re.match(r'^剧本准备_(?:项目设定|项目大纲)_', path.name):
            continue
        # 新旧自然剧本都兼容：模型目录中的创意稿、历史“剧本”命名，以及统一的新命名。
        # 剧本准备页会将用户导入或重命名后的文件放进 ``项目剧本`` 分类；这些
        # 文件名不一定带“剧本”或集数，不能因此在剧本整理页被遗漏。
        categorized_script = '项目剧本' in relative.parts
        numbered_script = bool(re.search(r'_(?:ep\d+|第\d+集)_\d{8}(?:_\d+)?\.md$', path.name, re.I))
        if ('剧本' not in path.name and 'script' not in name
                and not numbered_script and not categorized_script):
            continue
        try:
            if path.stat().st_size and is_natural_script(path.read_text(encoding='utf-8', errors='ignore')):
                candidates.append((priority, path))
        except OSError:
            continue
    # 同一份剧本可能同时留在旧 ``writing`` 和当前 ``01剧本准备``；当前阶段
    # 是唯一权威位置，先按目录优先级去重，再按正文指纹去重，避免结构页重复展示。
    seen_relative = set()
    seen_content = set()
    visible = []
    for priority, path in sorted(candidates, key=lambda item: (item[0], -item[1].stat().st_mtime, str(item[1]))):
        relative = path.relative_to(roots[priority]).as_posix().casefold()
        if relative in seen_relative:
            continue
        try:
            digest = hashlib.sha256(path.read_bytes()).digest()
        except OSError:
            continue
        seen_relative.add(relative)
        if digest in seen_content:
            continue
        seen_content.add(digest)
        visible.append(path)
    return tuple(visible)


def resolve_script_source(project):
    """优先使用用户可见的最新自然剧本；仅旧项目才回退内部 script_raw.md。"""
    paths = natural_script_paths(project)
    if paths:
        return paths[0]
    from stage_path_service import read_dirs
    for primary in (folder / RAW_SCRIPT_NAME for folder in read_dirs(project, 'script')):
        try:
            if (primary.is_file() and primary.stat().st_size
                    and is_natural_script(primary.read_text(encoding='utf-8', errors='ignore'))):
                return primary
        except OSError:
            continue
    return None


def project_name(project):
    """从项目目录取得稳定项目名，剥离创建目录附带的日期／序号。"""
    name = Path(project).name.strip()
    name = re.sub(r'_\d{8}(?:_\d+)?$', '', name)
    # 文件名片段必须能直接落在 Windows；项目目录名允许的字符范围更宽，不能原样
    # 拼进用户文件名。
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', '_', name)
    # 下划线是 Windows 合法文件名字符，也可能是项目目录名的有效末尾；
    # 不可在拼接四段式文件名时静默删掉，否则项目名与用户可见产物前缀不一致。
    name = re.sub(r'\s+', ' ', name).strip(' .')
    return name[:80] or '项目'


def _file_name_part(value, fallback):
    """把文件类型／内容收成稳定、安全的用户可见文件名片段。"""
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', '_', str(value or '').strip())
    value = re.sub(r'\s+', ' ', value).strip(' ._')
    return value[:80] or fallback


def stage_file_name(project, file_type, content, at=None):
    """用户可见剧本文件名：项目名_文件类型_文件内容_年月日.md。"""
    day = (datetime.fromtimestamp(at) if at is not None else datetime.now()).strftime('%Y%m%d')
    return '%s_%s_%s_%s.md' % (project_name(project),
                               _file_name_part(file_type, '文件'),
                               _file_name_part(content, '内容'), day)


_STAGE_FILE_TYPES = ('自然剧本', '项目大纲', '项目设定', '结构剧本')
_STAGE_FILE_PATTERN = re.compile(
    r'^(?P<project>.+)_(?P<file_type>%s)_(?P<content>.+)_(?P<date>\d{8})(?:_(?P<serial>\d+))?\.md$'
    % '|'.join(re.escape(value) for value in _STAGE_FILE_TYPES), re.I)


def stage_file_info(path):
    """解析用户可见创作文件名，并说明新旧格式的归类依据。

    返回 ``None`` 代表该文件不是受控创作文件；调用方不应再以字符串切片
    猜测其阶段或类型。兼容的旧 ``项目_EP001_年月日.md`` 仅认作自然剧本。
    """
    name = Path(path).name
    match = _STAGE_FILE_PATTERN.match(name)
    if match:
        info = match.groupdict()
        info.update(format='stage-v1', reason='四段式文件名中的文件类型段')
        return info
    legacy = re.match(r'^.+_ep\d+_\d{8}(?:_\d+)?\.md$', name, re.I)
    if legacy:
        return {'project': '', 'file_type': '自然剧本', 'content': '', 'date': '',
                'serial': '', 'format': 'legacy-episode',
                'reason': '旧版项目_集数_年月日命名'}
    return None


def structured_script_file_name(project, file_type='结构剧本', content='正稿', at=None):
    """剧本结构用户文件名，和剧本准备统一使用项目名四段式。"""
    return stage_file_name(project, file_type, content, at=at)


def is_structured_script_file_name(path):
    """识别当前格式和迁移前的阶段前缀格式。"""
    stem = Path(path).stem
    info = stage_file_info(path)
    return ((info is not None and info['file_type'] == '结构剧本') or
            stem.startswith('结构剧本_') or
            stem.startswith('剧本结构_结构剧本_'))


def is_structured_script(path):
    """按正文首部确认结构剧本，避免把误命名为 script.md 的大纲送入分镜。"""
    path = Path(path)
    if not path.is_file() or path.suffix.lower() != '.md':
        return False
    try:
        # 标题及档案区都在开头；仅读小块，不把整份长剧本重复载入。
        head = path.read_text(encoding='utf-8', errors='replace')[:4096]
    except OSError:
        return False
    if '# 结构化剧本' not in head or ('## 角色档案' not in head and '## 分场剧本' not in head):
        return False
    # 早期流程会把“项目大纲”直接送给结构化器，产出虽然有结构化标题，
    # 本质仍是大纲提取，不能伪装成可供初步分镜使用的自然剧本正稿。
    source = re.search(r'(?m)^>\s*来源：`?([^`\n]+)', head)
    source_name = source.group(1).casefold() if source else ''
    return not any(mark in source_name for mark in ('大纲', '纲要', 'outline', '梗概'))


def structured_script_paths(project):
    """返回独立阶段中的结构剧本；兼容旧 writing 目录，迁移后不再写回旧处。"""
    project = Path(project)
    from stage_path_service import read_dirs, write_dir
    writing = write_dir(project, 'script')
    candidates = []
    for folder in (write_dir(project, 'structure') / STRUCTURED_SCRIPT_DIR,
                   writing / STRUCTURED_SCRIPT_DIR,
                   *[legacy / STRUCTURED_SCRIPT_DIR for legacy in read_dirs(project, 'script')[1:]]):
        if folder.is_dir():
            candidates.extend(path for path in folder.rglob('*.md')
                              if is_structured_script(path) and _structured_source_is_available(project, path))
    # Old projects kept a compatibility copy directly under ``writing/``.
    # Discover it read-only, rather than creating a duplicate in the current
    # stage directory when a historic project is opened.
    legacy_scripts = (writing / STRUCTURED_SCRIPT_NAME, *(
        legacy_root / STRUCTURED_SCRIPT_NAME
        for legacy_root in read_dirs(project, 'script')[1:]
    ))
    for legacy in legacy_scripts:
        if (is_structured_script(legacy)
                and _structured_source_is_available(project, legacy)):
            candidates.append(legacy)
    # 旧结构稿常由同一内容迁移／联接而来；只显示当前独立阶段里的一份。
    visible = []
    fingerprints = set()
    for path in candidates:
        try:
            digest = hashlib.sha256(path.read_bytes()).digest()
        except OSError:
            continue
        if digest not in fingerprints:
            fingerprints.add(digest)
            visible.append(path)
    return tuple(sorted(visible, key=lambda item: (item.stat().st_mtime, str(item)), reverse=True))


def canonical_structured_script_path(project):
    """新建结构剧本的唯一位置：项目中的独立剧本结构阶段。"""
    from stage_path_service import write_dir
    return (write_dir(project, 'structure') / STRUCTURED_SCRIPT_DIR
            / structured_script_file_name(project, '结构剧本', '正稿'))


def structured_script_path(project):
    """当前最新结构剧本，兼容迁移前根目录的 writing/script.md。"""
    canonical = canonical_structured_script_path(project)
    paths = structured_script_paths(project)
    return paths[0] if paths else canonical


def _structured_source_is_available(project, structured_path):
    """结构稿只在其记录的原稿仍存在时显示，避免删除原稿后留下孤立下游稿。"""
    from artifact_lineage import source_available
    recorded = source_available(project, structured_path)
    if recorded is not None:
        return recorded
    try:
        head = Path(structured_path).read_text(encoding='utf-8', errors='replace')[:4096]
    except OSError:
        return False
    source = re.search(r'(?m)^>\s*来源：`?([^`\n]+)', head)
    if source is None:
        # 早期无来源标记的历史结构稿无法安全关联，继续兼容显示，不能猜测并删除。
        return True
    relative = source.group(1).strip().replace('\\', '/')
    if not relative or relative.startswith('/') or ':' in relative:
        return False
    candidate = Path(project) / Path(relative)
    try:
        if candidate.is_file() and candidate.stat().st_size > 0:
            return True
    except OSError:
        pass
    # 文件命名迁移只替换首段的阶段名为项目名，后面的“文件类型／内容／日期”
    # 是同一份原稿的稳定身份。直接按旧相对路径找不到时，仅以这段稳定身份关联；
    # 原稿被用户删除后自然剧本列表为空，结构稿仍会随之隐藏。
    signature = re.search(r'(_自然剧本_.+_\d{8}(?:_\d+)?\.md)$', Path(relative).name)
    if signature is None:
        return False
    return any(path.name.endswith(signature.group(1)) for path in natural_script_paths(project))


def _source_label(project, source):
    root = Path(project).resolve()
    return source.resolve().relative_to(root).as_posix()


def structure_script(raw_text, source_name=RAW_SCRIPT_NAME):
    """把自然语言原稿整理成供下游读取的 Markdown 正稿，不修改原始文本也不建立新 JSON 契约。"""
    raw = str(raw_text or '').strip()
    if not raw:
        raise ValueError('writing/script_raw.md 为空，无法整理结构化剧本。')
    scenes = _scene_blocks(raw)
    characters = _unique(name for _title, body in scenes for name in _speakers(body))
    props = _unique(match.group(1).strip() for match in re.finditer(r'(?:道具|物品)[：:]?\s*([^，。；\n]{1,30})', raw))
    lines = ['# 结构化剧本', '', '> 来源：`%s`（原稿保持不变）' % source_name, '', '## 角色档案', '']
    if characters:
        for name in characters:
            related = '\n'.join(body for _title, body in scenes if name in body)
            lines += ['### ' + name,
                      '- 物理特征：' + _first_sentence(related, ('岁', '发', '眼', '肤', '身', '高', '矮')),
                      '- 默认服装：' + _first_sentence(related, _CLOTHING),
                      '- 换装需求：待确认（原稿未明确）', '']
    else:
        lines += ['- 待确认：原稿未发现“人物名：对白”格式的角色。', '']
    lines += ['## 场景档案', '']
    for order, (title, body) in enumerate(scenes, 1):
        lines += ['### 场景 %02d：%s' % (order, title),
                  '- 空间锚点：' + _first_sentence(body, ('内', '外', '店', '家', '学校', '街', '楼', '房', '站')),
                  '- 光照方向：' + _first_sentence(body, ('光', '夜', '晨', '晚', '日', '灯')),
                  '- 尺度参考：待确认（原稿未明确）', '']
    lines += ['## 道具档案', '']
    lines += (['- ' + item + '：尺寸、材质、持有者待确认。' for item in props] or ['- 待确认：原稿未明确关键道具。'])
    lines += ['', '## 分场剧本', '']
    for order, (title, body) in enumerate(scenes, 1):
        participants = '、'.join(_speakers(body)) or '待确认'
        mood = _first_sentence(body, _EMOTIONS)
        lines += ['### 场次 %02d：%s' % (order, title), '- 出场角色：' + participants,
                  '- 情绪基调：' + mood, '- 起始状态：待确认（原稿未明确）',
                  '- 结束状态：待确认（原稿未明确）', '- 正文：', body, '']
    return '\n'.join(lines).rstrip() + '\n'


def _section(text, heading):
    """取一个二级档案区，供 Editor 只校验提取结果而非分场原文。"""
    marker = '## ' + heading
    start = text.find(marker)
    if start < 0:
        return ''
    next_heading = text.find('\n## ', start + len(marker))
    return text[start:] if next_heading < 0 else text[start:next_heading]


def _declared_props(raw):
    """返回原稿明确声明的道具名与尺寸；同一道具多尺寸是不能静默修补的源稿矛盾。"""
    records = []
    for match in _PROP_DECLARATION.finditer(raw):
        description = match.group(1).strip()
        name = re.split(r'[（(：:，,]', description, maxsplit=1)[0].strip()
        if name:
            records.append((name, tuple(_DIMENSION.findall(description))))
    return records


def review_structured_script(raw_text, structured_text):
    """Editor 审校 Writer 提取结果，返回可展示的反馈；不改动任何文件。"""
    raw = str(raw_text or '').strip()
    structured = str(structured_text or '').strip()
    feedback = []
    required = ('角色档案', '场景档案', '道具档案', '分场剧本')
    for heading in required:
        if '## ' + heading not in structured:
            feedback.append('缺少「%s」区块。' % heading)
    scenes = _scene_blocks(raw) if raw else ()
    characters = _unique(name for _title, body in scenes for name in _speakers(body))
    character_archive = _section(structured, '角色档案')
    for name in characters:
        profile = '### ' + name
        if profile not in character_archive:
            feedback.append('角色「%s」未建立档案。' % name)
            continue
        position = character_archive.find(profile)
        next_profile = character_archive.find('\n### ', position + len(profile))
        card = character_archive[position:] if next_profile < 0 else character_archive[position:next_profile]
        if '- 物理特征：' not in card:
            feedback.append('角色「%s」缺少物理特征。' % name)
        if '- 默认服装：' not in card:
            feedback.append('角色「%s」缺少默认服装。' % name)
    scene_archive = _section(structured, '场景档案')
    if scenes and scene_archive.count('### 场景 ') < len(scenes):
        feedback.append('场景档案数量少于原稿场次，需补全空间、光照和尺度信息。')
    prop_archive = _section(structured, '道具档案')
    dimensions_by_prop = {}
    for name, dimensions in _declared_props(raw):
        if name not in prop_archive:
            feedback.append('道具「%s」未提取到道具档案。' % name)
        if dimensions and not all(dimension in prop_archive for dimension in dimensions):
            feedback.append('道具「%s」的尺寸信息未完整提取。' % name)
        if dimensions:
            dimensions_by_prop.setdefault(name, set()).update(dimensions)
    for name, dimensions in dimensions_by_prop.items():
        if len(dimensions) > 1:
            feedback.append('原稿中道具「%s」存在互相矛盾的尺寸：%s。请先修正 script_raw.md。'
                            % (name, '、'.join(sorted(dimensions))))
    return {'approved': not feedback, 'feedback': tuple(feedback)}


def revise_structured_script(raw_text, feedback, source_name=RAW_SCRIPT_NAME):
    """Writer 根据 Editor 反馈重新提取；源稿矛盾保留给用户修正，绝不臆造事实。"""
    notes = tuple(feedback or ())
    conflicts = [note for note in notes if '互相矛盾的尺寸' in note]
    if conflicts:
        raise ValueError('；'.join(conflicts))
    return structure_script(raw_text, source_name=source_name)


def write_structured_script(project, content=None, source=None, publisher=None):
    """原子写入项目的独立结构阶段；旧 writing 目录仅兼容读取。"""
    root = Path(project)
    from stage_path_service import legacy_read_dirs, write_dir
    writing = write_dir(root, 'script').resolve()
    source = resolve_script_source(root) if source is None else Path(source)
    if source is None or not source.is_file():
        raise ValueError('未找到可读取的剧本原稿，请先在“剧本准备”生成或下载剧本。')
    source = source.resolve()
    readable = (writing, *[path.resolve() for path in legacy_read_dirs(root, 'script')])
    if not any(source.is_relative_to(folder) for folder in readable):
        raise ValueError('剧本来源必须位于当前项目的 writing 目录。')
    rendered = (structure_script(source.read_text(encoding='utf-8-sig'), _source_label(root, source))
                if content is None else str(content))
    if not rendered.strip():
        raise ValueError('结构剧本正文不能为空，未发布成果。')
    target = canonical_structured_script_path(root)
    from artifact_lineage import record
    if publisher is None:
        from agent.core import save_text
        save_text(target, rendered)

    def update_index(published):
        record(root, published, source, '结构剧本')

    if publisher is None:
        update_index(target)
    else:
        publisher(target, rendered, lambda value: bool(str(value).strip()),
                  update_index)
    return target
STAGE = '00_script'
# 此值是旧 manifest 的兼容键，不是新建目录名：stage_layout 会将它解析为
# 「01剧本准备」。剧本工作流已拆成「剧本准备」和「剧本结构」两段。
SCRIPT_SKILL_STAGES = ('script', 'script_structure')
# stage_layout.STAGES 通过兼容键引用它，两处不会各写一份。

# HOLLMWOOD 剧本准备的节奏约束是 SKILL 输入模板，不是本阶段新增产物；因此不加入
# STAGE_OUTPUTS，避免被完整性检查误判成必须生成的 manifest。后续编排器只通过这个字段
# 引用模板，不复制路径字符串。
RHYTHM_TEMPLATE_FIELD = 'rhythm_template'
RHYTHM_TEMPLATE_PATH = 'skills/templates/rhythm_template.yaml'

# HOLLMWOOD 的输入简报同样由本契约统一命名；创意接收层只负责从用户原话提取并落盘，
# 不在 idea_chat.py 再复制一套“哪些字段必须有”的判断。
BRIEF_REQUIRED_FIELDS = ('story_summary', 'main_characters', 'genre', 'length')
BRIEF_RECOMMENDED_FIELDS = ('physical_features',)
BRIEF_PRODUCTION_LOCKS_FIELD = 'production_locks'
BRIEF_OPTIONAL_FIELDS = ('special_requirements',)
BRIEF_REQUIREMENT_LEVELS = {
    'required': BRIEF_REQUIRED_FIELDS,
    'recommended': BRIEF_RECOMMENDED_FIELDS + (BRIEF_PRODUCTION_LOCKS_FIELD,),
    'optional': BRIEF_OPTIONAL_FIELDS,
}
BRIEF_FIELDS = BRIEF_REQUIRED_FIELDS + BRIEF_RECOMMENDED_FIELDS + BRIEF_OPTIONAL_FIELDS
BRIEF_LABELS = {
    'story_summary': '故事梗概',
    'main_characters': '主要角色',
    'physical_features': '角色物理特征',
    'genre': '题材类型',
    'length': '篇幅',
    'special_requirements': '特殊要求',
    BRIEF_PRODUCTION_LOCKS_FIELD: '制作锁',
}

# 此投影只定义 skill_config.json 的 L0 数据形状，不参与本轮的工作流运行。
# lock 的第一层按统筹 SKILL 名称命名空间保存；第二层键和值由统筹定义，本契约不列举。
WORKFLOW_PROJECTION_KEY = 'workflow'
WORKFLOW_LOCK_SCHEMA = {
    WORKFLOW_PROJECTION_KEY: {
        'name': '<统筹名称>',
        'skill_ref': '<统筹 SKILL 注册引用>',
        'lock': {'<统筹名称>': {'<键>': '<值>'}},
    },
}


def rhythm_template_reference():
    """HOLLMWOOD 创意简报引用的节奏模板字段。"""
    return {RHYTHM_TEMPLATE_FIELD: RHYTHM_TEMPLATE_PATH}


def normalize_brief(values=None):
    """将创意接收层的字段收敛到唯一的 HOLLMWOOD 输入简报形状。"""
    source = values if isinstance(values, dict) else {}
    brief = {field: str(source.get(field) or '').strip() for field in BRIEF_FIELDS}
    locks = source.get(BRIEF_PRODUCTION_LOCKS_FIELD)
    brief[BRIEF_PRODUCTION_LOCKS_FIELD] = dict(locks) if isinstance(locks, dict) else {}
    return brief


def missing_brief_fields(values, include_recommended=False, include_optional=False):
    """返回缺少项；必填阻断，建议只提示，可选仅按需盘点。"""
    brief = normalize_brief(values)
    fields = BRIEF_REQUIRED_FIELDS
    if include_recommended:
        fields += BRIEF_REQUIREMENT_LEVELS['recommended']
    if include_optional:
        fields += BRIEF_REQUIREMENT_LEVELS['optional']
    return tuple(field for field in fields if not brief.get(field))


def normalize_workflow_projection(values=None):
    """规范化顶层 workflow 投影，保留各统筹的锁命名空间。"""
    source = values if isinstance(values, dict) else {}
    workflow = source.get(WORKFLOW_PROJECTION_KEY, source)
    workflow = workflow if isinstance(workflow, dict) else {}
    name = str(workflow.get('name') or '').strip()
    skill_ref = str(workflow.get('skill_ref') or '').strip()
    raw_locks = workflow.get('lock')
    lock = {
        str(namespace): dict(lock_values)
        for namespace, lock_values in raw_locks.items()
        if isinstance(lock_values, dict)
    } if isinstance(raw_locks, dict) else {}
    if name:
        lock.setdefault(name, {})
    return {WORKFLOW_PROJECTION_KEY: {'name': name, 'skill_ref': skill_ref, 'lock': lock}}


def brief_document(values):
    """建立可供 HOLLMWOOD 读取的已确认简报，必填项未齐时拒绝伪造完成态。"""
    brief = normalize_brief(values)
    missing = missing_brief_fields(brief)
    if missing:
        raise ValueError('简报缺少：' + '、'.join(BRIEF_LABELS[field] for field in missing))
    return {
        'contract': 'script_brief',
        'version': 1,
        'brief': brief,
        'recommended_missing': list(missing_brief_fields(brief, include_recommended=True)),
        RHYTHM_TEMPLATE_FIELD: RHYTHM_TEMPLATE_PATH,
    }

# manifest 文件名 → (产出它的 SKILL, 这份产物按契约落在哪个阶段目录)
PRODUCERS = {
    'character_manifest.json': ('script-character-extraction', STAGE),
    'scene_manifest.json': ('script-character-extraction', STAGE),
    'prop_manifest.json': ('script-character-extraction', STAGE),
    'scene_breakdown.json': ('storyboard-scene-breakdown', STAGE),
    'emotion_curve.json': ('script-emotion-curve', STAGE)}
PRODUCER_SKILLS = tuple(sorted({skill for skill, _folder in PRODUCERS.values()}))

# ── 编号口径（任务 7）────────────────────────────────────────────────────────
# 角色／场景／道具沿用资产清单那一套（CHAR_／LOC_／PROP_），场次拆分与情绪节拍各给一套。
PREFIX = {'character': 'CHAR', 'scene': 'LOC', 'prop': 'PROP',
          'scene_breakdown': 'SC', 'emotion_curve': 'EC'}
PREFIX_OF = dict((value, key) for key, value in PREFIX.items())
ID_FIELD = {'character': 'character_id', 'scene': 'scene_id', 'prop': 'prop_id',
            'scene_breakdown': 'breakdown_id', 'emotion_curve': 'beat_id'}
PATTERN = dict((kind, '^%s_[0-9]{3,}$' % prefix) for kind, prefix in PREFIX.items())

# ── 物理特征五件（任务 6）────────────────────────────────────────────────────
PHYSICAL_KEYS = ('skin_tone', 'hair', 'eyes', 'distinctive_marks', 'body_type')
PHYSICAL_LABELS = {'skin_tone': '肤色', 'hair': '发型发色', 'eyes': '眼睛',
                   'distinctive_marks': '标志性特征', 'body_type': '体型'}
# 拆字段用的关键词：一个片段命中哪个键就进哪个键；命中多个时取「命中的词最长」的那个
# （先认长的，别让「短发」被「发」抢走），一样长就按这张表的先后。
HINTS = (
    ('skin_tone', ('肤色', '冷白', '白皙', '苍白', '小麦色', '小麦', '蜜色', '古铜', '黝黑', '偏黑')),
    ('hair', ('发型', '发色', '刘海', '马尾', '丸子头', '长辫', '麻花辫', '短发', '长发', '卷发',
              '直发', '银发', '黑发', '白发', '金发', '光头', '发')),
    ('eyes', ('眼型', '杏眼', '丹凤眼', '桃花眼', '双眼皮', '单眼皮', '瞳色', '蓝瞳', '金瞳',
              '琥珀瞳', '眼', '瞳', '眸')),
    ('distinctive_marks', ('胎记', '疤痕', '伤疤', '伤痕', '记号', '纹身', '刺青', '义肢', '机械臂',
                           '眼罩', '绷带', '耳钉', '耳饰', '断眉', '疤', '痣')),
    ('body_type', ('身形', '体型', '身材', '高挑', '高大', '矮小', '娇小', '魁梧', '修长', '匀称',
                   '结实', '瘦', '胖', '壮')))
# 拆句子的标点：中文逗号顿号分号句号全角冒号，加半角斜杠竖线与空白。
SPLIT = '\u3001\uff0c,\uff1b;\u3002\uff1a:/\uff5c \n\t'

# ── 任务 2／3／4 的审计表 ────────────────────────────────────────────────────
# 任务 3 的四种分类与对应的处理动作（唯一口径，报告照它写）。
CATEGORIES = {'核心': '保留并强化结构化', '支撑': '保留并降级为辅助',
              '重叠': '合并到唯一归属', '冗余': '删除或归档到 _archive/'}
# (SKILL 名, 分类, 改造后归属, 理由)——分类与理由来自任务 2 的四问法与任务 3 的归类。
AUDIT = (
    ('script-structured-generation', '核心', '剧本结构 · 结构化剧本生成',
     '剧本正稿的唯一产出者，拆镜、配音、字幕都读它；三类 manifest 的字段由它定型'),
    ('script-character-extraction', '核心', '剧本结构 · 角色与设定提取',
     '角色／场景／道具三条资产链路的唯一入口，直接支撑「资产」可控性'),
    ('script-emotion-curve', '核心', '剧本准备 · 情绪曲线标注',
     '只标注不改词，支撑「分镜」的镜头长短与语气；每场一条强度加钩子'),
    ('script-dialogue-polish', '重叠', 'script-structured-generation（台词那一段）',
     '台词本来就是正稿的一部分，润色结果没有独立的消费方，不单独出文件'),
    ('script-worldbuilding', '支撑', '剧本结构 · script-structured-generation（设定那一段）',
     '世界观是分镜与资产的背景，但不产出可校验的编号，产物落 docs（人读）'),
    ('screenplay-production-line', '支撑', '剧本准备 · 外部包总入口',
     '受控默认值只提供 creative-writing；不自动展开内部子 SKILL，且无 output/manifest 声明'),
    ('screenplay-writer', '支撑', '剧本准备 · 外部包总入口',
     '受控默认值只提供 creative-writing；不自动展开内部子 SKILL，且无 output/manifest 声明'),
    ('script-forging', '支撑', '剧本准备 · 外部包总入口',
     '受控默认值只提供 creative-writing；不自动展开内部子 SKILL，且无 output/manifest 声明'),
    ('短剧编剧搭子', '支撑', '剧本准备 · 外部包总入口',
     '受控默认值只提供 creative-writing；不自动展开内部子 SKILL，且无 output/manifest 声明'),
    ('编剧技能集', '支撑', '剧本准备 · 外部包总入口',
     '受控默认值只提供 creative-writing；不自动展开内部子 SKILL，且无 output/manifest 声明'))

# ── 任务 3 的收口（第 8 轮）：重叠／支撑的那两个并到哪一段去 ──────────────────
# 「合并／降级」在这一步都不是删文件：SKILL 文件留着（注册表与阶段并行表按这一层挂步，
# 按各阶段的实际分布挂步，变的是产物归属——不再单独出文件，并回唯一归属者的相应那一段。
MERGE_OWNER = 'script-structured-generation'
# (SKILL 名, 并回归属者的哪一段, 产物落在哪)
MERGED = (
    ('script-dialogue-polish', '台词那一段', '（并回正稿，不单独出文件）'),
    ('script-worldbuilding', '设定那一段', 'docs/world_bible.md'))
MERGED_SKILLS = tuple(skill for skill, _part, _landing in MERGED)
MERGE_PART = dict((skill, part) for skill, part, _landing in MERGED)
MERGE_LANDING = dict((skill, landing) for skill, _part, landing in MERGED)


# ── 编号 ────────────────────────────────────────────────────────────────────
def new_id(kind, index):
    """按类别发号：character → CHAR_001。"""
    return '%s_%03d' % (PREFIX.get(kind, 'X'), int(index))


def kind_of_id(aid):
    """编号 → 类别（认不出来返回空串）。"""
    match = re.match(r'^([A-Z]+)_[0-9]{3,}$', str(aid or '').strip())
    return PREFIX_OF.get(match[1], '') if match else ''


def id_field(kind):
    """这一类条目的编号写在哪个键上。"""
    return ID_FIELD.get(kind, '')


def id_of(kind, item):
    """这一条现在的编号（没有就是空串）。"""
    field = id_field(kind)
    return str((item or {}).get(field) or '').strip() if field else ''


# ── 字段与默认值 ────────────────────────────────────────────────────────────
def defaults(kind):
    """这一类条目的键与空壳（normalize 拿它补缺，只补不改）。"""
    if kind == 'character':
        return {'character_id': '', 'name': '', 'aliases': [], 'description': '',
                'physical_features': dict((key, '') for key in PHYSICAL_KEYS),
                'image_prompt': ''}
    if kind == 'scene':
        return {'scene_id': '', 'name': '', 'description': '', 'time_of_day': '',
                'weather': '', 'image_prompt': ''}
    if kind == 'prop':
        return {'prop_id': '', 'name': '', 'description': '', 'holder': '', 'image_prompt': ''}
    if kind == 'scene_breakdown':
        return {'breakdown_id': '', 'episode_id': '', 'scene_id': '', 'order': 0,
                'time_place': '', 'characters': [], 'task': '', 'boundary': ''}
    if kind == 'emotion_curve':
        return {'beat_id': '', 'episode_id': '', 'scene_id': '', 'order': 0, 'intensity': 0,
                'reason': '', 'hook': '', 'turn': ''}
    return {}


def _copy(value):
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    return value


def normalize(kind, item, index=1):
    """补缺的键与缺的编号（返回一份新 dict）：已有的值一个都不动。"""
    if not isinstance(item, dict):
        return None
    out = dict(item)
    for key, value in defaults(kind).items():
        if key not in out:
            out[key] = _copy(value)
    field = id_field(kind)
    if field and not str(out.get(field) or '').strip():
        out[field] = new_id(kind, index)
    if kind == 'character':
        out['physical_features'] = field_features(out.get('physical_features'))
    if kind in ('scene_breakdown', 'emotion_curve') and not out.get('order'):
        out['order'] = int(index)
    return out


# ── 任务 6：物理特征字段化 ──────────────────────────────────────────────────
def _pieces(body):
    """按中文标点把一句话切成片段（不用正则，省得当心转义）。"""
    out, buf = [], []
    for char in str(body or ''):
        if char in SPLIT:
            out.append(''.join(buf))
            buf = []
        else:
            buf.append(char)
    out.append(''.join(buf))
    return [piece.strip() for piece in out if piece.strip()]


def _hit(piece):
    """这个片段该进哪个键：命中的词最长的那个；没命中返回空串。"""
    best, size = '', 0
    for key, words in HINTS:
        for word in words:
            if word in piece and len(word) > size:
                best, size = key, len(word)
    return best


def split_features(text):
    """一整句自然语言 → 五个字段（认不出来的片段留在 raw 里，原文不丢）。"""
    out = dict((key, '') for key in PHYSICAL_KEYS)
    body = str(text or '').strip()
    if not body:
        return out
    rest = []
    for piece in _pieces(body):
        key = _hit(piece)
        if not key:
            rest.append(piece)
            continue
        out[key] = (out[key] + '\u3001' + piece) if out[key] else piece
    if rest:
        out['raw'] = '\u3001'.join(rest)
    return out


def field_features(value):
    """把 physical_features 收成五个字段：字符串＝整句自然语言，按关键词拆；对象＝补齐缺的键。

    老写法（一整句塞在其中一个字段里）也认：只有一个字段有值、而它拆得出两个以上字段时，
    就地拆开——任务 6 要的就是「不许拿自然语言顶上」。
    """
    if not isinstance(value, dict):
        return split_features(value)
    out = dict(value)
    for key in PHYSICAL_KEYS:
        item = out.get(key)
        out[key] = item if isinstance(item, str) else ('' if item is None else str(item))
    filled = [key for key in PHYSICAL_KEYS if out[key].strip()]
    if len(filled) == 1:
        split = split_features(out[filled[0]])
        if len([key for key in PHYSICAL_KEYS if split[key].strip()]) >= 2:
            out.update(split)
    return out


# ── 一份 manifest ───────────────────────────────────────────────────────────
def manifest(kind, items):
    """把条目收成一份 manifest：抬头三件（manifest／kind／items）＋ 补好缺的键与编号。"""
    return {'manifest': MANIFEST_OF_KIND.get(kind, ''), 'kind': kind,
            'items': [normalize(kind, item, index)
                      for index, item in enumerate(items or [], 1) if isinstance(item, dict)]}


def items_of(data):
    """从一份 manifest 里取条目（两种写法都认：带抬头的对象，或直接一个数组）。"""
    values = data.get('items') if isinstance(data, dict) else data
    return [item for item in values if isinstance(item, dict)] if isinstance(values, list) else []


def manifest_name(data, fallback=''):
    """这一份的抬头名（没写抬头时用调用方给的名字兜底）。"""
    return str(data.get('manifest') or fallback) if isinstance(data, dict) else str(fallback)


# ── 任务 7：ID 唯一性 ───────────────────────────────────────────────────────
def duplicate_ids(manifests):
    """所有 manifest 里重复或缺失的编号（跨份撞号也算）。空列表＝全部唯一。

    manifests 是 {manifest 文件名: 那一份数据}；少写的那几类自动跳过。
    """
    seen, problems = {}, []
    for name in MANIFESTS:                       # 顺序固定，报告每次一样
        data = (manifests or {}).get(name)
        if data is None:
            continue
        kind = KIND_OF_MANIFEST[name]
        for position, item in enumerate(items_of(data), 1):
            aid = id_of(kind, item)
            if not aid:
                problems.append('%s：第 %d 条还没有编号' % (name, position))
                continue
            if aid in seen:
                problems.append('%s：%s 与 %s 撞号' % (name, aid, seen[aid]))
                continue
            seen[aid] = name
    return problems


def unique_ids(manifests):
    """所有 manifest 的编号都不重（任务 7 的验收口径）。"""
    return not duplicate_ids(manifests)


def _spare(kind, taken):
    """发一个还没被占的号（从 001 往上找）。"""
    index = 1
    while new_id(kind, index) in taken:
        index += 1
    return new_id(kind, index)


def reassign_ids(manifests):
    """撞号的条目重发号（先出现的那个号留着）：返回 (改好的 manifests, 改动说明)。

    重发号只往空号上排，所以原本占着那个号的条目会跟着让位（每一条改动都记在说明里，
    一条不多一条不少）。形状照旧：原来是一份带抬头的对象，改完还是对象；原来是一个数组，
    改完还是数组。
    """
    taken, changes, fixed = set(), [], {}
    for name in MANIFESTS:
        data = (manifests or {}).get(name)
        if data is None:
            continue
        kind = KIND_OF_MANIFEST[name]
        items = []
        for item in items_of(data):
            item = dict(item)
            aid = id_of(kind, item)
            if aid and aid not in taken:
                taken.add(aid)
            else:
                fresh = _spare(kind, taken)
                taken.add(fresh)
                changes.append('%s：%s → %s' % (name, aid or '（空编号）', fresh))
                item[ID_FIELD[kind]] = fresh
            items.append(item)
        fixed[name] = dict(data, items=items) if isinstance(data, dict) else items
    return fixed, changes


# ── 校验 ────────────────────────────────────────────────────────────────────
def validate(kind, item):
    """这一条的问题（空列表＝通过）。规则就是这一类 manifest 的必填与值域。"""
    problems = []
    if not isinstance(item, dict):
        return ['条目必须是对象']
    field = id_field(kind)
    aid = id_of(kind, item)
    if not aid:
        problems.append('缺少 %s' % field)
    elif not re.match(PATTERN.get(kind, ''), aid):
        problems.append('%s 编号不合规（应为 %s_###）：%s' % (field, PREFIX.get(kind, ''), aid))
    if kind != 'emotion_curve' and not str(item.get('name') or '').strip():
        problems.append('缺少 name')
    if kind == 'character':
        features = item.get('physical_features')
        if isinstance(features, str) and features.strip():
            problems.append('物理特征要字段化（%s），别写成整句自然语言'
                            % '\u3001'.join(PHYSICAL_KEYS))
        elif features is not None and not isinstance(features, (dict, str)):
            problems.append('physical_features 必须是对象或字符串')
        elif not any(str((features or {}).get(key) or '').strip() for key in PHYSICAL_KEYS):
            problems.append('物理特征五件还是空的（%s）' % '\u3001'.join(PHYSICAL_KEYS))
    if kind in ('scene_breakdown', 'emotion_curve'):
        if not re.match(PATTERN['scene'], str(item.get('scene_id') or '').strip()):
            problems.append('scene_id 要写场景编号（LOC_###）：%r' % (item.get('scene_id'),))
    if kind == 'scene_breakdown':
        for member in item.get('characters') or []:
            if not re.match(PATTERN['character'], str(member or '').strip()):
                problems.append('characters 里要写角色编号（CHAR_###）：%r' % (member,))
    if kind == 'emotion_curve':
        value = item.get('intensity')
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 10:
            problems.append('intensity 须为 1～10 的整数：%r' % (value,))
    return problems


# ── 任务 8：五份交付物里「Schema／示例／完整性」这三份的落点 ────────────────
def _box(props, required):
    return {'type': 'object', 'required': list(required), 'properties': props,
            'additionalProperties': True}


def _features_box():
    return {'type': 'object', 'description': '物理特征（五件字段化，任务 6）',
            'properties': dict((key, {'type': 'string', 'description': PHYSICAL_LABELS[key]})
                               for key in PHYSICAL_KEYS),
            'additionalProperties': True}


def _item_box(kind):
    """一类 manifest 的一条目（JSON Schema 里的 items）。"""
    text = {'type': 'string'}
    boxes = {
        'character': (_box({'character_id': {'type': 'string', 'pattern': PATTERN['character']},
                            'name': {'type': 'string', 'minLength': 1},
                            'aliases': {'type': 'array', 'items': text},
                            'description': text, 'physical_features': _features_box(),
                            'image_prompt': text},
                           ('character_id', 'name', 'physical_features')),),
        'scene': (_box({'scene_id': {'type': 'string', 'pattern': PATTERN['scene']},
                        'name': {'type': 'string', 'minLength': 1}, 'description': text,
                        'time_of_day': text, 'weather': text, 'image_prompt': text},
                       ('scene_id', 'name')),),
        'prop': (_box({'prop_id': {'type': 'string', 'pattern': PATTERN['prop']},
                       'name': {'type': 'string', 'minLength': 1}, 'description': text,
                       'holder': {'type': 'string', 'description': '持有者角色编号，没有就留空'},
                       'image_prompt': text},
                      ('prop_id', 'name')),),
        'scene_breakdown': (_box({'breakdown_id': {'type': 'string',
                                                   'pattern': PATTERN['scene_breakdown']},
                                  'episode_id': text,
                                  'scene_id': {'type': 'string', 'pattern': PATTERN['scene']},
                                  'order': {'type': 'integer', 'minimum': 1},
                                  'time_place': text,
                                  'characters': {'type': 'array',
                                                 'items': {'type': 'string',
                                                           'pattern': PATTERN['character']}},
                                  'task': text, 'boundary': text},
                                 ('breakdown_id', 'scene_id', 'order')),),
        'emotion_curve': (_box({'beat_id': {'type': 'string', 'pattern': PATTERN['emotion_curve']},
                                'episode_id': text,
                                'scene_id': {'type': 'string', 'pattern': PATTERN['scene']},
                                'order': {'type': 'integer', 'minimum': 1},
                                'intensity': {'type': 'integer', 'minimum': 1, 'maximum': 10},
                                'reason': text, 'hook': text, 'turn': text},
                               ('beat_id', 'scene_id', 'intensity')),)}
    return boxes[kind][0]


def schema():
    """五类 manifest 的 JSON Schema（交付物 2）：manifest 文件名 → 一份 draft 2020-12 Schema。"""
    out = {}
    for kind in KINDS:
        name = MANIFEST_OF_KIND[kind]
        out[name] = {'$schema': 'https://json-schema.org/draft/2020-12/schema',
                     'title': '漫剧助手 %s（第 70 期任务 5～7）' % name,
                     'type': 'object', 'required': list(HEADER),
                     'properties': {'manifest': {'const': name}, 'kind': {'const': kind},
                                    'items': {'type': 'array', 'items': _item_box(kind)}},
                     'additionalProperties': True}
    return out


# 交付物 3 的那句示例：一句话里五个字段都能认出来。
SAMPLE = '肤色冷白，黑色短发，杏眼，左眉一道浅疤，身形修长'


def sample_character_manifest():
    """交付物 3：改造后的 character_manifest.json 示例（两个角色，物理特征全部字段化）。"""
    return manifest('character', (
        {'character_id': 'CHAR_001', 'name': '林小满', 'aliases': ['小满'],
         'description': '十七岁高中生，米色针织衫配深色长裤',
         'physical_features': SAMPLE,
         'image_prompt': '林小满，十七岁少女，冷白肤色，黑色齐耳短发，杏眼，左眉一道浅疤，'
                         '身形修长，米色针织衫'},
        {'character_id': 'CHAR_002', 'name': '陆时', 'aliases': [],
         'description': '二十出头，深灰风衣，常带着一块旧怀表',
         'physical_features': {'skin_tone': '小麦色', 'hair': '深棕微卷短发', 'eyes': '狭长眼',
                               'distinctive_marks': '左手腕一道旧疤', 'body_type': '高挑结实'},
         'image_prompt': '陆时，小麦肤色，深棕微卷短发，狭长眼，左手腕一道旧疤，高挑结实，深灰风衣'}))


def completeness(folder):
    """剧本阶段产出的完整性检查（交付物 5）：每一类一行（名字／状态／说明）。

    状态是三选一：已产出／缺失／有问题。folder 传 00_script/output（或 00_script）。
    """
    root = Path(folder)
    rows = []
    for name in MANIFESTS:
        path = root / name
        kind = KIND_OF_MANIFEST[name]
        if not path.is_file():
            rows.append((name, '缺失', '这一份还没产出'))
            continue
        try:
            data = read(path)
        except (OSError, ValueError) as exc:
            rows.append((name, '有问题', '读不出来：%s' % exc))
            continue
        items = items_of(data)
        bad = list(duplicate_ids({name: data}))
        for index, item in enumerate(items, 1):
            bad += ['第 %d 条：%s' % (index, text) for text in validate(kind, item)]
        if bad:
            rows.append((name, '有问题', '；'.join(bad[:3])))
        else:
            rows.append((name, '已产出', '%d 条，编号唯一' % len(items)))
    return tuple(rows)


# ── 任务 1～4 的表（从真注册表读，报告与代码同源）──────────────────────────
def program_root(program=None):
    """程序目录。"""
    return Path(program or Path(__file__).resolve().parent)


def manifest_rows(program=None):
    """任务 1 的表：剧本准备及剧本结构 SKILL 的名称／文件路径／输入／输出／输出格式。

    直接读真注册表（`skill_registry` 扫的就是本程序 skills/ 里的 SKILL 文件），
    不在代码里再抄一份——表跟 SKILL 文件不会各说各的。
    """
    # Compatibility facade for callers of the former contract API.  The
    # registry report belongs to L3 and is deliberately loaded only on demand.
    from importlib import import_module
    return import_module('script_skill_report').manifest_rows(program)


def audit_rows(program=None):
    """任务 2／3／4 的表：每个 SKILL 的类别、处理动作、改造后归属与理由。"""
    from importlib import import_module
    return import_module('script_skill_report').audit_rows(program)


def unlisted_skills(program=None):
    """剧本阶段有 SKILL、审计表里却没有它的（正常是空的）。"""
    known = {skill for skill, _category, _owner, _reason in AUDIT}
    return tuple(row['skill'] for row in manifest_rows(program) if row['skill'] not in known)



def support_rows(program=None):
    """任务 3 的收口表：那两个重叠／支撑的 SKILL 现在挂在哪、产物并到哪里去。

    归属者只有 `MERGE_OWNER` 一处；类别与理由仍从 `AUDIT` 读（跟着 `audit_rows()` 走），
    所以报告、面板与自检看的是同一份口径，不各写一遍。
    """
    rows = []
    for row in audit_rows(program):
        landing = MERGE_LANDING.get(row['skill'])
        if landing is None:
            continue
        merged = dict(row)
        merged['owner'] = MERGE_OWNER
        merged['part'] = MERGE_PART[row['skill']]
        merged['landing'] = landing
        rows.append(merged)
    return tuple(rows)


def merge_problems(program=None):
    """收口体检：归属者声明过这个子步骤、并回来的产物有真实落点（正常是空表）。"""
    from importlib import import_module
    return import_module('script_skill_report').merge_problems(program)
