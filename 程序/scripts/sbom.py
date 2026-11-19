"""Generate the release CycloneDX 1.5 SBOM and a human-readable notice list."""
from __future__ import annotations

import json
import re
from pathlib import Path


PYPI = {
    'requests': ('Apache-2.0', 'https://github.com/psf/requests'),
    'urllib3': ('MIT', 'https://github.com/urllib3/urllib3'),
    'certifi': ('MPL-2.0', 'https://github.com/certifi/python-certifi'),
    'charset-normalizer': ('MIT', 'https://github.com/jawah/charset_normalizer'),
    'idna': ('BSD-3-Clause', 'https://github.com/kjd/idna'),
    'pillow': ('MIT-CMU', 'https://github.com/python-pillow/Pillow'),
    'psutil': ('BSD-3-Clause', 'https://github.com/giampaolo/psutil'),
    'nvidia-ml-py': ('BSD-3-Clause', 'https://github.com/gpuopenanalytics/pynvml'),
}
SKILL_LICENSES = {
    'skills/00全流程SKILL/AIGC创作全流程': 'MIT',
    'skills/01 剧本准备SKILL/编剧技能集': 'MIT',
    # Upstream has no LICENSE and its README does not grant redistribution rights.
    'skills/01 剧本准备SKILL/剧本锻造': 'NOASSERTION',
}
LOCK_LINE = re.compile(r'^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s#]+)$')


def _json(path: Path) -> dict:
    with path.open(encoding='utf-8') as stream:
        data = json.load(stream)
    if not isinstance(data, dict):
        raise ValueError(f'{path.name} 必须是 JSON 对象')
    return data


def _license(identifier: str) -> list:
    return [{'license': {'id': identifier}}]


def _reference(url: str) -> list:
    return [{'type': 'vcs' if url.endswith('.git') or 'github.com' in url else 'distribution',
             'url': url}]


def _packages(program: Path) -> list:
    components = []
    for raw in (program / 'requirements.txt').read_text(encoding='utf-8').splitlines():
        line = raw.partition('#')[0].strip()
        if not line:
            continue
        match = LOCK_LINE.fullmatch(line)
        if not match:
            raise ValueError('生产依赖不是精确锁：' + line)
        name, version = match.groups()
        canonical = re.sub(r'[-_.]+', '-', name).lower()
        if canonical not in PYPI:
            raise ValueError('生产依赖缺许可证/来源登记：' + canonical)
        license_id, source = PYPI[canonical]
        purl = f'pkg:pypi/{canonical}@{version}'
        components.append({'type': 'library', 'name': canonical, 'version': version,
                           'bom-ref': purl, 'purl': purl, 'licenses': _license(license_id),
                           'externalReferences': _reference(source)})
    return components


def _optional_asr_packages(program: Path) -> list:
    voice = program / 'voice_engine'
    lock_path = voice / 'requirements.lock'
    supply_path = voice / 'supply_chain.lock.json'
    if not lock_path.is_file() or not supply_path.is_file():
        raise ValueError('离线 ASR 缺完整依赖锁或供应链登记')
    supply = _json(supply_path)
    licenses = {re.sub(r'[-_.]+', '-', name).lower(): value
                for name, value in (supply.get('licenses') or {}).items()}
    source_template = str(supply.get('source_template') or '')
    locked = {}
    for raw in lock_path.read_text(encoding='utf-8').splitlines():
        line = raw.partition('#')[0].strip()
        if not line:
            continue
        match = LOCK_LINE.fullmatch(line)
        if not match:
            raise ValueError('ASR 依赖不是精确锁：' + line)
        name, version = match.groups()
        locked[re.sub(r'[-_.]+', '-', name).lower()] = version
    if set(locked) != set(licenses):
        raise ValueError('ASR 供应链登记与完整锁不一致：' + str({
            'missing': sorted(set(locked) - set(licenses)),
            'extra': sorted(set(licenses) - set(locked)),
        }))
    components = []
    for name, version in sorted(locked.items()):
        source = source_template.format(name=name, version=version)
        purl = f'pkg:pypi/{name}@{version}'
        components.append({'type': 'library', 'name': name, 'version': version,
                           'bom-ref': 'optional-asr:' + purl, 'purl': purl,
                           'scope': 'optional', 'licenses': _license(str(licenses[name])),
                           'externalReferences': _reference(source),
                           'properties': [{'name': 'release:environment',
                                           'value': 'voice_engine isolated venv'}]})
    return components


