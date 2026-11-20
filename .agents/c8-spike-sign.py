"""Spike: sign TUF metadata with securesystemslib vendored ed25519 (no cryptography)."""
import sys, os, json, hashlib, tempfile, base64
from pathlib import Path
from datetime import datetime, timedelta, timezone

from tuf.api.metadata import Metadata, Root, Targets, Snapshot, Timestamp, MetaFile, TargetFile
from securesystemslib.signer import SSlibKey, Signature, Signer
from securesystemslib._vendor.ed25519 import ed25519 as _ed

SCHEME = 'ed25519'
KEYTYPE = 'ed25519'


class VendoredEd25519Signer(Signer):
    def __init__(self, seed):
        assert len(seed) == 32
        self._seed = bytes(seed)
        self._pub = _ed.publickey_unsafe(self._seed)
        self._key = SSlibKey(self._compute_keyid(), KEYTYPE, SCHEME, {'public': self._pub.hex()})

    def _compute_keyid(self):
        from securesystemslib.signer._utils import compute_default_keyid
        return compute_default_keyid(KEYTYPE, SCHEME, {'public': self._pub.hex()})

    @classmethod
    def from_priv_key_uri(cls, priv_key_uri, public_key, secret_store=None):
        raise NotImplementedError('vendored ed25519 signer only accepts raw seeds in-process')

    @property
    def public_key(self):
        return self._key

    def sign(self, payload):
        sig = _ed.signature_unsafe(payload, self._seed, self._pub)
        return Signature(self._key.keyid, sig.hex())


def build(repo_dir, raw):
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=7)
    signers = {r: VendoredEd25519Signer(bytes([i + 1]) * 32) for i, r in enumerate(('root', 'targets', 'snapshot', 'timestamp'))}
    root = Metadata(Root(expires=exp, consistent_snapshot=False))
    for role, signer in signers.items():
        root.signed.add_key(signer.public_key, role)
    root.sign(signers['root'])
    root1 = root.to_bytes()
    target = 'program-test-win_amd64.zip'
    targets = Metadata(Targets(expires=exp))
    tf = TargetFile.from_data(target, raw, ['sha256'])
    tf.unrecognized_fields['custom'] = {'app_version': '0.9', 'platform': 'win_amd64'}
    targets.signed.targets[target] = tf
    targets.sign(signers['targets'])
    tb = targets.to_bytes()
    snapshot = Metadata(Snapshot(expires=exp))
    snapshot.signed.meta['targets.json'] = MetaFile.from_data(1, tb, ['sha256'])
    snapshot.sign(signers['snapshot'])
    sb = snapshot.to_bytes()
    timestamp = Metadata(Timestamp(expires=exp))
    timestamp.signed.snapshot_meta = MetaFile.from_data(1, sb, ['sha256'])
    timestamp.sign(signers['timestamp'])
    ts = timestamp.to_bytes()
    repo_dir = Path(repo_dir)
    (repo_dir / 'metadata').mkdir(parents=True, exist_ok=True)
    (repo_dir / 'targets').mkdir(parents=True, exist_ok=True)
    (repo_dir / 'metadata' / '1.root.json').write_bytes(root1)
    (repo_dir / 'metadata' / 'root.json').write_bytes(root1)
    (repo_dir / 'metadata' / 'targets.json').write_bytes(tb)
    (repo_dir / 'metadata' / 'snapshot.json').write_bytes(sb)
    (repo_dir / 'metadata' / 'timestamp.json').write_bytes(ts)
    (repo_dir / 'targets' / target).write_bytes(raw)
    return root1, target, signers


from tuf.ngclient import Updater
from tuf.ngclient.fetcher import FetcherInterface
from tuf.api.exceptions import LengthOrHashMismatchError, DownloadHTTPError


class DirFetcher(FetcherInterface):
    def __init__(self, root):
        self.root = Path(root)
        self.calls = []
    def _fetch(self, url):
        path = url.split('/metadata/', 1)[-1] if '/metadata/' in url else url.split('/targets/', 1)[-1]
        self.calls.append(path)
        fp = self.root / ('metadata' if '/metadata/' in url else 'targets') / path
        if not fp.is_file():
            raise DownloadHTTPError('not found', 404)
        yield fp.read_bytes()


with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    repo = td / 'repo'
    raw = b'payload-bytes-' + b'x' * 100
    root1, target, signers = build(repo, raw)
    meta = td / 'cache' / 'metadata'
    tgt = td / 'cache' / 'targets'
    meta.mkdir(parents=True)
    fetcher = DirFetcher(repo)
    up = Updater(str(meta), 'https://repo.invalid/metadata/', str(tgt), 'https://repo.invalid/targets/', fetcher=fetcher, bootstrap=root1)
    up.refresh()
    info = up.get_targetinfo(target)
    print('target info:', info.length, info.hashes, info.unrecognized_fields if hasattr(info, 'unrecognized_fields') else None)
    p = up.download_target(info)
    print('downloaded', p, Path(p).read_bytes() == raw)
    # tamper metadata -> new repo state, same cache (should reject)
    print('OK signed with vendored ed25519')
