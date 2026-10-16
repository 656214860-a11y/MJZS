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
| emotion_curve.json | pipeline-script-preparation（全流程AIGC·剧本） | 剧本准备 |
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
    """返回全部用户可见自然剧本，明确排除内部工作稿副本。"""
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


def natural_script_selection_path(project):
    """项目采用版本台账；共享成果与模型聊天分区分别管理。"""
    from stage_path_service import write_dir
    return write_dir(project, 'script') / 'natural_script_selection.json'


# ── 分集增量账本：自然剧本按集解析与变更追踪 ─────────────────────────────────
# 阶段④的自然剧本按 `# 第{集数}集：{标题}` 分段输出。这里提供一条与 02 结构剧本
# 场次解析完全平行的能力，只回答「哪几集相对上次生成有改动」，不替换、不参与
# structure_script() 的场次整理。
EPISODE_LEDGER_NAME = '剧本分集增量账本.json'
UNSPLIT_EPISODE_KEY = '未分集'
_EPISODE_HEADING = re.compile(
    r'(?m)^[ \t]*(?:#{1,6}[ \t]*)?第[ \t]*(\d{1,4})[ \t]*集[ \t]*[：:]?[ \t]*(.*?)[ \t]*\r?$')


def split_script_episodes(text):
    """按「第N集」标题把正文切成有序分集。

    返回 ``{集号: 正文块}``：集号是 ``int``，正文块保留标题行本身，便于追溯。
    标题容错全半角冒号、零填充、标题文字缺失与 ``#`` 级数；正文开头若还有标题
    之前的整段文字，记到 ``UNSPLIT_EPISODE_KEY`` 一项。解析不出任何集号标题时，
    整篇作为一项「未分集」返回，不报错也不丢正文；空正文返回空字典。

    同一集号重复出现时保留首次出现的正文块，不把两次生成静默合并。
    """
    raw = str(text or '').replace('\r\n', '\n').replace('\r', '\n')
    hits = list(_EPISODE_HEADING.finditer(raw))
    if not hits:
        stripped = raw.strip()
        return {UNSPLIT_EPISODE_KEY: stripped} if stripped else {}
    episodes = {}
    preamble = raw[:hits[0].start()].strip()
    if preamble:
        episodes[UNSPLIT_EPISODE_KEY] = preamble
    for position, match in enumerate(hits):
        end = hits[position + 1].start() if position + 1 < len(hits) else len(raw)
        body = raw[match.start():end].strip()
        number = int(match.group(1))
        if body and number not in episodes:
            episodes[number] = body
    return episodes


def episode_digest(text):
    """单集正文的内容指纹；首尾空白与换行口径不影响判定。"""
    body = str(text or '').replace('\r\n', '\n').replace('\r', '\n').strip()
    return hashlib.sha256(body.encode('utf-8')).hexdigest()


def episode_label(number):
    """分集的用户可读称谓；未分集返回「未分集正文」。"""
    return '未分集正文' if number == UNSPLIT_EPISODE_KEY else '第%s集' % number


def episode_ledger_path(project):
    """分集增量账本路径；与自然剧本采用台账同目录、同阶段写入目录。"""
    from stage_path_service import write_dir
    return write_dir(project, 'script') / EPISODE_LEDGER_NAME


def read_episode_ledger(project):
    """读分集增量账本；缺失、损坏或格式不符时返回空账本，绝不阻断生成。"""
    path = episode_ledger_path(project)
    try:
        payload = read(path) if path.is_file() else {}
    except (OSError, ValueError):
        payload = {}
    episodes = payload.get('episodes') if isinstance(payload, dict) else None
    clean = {}
    for number, entry in (episodes or {}).items():
        if not isinstance(entry, dict) or not isinstance(entry.get('sha256'), str) or not entry['sha256']:
            continue
        based = entry.get('based_on')
        clean[str(number)] = {
            'sha256': entry['sha256'],
            'based_on': {str(key): value for key, value in (based or {}).items()
                         if isinstance(value, str) and value},
        }
    return {'version': 1, 'episodes': clean}


def write_episode_ledger(project, ledger):
    """原子写入分集增量账本；调用方负责在失败时不阻断本次生成。"""
    from agent.core import save
    path = episode_ledger_path(project)
    save(path, ledger)
    return path


def episode_change_report(text, ledger=None):
    """把当前分集与账本比对，返回 ``(changed, unchanged)`` 两个有序映射。

    账本缺失或某一集从未记录时，该集算作变化；首次使用时全部集都变化，等价于
    旧的全量参考行为。
    """
    episodes = split_script_episodes(text)
    known = (ledger or {}).get('episodes') or {}
    changed, unchanged = {}, {}
    for number, body in episodes.items():
        entry = known.get(str(number))
        if isinstance(entry, dict) and entry.get('sha256') == episode_digest(body):
            unchanged[number] = body
        else:
            changed[number] = body
    return changed, unchanged


