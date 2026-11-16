"""已采用分镜的下游选择数据，不依赖 Tk 控件。"""
from pathlib import Path

from file_cache import read_json
from domain.storyboard_catalog_service import file_order


ALL_SOURCES_LABEL = '全部分镜'


def source_options(sources, scope='current', current=None):
    """返回下拉框标签、对应路径及应显示的索引。"""
    records = [(Path(source).resolve(), read_json(source)) for source in sources]
    records.sort(key=lambda item: file_order(item[0], item[1]))
    ordered = [source for source, _data in records]
    labels = [f"{data.get('episode_id', '')} · {data.get('title', source.stem)}"
              f"（{len(data.get('shots', []))}镜） · {source.parent.name}" for source, data in records]
    broad = len(ordered) > 1
    if broad:
        labels.insert(0, ALL_SOURCES_LABEL)
        ordered.insert(0, None)
    if broad and scope != 'current':
        return labels, ordered, 0
    current = Path(current).resolve() if current else None
    return labels, ordered, ordered.index(current) if current in ordered else 0
