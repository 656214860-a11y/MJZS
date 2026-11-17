# -*- coding: utf-8 -*-
"""用户可见文件名的唯一命名中心（R3093，任务书 P0 轮，Q14）。

规则来源（成熟框架共识，任务书 §2.1 Q14）：Dendron 的层级前缀让文件名自带分类与
排序，Logseq 的 ISO 日期前缀保证零宽度可排序，beets／organize 的「元数据 → 路径模板」
杜绝各处手写命名漂移——三条合并成一句可执行规则：**机器可排序前缀 + 人类可读部分，
模板集中一处**。

本模块只做纯字符串运算：不读文件、不拼路径、不导入 L0 以外任何模块，因此 L0–L5
任意层都可调用它而不引入反向依赖。清洗规则与历史 ``script_contract._file_name_part``
逐字一致（``sanitize_part`` 就是它的原实现），因此接入本模块不会改变任何既有文件名。
"""
from __future__ import annotations

import re
import time

# DES §3.1 的文件类型集合。索引里原样存这些中文标签，侧栏筛选直接用。
KINDS = ('剧本', '设定', '分镜', '资产', '音频', '视频', '清单', '报告', '日志', '其他')
DEFAULT_KIND = '其他'

# 每类文件的命名模板。占位符：project／file_type／content／date／prefix／index／slug／stem／suffix。
TEMPLATES = {
    '剧本': '{project}_{file_type}_{content}_{date}.md',
    '设定': '{project}_{file_type}_{content}_{date}.md',
    '分镜': '{prefix}_{index:03d}_{slug}{suffix}',
    '资产': '{prefix}_{index:03d}_{slug}{suffix}',
    '音频': '{prefix}_{index:03d}_{slug}{suffix}',
    '视频': '{prefix}_{index:03d}_{slug}{suffix}',
    '清单': '{stem}{suffix}',
    '报告': '{stem}{suffix}',
    '日志': '{stem}{suffix}',
    '其他': '{stem}{suffix}',
}

# 整数值占位符：模板里的 ``{index:03d}`` 需要数字而不是字符串。
_INT_FIELDS = frozenset({'index', 'number', 'shot', 'episode', 'ep', 'seq'})
# 占位符缺省值：缺失时用这些替代，保证生成的永远是合法文件名。
_FALLBACKS = {'project': '项目', 'file_type': '文件', 'content': '内容',
              'prefix': 'item', 'slug': 'item', 'stem': '未命名'}
_SUFFIX_DEFAULT = ''

_ILLEGAL_RUN = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_SPACE_RUN = re.compile(r'\s+')
_PLACEHOLDER = re.compile(r'\{(\w+)')

# Windows 保留设备名（不区分大小写、且带扩展名同样非法）。
RESERVED_NAMES = frozenset(
    {'CON', 'PRN', 'AUX', 'NUL'}
    | {'COM%d' % index for index in range(1, 10)}
    | {'LPT%d' % index for index in range(1, 10)}
)
MAX_NAME = 120      # 单段文件名长度上限
MAX_PATH = 260      # Windows 传统路径上限（长路径支持不在本期，见任务书 §8）

# 历史命名方案识别（只读兼容，Q14「旧名只读兼容」）。顺序＝优先级。
_LEGACY_SCHEMES = (
    ('首帧', re.compile(r'^EP\d{3}_SH\d{3}_[0-9a-f]{8}\.(?:png|jpg|jpeg|webp)$')),
    ('分镜定稿目录', re.compile(r'^EP\d{3}_分镜定稿_\d{8}$')),
    ('剧本四段式', re.compile(r'^.+_[^_]+_[^_]+_\d{8}\.md$')),
    ('资产编号', re.compile(r'^(?:CHAR|LOC|PROP)_\d{3,}$')),
    ('导入后缀', re.compile(r'^.+_[0-9a-f]{6}(?:\.[^.]+)?$')),
    ('交接包', re.compile(r'^\d{3}_[^_]+(?:\.[^.]+)?$')),
)


def sanitize_part(value, fallback='文件', limit=80):
    """把任意文本收成安全、稳定的文件名片段（与历史 ``_file_name_part`` 逐字一致）。"""
    text = _ILLEGAL_RUN.sub('_', str(value or '').strip())
    text = _SPACE_RUN.sub(' ', text).strip(' ._')
    return text[:limit] or fallback


