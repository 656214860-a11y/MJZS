# -*- coding: utf-8 -*-
"""生成侧栏导航 PNG 图标（开发期工具；产物 ``assets/nav/*.png`` 随程序分发）。

图标字形来自 Microsoft Fluent System Icons（Filled 实心版，MIT，
字体与许可证在 ``assets/fonts/``）。主导航图标经 Pillow 倍率渲染后放入固定 24px 画布；
阶段文件复合图标按 M3 的设计裁边，不适用主导航尺寸规则。
运行时只加载 PNG，不依赖 Pillow 或字体文件；本脚本仅在新增/替换图标时重跑：

    python scripts/build_nav_icons.py

需要开发环境安装 Pillow（``pip install pillow``，只装系统 Python，不进运行环境）。
"""
from __future__ import annotations

import sys
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
FONT_PATH = PROGRAM / 'assets' / 'fonts' / 'FluentSystemIcons-Filled.ttf'
OUT_DIR = PROGRAM / 'assets' / 'nav'

# 语义键 → Fluent filled 图标码位（取自 glyphmap 中 -20-filled 变体）。
# 键名即输出文件名；语义到阶段/页面的映射在 desktop_page_registry.PAGE_NAV_ICONS 等表。
ICONS = {
    # 侧栏导航（13 阶段 + 资产清单 + 会员账户 + 参考网站）
    'account':        0xE9C5,  # premium-person 会员账户
    'script':         0xF314,  # compose        剧本准备（撰写）
    'structure':      0xF812,  # text-number-list-ltr 剧本结构（大纲）
    'storyboard':     0xEB20,  # slide-grid     初步分镜（分镜格）
    'animatic':       0xE9A6,  # play-circle    分镜预演（预览播放）
    'assets':         0xE472,  # database       资产管理（素材库）
    'asset_list':     0xF775,  # table          资产清单（清单表）
    'continuity':     0xF4EE,  # link           连贯性清单（前后呼应）
    'final':          0xE4FD,  # document-checkmark 分镜定稿（定稿文档）
    'keyframe':       0xF48F,  # image          首帧管理（关键帧图）
    'previs':         0xF335,  # cube           白模预演（3D 白模）
    'video':          0xF864,  # video          视频生成
    'audio':          0xE807,  # mic            配音与字幕（配音）
    'edit':           0xF33A,  # cut            后期剪辑（剪辑）
    'delivery':       0xEAD1,  # shield-checkmark 质检与交付（质检通过）
    'sites':          0xF45E,  # globe          参考网站
    # 项目区（分组筛选 + 操作）
    'project_making': 0xF847,  # toolbox        在制作项目
    'project_done':   0xF27E,  # certificate    已完成项目
    'project_new':    0xF420,  # folder-add     新建项目
    'project_open':   0xE89F,  # open-folder    打开项目目录
    'project_files':  0xF0128, # folder-list    项目文件列表（标题行右上角入口，R2962）
    # 固定底栏与授权态
    'settings':       0xF6B2,  # settings       设置（齿轮入口，与导航同套 Filled 图标）
    'lock':           0xE79D,  # lock-closed    未授权页的锁标（替换原文字 🔒）
    # 页头返回钮（R3060 输入框发送/终止键已于 U4 改回 MDL2 字形＋圆形描边，不再用 PNG）
    'back':           0xF178,  # arrow_reply    返回（卡片底，墨水用主题色——沿用原手绘箭头的品牌色）
}

# 返回等强调动作用主题色墨水（back），其余用正文色。
ACCENT_INK_KEYS = {'back'}

# R3191（零依赖边界与媒体预览任务书 M3，D10）：阶段文件图标＝阶段字形＋右下角小「文件」角标。
# 键名 ``<stage>_files``；阶段键 → Fluent 码位与上表侧栏图标一一对应（pet_bus.STAGES 顺序由
# 运行时决定，生成顺序无所谓）。角标是手绘折角纸形（L4-U4），不再复用其他字形。
STAGE_FILE_BASES = {
    'script':           0xF314,  # compose            剧本准备
    'script_structure': 0xF812,  # text-number-list   剧本结构
    'storyboard':       0xEB20,  # slide-grid         初步分镜
    'animatic':         0xE9A6,  # play-circle        分镜预演
    'assets':           0xE472,  # database           资产管理
    'continuity':       0xF4EE,  # link               连贯性清单
    'final':            0xE4FD,  # document-checkmark 分镜定稿
    'keyframe':         0xF48F,  # image              首帧管理
    'previs':           0xF335,  # cube               白模预演
    'video':            0xF864,  # video              视频生成
    'audio':            0xE807,  # mic                配音与字幕
    'edit':             0xF33A,  # cut                后期剪辑
    'delivery':         0xEAD1,  # shield-checkmark   质检与交付
}

RENDER_PX = 48      # 2 倍渲染后 LANCZOS 缩小，边缘更顺


def render_icons(ink: tuple[int, int, int, int], accent_ink=None):
    from PIL import ImageFont
    font = ImageFont.truetype(str(FONT_PATH), RENDER_PX)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for key, codepoint in ICONS.items():
        if key in ACCENT_INK_KEYS and accent_ink is not None:
            use_ink = accent_ink
        else:
            use_ink = ink
        char = chr(codepoint)
        canvas = _nav_glyph_image(font, char, use_ink)
        path = OUT_DIR / f'{key}.png'
        canvas.save(path)
        written.append((path.name, canvas.width, canvas.height))
    return written