def episode_reference_block(text, ledger=None):
    """构造模型 prompt 的「参考改动」段：只贴变化的集正文。

    未变化的集只列出集号，不重复正文；账本缺失或从未记录（首次使用）时退化为
    把现有全部集正文都当作参考改动，等价于旧的全量行为。没有正文时返回空串。
    """
    if not str(text or '').strip():
        return ''
    changed, unchanged = episode_change_report(text, ledger)
    if not changed and not unchanged:
        return ''
    known = (ledger or {}).get('episodes') or {}
    first_use = not any(str(number) in known for number in (list(changed) + list(unchanged)))
    total = len(changed) + len(unchanged)
    if first_use:
        lines = ['【分集增量参考】尚未建立分集变更基线；以下为当前全部已有集正文（首次记录）。']
        marker = '（当前版本）内容如下：'
    else:
        lines = ['【分集增量参考】当前自然剧本共 %d 集；只提供相对上次生成有改动的集正文。' % total]
        marker = '已修改，内容如下：'
    for number, body in changed.items():
        lines.append(episode_label(number) + marker)
        lines.append(body)
    if unchanged:
        lines.append('（未变化的集：' + '、'.join(episode_label(number) for number in unchanged)
                     + '；正文不重复提供，沿用已确认版本。）')
    return '\n'.join(lines)


def script_baseline_path(project):
    """当前自然剧本基准文件：优先采用版本，其次最新自然剧本，最后内部工作稿。

    用户手改自然剧本会让采用台账的哈希失效，因此这里不把采用台账当唯一依据，
    只取「最新一份可见自然剧本」；都读不到时返回 None。
    """
    try:
        source = resolve_script_source(project)
    except (OSError, ValueError):
        source = None
    candidates = [source] if source is not None else []
    try:
        candidates.extend(natural_script_paths(project))
    except (OSError, ValueError):
        pass
    from stage_path_service import write_dir
    candidates.append(write_dir(project, 'script') / RAW_SCRIPT_NAME)
    for path in candidates:
        try:
            if path.is_file() and path.stat().st_size:
                return path
        except OSError:
            continue
    return None


def script_episode_baseline(project):
    """当前分集比对基准正文；读不到时返回空串。"""
    path = script_baseline_path(project)
    try:
        return path.read_text(encoding='utf-8', errors='ignore') if path else ''
    except OSError:
        return ''


def record_episode_ledger(project, text, previous_text=''):
    """调用后更新账本：记录各集当前 sha256 与生成时其余各集的 sha256 快照。

    ``previous_text`` 是本次生成前的剧本正文（模型实际依据的版本）；有变化或新
    出现的集，其 ``based_on`` 取该版本其余各集的指纹；未变化的集保留已有记录。
    没有可解析正文时不改动账本。
    """
    episodes = split_script_episodes(text)
    ledger = read_episode_ledger(project)
    if not episodes:
        return ledger
    known = ledger['episodes']
    before = {str(number): episode_digest(body)
              for number, body in split_script_episodes(previous_text).items()}
    updated = {}
    for number, body in episodes.items():
        key = str(number)
        digest = episode_digest(body)
        if key in known and known[key]['sha256'] == digest:
            updated[key] = dict(known[key])
            continue
        updated[key] = {'sha256': digest,
                        'based_on': {other: value for other, value in before.items() if other != key}}
    ledger = {'version': 1, 'episodes': updated}
    write_episode_ledger(project, ledger)
    return ledger


def resolve_script_source(project):
    """优先采用用户确认的内容版本；多份候选不得按修改时间自动替换。"""
    paths = natural_script_paths(project)
    selection_path = natural_script_selection_path(project)
    if selection_path.exists():
        selection = read(selection_path)
        if not isinstance(selection, dict):
            return None
        source = (Path(project) / str(selection.get('path') or '')).resolve()
        if not source.is_relative_to(Path(project).resolve()) or not source.is_file():
            return None
        from stage_path_service import read_dirs
        if not any(source.is_relative_to(folder.resolve()) for folder in read_dirs(project, 'script')):
            return None
        content = source.read_bytes()
        if (hashlib.sha256(content).hexdigest() != selection.get('sha256')
                or not is_natural_script(content.decode('utf-8', errors='ignore'))):
            return None
        return source
    if len(paths) == 1:
        return paths[0]
    if paths:
        return None
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


