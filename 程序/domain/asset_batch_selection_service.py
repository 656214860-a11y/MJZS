"""资产批量窗口的无界面筛选与勾选规则。"""


def selectable_rows(rows, enabled_kinds, excluded=()):
    """返回当前类别中尚未导入的资产；不修改调用方的勾选集合。"""
    return [(aid, asset) for aid, asset in rows.items()
            if aid.split('_', 1)[0] in enabled_kinds and asset.get('status') != '已导入']


def pending_rows(rows, enabled_kinds, excluded=()):
    excluded = set(excluded)
    return [(aid, asset) for aid, asset in selectable_rows(rows, enabled_kinds)
            if aid not in excluded]


def initial_excluded(rows, engine, selected_ids=None):
    """工作流窗口仅预选调用方指定的资产；其他入口不预先排除。"""
    if engine != 'workflow' or selected_ids is None:
        return set()
    selected = {str(aid) for aid in selected_ids}
    return {aid for aid in rows if aid not in selected}


def select_category(rows, excluded, prefix):
    """勾选一个类别时，返回去掉该类别排除项后的新集合。"""
    return set(excluded) - {aid for aid in rows if aid.startswith(prefix + '_')}


def toggle_excluded(excluded, ids):
    """反转指定资产的勾选状态；不修改调用方持有的集合。"""
    return set(excluded) ^ {str(aid) for aid in ids}


def set_selection(excluded, ids, selected):
    """把给定资产集合整体设为选中或排除。"""
    ids = {str(aid) for aid in ids}
    return set(excluded) - ids if selected else set(excluded) | ids


def all_selected(ids, excluded):
    """给定非空资产集合是否均未被排除。"""
    ids = {str(aid) for aid in ids}
    return bool(ids) and not bool(ids & set(excluded))


def scope_label(scope, sources, episode_id=''):
    labels = {'all': '全部资产', 'adopted': f'已采用的 {len(sources)} 份分镜',
              'current': '当前分镜 ' + str(episode_id or '')}
    return labels.get(scope, labels['all'])
