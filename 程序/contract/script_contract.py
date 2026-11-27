# -*- coding: utf-8 -*-
"""剧本阶段产出契约（第 70 期任务 5／6／7）：五类 manifest 的字段、字段化物理特征与 ID 唯一性。

附件《剧本阶段SKILL审计命令》里，任务 1～4 是审计、任务 5～7 是「缺什么补什么」。这一份把要补的
东西落成能跑、能验的代码，不再只是报告里的一段话：

- 任务 5：剧本阶段要产出五类 JSON —— character_manifest／scene_manifest／prop_manifest／
  scene_breakdown／emotion_curve。`MANIFESTS` 是这五个文件名，`STAGE_MANIFESTS` 按产出阶段
  交给 `stage_layout.STAGES` 各阶段的输出，`manifest()` 把条目收成一份带抬头的文件
  （抬头三件：manifest／kind／items）。
- 任务 6：character_manifest.json 里每个角色的 physical_features 必须是字段化的五件：
  skin_tone／hair／eyes／distinctive_marks／body_type。整句自然语言交给 `field_features()` 拆字段，
  认不出来的片段留在 raw 里（原文不丢）。
- 任务 7：所有 manifest 里的 ID 必须唯一。`duplicate_ids()` 报重复、`reassign_ids()` 重发号、
  `unique_ids()` 是验收口径；`completeness()` 是产出完整性那一份报告（交付物 5）。
- 任务 1～4 的审计表也做成数据：`AUDIT` 等常量声明每个 SKILL 的类别与处理动作；
  读真注册表的报告函数（`manifest_rows()`／`audit_rows()`／`support_rows()`／
  `merge_problems()`／`unlisted_skills()`）权威实现在 L3 `orchestrator.script_skill_report`，
  本层不反向依赖注册表（K2）。

口径跟 `asset_contract` 一致——**只补不改**：normalize 只补缺的键与缺的编号，已有的值一个都不动，
老 JSON 少这几个键照旧读得出来。

五类 manifest 的产出者（`PRODUCERS` 是唯一口径）：

| manifest | 产出 SKILL | 这一步在哪一阶段 |
|:---|:---|:---|
| character_manifest.json／scene_manifest.json／prop_manifest.json | script-character-extraction（角色与设定提取） | 剧本结构 |
| emotion_curve.json | stage:script（剧本准备阶段产出；旧值 pipeline-script-preparation 只读兼容） | 剧本准备 |
| scene_breakdown.json | storyboard-scene-breakdown（场次拆分） | 初步分镜 |

场次拆分那个 SKILL 归在「初步分镜」，产物按契约落在 03初步分镜/output（由已采用分镜派生并核验），
所以它也算剧本阶段的产出——`PRODUCERS` 里照实写，别归错。
"""
import json
from agent.core import read
import re
import hashlib
from datetime import datetime
from pathlib import Path
from contract.script_manifest_contract import (HEADER, KIND_OF_MANIFEST, MANIFEST_KINDS, MANIFEST_OF_KIND,
                                      MANIFESTS, STAGE_OUTPUTS, STRUCTURE_MANIFESTS)

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

def save_natural_script(path, text):
    """原子保存用户手改的自然剧本。"""
    path = Path(path)
    if path.suffix.lower() != '.md':
        raise ValueError('自然剧本必须保存为 Markdown 文件。')
    value = str(text or '').strip()
    if not value:
        raise ValueError('空正文')
    from agent.core import save_text
    save_text(path, value + '\n')
    return path


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
    from contract.stage_path_service import read_dirs
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
            if path.stat().st_size:
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
    from contract.stage_path_service import write_dir
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
    from contract.stage_path_service import write_dir
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
    """当前自然剧本基准文件。

    已有采用／定稿记录时，只认那一份：内容被手改导致哈希失效时返回 None，
    不得改用另一份更新的草稿。没有采用记录时，才回退到唯一自然剧本或内部工作稿。
    """
    try:
        source = resolve_script_source(project)
    except (OSError, ValueError):
        source = None
    locked = bool(getattr(resolve_script_source, 'selection_present', False))
    candidates = [source] if source is not None else []
    try:
        found = list(natural_script_paths(project))
    except (OSError, ValueError):
        found = []
    candidates.extend([] if locked else found)
    from contract.stage_path_service import write_dir
    raw = write_dir(project, 'script') / RAW_SCRIPT_NAME
    candidates.extend([] if locked else [raw])
    for path in candidates:
        try:
            if path.is_file() and (locked or path.stat().st_size):
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
    resolve_script_source.selection_present = False
    paths = natural_script_paths(project)
    selection_path = natural_script_selection_path(project)
    present = selection_path.exists()
    resolve_script_source.selection_present = present
    if present:
        selection = read(selection_path)
        if not isinstance(selection, dict):
            return None
        source = (Path(project) / str(selection.get('path') or '')).resolve()
        if not source.is_relative_to(Path(project).resolve()) or not source.is_file():
            return None
        from contract.stage_path_service import read_dirs
        if not any(source.is_relative_to(folder.resolve()) for folder in read_dirs(project, 'script')):
            return None
        content = source.read_bytes()
        if hashlib.sha256(content).hexdigest() != selection.get('sha256'):
            return None
        return source
    if len(paths) == 1:
        return paths[0]
    if paths:
        return None
    from contract.stage_path_service import read_dirs
    for primary in (folder / RAW_SCRIPT_NAME for folder in read_dirs(project, 'script')):
        try:
            if primary.is_file() and primary.stat().st_size:
                return primary
        except OSError:
            continue
    return None