_STAGE_FILE_TYPES = ('自然剧本', '项目大纲', '项目设定', '角色卡', '结构剧本')
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


_FEATURES = ('岁', '发', '眼', '肤', '身', '高', '矮')
_ALIAS = re.compile(r'(?:又名|别名|绰号|昵称)[：:]?\s*([^\s，。；、）)]{1,12})')
_FLASHBACK = ('回忆', '闪回', '倒叙', '梦境', '梦里')
_UNTAGGED_SPEAKERS = '待确认（原稿本场未出现“人物名：对白”标签）'
_RULE_NOTE = ('> 生成方式：本地规则提取（未调用模型）；未标明的字段来自原稿，'
              '标「待确认」的是原稿未明确、需人工补充的制作信息。')
_COMPLETENESS_NOTE = '> 结构合法不等于制作信息齐全：待确认项由人工补充，程序不臆造。'


def _alias_of(raw, name):
    """只认原稿明确声明的别名；没有就标待确认，绝不从上下文编造。"""
    for line in raw.splitlines():
        if name in line:
            match = _ALIAS.search(line)
            if match and match.group(1).strip():
                return match.group(1).strip() + '（来源：原稿声明）'
    return '待确认（原稿未明确）'


def _character_id(name):
    """按角色名生成稳定的跨集 ID：同一名字在任何一集得到同一串。"""
    digest = hashlib.sha1(str(name).encode('utf-8')).hexdigest()[:8]
    return 'char-%s（程序按角色名生成，仅作跨集引用；可人工改名）' % digest


def _same_name_note(scenes, name):
    """同名不同人只在原稿特征互相矛盾时提醒，不凭猜测拆角色。"""
    features = {_first_sentence(body, _FEATURES) for _title, body in scenes if name in body}
    features.discard('待确认（原稿未明确）')
    if len(features) > 1:
        return '原稿中「%s」在不同场次特征不一致，可能是同名不同人（待确认）。' % name
    return ''


def _scene_timeline(body):
    """只在原稿出现回忆／闪回等关键词时标注，并点明这是关键词识别、仍需确认。"""
    if any(word in body for word in _FLASHBACK):
        return '回忆／闪回（待确认：原稿未逐场标注，仅按关键词识别）'
    return ''


def structure_script(raw_text, source_name=RAW_SCRIPT_NAME):
    """按本地规则把自然语言原稿整理成 Markdown 正稿；不调用模型，也不改动原始文本。"""
    raw = str(raw_text or '').strip()
    if not raw:
        raise ValueError('writing/script_raw.md 为空，无法整理结构化剧本。')
    scenes = _scene_blocks(raw)
    characters = _unique(name for _title, body in scenes for name in _speakers(body))
    props = _unique(match.group(1).strip() for match in re.finditer(r'(?:道具|物品)[：:]?\s*([^，。；\n]{1,30})', raw))
    lines = ['# 结构化剧本', '', '> 来源：`%s`（原稿保持不变）' % source_name, _RULE_NOTE, _COMPLETENESS_NOTE,
             '', '## 角色档案', '']
    if characters:
        for name in characters:
            related = '\n'.join(body for _title, body in scenes if name in body)
            lines += ['### ' + name,
                      '- 别名：' + _alias_of(raw, name),
                      '- 跨集 ID：' + _character_id(name),
                      '- 物理特征：' + _first_sentence(related, _FEATURES),
                      '- 默认服装：' + _first_sentence(related, _CLOTHING),
                      '- 换装需求：待确认（原稿未明确）']
            note = _same_name_note(scenes, name)
            if note:
                lines.append('- 同名提醒：' + note)
            lines.append('')
    else:
        lines += ['- 待确认：原稿未出现“人物名：对白”标签，未能识别角色；请人工补充角色档案。', '']
    lines += ['## 场景档案', '']
    for order, (title, body) in enumerate(scenes, 1):
        lines += ['### 场景 %02d：%s' % (order, title),
                  '- 空间锚点：' + _first_sentence(body, ('内', '外', '店', '家', '学校', '街', '楼', '房', '站')),
                  '- 光照方向：' + _first_sentence(body, ('光', '夜', '晨', '晚', '日', '灯')),
                  '- 尺度参考：待确认（原稿未明确）']
        timeline = _scene_timeline(body)
        if timeline:
            lines.append('- 时间线：' + timeline)
        lines.append('')
    lines += ['## 道具档案', '']
    lines += (['- ' + item + '：尺寸、材质、持有者待确认（来源：原稿声明）。' for item in props]
              or ['- 待确认：原稿未明确关键道具。'])
    lines += ['', '## 分场剧本', '']
    for order, (title, body) in enumerate(scenes, 1):
        participants = '、'.join(_speakers(body)) or _UNTAGGED_SPEAKERS
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
    """本地规则校验提取结果，返回可展示的反馈；不调用模型、不改动任何文件。"""
    raw = str(raw_text or '').strip()
    structured = str(structured_text or '').strip()
    feedback = []
    required = ('角色档案', '场景档案', '道具档案', '分场剧本')
    for heading in required:
        if '## ' + heading not in structured:
            feedback.append('缺少「%s」区块。' % heading)
    if '本地规则提取' not in structured:
        feedback.append('结构剧本未标明生成方式为本地规则提取（未调用模型）。')
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
        if '- 别名：' not in card:
            feedback.append('角色「%s」缺少别名项（应保留出处或标待确认）。' % name)
        if '- 跨集 ID：' not in card:
            feedback.append('角色「%s」缺少跨集 ID。' % name)
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
    """按反馈用本地规则重新提取；源稿矛盾保留给用户修正，绝不臆造事实。"""
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
# 此值是旧 manifest 的兼容键，不是新建目录名：stage_layout 会将它解析为
# 「01剧本准备」。剧本工作流已拆成「剧本准备」和「剧本结构」两段。
SCRIPT_SKILL_STAGES = ('script', 'script_structure')
# stage_layout.STAGES 通过兼容键引用它，两处不会各写一份。

