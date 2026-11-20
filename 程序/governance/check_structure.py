"""Repository structure protocol checker; development-only, no product imports."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

RULES = frozenset(('STR002', 'STR003', 'STR004', 'STR005', 'STR006', 'STR008', 'STR009', 'STR010', 'STR011', 'STR012'))
FIELDS = frozenset(('schema_version', 'source_root', 'roles', 'excludes', 'naming_exceptions', 'max_depth', 'test_ownership', 'frozen_contract_tests', 'packaging', 'retirement', 'decisions'))
RATCHET_RULES = frozenset(('STR003', 'STR004', 'STR006'))


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise ValueError('Git inventory failed: ' + result.stderr.decode('utf-8', errors='replace')[:200])
    return result.stdout


def relative_name(value):
    if not isinstance(value, str) or not value or '\\' in value or '\x00' in value:
        raise ValueError('Expected a repository-relative POSIX path')
    path = PurePosixPath(value)
    if path.is_absolute() or PureWindowsPath(value).drive or any(p in ('', '.', '..') for p in value.split('/')):
        raise ValueError('Unsafe relative path: ' + value)
    return path.as_posix()


def safe_file(root, name):
    name = relative_name(name)
    path = root
    for part in PurePosixPath(name).parts:
        path = path / part
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise ValueError('Linked path is outside the checker trust boundary: ' + name)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Path escaped root: ' + name)
    return path


def under(path, parent):
    return path == parent or path.startswith(parent + '/')


def load_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ValueError('Cannot read configuration: ' + str(path)) from exc


def validate_policy(policy):
    if not isinstance(policy, dict) or set(policy) != FIELDS or policy.get('schema_version') != 1:
        raise ValueError('Invalid policy schema or unknown fields')
    relative_name(policy['source_root'])
    if type(policy['max_depth']) is not int or not 1 <= policy['max_depth'] <= 8:
        raise ValueError('max_depth must be an integer from 1 to 8')
    if not isinstance(policy['roles'], dict) or not policy['roles']:
        raise ValueError('roles must be a nonempty object')
    for path, item in policy['roles'].items():
        relative_name(path)
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item[k] for k in ('role', 'owner', 'description')):
            raise ValueError('A directory role requires owner and description: ' + path)
        if item['role'] not in ('source', 'tooling', 'docs', 'governance', 'resources', 'vendor', 'history', 'tests', 'legacy'):
            raise ValueError('Unknown directory role: ' + path)
    for field in ('excludes', 'naming_exceptions', 'test_ownership', 'packaging', 'retirement'):
        if not isinstance(policy[field], dict):
            raise ValueError(field + ' must be an object')
    for path, item in policy['excludes'].items():
        relative_name(path)
        ancestors = [prefix for prefix in policy['roles'] if under(path, prefix)]
        effective = policy['roles'][max(ancestors, key=len)] if ancestors else None
        if ((path in policy['roles'] and policy['roles'][path]['role'] in ('source', 'governance', 'tests', 'docs'))
                or (effective and effective['role'] in ('source', 'governance', 'tests', 'docs')
                    and isinstance(item, dict) and item.get('category') == 'vendor')):
            raise ValueError('Cannot exclude owned source or governance directory: ' + path)
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item[k] for k in ('category', 'owner', 'reason')):
            raise ValueError('Exclusion requires category, owner and reason: ' + path)
        if path == policy['source_root'] or '*' in path or item['category'] not in ('vendor', 'history', 'private', 'runtime', 'cache', 'build', 'worktree', 'tooling'):
            raise ValueError('Exclusion cannot hide the source root or use wildcard boundaries: ' + path)
    for path, item in policy['naming_exceptions'].items():
        relative_name(path)
        if not all(isinstance(item.get(k), str) and item[k] for k in ('owner', 'reason', 'review_when')):
            raise ValueError('Exception requires owner, reason and review condition: ' + path)
    if not isinstance(policy['test_ownership'], dict) or not isinstance(policy['retirement'], dict):
        raise ValueError('Ownership and retirement must be objects')
    frozen = policy['frozen_contract_tests']
    if not isinstance(frozen, dict) or set(frozen) != {'paths', 'owner', 'reason', 'review_when'}:
        raise ValueError('Existing cross-module test exceptions need accountable exact paths')
    if not all(isinstance(frozen[key], str) and frozen[key] for key in ('owner', 'reason', 'review_when')):
        raise ValueError('Existing test exceptions need owner, reason and review condition')
    if not isinstance(frozen['paths'], list) or len(frozen['paths']) != len(set(frozen['paths'])):
        raise ValueError('Duplicate or malformed frozen test paths')
    for path in frozen['paths']:
        relative_name(path)
        if not path.startswith(policy['source_root'] + '/tests/') or not Path(path).name.startswith('test_'):
            raise ValueError('Frozen test exception must name an exact test file')
    if not isinstance(policy['decisions'], list) or not policy['decisions']:
        raise ValueError('Directory decisions must be declared')
    for path in policy['decisions']:
        relative_name(path)
    packaging = policy['packaging']
    if set(packaging) != {'manifest', 'exclude_prefixes', 'ignore_patterns', 'configuration_home', 'private_keys'}:
        raise ValueError('Incomplete packaging ownership declaration')
    relative_name(packaging['manifest'])
    relative_name(packaging['configuration_home'])
    if not all(isinstance(packaging[key], list) and all(isinstance(p, str) for p in packaging[key]) for key in ('exclude_prefixes', 'ignore_patterns')):
        raise ValueError('Packaging exclusion and ignore declarations must be string lists')
    if packaging['private_keys'] != 'outside-repository':
        raise ValueError('Signing private keys must remain outside the repository')
    legacy_paths = [path for path, role in policy['roles'].items() if role['role'] == 'legacy']
    if any(path not in packaging['exclude_prefixes'] for path in legacy_paths):
        raise ValueError('Legacy directories must be explicitly excluded from distribution')
    return policy


def entries(root, candidates, policy):
    found = {}
    raw = git(root, 'ls-files', '--stage', '-z').decode('utf-8')
    for item in filter(None, raw.split('\x00')):
        head, name = item.split('\t', 1)
        mode, oid, stage = head.split()
        if stage != '0':
            raise ValueError('Unmerged index entry: ' + name)
        name = relative_name(name)
        found[name] = {'mode': mode, 'oid': oid, 'candidate': False}
    links = [name for name, row in found.items() if row['mode'] == '160000']
    for name in candidates:
        name = relative_name(name)
        if any(under(name, p) for p in list(policy['excludes']) + links):
            raise ValueError('Candidate crosses excluded or gitlink boundary: ' + name)
        path = safe_file(root, name)
        if not path.is_file():
            raise ValueError('Candidate must be a regular file: ' + name)
        found[name] = {'mode': '100644', 'oid': '', 'candidate': True}
    folded = {}
    for name in found:
        previous = folded.setdefault(name.casefold(), name)
        if previous != name:
            raise ValueError('Case-insensitive path collision: ' + previous + ' / ' + name)
    return found


def violation(rule, path, subject, detail):
    return {'rule_id': rule, 'path': path, 'subject': subject, 'detail': detail}


def excluded(name, policy):
    return next((item for prefix, item in policy['excludes'].items() if under(name, prefix)), None)


def role_for(name, policy):
    matches = [p for p in policy['roles'] if under(name, p)]
    return policy['roles'][max(matches, key=len)] if matches else None


def naming(path, policy, role):
    if path in policy['naming_exceptions']:
        return []
    name = PurePosixPath(path).name
    findings = []
    if name.endswith(('.py', '.pyw')) and not re.fullmatch(r'[a-z_][a-z0-9_]*\.(?:py|pyw)', name):
        findings.append(violation('STR003', path, 'code_name', 'Own code uses lowercase ASCII snake_case'))
    if name.endswith('.md') and re.search(r'(?:[_-](?:20\d{6}|v\d+|T\d+|R\d{3,}))(?=\.|[_-])', name) and role['role'] not in ('history', 'decisions'):
        findings.append(violation('STR003', path, 'version_suffix', 'Use Git history or document metadata for versions'))
    if role['role'] in ('source', 'governance'):
        source = policy['source_root'] + '/'
        tail = path[len(source):] if path.startswith(source) else path
        for component in PurePosixPath(tail).parts[:-1]:
            if not re.fullmatch(r'[a-z_][a-z0-9_]*', component):
                findings.append(violation('STR003', path, 'directory:' + component, 'Own source directories use lowercase ASCII'))
    return findings


def ownership(name, policy, inventory, root):
    file = PurePosixPath(name)
    if not (file.name.startswith('test_') and file.suffix == '.py'):
        return []
    if name in policy['frozen_contract_tests']['paths']:
        return []
    path = safe_file(root, name)
    tree = ast.parse(path.read_text(encoding='utf-8-sig'), filename=name)
    if not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and node.name.startswith('test_') for node in ast.walk(tree)):
        return [violation('STR006', name, 'no_test_case', 'Test file must contain an actual test case')]
    item = policy['test_ownership'].get(name)
    if item:
        if not item.get('owner') or not item.get('contract') or item.get('kind') not in ('module', 'integration', 'contract', 'architecture'):
            raise ValueError('Invalid test ownership: ' + name)
        targets = item.get('targets', [])
        scopes = item.get('scopes', [])
        if any(target not in inventory for target in targets) or not (targets or scopes):
            return [violation('STR006', name, 'ownership', 'Ownership target missing')]
        if any(not any(under(p, scope) for p in inventory) for scope in scopes):
            return [violation('STR006', name, 'ownership', 'Ownership scope missing')]
        return []
    stem = file.stem[5:]
    candidates = [p for p in inventory if PurePosixPath(p).name == stem + '.py' and '/tests/' not in p and role_for(p, policy) and role_for(p, policy)['role'] == 'source']
    if candidates:
        return []
    return [violation('STR006', name, 'ownership',
                      'New cross-module tests need an explicit named target and contract')]


def legacy_references(name, path, policy):
    role = role_for(name, policy)
    if role['role'] != 'source' or path.suffix not in ('.py', '.pyw'):
        return []
    tree = ast.parse(path.read_text(encoding='utf-8-sig'), filename=name)
    findings = []
    for node in ast.walk(tree):
        modules = []
        if isinstance(node, ast.Import):
            modules = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or '']
            if any(alias.name == 'legacy' for alias in node.names):
                modules.append((node.module or '') + '.legacy')
        for module in modules:
            if module == 'legacy' or module.startswith('legacy.') or '.legacy.' in module or module.endswith('.legacy'):
                findings.append(violation('STR009', name, 'import:' + module, 'Production must not import retired code'))
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute)):
            function = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
            if function in ('import_module', '__import__', 'run_path', 'Popen', 'run', 'open', 'Path'):
                for argument in node.args:
                    for part in ast.walk(argument):
                        if isinstance(part, ast.Constant) and isinstance(part.value, str):
                            target = part.value.replace('\\', '/')
                            if target == 'legacy' or target.startswith('legacy.') or re.search(r'(?:^|/)legacy/', target):
                                findings.append(violation('STR010', name, function + ':' + target, 'Runtime reference to retired content'))
    return findings


def check(root, policy, inventory):
    findings = []
    for name in policy['frozen_contract_tests']['paths']:
        if name not in inventory:
            findings.append(violation('STR006', name, 'stale_frozen_test', 'Frozen cross-module test path no longer exists'))
    for name, row in sorted(inventory.items()):
        boundary = excluded(name, policy)
        if boundary:
            if boundary['category'] in ('private', 'runtime', 'build'):
                findings.append(violation('STR012', name, 'tracked_runtime', 'Private/runtime/build output must not be tracked'))
            continue
        if row['mode'] == '160000':
            continue
        path = safe_file(root, name)
        if not path.is_file():
            findings.append(violation('STR012', name, 'missing', 'Tracked file is absent'))
            continue
        role = role_for(name, policy)
        if role is None:
            findings.append(violation('STR002', name, 'role', 'Path has no accountable role'))
            continue
        findings.extend(naming(name, policy, role))
        if role['role'] in ('source', 'governance'):
            depth = len(PurePosixPath(name).parts) - len(PurePosixPath(policy['source_root']).parts) - 1
            if depth > policy['max_depth']:
                findings.append(violation('STR004', name, 'depth', 'Source parent directory exceeds depth budget'))
        if role['role'] == 'tests':
            findings.extend(ownership(name, policy, inventory, root))
        findings.extend(legacy_references(name, path, policy))
    for name in policy['decisions']:
        if name not in inventory or not safe_file(root, name).is_file():
            findings.append(violation('STR002', name, 'decision', 'Directory decision must be tracked'))
    for name, item in policy['retirement'].items():
        relative_name(name)
        if not all(item.get(key) for key in ('source', 'reason', 'last_version', 'owner')):
            raise ValueError('Incomplete retirement record: ' + name)
    findings.extend(directory_checks(root, policy, inventory))
    return sorted({identity(row): row for row in findings}.values(), key=identity)


def directory_checks(root, policy, inventory):
    findings = []
    source = root / policy['source_root']
    if source.is_dir():
        for directory in source.iterdir():
            name = directory.relative_to(root).as_posix()
            if directory.is_symlink() or (hasattr(directory, 'is_junction') and directory.is_junction()):
                continue
            if not directory.is_dir() or excluded(name, policy):
                continue
            if name not in policy['roles']:
                findings.append(violation('STR002', name, 'owner', 'Own top-level directory needs an explicit role and owner'))
            role = role_for(name, policy)
            if role and role['role'] in ('source', 'governance', 'docs', 'tests', 'legacy') and not any(directory.iterdir()):
                findings.append(violation('STR005', name, 'empty', 'Do not create empty optional directories'))
    for name in inventory:
        if role_for(name, policy) and role_for(name, policy)['role'] == 'legacy':
            if name.endswith('README.md'):
                continue
            if not any(under(name, target) for target in policy['retirement']):
                findings.append(violation('STR008', name, 'retirement', 'Retired content needs source, version, owner and reason'))
    packaging = policy['packaging']
    manifest = safe_file(root, packaging['manifest'])
    text = manifest.read_text(encoding='utf-8')
    exclusions = text.split('## 必须排除', 1)[-1].split('## ', 1)[0]
    for prefix in packaging['exclude_prefixes']:
        relative_name(prefix)
        if '`' + prefix + '/**`' not in exclusions:
            findings.append(violation('STR011', packaging['manifest'], prefix, 'Distribution must explicitly exclude development/retired content'))
    ignore = safe_file(root, '.gitignore').read_text(encoding='utf-8')
    patterns = {line.strip() for line in ignore.splitlines() if line.strip() and not line.startswith('#')}
    for pattern in packaging['ignore_patterns']:
        if pattern not in patterns:
            findings.append(violation('STR012', '.gitignore', pattern, 'Shared ignore rule is missing'))
    return findings


def identity(row):
    if not isinstance(row, dict) or row.get('rule_id') not in RULES:
        raise ValueError('Invalid violation rule')
    return row['rule_id'], relative_name(row['path']), row['subject']


def compare(actual, baseline, *, policy_sha256=None):
    if not isinstance(baseline, dict) or baseline.get('schema_version') != 1:
        raise ValueError('Invalid baseline schema')
    for field in ('source_commit', 'inventory_sha256', 'policy_sha256', 'violations'):
        if field not in baseline:
            raise ValueError('Missing baseline provenance: ' + field)
    if policy_sha256 is not None and baseline['policy_sha256'] != policy_sha256:
        raise ValueError('Directory policy changed without explicit baseline review')
    old = baseline['violations']
    if any(not all(row.get(k) for k in ('owner', 'reason', 'review_when')) for row in old):
        raise ValueError('Accepted violations require accountability')
    accepted = {identity(row) for row in old}
    if any(key[0] not in RATCHET_RULES for key in accepted):
        raise ValueError('Hard violations cannot be accepted in a baseline')
    if len(accepted) != len(old):
        raise ValueError('Duplicate baseline identities')
    current = {identity(row) for row in actual}
    return {'added': sorted(current - accepted), 'removed': sorted(accepted - current)}


def parser():
    command = argparse.ArgumentParser(description=__doc__)
    group = command.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--write-baseline', action='store_true')
    command.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    command.add_argument('--policy', default='程序/governance/structure.json')
    command.add_argument('--baseline', default='程序/governance/structure-baseline.json')
    command.add_argument('--candidate', action='append', default=[])
    command.add_argument('--summary', action='store_true', help='Only print delta and finding counts')
    return command


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        root = args.root.resolve()
        policy_path = safe_file(root, args.policy)
        policy = validate_policy(load_json(policy_path))
        inventory = entries(root, args.candidate, policy)
        actual = check(root, policy, inventory)
        baseline_path = safe_file(root, args.baseline)
        if args.write_baseline:
            if any(row['rule_id'] not in RATCHET_RULES for row in actual):
                raise ValueError('Resolve hard violations before freezing a baseline')
            old = load_json(baseline_path) if baseline_path.exists() else {'schema_version': 1, 'source_commit': '', 'inventory_sha256': '', 'policy_sha256': '', 'violations': []}
            delta = compare(actual, old)
            rows = [dict(row, owner='项目维护者', reason='冻结治理前存量，禁止新增同类违规', review_when='对应路径迁移或命名调整时') for row in actual]
            payload = {'schema_version': 1, 'source_commit': git(root, 'rev-parse', 'HEAD').decode().strip(), 'inventory_sha256': hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest(), 'policy_sha256': hashlib.sha256(policy_path.read_bytes()).hexdigest(), 'violations': rows}
            baseline_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        else:
            delta = compare(actual, load_json(baseline_path),
                            policy_sha256=hashlib.sha256(policy_path.read_bytes()).hexdigest())
        print(json.dumps({'ok': not delta['added'], 'delta': delta, 'finding_count': len(actual), 'findings': [] if args.summary else actual}, ensure_ascii=False, indent=2))
        return 1 if delta['added'] and not args.write_baseline else 0
    except (OSError, ValueError, SyntaxError, subprocess.SubprocessError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
