#!/usr/bin/env python3
"""Deterministic repository checks for the published skill package."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import unquote, urlsplit


REQUIRED_FILES = (
    "SKILL.md",
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "_meta.json",
    "evals/evals.json",
    "scripts/storyboard_gen.py",
)
TEXT_SUFFIXES = {".md", ".py", ".json", ".yml", ".yaml", ".txt"}
LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
SECRET_PATTERNS = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\bgh[opusr]_[A-Za-z0-9]{20,}\b")),
    ("generic API key", re.compile(r"(?i)\b(?:api[_-]?key|token|secret)\s*[:=]\s*['\"]sk-[A-Za-z0-9_-]{20,}")),
)


def parse_frontmatter(text: str) -> Dict[str, str]:
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md 缺少 YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("SKILL.md frontmatter 未闭合")
    values: Dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line.startswith((" ", "\t")) or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def validate_markdown_links(root: Path) -> List[str]:
    errors = []
    for path in sorted(root.rglob("*.md")):
        if ".git" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for raw_target in LINK_PATTERN.findall(text):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or target.startswith(("#", "mailto:")):
                continue
            candidate = (path.parent / unquote(parsed.path)).resolve()
            try:
                candidate.relative_to(root.resolve())
            except ValueError:
                errors.append(f"{path.relative_to(root)}: 链接越出仓库: {target}")
                continue
            if not candidate.exists():
                errors.append(f"{path.relative_to(root)}: 链接不存在: {target}")
    return errors


def validate_evals(payload: Any) -> List[str]:
    errors = []
    if not isinstance(payload, dict):
        return ["evals/evals.json: 顶层必须是对象"]
    required_top = {"schema_version", "skill", "evaluations"}
    missing = required_top - set(payload)
    if missing:
        errors.append("evals/evals.json: 缺少字段: " + ", ".join(sorted(missing)))
    evaluations = payload.get("evaluations")
    if not isinstance(evaluations, list) or not evaluations:
        errors.append("evals/evals.json: evaluations 必须是非空数组")
        return errors
    ids = set()
    total = 0.0
    required = {"id", "name", "prompt", "expectations", "weight"}
    for index, evaluation in enumerate(evaluations):
        if not isinstance(evaluation, dict):
            errors.append(f"evals/evals.json: evaluations[{index}] 必须是对象")
            continue
        absent = required - set(evaluation)
        if absent:
            errors.append(f"evals/evals.json: evaluations[{index}] 缺少: {', '.join(sorted(absent))}")
        eval_id = evaluation.get("id")
        if not isinstance(eval_id, str) or not re.fullmatch(r"[a-z0-9-]+", eval_id):
            errors.append(f"evals/evals.json: evaluations[{index}].id 格式无效")
        elif eval_id in ids:
            errors.append(f"evals/evals.json: id 重复: {eval_id}")
        ids.add(eval_id)
        expectations = evaluation.get("expectations")
        if not isinstance(expectations, list) or not expectations or not all(isinstance(x, str) and x.strip() for x in expectations):
            errors.append(f"evals/evals.json: evaluations[{index}].expectations 必须是非空字符串数组")
        weight = evaluation.get("weight")
        if not isinstance(weight, (int, float)) or isinstance(weight, bool) or weight <= 0:
            errors.append(f"evals/evals.json: evaluations[{index}].weight 必须大于0")
        else:
            total += float(weight)
    if abs(total - 1.0) > 1e-9:
        errors.append(f"evals/evals.json: weight 总和必须为1.0，当前为{total:g}")
    return errors


def scan_secrets(root: Path) -> List[str]:
    errors = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"{path.relative_to(root)}: 疑似 {label}")
    return errors


def validate_repository(root: Path) -> List[str]:
    root = root.resolve()
    errors = [f"缺少必需文件: {name}" for name in REQUIRED_FILES if not (root / name).is_file()]
    for path in sorted(root.rglob("*.json")):
        if ".git" in path.parts:
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            errors.append(f"{path.relative_to(root)}: JSON 无效: {error}")

    skill_path = root / "SKILL.md"
    meta_path = root / "_meta.json"
    eval_path = root / "evals" / "evals.json"
    if skill_path.is_file():
        try:
            frontmatter = parse_frontmatter(skill_path.read_text(encoding="utf-8"))
            name = frontmatter.get("name")
            if not name or not re.fullmatch(r"[a-z0-9-]+", name):
                errors.append("SKILL.md: name 必须是小写 kebab-case")
            if not frontmatter.get("description"):
                errors.append("SKILL.md: description 不能为空")
            if set(frontmatter) - {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}:
                errors.append("SKILL.md: 包含非标准顶层 frontmatter 字段")
        except (UnicodeDecodeError, ValueError) as error:
            errors.append(str(error))
            name = None
    else:
        name = None
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if name and meta.get("slug") != name:
                errors.append("_meta.json: slug 必须与 SKILL.md name 一致")
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    if eval_path.is_file():
        try:
            evals = json.loads(eval_path.read_text(encoding="utf-8"))
            errors.extend(validate_evals(evals))
            if name and evals.get("skill") != name:
                errors.append("evals/evals.json: skill 必须与 SKILL.md name 一致")
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    errors.extend(validate_markdown_links(root))
    errors.extend(scan_secrets(root))

    script = root / "scripts" / "storyboard_gen.py"
    if script.is_file():
        smoke = subprocess.run(
            [sys.executable, str(script), "generate", "验证样例", "--duration", "12", "--format", "json"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if smoke.returncode:
            errors.append(f"CLI smoke 失败: {smoke.stderr.strip()}")
        else:
            try:
                payload = json.loads(smoke.stdout)
                if payload.get("duration_seconds") != 12 or payload["shots"][-1].get("end_seconds") != 12:
                    errors.append("CLI smoke: 输出未覆盖完整时长")
            except (json.JSONDecodeError, KeyError, IndexError) as error:
                errors.append(f"CLI smoke: JSON 输出无效: {error}")
    return sorted(set(errors))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="验证技能仓库的发布完整性")
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    errors = validate_repository(args.root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"validation failed: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
