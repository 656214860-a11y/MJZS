"""Build-time policy for a relocatable Python runtime containing production packages only."""
from __future__ import annotations

import re
from importlib.metadata import distributions
from pathlib import Path


SITE = Path('运行环境/Python/Lib/site-packages')
LOCK = re.compile(r'^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s#]+)$')


def canonical(name: str) -> str:
    return re.sub(r'[-_.]+', '-', name).lower()


def locked(program: Path) -> dict[str, str]:
    result = {}
    for raw in (Path(program) / 'requirements.txt').read_text(encoding='utf-8').splitlines():
        line = raw.partition('#')[0].strip()
        if not line:
            continue
        match = LOCK.fullmatch(line)
        if not match:
            raise ValueError('生产依赖不是精确锁：' + line)
        name, version = match.groups()
        result[canonical(name)] = version
    return result


def inventory(root: Path) -> dict[str, dict]:
    """Read distribution metadata without importing any installed package."""
    root = Path(root).resolve()
    site = root / SITE
    if not site.is_dir():
        return {}
    runtime_relative = SITE.parents[1]
    runtime = (root / runtime_relative).resolve()
    site = site.resolve()
    physical_site = site.resolve()
    found = {}
    for dist in distributions(path=[str(site)]):
        name = dist.metadata.get('Name')
        if not name:
            continue
        files = []
        for item in dist.files or ():
            candidate = (physical_site / item).resolve()
            try:
                relative = candidate.relative_to(runtime)
            except ValueError:
                raise ValueError(f'{name} 的 RECORD 越出运行时根目录：{item}')
            files.append((runtime_relative / relative).as_posix())
        found[canonical(name)] = {'version': dist.version, 'files': files}
    return found


def plan(root: Path, program: Path) -> dict:
    expected = locked(program)
    installed = inventory(root)
    missing = sorted(set(expected) - set(installed))
    mismatches = sorted(f'{name}: {installed[name]["version"]}（预期 {version}）'
                        for name, version in expected.items()
                        if name in installed and installed[name]['version'] != version)
    unknown = sorted(set(installed) - set(expected))
    owners = {}
    for name, item in installed.items():
        for path in item['files']:
            owners.setdefault(path, set()).add(name)
    remove = sorted(path for path, names in owners.items()
                    if names and names <= set(unknown))
    untracked = [name for name in unknown if not installed[name]['files']]
    if untracked:
        raise ValueError('无法安全裁剪缺少 RECORD 的依赖：' + ', '.join(untracked))
    return {'expected': expected, 'installed': {k: v['version'] for k, v in installed.items()},
            'missing': missing, 'version_mismatches': mismatches,
            'removed_distributions': unknown, 'remove_files': remove}


def validate(root: Path, program: Path) -> dict:
    expected = locked(program)
    installed = {name: item['version'] for name, item in inventory(root).items()}
    return {'ok': installed == expected, 'expected': expected, 'installed': installed,
            'unknown': sorted(set(installed) - set(expected)),
            'missing': sorted(set(expected) - set(installed)),
            'version_mismatches': sorted(
                f'{name}: {installed[name]}（预期 {version}）'
                for name, version in expected.items()
                if name in installed and installed[name] != version)}
