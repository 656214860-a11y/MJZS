# -*- coding: utf-8 -*-
"""项目文件夹层级：阶段目录 ＋ 固定子目录，JSON 与 MD 物理隔离（第 61 期 v0.8 任务 2／9／11）。

用户附件（v0.8 任务 2）要的顶层结构：

    project/
    ├── 01剧本准备/ … 13质检交付/       每个阶段一个目录（阶段目录 ＋ 固定子目录）
    ├── _shared/                       跨阶段共享：schema、锚点库、三元组字典
    └── _archive/                      废弃文件

每个阶段目录下固定七件：input／output／assets／docs／skills／logs／README.md。

三条不变量（任务 11「MD/JSON 职责分离」）：
1. output/ 只放 JSON（机器读），docs/ 只放 MD（人读），两棵树物理隔离——机器不读 MD；
2. 阶段目录里的 README.md 就是这一阶段的「输入输出契约」，缺了就按 STAGES 现生成一份；
3. **只补不改**：ensure() 只建缺的目录与缺的 README，已有的文件一个字节都不动
   （硬约束 2「不重做已有功能，只做插入和约束」）。

旧目录一个都不搬：现有 writing／storyboard／episode／audio… 只作为兼容来源；
LEGACY 是历史路径的只读归位清单；`adopt_legacy()` 只建立目录联接，不搬运历史文件。

第 64 期任务 3：用户报「文件还在旧文件夹中，没有导入新的文件夹架构」。真搬会把这些路径上
的读者一起改掉，所以只做**目录联接**——旧目录不搬动，当前编号阶段目录下多一个同名入口。
旧的内部阶段标识只用于兼容读取，绝不能再生成旧顶层阶段目录。
"""
import os
import subprocess
from pathlib import Path

from agent.core import save_text

from script_manifest_contract import STAGE_OUTPUTS

# ── 顶层结构 ────────────────────────────────────────────────────────────────
# (目录名, 状态机阶段 id 或 '', 中文阶段名, 这一阶段干什么, 输入 JSON, 输出 JSON)
STAGES = (
    ('01剧本准备', 'script', '剧本准备', '把创意落成剧本、角色设定与分集规划',
     (), ('episode.json', 'outline.json', 'characters.json') + STAGE_OUTPUTS),
    ('02剧本结构', 'script_structure', '剧本结构', '整理剧本原稿，输出供分镜使用的剧本正稿',
     (), ()),
    ('03初步分镜', 'storyboard', '初步分镜', '剧本 ＋ SKILL 拆出分镜初稿 JSON',
     ('episode.json', 'characters.json'), ('storyboard_draft.json',)),
    ('04分镜预演', 'animatic', '分镜预演', '参考图与分镜提示词生成预演草图，临时声音合成 Animatic，人工确认后进入资产管理',
     ('storyboard_draft.json',), ('animatic_manifest.json',)),
    ('05资产管理', 'assets', '资产管理', '资产清单、正典板、状态变体与参考图',
     ('storyboard_draft.json',), ('assets.json',)),
    ('06连贯性清单', 'continuity', '连贯性清单', '跨镜约束、锚点冻结与三元组校验',
     ('storyboard_draft.json', 'assets.json'), ('continuity_ledger.json',)),
    ('07分镜定稿', 'final', '分镜定稿', '批次划分、三元组补全、定稿 JSON',
     ('storyboard_draft.json', 'assets.json', 'continuity_ledger.json'), ('storyboard_final.json',)),
    ('08首帧管理', 'keyframe', '首帧管理', '每镜首帧图与首帧任务表',
     ('storyboard_final.json',), ('frames.json',)),
    ('09白模预演', 'previs', '白模预演', '复杂动作镜头的白模预演',
     ('storyboard_final.json', 'frames.json'), ('previs.json',)),
    ('10视频生成', 'video', '视频生成', '图生／文生视频成片与任务表',
     ('frames.json', 'previs.json'), ('videos.json',)),
    ('11配音与字幕', 'audio', '配音与字幕', '配音音频与字幕文件',
     ('storyboard_final.json',), ('voice.json', 'subtitles.json')),
    ('12后期剪辑', 'edit', '后期剪辑', '按批次剪辑成片',
     ('videos.json', 'voice.json', 'subtitles.json'), ('edits.json',)),
    ('13质检交付', 'delivery', '质检与交付', '质检报告与交付包',
     ('edits.json',), ('qc_report.json', 'delivery.json')),
)

