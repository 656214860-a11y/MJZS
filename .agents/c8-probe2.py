import sys, sysconfig, importlib.metadata as m
print(sys.executable, sys.version)
pure = sysconfig.get_paths()['purelib']
for d in sorted(m.distributions(path=[pure]), key=lambda d: (d.metadata['Name'] or '').lower()):
    print((d.metadata['Name'] or '?') + '==' + d.version)