# 剧本准备的节奏约束是 SKILL 输入模板，不是本阶段新增产物；因此不加入
# STAGE_OUTPUTS，避免被完整性检查误判成必须生成的 manifest。后续编排器只通过这个字段
# 引用模板，不复制路径字符串。
RHYTHM_TEMPLATE_FIELD = 'rhythm_template'
RHYTHM_TEMPLATE_PATH = 'skills/templates/rhythm_template.yaml'

# 剧本准备的输入简报同样由本契约统一命名；创意接收层只负责从用户原话提取并落盘，
# 不在 idea_chat.py 再复制一套“哪些字段必须有”的判断。
BRIEF_REQUIRED_FIELDS = ('story_summary', 'main_characters', 'genre', 'length')
INLINE_REQUIRED_LABELS = ('故事梗概', '故事题材', '故事角色', '故事集数', '单集时间')
STAGE_LOCK_REQUIREMENTS = {
    'script': ('delivery_format', 'track', 'material_source'),
    'keyframe': ('aspect_ratio', 'video_model_version', 'delivery_format'),
    'video': ('aspect_ratio', 'video_model_version', 'delivery_format'),
    'previs': ('aspect_ratio', 'video_model_version', 'delivery_format'),
}
PRODUCTION_LOCK_DEFINITIONS = (
    # options 是界面下拉的常用值，不是白名单；画幅、交付形态、视频模型与 AIGC 全流程 SKILL 的 A/B/C 锁对齐。
    {'key': 'aspect_ratio', 'label': '画幅', 'aliases': ('故事画幅',), 'options': ['9:16', '16:9', '21:9', '1:1']},
    {'key': 'resolution', 'label': '分辨率', 'aliases': ('输出分辨率',), 'options': [
        '1080x1920', '1920x1080', '720x1280', '1280x720', '480x854', '854x480', '1440x2560', '2560x1440',
        '2160x3840', '3840x2160', '2560x1080', '1080x1080']},
    {'key': 'fps', 'label': '帧率', 'aliases': ('输出帧率',), 'options': ['24', '25', '30', '50', '60']},
    {'key': 'delivery_format', 'label': '交付形态', 'aliases': (), 'options': ['两者都交付', '只要离线看板', '只要 markdown 文档']},
    {'key': 'video_model_version', 'label': '视频模型版本', 'aliases': ('视频模型',), 'options': ['Seedance 2.5', 'Seedance 2.0', 'MiniMax H3', '即梦 3.0'],
     # 手填了下拉以外的模型：统筹 SKILL 没有它的专用语法，提示词退回 SKILL 默认格式，不现编格式。
     'fallback': '总控 SKILL 未适配该模型，提示词按 SKILL 默认格式撰写（七段式，Seedance 2.5 语法）'},
    {'key': 'track', 'label': '赛道', 'aliases': ('故事赛道',),
     'options': ['国内剧', '海外剧', '解说叙事类', '其他'], 'required_from': '2026-10-15'},
    {'key': 'material_source', 'label': '素材来源', 'aliases': ('创作来源',),
     'options': ['原创', '改编（有原著）', '对标爆款（现场采风）', '热点速成（给方向先找选题）'],
     'required_from': '2026-10-15'},
    {'key': 'reference_mode', 'label': '参考模式', 'aliases': ('视频参考模式',),
     'options': ['全能参考模式', '首尾帧模式'], 'default': '全能参考模式',
     'depends_on': {'video_model_version': 'Seedance 2.5'}},
    {'key': 'splice_mode', 'label': '段缝衔接方式', 'aliases': ('段缝衔接',),
     'options': ['末帧定格承接', '换机位硬切', '空镜过渡', '技巧型转场'], 'default': '末帧定格承接'},
    {'key': 'style_base', 'label': '画风基底', 'aliases': ('风格基底',),
     'options': ['真人实拍质感', '2D 手绘动画', '3D CG 动画', '水墨二维']},
    {'key': 'style_directors', 'label': '导演风格卡', 'aliases': ('导演卡',), 'options': []},

)