# v0.8 期间曾写入项目和模块的内部阶段名。保留读取兼容，但所有 paths() 统一
# 返回上面 STAGES 定义的当前用户可见目录，避免重新创建 00_script 等第二套目录。
LEGACY_STAGE_ALIASES = {
    '00_script': '01剧本准备',
    '01_script_structure': '02剧本结构',
    '01_storyboard_draft': '03初步分镜',
    '02_assets': '05资产管理',
    '03_continuity': '06连贯性清单',
    '04_storyboard_final': '07分镜定稿',
    '05_first_frame': '08首帧管理',
    '06_previs': '09白模预演',
    '07_video_gen': '10视频生成',
    '08_audio_subtitle': '11配音与字幕',
    '09_post_edit': '12后期剪辑',
    '10_qc_delivery': '13质检交付',
}
SHARED = '_shared'
ARCHIVE = '_archive'
SUBDIRS = (
    ('input', '本阶段输入 JSON（机器读）'),
    ('output', '本阶段输出 JSON（机器读）'),
    ('assets', '本阶段产出的图片／音频／视频'),
    ('docs', '本阶段 MD 文件（人读），机器不读'),
    ('skills', '本阶段 SKILL 文件'),
    ('logs', 'Agent 执行日志'),
)
README = 'README.md'
SHARED_SUBDIRS = (
    ('schema', '各阶段 JSON Schema（assets／shot／continuity_ledger）'),
    ('anchors', '锚点库：角色 character_anchor 逐字复用，禁止 LLM 重写'),
    ('triplets', '三元组字典：scene_id ＋ character_ids ＋ costume_id 的合法组合'),
)

# 旧目录 → 阶段目录 的对照（只读，不搬）。
# (阶段目录, 项目内相对路径, 说明)
LEGACY = (
    ('00_script', 'writing', '创意、任务书与剧本阶段产物（MD）'),
    ('01_storyboard_draft', 'storyboard/分镜拆分', '初步分镜 JSON 与工作稿'),
    ('02_assets', 'episode/assets/资产清单', '资产清单 assets.json 与生成图登记'),
    ('02_assets', 'episode/assets/参考图', '参考图（按类目／用途归档）'),
    ('02_assets', 'episode/生成资产', '批量生成的资产图'),
    ('03_continuity', 'episode/assets/资产清单', '连贯性台账与资产清单同源'),
    ('04_storyboard_final', 'storyboard/分镜拆分', '定稿 JSON（EP00X_分镜定稿_…）'),
    ('05_first_frame', 'episode/frames', '首帧 PNG'),
    ('05_first_frame', 'episode/首帧任务', '首帧批量任务记录'),
    ('06_previs', 'workflows/白模批量任务', '白模预演任务与产物'),
    ('07_video_gen', 'cloud_video', '云端视频工作集'),
    ('07_video_gen', 'episode/video_prompts', '视频提示词记录'),
    ('08_audio_subtitle', 'episode/audio', '配音音频'),
    ('08_audio_subtitle', 'episode/subtitles', '字幕文件'),
    ('09_post_edit', 'episode/editing', '剪辑工程与成片'),
    ('10_qc_delivery', 'episode/delivery', '交付包'),
    ('10_qc_delivery', 'episode/exports', '导出成片'),
    ('_archive', 'episode/回收站', '废弃文件与回收站'),
    ('_archive', 'episode/历史版本', '历史版本快照'),
)

