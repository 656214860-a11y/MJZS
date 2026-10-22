"""engine_probe.main 压平：旧实现原样内嵌，与新实现在各种命令行上逐例对照（输出与返回码）。"""
import contextlib
import io
import itertools
import unittest
from unittest import mock

import engine_probe

LEGACY_SRC = r'''def _legacy_main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    engine, program, model, dry, write, show = 'claude', '', '', False, True, False
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == '--dry-run':
            dry = True
        elif arg == '--no-record':
            write = False
        elif arg == '--json':
            show = True
        elif arg in ('--engine', '--program', '--model'):
            index += 1
            if index >= len(args):
                print('%s 后面要跟一个值' % arg)
                return 2
            value = args[index]
            if arg == '--engine':
                if value not in ENGINES:
                    print('不认识的引擎：%s（可选的：%s）' % (value, '、'.join(ENGINES)))
                    return 2
                engine = value
            elif arg == '--program':
                program = value
            else:
                model = value
        elif arg in ('-h', '--help'):
            print(USAGE)
            return 0
        else:
            print('不认识的参数：%s\n\n%s' % (arg, USAGE))
            return 2
        index += 1
    print('引擎真机验证 · %s' % ENGINES[engine])
    folder = Path(tempfile.mkdtemp(prefix='engine_probe_'))
    try:
        row = probe(engine, program=program, model=model, offline=dry, workdir=folder)
    finally:
        from file_cache import remove_temporary_tree
        remove_temporary_tree(folder)
    print('  ' + summary(row))
    for flag, known in sorted(row.get('flags', {}).items()):
        print('    %s %s' % ('✅' if known else '❌', flag))
    if write and not dry:
        print('  台账：%s' % record(row))
    if show:
        print(json.dumps(row, ensure_ascii=False, indent=2))
    return 1 if row['verdict'] in ('installed-switches-missing', 'installed-one-shot-failed') else 0
'''


def _stubs(verdict):
    calls = []

    def probe(engine, program='', model='', offline=False, workdir=None):
        calls.append(('probe', engine, program, model, offline))
        return {'verdict': verdict, 'flags': {'--a': True, '--b': False}, 'engine': engine}

    def record(row):
        calls.append(('record', row['engine']))
        return 'LEDGER'

    return calls, {'probe': probe, 'record': record, 'summary': lambda row: 'SUMMARY ' + row['verdict']}


def _run(function, namespace, args, verdict):
    calls, stubs = _stubs(verdict)
    out = io.StringIO()
    saved = {key: namespace[key] for key in stubs}
    namespace.update(stubs)
    try:
        with contextlib.redirect_stdout(out):
            code = function(args)
    finally:
        namespace.update(saved)
    return code, out.getvalue(), calls


class MainEquivalence(unittest.TestCase):
    def setUp(self):
        self.legacy_ns = dict(vars(engine_probe))
        exec(compile(LEGACY_SRC, 'legacy_engine_probe_main', 'exec'), self.legacy_ns)
        self.legacy = self.legacy_ns['_legacy_main']

    def _cases(self):
        engines = list(engine_probe.ENGINES)
        singles = [[], ['--dry-run'], ['--no-record'], ['--json'], ['-h'], ['--help'], ['--bogus'], ['x'],
                   ['--engine'], ['--program'], ['--model'], ['--engine', 'nope'], ['--engine', engines[0]],
                   ['--program', 'C:/x/cli.exe'], ['--model', 'm1'], ['--engine', engines[-1], '--model', 'm2'],
                   ['--dry-run', '--json', '--no-record'], ['--json', '--bogus'], ['--bogus', '--help'],
                   ['--help', '--bogus'], ['--engine', engines[0], '--engine', 'nope'], ['--program', '--model'],
                   ['--model', '--dry-run'], ['--engine', engines[0], '--program', 'p', '--model', 'm', '--json']]
        yield from singles
        for engine in engines:
            for flags in itertools.product(([], ['--dry-run']), ([], ['--no-record']), ([], ['--json'])):
                yield ['--engine', engine] + [f for group in flags for f in group]

    def test_command_lines(self):
        n = 0
        for args in self._cases():
            for verdict in ('ok', 'installed-switches-missing', 'installed-one-shot-failed'):
                old = _run(self.legacy, self.legacy_ns, args, verdict)
                new = _run(engine_probe.main, vars(engine_probe), args, verdict)
                self.assertEqual(new, old, (args, verdict))
                n += 1
        self.assertGreater(n, 90)

    def test_argv_default_reads_sys_argv(self):
        with mock.patch('sys.argv', ['engine_probe.py', '--bogus']):
            old = _run(lambda _a: self.legacy(), self.legacy_ns, [], 'ok')
            new = _run(lambda _a: engine_probe.main(), vars(engine_probe), [], 'ok')
        self.assertEqual(new, old)


if __name__ == '__main__':
    unittest.main()