# 提取范围独立于必填范围：建议值仍保留，不因阶段门禁收窄而丢失。
BRIEF_EXTRACTION_LABELS = INLINE_REQUIRED_LABELS + tuple(
    next(iter(item['aliases']), item['label']) for item in PRODUCTION_LOCK_DEFINITIONS)


def lock_stage(stage):
    """工作流名称与阶段编号名称在契约边界归一。"""
    return {'writing': 'script', 'frames': 'keyframe', 'video_prompt': 'video'}.get(stage, stage)


def production_lock_date(value):
    """未记录创建时间的旧调用保留兼容；有时间时按本地自然日比较。"""
    from datetime import datetime
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value).date().isoformat()
    return str(value or '')[:10]


def production_lock_active(item, values):
    return all(values.get(key) == value for key, value in item.get('depends_on', {}).items())


def validate_production_locks(values):
    import re
    cards = [card.strip() for card in re.split('[,，]', str(values.get('style_directors') or '')) if card.strip()]
    if len(cards) > 4:
        raise ValueError('导演风格卡最多 4 张，请用逗号分隔')


def stage_lock_requirements(stage, created_at=None):
    """未登记阶段没有必填制作锁。"""
    required = STAGE_LOCK_REQUIREMENTS.get(lock_stage(stage), ())
    dated = {item['key']: item['required_from'] for item in PRODUCTION_LOCK_DEFINITIONS if item.get('required_from')}
    day = production_lock_date(created_at)
    return tuple(key for key in required if key not in dated or (day and day >= dated[key]))

def stage_lock_definitions(stage, definitions):
    """优先使用统筹标签；未配置统筹时，必填锁仍使用契约默认标签。"""
    definitions = tuple(definitions)
    known = {item['key'] for item in definitions}
    required = STAGE_LOCK_REQUIREMENTS.get(lock_stage(stage), ())
    return definitions + tuple(item for item in PRODUCTION_LOCK_DEFINITIONS
                               if item['key'] in required and item['key'] not in known)


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
    """创意简报引用的节奏模板字段。"""
    return {RHYTHM_TEMPLATE_FIELD: RHYTHM_TEMPLATE_PATH}


def normalize_brief(values=None):
    """将创意接收层的字段收敛到唯一的剧本准备输入简报形状。"""
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
    """建立可供剧本准备读取的已确认简报，必填项未齐时拒绝伪造完成态。"""
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

from script_manifest_schema import (
          AUDIT,
          CATEGORIES,
          HINTS,
          ID_FIELD,
          MERGED,
          MERGED_SKILLS,
          MERGE_LANDING,
          MERGE_OWNER,
          MERGE_PART,
          PATTERN,
          PHYSICAL_KEYS,
          PHYSICAL_LABELS,
          PREFIX,
          PREFIX_OF,
          PRODUCERS,
          PRODUCER_SKILLS,
          SAMPLE,
          SPLIT,
          STAGE,
          _box,
          _copy,
          _features_box,
          _hit,
          _item_box,
          _pieces,
          _spare,
          completeness,
          defaults,
          duplicate_ids,
          field_features,
          id_field,
          id_of,
          items_of,
          kind_of_id,
          manifest,
          manifest_name,
          new_id,
          normalize,
          reassign_ids,
          sample_character_manifest,
          schema,
          split_features,
          unique_ids,
          validate)

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




from script_output_spec import (
          LOUDNESS_DEFAULTS,
          OUTPUT_SPEC_DEFAULTS,
          PREVIEW_FPS,
          PREVIEW_SHORT_EDGE,
          _even,
          _fit_ratio,
          _fps,
          describe_output_spec,
          loudness_filter,
          output_filter,
          overlay_metrics,
          parse_ratio,
          parse_resolution,
          preview_spec,
          resolve_output_spec)