# 每个阶段的 docs/ 该有哪些 MD（任务 11：各阶段 docs/ 目录文件清单）。机器一个都不读。
DOCS = {
    '04分镜预演': (('animatic_notes.md', '节奏、时长与对白同步确认记录'),),
    '01剧本准备': (('story_brief.md', '创意与需求原稿'), ('outline.md', '全局大纲'),
                  ('characters.md', '角色设定（自然语言，人读）'), ('episode_plan.md', '分集规划'),
                  ('world_bible.md', '世界观设定集（人读；script-worldbuilding 那一段并回正稿）')),
    '02剧本结构': (('script_raw.md', '剧本原稿（输入）'), ('script.md', '结构化剧本正稿（输出）')),
    '03初步分镜': (('storyboard_notes.md', '拆镜思路与取舍'),
                            ('shot_intent.md', '每镜的戏剧意图（人读）')),
    '05资产管理': (('character_brief.md', '角色创意描述（自然语言，只给人看）'),
                  ('scene_brief.md', '场景描述'), ('prop_brief.md', '道具描述'),
                  ('canon_board.md', '正典板与状态变体的说明')),
    '06连贯性清单': (('continuity_ledger.md', '连贯性台账（人读版）'),
                      ('conflict_decisions.md', '参考图冲突的裁决记录')),
    '07分镜定稿': (('batch_plan.md', '批次划分说明'), ('shot_table.md', '镜头表')),
    '08首帧管理': (('first_frame_notes.md', '首帧制作记录'),),
    '09白模预演': (('previs_notes.md', '白模预演记录'),),
    '10视频生成': (('video_prompt_log.md', '视频提示词记录（只写动作与运镜）'),),
    '11配音与字幕': (('voice_cast.md', '配音选角'), ('subtitle_notes.md', '字幕校对记录')),
    '12后期剪辑': (('edit_notes.md', '剪辑记录'),),
    '13质检交付': (('qc_report.md', '质检报告'), ('delivery_notes.md', '交付说明')),
}

# 需要删除的重复字段（任务 6「SKILL 去重」＋ 任务 10／11 的字段收敛）。
# (旧的写法, 唯一归属, 删它的理由)
DEAD_FIELDS = (
    ('分镜 JSON 的 characters', 'character_ids（shot_batches 默认值自动补齐）',
     '与 character_ids 同义，两个名字会在下游各写一遍'),
    ('分镜 JSON 的 location', 'scene_id（shot_batches 默认值自动补齐）',
     '与 scene_id 同义；场景锚点统一从资产 JSON 的 scene_id 取'),
    ('分镜 JSON 的 duration 当批次时长用', 'estimated_duration（批次划分只看它）',
     '剪辑时长 trim 之后就不是生成时长了，批次划分必须用估计时长'),
    ('资产 JSON 里散落的角色外观自然语言', 'character_anchor（逐字复用）',
     '自然语言描述要挪到 02_assets/docs/character_brief.md，机器不复述'),
    ('视频 SKILL 里的静态外观描述', '图片提示词（asset_contract＋shot_prompts）',
     '视频提示词只写动作、运镜与物理交互，长相与服装不许再说一遍'),
    ('reference_images 里混着正典板与参考图', 'canonical_board ＋ reference_images 分开登记',
     '正典板是身份基线、参考图是风格补充，职责不同不能同栏'),
)


# SKILL 去重清单（第 61 期 v0.8 任务 6，交付物 7）：同一件活只留一个归属。
# (哪份 SKILL, 重复的活, 唯一归属, 动作)
SKILL_DEDUPE = (
    ('storyboard-consistency-lock', '角色描述生成（发型／服装／配色要点）', '资产管理（character_brief.md ＋ character_anchor）',
     '合并：本 SKILL 只把资产里的锚点锁进分镜，不再自己抽一遍外观'),
    ('asset-visual-rank ＋ asset-candidate-wall', '参考图职责声明', '资产管理（reference_roles）',
     '合并：职责只在资产清单里声明一次，选图那两份 SKILL 只读不改'),
    ('storyboard-scene-breakdown', '批次划分', '分镜定稿（shot_batches.group）',
     '删除：拆镜时不再切批次，批次统一在定稿阶段按三元组切'),
    ('storyboard-consistency-lock', '连续性约束生成', '连贯性清单（continuity_ledger.json）',
     '删除：约束由连贯性清单产出一次，本 SKILL 只锁不改'),
    ('video-batch-submit', '视频提示词静态外观描述／成片质检', 'pictures: 图片提示词（prompt_templates）；质检: video-quality-check',
     '删除：视频提示词只写动作与运镜；技术质检归 video-quality-check'),
)


