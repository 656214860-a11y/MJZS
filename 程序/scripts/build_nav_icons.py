# -*- coding: utf-8 -*-
"""生成侧栏导航 PNG 图标（开发期工具；产物 ``assets/nav/*.png`` 随程序分发）。

图标字形来自 Microsoft Fluent System Icons（Filled 实心版，MIT，
字体与许可证在 ``assets/fonts/``），经 Pillow 按 2 倍率渲染后缩到 20px 网格并自动裁边。
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
    # R3060 输入框发送/终止与页头返回钮统一 Fluent 图标
    'send':           0xF6A3,  # send           发送（主色底，墨水用卡片色）
    'stop':           0xF743,  # stop           终止（同上）
    'back':           0xF178,  # arrow_reply    返回（卡片底，墨水用主题色——沿用原手绘箭头的品牌色）
}

# 墨水分三档：画在主色块上的用卡片色（send/stop），返回等强调动作用主题色（back），其余用正文色。
LIGHT_INK_KEYS = {'send', 'stop'}
ACCENT_INK_KEYS = {'back'}

# R3191（零依赖边界与媒体预览任务书 M3，D10）：阶段文件图标＝阶段字形＋右下角小「文件」角标。
# 键名 ``<stage>_files``；阶段键 → Fluent 码位与上表侧栏图标一一对应（pet_bus.STAGES 顺序由
# 运行时决定，生成顺序无所谓）。角标复用 ``project_files`` 的 folder-list 字形。
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
FILE_BADGE_CODEPOINT = ICONS['project_files']  # folder-list：与「项目文件」入口同字形

RENDER_PX = 48      # 2 倍渲染后 LANCZOS 缩到 24px，边缘更顺（R2946 图标放大一档）
TARGET_PX = 24


def render_icons(ink: tuple[int, int, int, int], light_ink=None, accent_ink=None):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(str(FONT_PATH), RENDER_PX)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for key, codepoint in ICONS.items():
        if key in LIGHT_INK_KEYS and light_ink is not None:
            use_ink = light_ink
        elif key in ACCENT_INK_KEYS and accent_ink is not None:
            use_ink = accent_ink
        else:
            use_ink = ink
        char = chr(codepoint)
        bbox = font.getbbox(char)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pad = RENDER_PX // 2
        image = Image.new('RGBA', (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
        ImageDraw.Draw(image).text((pad - bbox[0], pad - bbox[1]), char,
                                   font=font, fill=use_ink)
        image = image.resize((image.width // 2, image.height // 2), Image.LANCZOS)
        box = image.getchannel('A').getbbox()
        if box:
            left, top, right, bottom = box
            image = image.crop((max(0, left - 1), max(0, top - 1),
                                min(image.width, right + 1), min(image.height, bottom + 1)))
        path = OUT_DIR / f'{key}.png'
        image.save(path)
        written.append((path.name, image.width, image.height))
    return written


def _glyph_layer(font, codepoint, ink, canvas_px):
    """把一个字形画成透明小图并缩到 ``canvas_px`` 内（返回裁好透明边的图层，由调用方定位）。"""
    from PIL import Image, ImageDraw
    char = chr(codepoint)
    bbox = font.getbbox(char)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = RENDER_PX // 2
    glyph = Image.new('RGBA', (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(glyph).text((pad - bbox[0], pad - bbox[1]), char, font=font, fill=ink)
    scale = min(1.0, canvas_px / max(glyph.width, glyph.height))
    if scale < 1.0:
        glyph = glyph.resize((max(1, int(glyph.width * scale)), max(1, int(glyph.height * scale))),
                             Image.LANCZOS)
    box = glyph.getchannel('A').getbbox()
    return glyph.crop(box) if box else glyph


def render_stage_file_icons(ink):
    """13 张 ``<stage>_files.png``：阶段字形居中偏上，右下角叠小「文件」角标。

    画布取 2×RENDER_PX（96px）保证角标边缘顺滑，合成后整体 LANCZOS 减半再裁透明边，
    与单图标同一条输出管线（最终约 24px 网格）。
    """
    from PIL import Image, ImageFont
    font = ImageFont.truetype(str(FONT_PATH), RENDER_PX)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    side = RENDER_PX * 2
    for stage, codepoint in STAGE_FILE_BASES.items():
        canvas = Image.new('RGBA', (side, side), (0, 0, 0, 0))
        base = _glyph_layer(font, codepoint, ink, int(RENDER_PX * 1.15))
        badge = _glyph_layer(font, FILE_BADGE_CODEPOINT, ink, int(RENDER_PX * 0.6))
        # 字形略偏上、略偏左为右下角角标让位；角标贴右下、留约 8% 边距。
        canvas.paste(base, ((side - base.width) // 2 - int(RENDER_PX * 0.15),
                            (side - base.height) // 2 - int(RENDER_PX * 0.3)), base)
        margin = int(RENDER_PX * 0.35)
        canvas.paste(badge, (side - badge.width - margin, side - badge.height - margin), badge)
        image = canvas.resize((canvas.width // 2, canvas.height // 2), Image.LANCZOS)
        box = image.getchannel('A').getbbox()
        if box:
            left, top, right, bottom = box
            image = image.crop((max(0, left - 1), max(0, top - 1),
                                min(image.width, right + 1), min(image.height, bottom + 1)))
        path = OUT_DIR / f'{stage}_files.png'
        image.save(path)
        written.append((path.name, image.width, image.height))
    return written


def main():
    sys.path.insert(0, str(PROGRAM))
    from ui_tokens import COLORS
    if not FONT_PATH.is_file():
        raise SystemExit(f'缺少图标字体：{FONT_PATH}')
    hex_color = COLORS['text_primary'].lstrip('#')
    ink = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    card_hex = COLORS['background_card'].lstrip('#')
    light_ink = tuple(int(card_hex[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    primary_hex = COLORS['primary'].lstrip('#')
    accent_ink = tuple(int(primary_hex[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    try:
        written = render_icons(ink, light_ink, accent_ink)
        written += render_stage_file_icons(ink)
    except ImportError:
        raise SystemExit('需要 Pillow：pip install pillow（仅开发环境，不进运行环境）')
    for name, width, height in written:
        print(f'{name}: {width}x{height}')
    print(f'共 {len(written)} 个图标 → {OUT_DIR.relative_to(PROGRAM.parent)}')


if __name__ == '__main__':
    main()