def project_name(project):
    """从项目目录取得稳定项目名，剥离创建目录附带的日期／序号。"""
    from contract.file_naming import existing_project_name
    return existing_project_name(project)


def _file_name_part(value, fallback):
    """把文件类型／内容收成稳定、安全的用户可见文件名片段。

    R3093（任务书 P0，Q14）：清洗规则的实体已收到 L0 ``contract.file_naming.sanitize_part``，
    这里只做等价委托——输出逐字不变，命名规则从此只有一处实现。
    """
    from contract.file_naming import sanitize_part
    return sanitize_part(value, fallback)


def stage_file_name(project, file_type, content, at=None):
    """用户可见剧本文件名：项目名_文件类型_文件内容_年月日.md。"""
    day = (datetime.fromtimestamp(at) if at is not None else datetime.now()).strftime('%Y%m%d')
    from contract.file_naming import generate_existing
    return generate_existing('stage_script', project=project, file_type=file_type, content=content, date=day)


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


def structured_script_file_name(project, file_type='结构剧本', content='本地', at=None):
    """剧本结构用户文件名，和剧本准备统一使用项目名四段式。

    内容段默认 ``本地``（本地规则生成，不调模型）；经模型生成时由调用方传入厂商名。
    旧 ``_正稿_`` 文件不再新生成，仅作只读兼容识别，不批量改名。
    """
    return stage_file_name(project, file_type, content, at=at)


def is_structured_script_file_name(path):
    """识别当前格式和迁移前的阶段前缀格式。"""
    stem = Path(path).stem
    info = stage_file_info(path)
    return ((info is not None and info['file_type'] == '结构剧本') or
            stem.startswith('结构剧本_') or
            stem.startswith('剧本结构_结构剧本_'))


def _is_declared_structured_script(path, head):
    """按命名规则写进「结构剧本」目录的稿：文件名声明了文件类型，正文非空即认。

    模型写的结构稿常按集排版（「# 第1集：…」＋「分场结构」），和本地规则的版式不同。
    这类稿不靠正文版式猜：目录和文件名是用户看得见、说得清的约定（REQ-S02-21）。
    """
    return (STRUCTURED_SCRIPT_DIR in path.parent.parts
            and is_structured_script_file_name(path)
            and bool(head.lstrip('\ufeff').strip()))


def is_structured_script(path):
    """确认结构剧本：本地规则版式看正文首部，其余只认「结构剧本」目录里按命名规则写的稿。

    看正文首部是为了不把误命名为 script.md 的大纲送入分镜。
    """
    path = Path(path)
    if not path.is_file() or path.suffix.lower() != '.md':
        return False
    try:
        # 标题及档案区都在开头；仅读小块，不把整份长剧本重复载入。
        head = path.read_text(encoding='utf-8', errors='replace')[:4096]
    except OSError:
        return False
    standard = '# 结构化剧本' in head and ('## 角色档案' in head or '## 分场剧本' in head)
    if not standard and not _is_declared_structured_script(path, head):
        return False
    # 早期流程会把“项目大纲”直接送给结构化器，产出虽然有结构化标题，
    # 本质仍是大纲提取，不能伪装成可供初步分镜使用的自然剧本正稿。
    source = re.search(r'(?m)^>\s*来源：`?([^`\n]+)', head)
    source_name = source.group(1).casefold() if source else ''
    return not any(mark in source_name for mark in ('大纲', '纲要', 'outline', '梗概'))