def skill_rows():
    """SKILL 去重清单（交付物 7）：保留／合并／删除三种动作各归一处。"""
    return SKILL_DEDUPE


def stage_dir(name):
    """阶段目录名 → 那一行（认不出来返回 None）。"""
    text = str(name or '').strip().rstrip('/\\')
    text = LEGACY_STAGE_ALIASES.get(text, text)
    for row in STAGES:
        if row[0] == text:
            return row
    return None


def dirname_of(stage):
    """状态机阶段 id → 阶段目录名（一个阶段 id 可能对应两个目录，取第一个）。"""
    text = str(stage or '').strip()
    for row in STAGES:
        if row[1] == text:
            return row[0]
    return ''


def names():
    """全部阶段目录名（按流程先后）。"""
    return tuple(row[0] for row in STAGES)


def stage_names():
    """全部阶段中文名（按流程先后）。"""
    return tuple(row[2] for row in STAGES)


def stage_contract_errors():
    """目录阶段契约与运行阶段契约之间的差异。

    ``pet_bus.STAGES`` 是运行时唯一阶段顺序，``stage_layout.STAGES`` 是
    用户可见目录与 README 输入输出契约。两份表必须一一对应；这里刻意在
    调用时才导入，避免把总线的运行依赖带入普通路径查询。
    """
    from pet_bus import STAGES as runtime_stages
    layout_stages = tuple(row[1] for row in STAGES)
    errors = []
    if layout_stages != tuple(runtime_stages):
        errors.append('阶段目录顺序与 pet_bus.STAGES 不一致')
    if len(layout_stages) != len(set(layout_stages)):
        errors.append('阶段目录契约含重复阶段 ID')
    if any(not stage or not name for _folder, stage, name, *_rest in STAGES):
        errors.append('阶段目录契约含空阶段 ID 或中文名称')
    return tuple(errors)


def validate_stage_contract():
    """校验 L0 的运行阶段、目录阶段与中文阶段名契约。"""
    errors = stage_contract_errors()
    if errors:
        raise ValueError('；'.join(errors))
    return True


def paths(project, folder):
    """某阶段目录下的七个固定位置：{'root','input','output','assets','docs','skills','logs','readme'}。"""
    row = stage_dir(folder)
    if row is None:
        raise ValueError('未知阶段目录：' + str(folder))
    root = Path(project) / row[0]
    out = {'root': root, 'readme': root / README}
    for name, _duty in SUBDIRS:
        out[name] = root / name
    return out


def shared_paths(project):
    """_shared 下的三个固定位置。"""
    root = Path(project) / SHARED
    out = {'root': root}
    for name, _duty in SHARED_SUBDIRS:
        out[name] = root / name
    return out


def schema_path(project, name):
    """_shared/schema 下的一份 Schema 文件（name 不用带后缀）。"""
    return shared_paths(project)['schema'] / (str(name) + '.schema.json')


def anchors_path(project):
    """锚点库：角色 character_anchor 的唯一存放处（机器逐字复用）。"""
    return shared_paths(project)['anchors'] / 'anchors.json'


def triplets_path(project):
    """三元组字典：scene_id ＋ character_ids ＋ costume_id 的合法组合。"""
    return shared_paths(project)['triplets'] / 'triplets.json'


