import inspect
from tuf.api import metadata as md
for cls in ('Targets', 'Snapshot', 'Timestamp', 'Root', 'DelegatedRole', 'TargetFile', 'MetaFile', 'Key', 'Signature'):
    c = getattr(md, cls, None)
    print(cls, '->', (c, [n for n in dir(c) if not n.startswith('_')]) if c else 'MISSING')
print('Targets.init', inspect.signature(md.Targets.__init__))
print('Snapshot.init', inspect.signature(md.Snapshot.__init__))
print('Timestamp.init', inspect.signature(md.Timestamp.__init__))
print('Root.init', inspect.signature(md.Root.__init__))
print('TargetFile.init', inspect.signature(md.TargetFile.__init__))
print('MetaFile.init', inspect.signature(md.MetaFile.__init__))
print('Targets.add_targets', inspect.signature(md.Targets.add_targets))
from securesystemslib.signer import Signer, Key, Signature
print('Signer proto:', [n for n in dir(Signer) if not n.startswith('_')])
print('Key.from_dict', inspect.signature(Key.from_dict))
print('Signature.init', inspect.signature(Signature.__init__))
print('verify sig', inspect.signature(md.Metadata.verify_delegate))