def _structured_script_candidates(project, available_only=True):
    """发现独立阶段与旧 writing 目录中的结构剧本文件。

    ``available_only`` 为 True 时只保留来源仍可用的稿（供下拉框展示）；为 False 时
    返回全部合格结构稿（供回收同源旧份时定位，来源已失效也要回收）。
    """
    project = Path(project)
    from contract.stage_path_service import read_dirs, write_dir
    writing = write_dir(project, 'script')
    candidates = []
    for folder in (write_dir(project, 'structure') / STRUCTURED_SCRIPT_DIR,
                   writing / STRUCTURED_SCRIPT_DIR,
                   *[legacy / STRUCTURED_SCRIPT_DIR for legacy in read_dirs(project, 'script')[1:]]):
        if folder.is_dir():
            for path in folder.rglob('*.md'):
                if is_structured_script(path) and (
                        not available_only or _structured_source_is_available(project, path)):
                    candidates.append(path)
    # Old projects kept a compatibility copy directly under ``writing/``.
    # Discover it read-only, rather than creating a duplicate in the current
    # stage directory when a historic project is opened.
    legacy_scripts = (writing / STRUCTURED_SCRIPT_NAME, *(
        legacy_root / STRUCTURED_SCRIPT_NAME
        for legacy_root in read_dirs(project, 'script')[1:]
    ))
    for legacy in legacy_scripts:
        if is_structured_script(legacy) and (
                not available_only or _structured_source_is_available(project, legacy)):
            candidates.append(legacy)
    return candidates


def _structured_source_identity(project, path):
    """结构稿的来源身份：有血缘记录用来源路径，无记录退化为内容指纹。

    返回 ``('source', (相对来源路径, ...))`` 或 ``('content', sha256 十六进制)``；
    读不动返回 None（调用方跳过）。
    """
    from contract.artifact_lineage import check
    try:
        report = check(Path(project), Path(path))
    except (OSError, ValueError):
        report = {}
    sources = tuple(sorted(
        str(row.get('path') or '') for row in report.get('sources', ())
        if isinstance(row, dict) and row.get('path')))
    if sources:
        return ('source', sources)
    try:
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None
    return ('content', digest)


def _is_newer(path, other):
    """同一来源内比较新旧：mtime 优先，同名时按路径字符串兜底保证确定性。"""
    try:
        left = (Path(path).stat().st_mtime, str(path))
        right = (Path(other).stat().st_mtime, str(other))
    except OSError:
        return False
    return left > right


def structured_script_paths(project):
    """返回独立阶段中的结构剧本，同一来源只保留最新一份。

    有血缘记录的结构稿按来源分组去重（同源只显示最新）；无来源记录的历史稿按内容
    sha256 去重，不因没有来源记录而被误删或误合并。
    """
    latest = {}
    for path in _structured_script_candidates(project):
        key = _structured_source_identity(project, path)
        if key is None:
            continue
        previous = latest.get(key)
        if previous is None or _is_newer(path, previous):
            latest[key] = path
    return tuple(sorted(latest.values(),
                        key=lambda item: (item.stat().st_mtime, str(item)), reverse=True))


def canonical_structured_script_path(project, content='本地'):
    """新建结构剧本的唯一位置：项目中的独立剧本结构阶段。

    ``content`` 是四段式文件名中的内容段：本地规则生成用 ``本地``，经模型生成用厂商名。
    """
    from contract.stage_path_service import write_dir
    return (write_dir(project, 'structure') / STRUCTURED_SCRIPT_DIR
            / structured_script_file_name(project, '结构剧本', content))


def superseded_structured_scripts(project, source, *, exclude=None):
    """返回与 ``source`` 同来源、可被新稿取代的旧结构稿路径（不含 ``exclude``）。

    只按血缘来源路径匹配；无来源记录的历史稿不会被当成同源份回收。
    """
    root = Path(project)
    source = Path(source)
    new_key = ('source', (_source_label(root, source),))
    excluded = Path(exclude).resolve() if exclude is not None else None
    superseded = []
    for path in _structured_script_candidates(root, available_only=False):
        if excluded is not None and Path(path).resolve() == excluded:
            continue
        if _structured_source_identity(root, path) == new_key:
            superseded.append(path)
    return superseded


def structured_script_path(project):
    """当前最新结构剧本，兼容迁移前根目录的 writing/script.md。"""
    canonical = canonical_structured_script_path(project)
    paths = structured_script_paths(project)
    return paths[0] if paths else canonical


def _structured_source_is_available(project, structured_path):
    """结构稿只在其记录的原稿仍存在时显示，避免删除原稿后留下孤立下游稿。"""
    from contract.artifact_lineage import source_available
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