def _tools(program: Path) -> list:
    components = []
    for path, item in sorted((_json(program / 'external_tools.lock.json').get('tools') or {}).items()):
        for field in ('version', 'sha256', 'source', 'license'):
            if not item.get(field):
                raise ValueError(f'{path} 缺供应链字段 {field}')
        components.append({'type': 'application', 'name': Path(path).name,
                           'version': str(item['version']), 'bom-ref': 'tool:' + path,
                           'licenses': _license(str(item['license'])),
                           'hashes': [{'alg': 'SHA-256', 'content': str(item['sha256']).lower()}],
                           'externalReferences': _reference(str(item['source'])),
                           'properties': [{'name': 'release:path', 'value': path},
                                          {'name': 'release:bytes', 'value': str(item.get('bytes', ''))}]})
    return components


def _skills(program: Path, release_files=None) -> list:
    registry = _json(program / '维护记录' / '外部技能包哈希.json')
    components = []
    for path, item in sorted((registry.get('packages') or {}).items()):
        prefix = '程序/' + path.rstrip('/') + '/'
        if release_files is not None and not any(
                str(relative).replace('\\', '/').startswith(prefix)
                for relative in release_files):
            continue
        components.append({'type': 'library', 'name': Path(path).name,
                           'version': str(item['commit']), 'bom-ref': 'skill:' + path,
                           'licenses': _license(SKILL_LICENSES.get(path, 'NOASSERTION')),
                           'hashes': [{'alg': 'SHA-1', 'content': str(item['tree']).lower()}],
                           'externalReferences': _reference(str(item['source'])),
                           'properties': [{'name': 'release:path', 'value': path},
                                          {'name': 'vcs:commit', 'value': str(item['commit'])}]})
    return components


def build(program: Path, app_version='', release_files=None) -> tuple[dict, str]:
    program = Path(program)
    components = (_packages(program) + _optional_asr_packages(program)
                  + _tools(program) + _skills(program, release_files=release_files))
    document = {
        'bomFormat': 'CycloneDX', 'specVersion': '1.5', 'version': 1,
        'metadata': {'component': {'type': 'application', 'name': '漫剧制作助手',
                                   'version': str(app_version or 'unversioned'),
                                   'bom-ref': 'application:manju-assistant'}},
        'components': components,
    }
    lines = ['漫剧制作助手第三方组件清单', '格式：名称 版本 | 许可证 | 来源', '']
    for item in components:
        license_id = item['licenses'][0]['license']['id']
        source = item['externalReferences'][0]['url']
        lines.append(f"{item['name']} {item['version']} | {license_id} | {source}")
        path = next((p['value'] for p in item.get('properties', [])
                     if p['name'] == 'release:path'), '')
        if path:
            lines.append('  路径：' + path)
    lines += ['', 'NOASSERTION 表示上游未提供可确认的再分发许可证；正式发布前必须移除该组件或取得授权。']
    return document, '\n'.join(lines) + '\n'


def write(program: Path, destination: Path, app_version='', release_files=None) -> tuple[Path, Path]:
    document, notices = build(program, app_version=app_version, release_files=release_files)
    destination = Path(destination)
    sbom_path = destination / 'sbom.cdx.json'
    notices_path = destination / 'THIRD_PARTY_NOTICES.txt'
    sbom_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    notices_path.write_text(notices, encoding='utf-8')
    return sbom_path, notices_path
