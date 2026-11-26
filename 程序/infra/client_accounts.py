"""Select a configured client account once per launch."""
from collections import defaultdict
from threading import Lock

_lock = Lock()
_next = defaultdict(int)


def account_args(config):
    profiles = config.get('client_accounts') or []
    if not profiles:
        return []
    key = (config.get('program'), tuple((p['option'], p['value']) for p in profiles))
    with _lock:
        index = _next[key] % len(profiles)
        _next[key] = index + 1
    option, value = key[1][index]
    return [option + value] if option.endswith('=') else [option, value]