def write_structured_script(project, content=None, source=None, publisher=None,
                            vendor=None, supersede=None):
    """原子写入项目的独立结构阶段；旧 writing 目录仅兼容读取。

    ``vendor`` 是文件名内容段：默认 ``本地``（本地规则生成，不调模型），经模型生成时
    由调用方传厂商名（经 :func:`_file_name_part` 净化）。``supersede`` 是可选回调
    ``supersede(paths)``，在新稿写入成功后把同来源的旧结构稿移入回收站（回收动作由
    L3/L4 注入，本契约层不直接依赖回收服务）。
    """
    root = Path(project)
    from contract.stage_path_service import legacy_read_dirs, write_dir
    writing = write_dir(root, 'script').resolve()
    source = resolve_script_source(root) if source is None else Path(source)
    if source is None or not source.is_file():
        raise ValueError('未找到可读取的剧本原稿，请先在“剧本准备”生成或添加剧本。')
    source = source.resolve()
    readable = (writing, *[path.resolve() for path in legacy_read_dirs(root, 'script')])
    if not any(source.is_relative_to(folder) for folder in readable):
        raise ValueError('剧本来源必须位于当前项目的 writing 目录。')
    rendered = (structure_script(source.read_text(encoding='utf-8-sig'), _source_label(root, source))
                if content is None else str(content))
    if not rendered.strip():
        raise ValueError('结构剧本正文不能为空，未发布成果。')
    name_segment = _file_name_part(vendor, '本地') if vendor else '本地'
    target = canonical_structured_script_path(root, content=name_segment)
    from contract.artifact_lineage import record
    if publisher is None:
        from agent.core import save_text
        save_text(target, rendered)

    def update_index(published):
        record(root, published, source, '结构剧本')
        write_structure_manifests(root, rendered)

    if publisher is None:
        update_index(target)
    else:
        publisher(target, rendered, lambda value: bool(str(value).strip()),
                  update_index)
    if supersede is not None:
        superseded = superseded_structured_scripts(root, source, exclude=target)
        if superseded:
            supersede(superseded)
    return target


# ── 02 剧本结构的三份 manifest（REQ-S02-23）：由结构剧本的档案区派生，程序写、程序核验 ──
def _known(value):
    """档案字段里「待确认」不是事实，manifest 里留空，不把占位文字当内容。"""
    text = re.sub(r'（来源：原稿声明）', '', str(value or '')).strip()
    return '' if not text or text.startswith('待确认') else text


def _cards(text, heading):
    """档案区里每个「### 标题」小节 → (标题, {字段名: 字段值})。"""
    for block in re.split(r'(?m)^### ', _section(text, heading))[1:]:
        title, _, body = block.partition('\n')
        yield title.strip(), dict(re.findall(r'(?m)^- ([^：\n]+)：(.*)$', body))


def _character_items(text):
    items = []
    for name, card in _cards(text, '角色档案'):
        alias = _known(card.get('别名'))
        clothing = _known(card.get('默认服装'))
        items.append({'name': name, 'aliases': [alias] if alias else [],
                      'cross_episode_id': card.get('跨集 ID', '').split('（')[0],
                      'description': ('默认服装：' + clothing) if clothing else '',
                      'physical_features': field_features(_known(card.get('物理特征')))})
    return items


def _scene_items(text):
    return [{'name': re.sub(r'^场景\s*\d+[：:]', '', title).strip() or title,
             'description': _known(card.get('空间锚点')),
             'time_of_day': _known(card.get('光照方向')),
             'timeline': _known(card.get('时间线'))}
            for title, card in _cards(text, '场景档案')]


def _prop_items(text):
    names = (re.match(r'- ([^：\n]+)：', line) for line in _section(text, '道具档案').splitlines())
    return [{'name': match.group(1).strip(), 'description': '', 'holder': ''}
            for match in names if match and not match.group(1).startswith('待确认')]


def structure_manifests(structured_text):
    """结构剧本正文 → {文件名: manifest}（角色／场景／道具三份）。"""
    text = str(structured_text or '')
    return {'character_manifest.json': manifest('character', _character_items(text)),
            'scene_manifest.json': manifest('scene', _scene_items(text)),
            'prop_manifest.json': manifest('prop', _prop_items(text))}


def structure_manifest_dir(project):
    import contract.stage_layout as stage_layout
    return stage_layout.paths(Path(project), STRUCTURE_STAGE)['output']


def write_structure_manifests(project, structured_text):
    """把三份 manifest 原子写入 02剧本结构/output/；返回目录。"""
    from agent.core import save_text
    folder = structure_manifest_dir(project)
    for name, data in structure_manifests(structured_text).items():
        save_text(folder / name, json.dumps(data, ensure_ascii=False, indent=2))
    return folder