def _nav_glyph_image(font, char, ink):
    """把一个 Fluent 字形渲染成 NAV_ICON_SIZE 方画布图标；主导航与阶段文件图标共用本管线。"""
    from PIL import Image, ImageDraw
    from ui_tokens import NAV_ICON_SIZE
    bbox = font.getbbox(char)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = RENDER_PX // 2
    image = Image.new('RGBA', (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(image).text((pad - bbox[0], pad - bbox[1]), char,
                               font=font, fill=ink)
    image = image.resize((image.width // 2, image.height // 2), Image.LANCZOS)
    box = image.getchannel('A').getbbox()
    canvas = Image.new('RGBA', (NAV_ICON_SIZE, NAV_ICON_SIZE), (0, 0, 0, 0))
    if box:
        image = image.crop(box)
        max_ink = NAV_ICON_SIZE - 2  # leave one transparent pixel on each edge
        if image.width > max_ink or image.height > max_ink:
            scale = min(max_ink / image.width, max_ink / image.height)
            image = image.resize((max(1, round(image.width * scale)),
                                  max(1, round(image.height * scale))), Image.LANCZOS)
        alpha = image.getchannel('A')
        image = Image.new('RGBA', image.size, ink)
        image.putalpha(alpha)
        canvas.paste(image, ((NAV_ICON_SIZE - image.width) // 2,
                             (NAV_ICON_SIZE - image.height) // 2))
    return canvas


# L4-U4（任务书，默认 L4-Q4）：阶段图形＝对应导航图标原大小贴左上，文件标识＝折角纸形在右下角，
# 宽高各占画布边长的 35%–45%，全部 13 张图的标识位置和大小完全一致。
# 用户反馈（REQ-S01-93 修订）：原标识是浅色纸面、大半挂在阶段图形外面，在浅色背景上看不清。
# 现改为画布 28×28、标识外框 12×12 压在阶段图形右下角之上（四成以上面积在 24×24 图形范围内），
# 纸面用主题色实心，外圈 1 像素不透明浅色描边把它和被压住的图形分开。
STAGE_FILE_CANVAS = (28, 28)
STAGE_FILE_BADGE_POS = (16, 16)
STAGE_FILE_BADGE_SIZE = (12, 12)
STAGE_FILE_BADGE_FOLD = 3


def _file_badge_layer(colors):
    """折角纸张角标：主题色实心纸面、右上角浅色折角、两条浅色文字线；外圈 1 像素不透明浅色描边。"""
    from PIL import Image, ImageDraw
    w, h = STAGE_FILE_BADGE_SIZE
    fold = STAGE_FILE_BADGE_FOLD
    image = Image.new('RGBA', (w, h), colors['background_primary'])
    draw = ImageDraw.Draw(image)
    body = [(1, 1), (w - 2 - fold, 1), (w - 2, 1 + fold), (w - 2, h - 2), (1, h - 2)]
    draw.polygon(body, fill=colors['primary'])
    flap = [(w - 2 - fold, 1), (w - 2, 1 + fold), (w - 2 - fold, 1 + fold)]
    draw.polygon(flap, fill=colors['primary_subtle'])
    for y in (h // 2, h // 2 + 2):
        draw.line([(3, y), (w - 4, y)], fill=colors['background_card'])
    return image


def render_stage_file_icons(ink, colors):
    """13 张 ``<stage>_files.png``：阶段图形与 ``<nav>.png`` 逐像素一致，文件标识压在其右下角之上。"""
    from PIL import Image, ImageFont
    font = ImageFont.truetype(str(FONT_PATH), RENDER_PX)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    badge = _file_badge_layer(colors)
    written = []
    for stage, codepoint in STAGE_FILE_BASES.items():
        canvas = Image.new('RGBA', STAGE_FILE_CANVAS, (0, 0, 0, 0))
        canvas.paste(_nav_glyph_image(font, chr(codepoint), ink), (0, 0))
        canvas.paste(badge, STAGE_FILE_BADGE_POS, badge)
        path = OUT_DIR / f'{stage}_files.png'
        canvas.save(path)
        written.append((path.name, canvas.width, canvas.height))
    return written


def main():
    sys.path.insert(0, str(PROGRAM))
    from ui_tokens import COLORS
    if not FONT_PATH.is_file():
        raise SystemExit(f'缺少图标字体：{FONT_PATH}')
    hex_color = COLORS['text_primary'].lstrip('#')
    ink = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    primary_hex = COLORS['primary'].lstrip('#')
    accent_ink = tuple(int(primary_hex[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    try:
        written = render_icons(ink, accent_ink)
        written += render_stage_file_icons(ink, COLORS)
    except ImportError:
        raise SystemExit('需要 Pillow：pip install pillow（仅开发环境，不进运行环境）')
    for name, width, height in written:
        print(f'{name}: {width}x{height}')
    print(f'共 {len(written)} 个图标 → {OUT_DIR.relative_to(PROGRAM.parent)}')


if __name__ == '__main__':
    main()
