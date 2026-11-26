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


def normalize_accounts(source, item):
    if source.get('flow_project') and item['model'].startswith('gflow-'):
        item['flow_project'] = str(source['flow_project']).strip()
    if isinstance(source.get('client_accounts'), list):
        item['client_accounts'] = [
            {key: str(row[key]).strip() for key in ('option', 'value')}
            for row in source['client_accounts'] if isinstance(row, dict) and row.get('option') and row.get('value')]
    if isinstance(source.get('profiles'), list) and item['model'].startswith('gflow-'):
        item['profiles'] = list(dict.fromkeys(p for p in source['profiles'] if isinstance(p, str) and p.strip()))


def apply_account_config(result, selected, item):
    if item.get('client_accounts'):
        result['client_accounts'] = item['client_accounts']
    if selected.startswith('gflow-') and item.get('modality') == 'image' and item.get('profiles'):
        result['gflow_model'] = selected