def readme_text(row):
    """这一阶段的「输入输出契约」正文（README.md）。"""
    folder, stage, title, duty, inputs, outputs = row
    lines = ['# %s · %s' % (folder, title), '', duty + '。', '',
             '## 输入（只在 input/ 里放 JSON）']
    lines += ['- %s' % item for item in inputs] or ['- （本项目第一步，没有上游输入）']
    lines += ['', '## 输出（只在 output/ 里放 JSON，机器读）']
    lines += ['- %s' % item for item in outputs]
    lines += ['', '## 固定子目录',
              '- `input/`　本阶段输入 JSON', '- `output/`　本阶段输出 JSON（机器读）',
              '- `assets/`　本阶段产出的图片／音频／视频', '- `docs/`　本阶段 MD（人读），机器不读',
              '- `skills/`　本阶段 SKILL 文件', '- `logs/`　Agent 执行日志', '',
              '## docs/ 该有哪些（只给人看，机器一个都不读）']
    lines += ['- `%s`　%s' % item for item in DOCS.get(folder, ())]
    lines += ['', '## 不变量',
              '1. JSON 为唯一机器输入：output/ 与 docs/ 物理隔离，提示词生成只读 JSON，不读任何 MD。',
              '2. 本目录里的 JSON 字段与 Schema 见 `_shared/schema/`，新增字段必须有默认值与校验规则。',
              '3. 只补不改：本文件由程序按 stage_layout.STAGES 生成，重跑不会覆盖已有内容。']
    if stage:
        lines += ['', '## 状态机', '- 对应阶段 id：`%s`' % stage]
    return '\n'.join(lines) + '\n'


def ensure(project, dry=False):
    """把整个阶段目录树补齐（只建缺的），返回这一次真的新建了哪些路径。"""
    root = Path(project)
    created = []
    targets = [root / name for name in names()] + [root / SHARED, root / ARCHIVE]
    targets += [root / SHARED / name for name, _duty in SHARED_SUBDIRS]
    for row in STAGES:
        # 只拿目录：paths() 里的 'readme' 是文件路径，别把它 mkdir 成目录。
        targets += [value for key, value in paths(root, row[0]).items() if key != 'readme']
    targets.append(root / ARCHIVE / 'logs')
    for path in targets:
        if path.exists():
            continue
        created.append(path)
        if not dry:
            path.mkdir(parents=True, exist_ok=True)
    for row in STAGES:
        file = paths(root, row[0])['readme']
        if file.is_file():
            continue
        created.append(file)
        if not dry:
            save_text(file, readme_text(row))
    return created


def tree_text():
    """完整的目录树（交付物 1），每个目录带一句职责说明。"""
    lines = ['project/']
    for row in STAGES:
        lines.append('├── %-22s %s' % (row[0] + '/', row[2] + '：' + row[3]))
        for name, duty in SUBDIRS:
            # 每个阶段里 README.md 才是最后一个分支，六个子目录一律用 ├──。
            lines.append('│   ├── %-10s %s' % (name + '/', duty))
        lines.append('│   └── %-10s %s' % (README, '本阶段输入输出契约'))
    lines.append('├── %-22s %s' % (SHARED + '/', '跨阶段共享：schema、锚点库、三元组字典'))
    for name, duty in SHARED_SUBDIRS:
        lines.append('│   ├── %-10s %s' % (name + '/', duty))
    lines.append('└── %-22s %s' % (ARCHIVE + '/', '废弃文件（回收站与历史版本）'))
    return '\n'.join(lines) + '\n'


def duty_rows():
    """每个目录的职责说明（交付物 1 的表格版）。"""
    rows = [(row[0] + '/', row[2], row[3]) for row in STAGES]
    rows.append((SHARED + '/', '跨阶段共享', 'schema／anchors／triplets 三份公共数据'))
    rows.append((ARCHIVE + '/', '废弃文件', '回收站与历史版本，机器不读'))
    return rows


def docs_rows():
    """各阶段 docs/ 目录文件清单（交付物 11）。"""
    rows = []
    for row in STAGES:
        for name, text in DOCS.get(row[0], ()):
            rows.append((row[0], name, text))
    return rows