def _manifest_file_problems(path, name):
    kind = KIND_OF_MANIFEST[name]
    if not path.is_file():
        return [name + ' 还没产出'], None
    try:
        data = read(path)
    except (OSError, ValueError) as exc:
        return ['%s 读不出来：%s' % (name, exc)], None
    problems = [] if (manifest_name(data) == name and data.get('kind') == kind) else ['%s 抬头（manifest／kind）不对' % name]
    problems += duplicate_ids({name: data})
    for index, item in enumerate(items_of(data), 1):
        # 物理特征全空是「待确认」，由人工补充；这里只拦结构性错误。
        problems += ['%s 第 %d 条：%s' % (name, index, text) for text in validate(kind, item)
                     if not text.startswith('物理特征五件')]
    return problems, items_of(data)


def structure_manifest_problems(project, structured_path=None):
    """核验 02 的三份 manifest：文件在、抬头对、编号唯一、条目合规、名单与结构剧本一致。空列表＝通过。"""
    folder = structure_manifest_dir(project)
    problems = []
    expected = None
    if structured_path is not None:
        try:
            expected = structure_manifests(Path(structured_path).read_text(encoding='utf-8-sig', errors='replace'))
        except OSError:
            expected = None
    for name in STRUCTURE_MANIFESTS:
        found, items = _manifest_file_problems(folder / name, name)
        problems += found
        if items is not None and expected is not None:
            want = sorted(item['name'] for item in expected[name]['items'])
            if sorted(str(item.get('name') or '') for item in items) != want:
                problems.append('%s 的名单与当前结构剧本不一致，需要重新整理' % name)
    return problems
# 此值是旧 manifest 的兼容键，不是新建目录名：stage_layout 会将它解析为
# 「01剧本准备」。剧本工作流已拆成「剧本准备」和「剧本结构」两段。
SCRIPT_SKILL_STAGES = ('script', 'script_structure')
# stage_layout.STAGES 通过兼容键引用它，两处不会各写一份。

# 简报契约（字段分级、收敛、workflow 投影、节奏模板引用）已拆到 script_brief（L0）。
# 这里按原名转发，调用方仍可 from script_contract import brief_document / BRIEF_REQUIRED_FIELDS 等。
from contract.script_brief import (BRIEF_FIELDS, BRIEF_LABELS, BRIEF_OPTIONAL_FIELDS, BRIEF_PRODUCTION_LOCKS_FIELD,
                          BRIEF_RECOMMENDED_FIELDS, BRIEF_REQUIRED_FIELDS, BRIEF_REQUIREMENT_LEVELS,
                          RHYTHM_TEMPLATE_FIELD, RHYTHM_TEMPLATE_PATH, WORKFLOW_LOCK_SCHEMA,
                          WORKFLOW_PROJECTION_KEY, brief_document, missing_brief_fields,
                          normalize_brief, normalize_workflow_projection)

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
     # 手填模型需按其能力与已选 SKILL 核对格式，不强套其他供应商语法。
     'fallback': '请按所选模型能力与已选 SKILL 核对提示词格式，不套用其他模型专用语法'},
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


from contract.script_manifest_schema import AUDIT, CATEGORIES, HINTS, ID_FIELD, LEGACY_STAGE_PRODUCERS, MERGED, MERGED_SKILLS, MERGE_LANDING, MERGE_OWNER, MERGE_PART, PATTERN, PHYSICAL_KEYS, PHYSICAL_LABELS, PREFIX, PREFIX_OF, PRODUCERS, PRODUCER_SKILLS, SAMPLE, SPLIT, STAGE, STAGE_PRODUCER_PREFIX, STORYBOARD_STAGE, STRUCTURE_STAGE, completeness, defaults, duplicate_ids, field_features, id_field, id_of, is_stage_producer, items_of, kind_of_id, manifest, manifest_name, new_id, normalize, normalize_producer, producer_stage_key, reassign_ids, sample_character_manifest, schema, split_features, unique_ids, validate

# ── 任务 1～4 的表（从真注册表读，报告与代码同源）──────────────────────────
def program_root(program=None):
    """程序目录；缺省取本文件上两级（contract/script_contract.py → 程序/）。"""
    return Path(program or Path(__file__).resolve().parent.parent)


from contract.script_output_spec import LOUDNESS_DEFAULTS, OUTPUT_SPEC_DEFAULTS, PREVIEW_FPS, PREVIEW_SHORT_EDGE, describe_output_spec, loudness_filter, output_filter, overlay_metrics, parse_ratio, parse_resolution, preview_spec, resolve_output_spec

