"""白模预演记录的 L3 发布编排，避免 UI 直连正式写入器。"""
from agent.core import save


def _gateway():
    return {'publish_json': save}


def write_record(root, data, *, writer):
    return writer(root, data, publish=_gateway()['publish_json'])


def import_media(root, sid, source, *, importer):
    return importer(root, sid, source, publish=_gateway()['publish_json'])


def save_notes(root, sid, notes, *, saver):
    return saver(root, sid, notes, publish=_gateway()['publish_json'])
