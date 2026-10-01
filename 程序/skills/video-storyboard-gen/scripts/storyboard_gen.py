#!/usr/bin/env python3
"""Deterministic, dependency-free Chinese storyboard scaffold generator."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


STORY_STRUCTURES = {
    "戏剧式": {
        "name": "三幕式戏剧结构",
        "acts": [
            {"name": "建置", "ratio": 0.15, "purpose": "引入人物、场景、核心冲突"},
            {"name": "对抗", "ratio": 0.70, "purpose": "遭遇阻碍、尝试解决、冲突升级"},
            {"name": "解决", "ratio": 0.15, "purpose": "问题解决、情感升华"},
        ],
    },
    "广告式": {
        "name": "痛点-方案-效果结构",
        "acts": [
            {"name": "痛点", "ratio": 0.20, "purpose": "痛点刺激、建立共鸣"},
            {"name": "方案", "ratio": 0.30, "purpose": "产品登场、解决方案"},
            {"name": "效果", "ratio": 0.40, "purpose": "效果展示、变化呈现"},
            {"name": "号召", "ratio": 0.10, "purpose": "CTA、引导行动"},
        ],
    },
    "宣传式": {
        "name": "吸引-展示-号召结构",
        "acts": [
            {"name": "吸引", "ratio": 0.25, "purpose": "精彩开场、建立兴趣"},
            {"name": "展示", "ratio": 0.55, "purpose": "核心内容展示"},
            {"name": "号召", "ratio": 0.20, "purpose": "行动号召"},
        ],
    },
}

SHOT_SIZES = {
    "大远景": {"range": "环境+极小人物", "purpose": "展示环境全貌、交代地理位置"},
    "远景": {"range": "人物全身+环境", "purpose": "展示人物与环境关系、开场定位"},
    "全景": {"range": "人物全身", "purpose": "展示完整动作、人物形象"},
    "中景": {"range": "膝上/腰部以上", "purpose": "人物交流、动作展示"},
    "近景": {"range": "胸部以上", "purpose": "表情细节、人物互动"},
    "特写": {"range": "面部/局部", "purpose": "强调细节、情感传递"},
    "大特写": {"range": "极局部", "purpose": "强调关键信息、视觉冲击"},
}

CAMERA_MOVEMENTS = {
    "固定": {"effect": "稳定、客观、专注", "emotion": "平静"},
    "推镜头": {"effect": "强调、关注、压缩空间", "emotion": "紧张、期待"},
    "拉镜头": {"effect": "揭示、扩展、释放", "emotion": "释然、转折"},
    "摇镜头": {"effect": "观察、浏览、跟随视线", "emotion": "探索"},
    "移镜头": {"effect": "跟随、展示、流动", "emotion": "伴随"},
    "跟拍": {"effect": "伴随感、代入感", "emotion": "参与"},
    "环绕": {"effect": "展示全方位、立体感", "emotion": "强调"},
    "升降": {"effect": "视点变化、揭示信息", "emotion": "变化"},
    "手持": {"effect": "真实感、紧张感", "emotion": "临场"},
}

TRANSITIONS = {
    "硬切": {"effect": "干净利落", "suitable": "动作连续、节奏快"},
    "叠化": {"effect": "流畅柔和", "suitable": "时间流逝、情绪变化"},
    "淡入": {"effect": "开场感", "suitable": "视频/场景开始"},
    "淡出": {"effect": "结束感", "suitable": "视频/场景结束"},
    "白场": {"effect": "梦幻、回忆", "suitable": "时间跳跃、意识流"},
    "遮罩": {"effect": "自然流畅", "suitable": "人物移动场景"},
}

VIDEO_TYPES = ("剧情", "广告", "宣传", "带货")
MAX_DURATION = 86400


def _clean_text(value: str, label: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError(f"{label}不能为空")
    if len(cleaned) > 200:
        raise ValueError(f"{label}不能超过200个字符")
    return cleaned


def _allocate(total: int, weights: Sequence[float], minimum: int = 1) -> List[int]:
    if total < len(weights) * minimum:
        raise ValueError("时长不足以覆盖所选结构")
    remaining = total - len(weights) * minimum
    raw = [remaining * weight / sum(weights) for weight in weights]
    values = [minimum + int(value) for value in raw]
    missing = total - sum(values)
    order = sorted(range(len(weights)), key=lambda i: (-(raw[i] - int(raw[i])), i))
    for index in order[:missing]:
        values[index] += 1
    return values


def _select_structure(video_type: str) -> Dict[str, Any]:
    if video_type in ("广告", "带货"):
        return STORY_STRUCTURES["广告式"]
    if video_type == "宣传":
        return STORY_STRUCTURES["宣传式"]
    return STORY_STRUCTURES["戏剧式"]


def build_storyboard(
    title: str,
    video_type: str,
    duration: int,
    subject: Optional[str] = None,
    platform: str = "抖音",
) -> Dict[str, Any]:
    """Build a deterministic storyboard data structure without I/O."""
    title = _clean_text(title, "标题")
    platform = _clean_text(platform, "平台")
    subject = _clean_text(subject, "主题") if subject is not None else None
    if video_type not in VIDEO_TYPES:
        raise ValueError("类型必须是：" + "、".join(VIDEO_TYPES))
    if isinstance(duration, bool) or not isinstance(duration, int) or duration <= 0:
        raise ValueError("时长必须是正整数秒")
    if duration > MAX_DURATION:
        raise ValueError(f"时长不能超过{MAX_DURATION}秒")

    structure = _select_structure(video_type)
    acts = structure["acts"]
    if duration < len(acts):
        raise ValueError(f"{video_type}结构至少需要{len(acts)}秒")
    act_durations = _allocate(duration, [act["ratio"] for act in acts])
    target_shots = duration if duration <= 6 else max(len(acts), (duration + 5) // 6)
    shot_counts = [1] * len(acts)
    for _ in range(target_shots - len(acts)):
        candidates = [i for i in range(len(acts)) if shot_counts[i] < act_durations[i]]
        index = max(candidates, key=lambda i: (act_durations[i] / shot_counts[i], -i))
        shot_counts[index] += 1

    shots: List[Dict[str, Any]] = []
    current = 0
    sizes = ("中景", "近景", "特写", "全景", "远景", "大特写")
    movements = ("固定", "推镜头", "拉镜头", "摇镜头", "移镜头", "跟拍", "环绕")
    transitions = ("硬切", "叠化", "硬切", "硬切", "遮罩")
    opening = {"建置", "痛点", "吸引"}
    middle = {"对抗", "方案", "展示", "效果"}
    for act_index, (act, act_duration, shot_count) in enumerate(zip(acts, act_durations, shot_counts)):
        durations = _allocate(act_duration, [1.0] * shot_count)
        for local_index, shot_duration in enumerate(durations):
            shot_number = len(shots) + 1
            if act["name"] in opening:
                description = f"【{act['name']}】人物出场，交代环境与核心信息，建立情境。"
                sound = "旁白/环境音"
            elif act["name"] in middle:
                description = f"【{act['name']}】事件发展，以具体动作推进信息与节奏。"
                sound = "台词+音乐渐进"
            else:
                description = f"【{act['name']}】回应前文，完成情感或行动收束。"
                sound = "台词/CTA"
            end = current + shot_duration
            shots.append(
                {
                    "number": shot_number,
                    "act": act["name"],
                    "start_seconds": current,
                    "end_seconds": end,
                    "duration_seconds": shot_duration,
                    "shot_size": sizes[(shot_number - 1) % len(sizes)],
                    "description": description,
                    "movement": movements[(shot_number - 1) % len(movements)],
                    "sound": sound,
                    "transition": "淡出" if end == duration else transitions[(shot_number - 1) % len(transitions)],
                }
            )
            current = end

    return {
        "schema_version": "1.0",
        "title": title,
        "video_type": video_type,
        "duration_seconds": duration,
        "subject": subject,
        "platform": platform,
        "structure": {
            "name": structure["name"],
            "acts": [
                {**act, "duration_seconds": act_duration}
                for act, act_duration in zip(acts, act_durations)
            ],
        },
        "shots": shots,
    }


def _cell(value: Any) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|")


def render_markdown(storyboard: Dict[str, Any]) -> str:
    """Render the stable public Markdown contract."""
    lines = [
        "# 视频分镜脚本",
        "",
        "## 项目信息",
        "",
        "| 项目 | 内容 |",
        "|------|------|",
        f"| 名称 | {_cell(storyboard['title'])} |",
        f"| 类型 | {_cell(storyboard['video_type'])}视频 |",
        f"| 时长 | {storyboard['duration_seconds']}秒 |",
        f"| 平台 | {_cell(storyboard['platform'])} |",
    ]
    if storyboard["subject"]:
        lines.append(f"| 主题 | {_cell(storyboard['subject'])} |")
    lines.extend(["", "## 故事结构", "", f"**{storyboard['structure']['name']}**", ""])
    lines.extend(["| 幕 | 时间占比 | 时长 | 核心任务 |", "|---|---:|---:|---|"])
    for act in storyboard["structure"]["acts"]:
        lines.append(
            f"| {act['name']} | {act['ratio']:.0%} | {act['duration_seconds']}秒 | {act['purpose']} |"
        )
    lines.extend(
        [
            "",
            "## 分镜表",
            "",
            "| 镜号 | 时间 | 景别 | 画面描述 | 运镜 | 台词/音效 | 转场 |",
            "|---:|---|---|---|---|---|---|",
        ]
    )
    for shot in storyboard["shots"]:
        lines.append(
            "| {number} | {start_seconds}-{end_seconds}s | {shot_size} | {description} | "
            "{movement} | {sound} | {transition} |".format(**shot)
        )
    lines.extend(
        [
            "",
            "## 剪辑与视听建议",
            "",
            "- 节奏：开场明确钩子，中段逐步加速，高潮后留出收束。",
            "- 色调：依据叙事从问题色调过渡到解决色调，保持主体连续性。",
            "- 声音：台词、环境音、音乐分层，关键剪辑点对齐动作或节拍。",
            "",
            "> 本结果是可编辑脚手架；拍摄前请核验事实、授权、平台规则与执行条件。",
            "",
        ]
    )
    return "\n".join(lines)


def render_reference(output_format: str) -> str:
    payload = {
        "schema_version": "1.0",
        "shot_sizes": SHOT_SIZES,
        "camera_movements": CAMERA_MOVEMENTS,
        "transitions": TRANSITIONS,
    }
    if output_format == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    lines = ["# 镜头语言参考", "", "## 景别", "", "| 景别 | 取景范围 | 功能 |", "|---|---|---|"]
    lines.extend(f"| {name} | {info['range']} | {info['purpose']} |" for name, info in SHOT_SIZES.items())
    return "\n".join(lines) + "\n"


def _write_output(content: str, output: Optional[Path]) -> None:
    if output is None:
        try:
            sys.stdout.write(content)
        except UnicodeEncodeError as error:
            raise ValueError("终端编码无法输出中文；请使用 --output 写入 UTF-8 文件") from error
        return
    try:
        output = output.expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8", newline="\n")
    except OSError as error:
        raise ValueError(f"无法写入 {output}: {error}") from error


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="确定性视频分镜脚本生成器")
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate", help="生成分镜脚手架")
    generate.add_argument("title", help="视频标题")
    generate.add_argument("--type", default="剧情", choices=VIDEO_TYPES, help="视频类型")
    generate.add_argument("--duration", type=int, default=60, help="总时长（正整数秒）")
    generate.add_argument("--subject", help="主题描述")
    generate.add_argument("--platform", default="抖音", help="目标平台")
    generate.add_argument("--format", choices=("markdown", "json"), default="markdown")
    generate.add_argument("--output", type=Path, help="UTF-8 输出文件；默认写到标准输出")
    reference = subparsers.add_parser("reference", help="显示镜头语言参考")
    reference.add_argument("--format", choices=("markdown", "json"), default="markdown")
    reference.add_argument("--output", type=Path, help="UTF-8 输出文件")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            storyboard = build_storyboard(
                args.title, args.type, args.duration, args.subject, args.platform
            )
            content = (
                json.dumps(storyboard, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
                if args.format == "json"
                else render_markdown(storyboard)
            )
        else:
            content = render_reference(args.format)
        _write_output(content, args.output)
    except ValueError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
