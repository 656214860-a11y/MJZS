import sys, inspect
import tuf, securesystemslib
print('tuf', tuf.__version__ if hasattr(tuf, '__version__') else '?')
from tuf.ngclient import Updater
from tuf.ngclient.fetcher import FetcherInterface
print('Updater sig:', inspect.signature(Updater.__init__))
print('FetcherInterface abstract:', FetcherInterface.__abstractmethods__)
print('fetch sig:', inspect.signature(FetcherInterface._fetch))
try:
    from tuf.ngclient import RequestsFetcher
    print('RequestsFetcher available')
except Exception as exc:
    print('RequestsFetcher FAIL', exc)
from securesystemslib import _vendor
print('vendor ok', _vendor.__file__)
from securesystemslib._vendor.ed25519 import ed25519 as e
print('ed25519 funcs:', [n for n in dir(e) if not n.startswith('_')])
for fn in ('create_keypair', 'sign', 'verify'):
    f = getattr(e, fn, None)
    if f:
        try:
            print(fn, inspect.signature(f))
        except Exception as exc:
            print(fn, 'sigfail', exc)
try:
    from securesystemslib.signer import CryptoSigner
    print('CryptoSigner present')
    try:
        CryptoSigner.generate_ed25519()
        print('CryptoSigner usable')
    except Exception as exc:
        print('CryptoSigner unusable:', type(exc).__name__, exc)
except Exception as exc:
    print('CryptoSigner import fail', type(exc).__name__, exc)