def json_md_rows():
    """JSON 与 MD 的字段对照表（交付物 11 的第二半）。

    左边是机器唯一输入（JSON），右边只给人看（docs/ 里的 MD）——同一件事不许两边各写一份。
    """
    return (
        ('assets.json · character_anchor', '05资产管理/docs/character_brief.md',
         '锚点字符串逐字复用；创意描述只给人看'),
        ('assets.json · state_variants', '05资产管理/docs/canon_board.md',
         '状态变体的数据结构在 JSON 里，说明写在 MD'),
        ('assets.json · scene_id／spatial_anchors', '05资产管理/docs/scene_brief.md',
         '场景的空间锚点是机器输入，文字描述给人看'),
        ('storyboard_final.json · batch_id', '07分镜定稿/docs/batch_plan.md',
         '批次是机器切的，说明给人看'),
        ('continuity_ledger.json', '06连贯性清单/docs/continuity_ledger.md',
         '台账 JSON 是机器输入，人读版在 docs'),
        ('shot.video_prompt', '10视频生成/docs/video_prompt_log.md',
         '视频提示词只写动作与运镜'),
    )


def legacy_map(project):
    """现有目录 → 阶段目录的对照（只读）：给出「这一坨东西归哪一阶段」和它现在在不在。"""
    root = Path(project)
    rows = []
    for folder, relative, note in LEGACY:
        path = root / relative
        rows.append((folder, relative, note, path.is_dir()))
    return rows


def real_dir(path):
    """这一条是不是「真目录」：链接（符号联接／目录联接）一律不算，免得接出一条链到链。"""
    path = Path(path)
    try:
        return path.is_dir() and not path.is_symlink() and not path.is_junction()
    except OSError:
        return False


def link_dir(source, dest):
    """把 dest 接到 source 上：先试 os.symlink（开发者模式），不行退回 mklink /J（都不用管理员）。

    只建链接，不复制也不搬动：链接坏了删掉它就行，源目录一个字节都没动。建不出来的返回 False。
    """
    dest = Path(dest)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    try:
        os.symlink(str(source), str(dest), target_is_directory=True)
        return True
    except (OSError, NotImplementedError, AttributeError):
        pass
    try:
        done = run_process(['cmd', '/c', 'mklink', '/J', str(dest), str(source)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           run=subprocess.run)
    except Exception:
        return False
    return done.returncode == 0 and dest.is_dir()


def legacy_targets(project):
    """老目录在阶段树里的落脚点：(阶段目录, 老目录, <阶段目录>/<老目录原名>)。"""
    root = Path(project)
    def target_root(stage):
        return root / ARCHIVE if stage == ARCHIVE else paths(root, stage)['root']
    return [(target_root(stage), root / relative,
             target_root(stage) / Path(relative).name)
            for stage, relative, _note in LEGACY]


def adopt_legacy(project, dry=False):
    """把老目录接进对应的阶段目录（第 64 期任务 3）。返回 {"made":[…], "skipped":[(路径,原因)]}。

    只做目录联接，一条都不搬、一个字节都不删：老目录照旧是权威位置（程序到处都在读它），
    阶段树里补一个同名入口，用户在新架构下就能看见这一阶段的文件。
    落脚点上已经有东西＝跳过并记一笔；建链接失败＝也记一笔，绝不拦下「打开项目」。
    """
    made, skipped = [], []
    for _stage, source, dest in legacy_targets(project):
        if not real_dir(source):
            continue
        if dest.exists() or dest.is_symlink():
            skipped.append((dest, 'already'))
            continue
        if dry:
            made.append(dest)
        elif link_dir(source, dest):
            made.append(dest)
        else:
            skipped.append((dest, 'failed'))
    return {'made': made, 'skipped': skipped}


def ready(project):
    """整棵阶段树都齐了吗（ensure 的幂等判据）。"""
    return not ensure(project, dry=True)
from platform_tools import run_process
