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
}

RENDER_PX = 36      # 2 倍渲染后 LANCZOS 缩到 18px，边缘更顺
TARGET_PX = 18


def render_icons(ink: tuple[int, int, int, int]):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(str(FONT_PATH), RENDER_PX)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for key, codepoint in ICONS.items():
        char = chr(codepoint)
        bbox = font.getbbox(char)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pad = RENDER_PX // 2
        image = Image.new('RGBA', (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
        ImageDraw.Draw(image).text((pad - bbox[0], pad - bbox[1]), char,
                                   font=font, fill=ink)
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


def main():
    sys.path.insert(0, str(PROGRAM))
    from ui_tokens import COLORS
    if not FONT_PATH.is_file():
        raise SystemExit(f'缺少图标字体：{FONT_PATH}')
    hex_color = COLORS['text_primary'].lstrip('#')
    ink = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    try:
        written = render_icons(ink)
    except ImportError:
        raise SystemExit('需要 Pillow：pip install pillow（仅开发环境，不进运行环境）')
    for name, width, height in written:
        print(f'{name}: {width}x{height}')
    print(f'共 {len(written)} 个图标 → {OUT_DIR.relative_to(PROGRAM.parent)}')


if __name__ == '__main__':
    main()