def validate(name):
    """校验单段文件名；合法时返回去空格后的名字，不合法抛 ``ValueError`` 并说明原因。"""
    raw = str(name or '')
    text = raw.strip()
    if not text:
        raise ValueError('文件名不能为空')
    if text != raw:
        raise ValueError('文件名首尾不能有空格：' + repr(raw))
    if len(text) > MAX_NAME:
        raise ValueError('文件名过长（%d 字符，上限 %d）：%s' % (len(text), MAX_NAME, text[:40] + '…'))
    if _ILLEGAL_RUN.search(text):
        found = sorted(set(_ILLEGAL_RUN.search(text).group(0)))
        raise ValueError('文件名不能包含这些字符 %s：%s' % (' '.join(found), text))
    if text.endswith('.') or text.endswith(' '):
        raise ValueError('文件名不能以点或空格结尾：' + text)
    if text.split('.')[0].strip().upper() in RESERVED_NAMES:
        raise ValueError('文件名不能使用 Windows 保留名（CON/PRN/AUX/NUL/COM1-9/LPT1-9）：' + text)
    return text


def check_path(path_text):
    """校验整条相对路径长度；只做长度判断，供侧栏与迁移工具提示用。"""
    text = str(path_text or '')
    if len(text) > MAX_PATH:
        raise ValueError('路径过长（%d 字符，上限 %d）：%s' % (len(text), MAX_PATH, text[:60] + '…'))
    return text


def generate_name(kind=DEFAULT_KIND, **fields):
    """按类型模板生成文件名；缺省补当天日期，所有文本片段先经 ``sanitize_part``。"""
    template = TEMPLATES.get(kind) or TEMPLATES[DEFAULT_KIND]
    placeholders = _PLACEHOLDER.findall(template)
    if 'date' in placeholders and not fields.get('date'):
        fields = dict(fields, date=time.strftime('%Y%m%d'))
    values = {}
    for placeholder in placeholders:
        value = fields.get(placeholder)
        if placeholder in _INT_FIELDS:
            try:
                values[placeholder] = int(value or 0)
            except (TypeError, ValueError):
                values[placeholder] = 0
        elif placeholder == 'suffix':
            text = str(value if value is not None else _SUFFIX_DEFAULT)
            values[placeholder] = text if not text or text.startswith('.') else '.' + text
        else:
            values[placeholder] = sanitize_part(value, _FALLBACKS.get(placeholder, '文件'))
    return validate(template.format(**values))


def parse(name):
    """从既有文件名里取出排序键与人类可读标题，供索引的 ``order``／``title`` 字段。

    ``kind`` 是按扩展名做的尽力猜测（脚本类产物要靠索引的路径规则定类型，不依赖这里）。
    """
    text = str(name or '').strip()
    stem, dot, extension = text.rpartition('.')
    if not dot:
        stem, extension = text, ''
    order = 0
    for pattern in (r'^EP0*(\d{1,4})', r'^SH0*(\d{1,4})', r'^S0*(\d{1,4})', r'^(\d{1,6})'):
        match = re.match(pattern, stem)
        if match:
            order = int(match.group(1))
            break
    title = re.sub(r'[_\-]+', ' ', stem).strip()
    return {'kind': kind_from_suffix(text), 'order': order,
            'title': title or stem, 'ext': ('.' + extension.lower()) if dot else ''}


_SUFFIX_KINDS = {
    '.png': '资产', '.jpg': '资产', '.jpeg': '资产', '.webp': '资产', '.bmp': '资产',
    '.gif': '资产', '.tga': '资产', '.psd': '资产',
    '.mp3': '音频', '.wav': '音频', '.m4a': '音频', '.aac': '音频', '.flac': '音频',
    '.mp4': '视频', '.mov': '视频', '.mkv': '视频', '.avi': '视频', '.webm': '视频',
    '.json': '清单', '.md': '报告', '.txt': '报告', '.csv': '清单', '.srt': '清单', '.ass': '清单',
    '.log': '日志',
}


def kind_from_suffix(name):
    """按扩展名猜类型；认不出来归「其他」。"""
    suffix = re.search(r'(\.[^./\\]+)$', str(name or ''))
    return _SUFFIX_KINDS.get(suffix.group(1).lower() if suffix else '', DEFAULT_KIND)


def legacy_scheme(name):
    """识别历史命名方案名；不是历史命名返回 ``None``（Q14：旧名只读兼容，不批量改名）。"""
    text = str(name or '').strip()
    for label, pattern in _LEGACY_SCHEMES:
        if pattern.match(text):
            return label
    return None
