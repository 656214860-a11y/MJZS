import inspect
from tuf.api import metadata as md
print('Metadata methods:', [n for n in dir(md.Metadata) if not n.startswith('_')])
print('sign sig:', inspect.signature(md.Metadata.sign))
print('from_file:', inspect.signature(md.Metadata.from_file))
print('Root methods:', [n for n in dir(md.Root) if not n.startswith('_')][:40])
print('Targets.add_target:', inspect.signature(md.Targets.add_target))
print('TargetFile init:', inspect.signature(md.TargetFile.__init__))
print('Targets init:', inspect.signature(md.Targets.__init__))
print('Snapshot init:', inspect.signature(md.Snapshot.__init__))
print('Timestamp init:', inspect.signature(md.Timestamp.__init__))
print('Root init:', inspect.signature(md.Root.__init__))
from securesystemslib.signer import Signer, Key, Signature
print('Signer proto:', [n for n in dir(Signer) if not n.startswith('_')])
print('Key.from_dict:', inspect.signature(Key.from_dict))
print('Signature init:', inspect.signature(Signature.__init__))
import tuf.api.metadata as m2
print('Signed:', [n for n in dir(m2.Signed) if not n.startswith('_')])
