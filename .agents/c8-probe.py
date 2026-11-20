import sys, sysconfig, importlib.metadata as m
print(sys.version)
pure = sysconfig.get_paths()['purelib']
print('purelib', pure)
for d in sorted(m.distributions(path=[pure]), key=lambda d: (d.metadata['Name'] or '').lower()):
    print((d.metadata['Name'] or '?') + '==' + d.version)
for name in ('tuf', 'securesystemslib', 'cryptography', 'requests'):
    try:
        mod = __import__(name)
        print('IMPORT OK', name, getattr(mod, '__version__', '?'))
    except Exception as exc:
        print('IMPORT FAIL', name, type(exc).__name__, exc)
