"""任务队列的零依赖认领器：原子替换、租约回收与红档保护。"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT = Path(__file__).with_name('任务队列.json')


def now():
    return datetime.now(timezone.utc)


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def publish(path, data):
    path = Path(path)
    encoded = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def reclaim(data, current=None):
    current = current or now(); released = []
    for item in data['items']:
        expiry = item.get('lease_until') or ''
        if item.get('status') == 'claimed' and expiry and datetime.fromisoformat(expiry) <= current:
            item.update(status='pending', owner='', lease_until='')
            released.append(item['id'])
    return released


def claim(path, item_id, owner, current=None):
    data = load(path); current = current or now(); reclaimed = reclaim(data, current)
    item = next((entry for entry in data['items'] if entry['id'] == item_id), None)
    if item is None: raise ValueError('未知任务：' + item_id)
    if item.get('status') == 'red': raise ValueError('红档任务拒绝认领：' + item_id)
    if item.get('status') == 'claimed': raise ValueError('任务已被认领：' + item_id)
    minutes = int(data.get('lease_minutes', 60))
    item.update(status='claimed', owner=owner,
                lease_until=(current + timedelta(minutes=minutes)).isoformat())
    publish(path, data)
    return item, reclaimed


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--queue', type=Path, default=DEFAULT)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('show')
    take = commands.add_parser('claim'); take.add_argument('id'); take.add_argument('--owner', required=True)
    args = parser.parse_args(argv)
    if args.command == 'show':
        data = load(args.queue); released = reclaim(data)
        if released: publish(args.queue, data)
        for item in data['items']:
            print('{id}\t{status}\t{owner}\t{lease_until}'.format(**item))
        return 0
    try:
        item, released = claim(args.queue, args.id, args.owner)
    except ValueError as error:
        print('REFUSED: ' + str(error)); return 2
    print('CLAIMED: {id} by {owner} until {lease_until}'.format(**item))
    if released: print('RECLAIMED: ' + ', '.join(released))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
