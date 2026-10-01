#!/usr/bin/env python3
"""
短剧剧本格式检查工具
检查短剧剧本的格式规范，包括：
- 集数标注是否正确
- 场景标题格式是否规范
- 台词格式是否规范
- 是否有心理描写（违规）
- 单集字数是否在合理范围
"""

import re
import sys
from pathlib import Path


def check_format(file_path):
    """检查短剧剧本格式"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    issues = []
    lines = content.split('\n')
    
    # 1. 检查集数标注
    episode_pattern = re.compile(r'^〖第\d+集〗')
    episodes = []
    for i, line in enumerate(lines, 1):
        if '集' in line and ('〖' in line or '第' in line and '集' in line):
            if episode_pattern.match(line.strip()):
                episodes.append((i, line.strip()))
            else:
                issues.append(f"第{i}行：集数标注格式不规范，应为「〖第X集〗」，当前：{line.strip()}")
    
    if not episodes:
        issues.append("未找到集数标注，请检查是否使用了「〖第X集〗」格式")
    
    # 2. 检查场景标题
    scene_pattern = re.compile(r'^场景\d+：.+\s+(日|夜|晨|昏)\s+(内|外)$')
    scene_count = 0
    for i, line in enumerate(lines, 1):
        line_stripped = line.strip()
        if line_stripped.startswith('场景') and '：' in line_stripped:
            scene_count += 1
            if not scene_pattern.match(line_stripped):
                issues.append(f"第{i}行：场景标题格式不规范，应为「场景X：地点 时间 内外景」，当前：{line_stripped}")
    
    # 3. 检查台词格式
    # 简单检查：角色名+冒号的格式
    dialogue_pattern = re.compile(r'^[\u4e00-\u9fa5A-Za-z]+：')
    dialogue_count = 0
    for i, line in enumerate(lines, 1):
        line_stripped = line.strip()
        if dialogue_pattern.match(line_stripped) and '场景' not in line_stripped[:5]:
            dialogue_count += 1
    
    # 4. 检查心理描写（简单规则：出现"心想""心里想""暗道""暗自"等）
    mind_words = ['心想', '心里想', '暗道', '暗自', '心中暗想', '心里暗道', '他想', '她想']
    for i, line in enumerate(lines, 1):
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith('〖') or line_stripped.startswith('场景'):
            continue
        for word in mind_words:
            if word in line_stripped and '说' not in line_stripped:
                issues.append(f"第{i}行：可能存在心理描写（\"{word}\"），短剧剧本应通过动作/台词表达，当前：{line_stripped[:50]}")
                break
    
    # 5. 统计字数和集数
    total_chars = len(content.replace('\n', '').replace(' ', ''))
    episode_count = len(episodes)
    
    if episode_count > 0:
        avg_chars = total_chars / episode_count
        if avg_chars < 200:
            issues.append(f"平均每集约{int(avg_chars)}字，偏少（建议300-800字/集）")
        elif avg_chars > 1000:
            issues.append(f"平均每集约{int(avg_chars)}字，偏多（建议300-800字/集）")
    
    # 输出结果
    print("=" * 60)
    print(f"短剧剧本格式检查报告")
    print(f"文件：{file_path}")
    print("=" * 60)
    print(f"总集数：{episode_count} 集")
    print(f"场景数：{scene_count} 个")
    print(f"台词数：{dialogue_count} 句")
    print(f"总字数：约 {total_chars} 字")
    if episode_count > 0:
        print(f"平均每集：约 {int(total_chars/episode_count)} 字")
    print("-" * 60)
    
    if issues:
        print(f"发现 {len(issues)} 个问题：")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("✅ 格式检查通过，未发现明显问题！")
    
    print("=" * 60)
    return len(issues) == 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法：python format_check.py <剧本文件路径>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    if not Path(file_path).exists():
        print(f"错误：文件不存在 - {file_path}")
        sys.exit(1)
    
    success = check_format(file_path)
    sys.exit(0 if success else 1)
