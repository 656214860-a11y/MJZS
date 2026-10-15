"""真实首帧质量基准：生成待评审表、校验媒体与双人评分，不调用模型。"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

AXES = ('剧情准确', '角色服装一致', '动作构图', '画面缺陷', '可剪辑性')
STORIES = {
    'repair': ('雨夜修伞', '林禾修伞人、顾川快递员；深蓝围裙、橙色雨衣；修伞铺和门口',
               '雨打店门|顾川抱破伞进店|林禾查看折断伞骨|顾川护住怀中信件|林禾取出备用伞骨|灯下固定连接处|顾川递上干毛巾|修好的伞撑开|两人在门口试伞|顾川撑伞离去林禾挥手'),
    'garden': ('屋顶的一盆绿', '安宁邻居、周远花匠；米色外套、绿色工作服；楼梯口和屋顶',
               '安宁抱着枯萎盆栽|周远在楼梯口看见|两人来到屋顶|周远检查盆底|安宁取来空盆|周远铺上透水石|两人扶正植物|安宁浇少量水|周远把花盆移到半阴处|两人望着安放好的盆栽微笑'),
    'station': ('末班车前', '许舟旅客、宋叶站务员；灰夹克、蓝制服；候车室和站台',
                '许舟看着末班车时刻|他发现车票不在口袋|宋叶看到他寻找|两人检查座椅下|许舟指向刚坐的长椅|宋叶捡起椅缝纸票|许舟接过车票致谢|宋叶指向正确站台|许舟从容走向车门|宋叶在安全线后挥手'),
    'holdout': ('海边归还', '陆青游客、沈岚店主；白衬衣、棕围裙；海边步道和小店门口',
                '陆青在步道看见遗落画册|他捡起查看封面署名|远处小店挂着同名招牌|陆青拿画册走到店门|沈岚正在找东西|陆青举起画册询问|沈岚认出画册微笑|陆青把画册交还|沈岚指给他看画中的海|两人站在门口望向海面'),
}


def template():
    stories = []
    for key, (title, anchors, actions) in STORIES.items():
        stories.append({'id': key, 'title': title, 'anchors': anchors,
                        'role': 'holdout' if key == 'holdout' else 'calibration',
                        'shots': [{'id': '%s-%02d' % (key, index), 'seconds': 6,
                                   'action': action, 'status': 'not_run', 'attempt': 1,
                                   'request_id': '', 'model': '', 'artifact': '',
                                   'sha256': '', 'reviews': [], 'adjudication': None,
                                   'cost': None, 'retry_cost': None, 'human_minutes': None}
                                  for index, action in enumerate(actions.split('|'), 1)]})
    return {'schema': 1, 'application_commit': '', 'reviewers': [],
            'currency': 'CNY', 'stories': stories}


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _rating(review):
    ratings = review.get('ratings')
    return (isinstance(ratings, dict) and set(ratings) == set(AXES)
            and all(type(value) is int and value in (0, 1, 2) for value in ratings.values())
            and bool(str(review.get('reason', '')).strip()))


def _media(base, shot):
    path = (base / shot['artifact']).resolve()
    if not path.is_relative_to(base.resolve()):
        return False
    try:
        data = path.read_bytes()
    except OSError:
        return False
    signature = (data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff')
                 or (data[:4] == b'RIFF' and data[8:12] == b'WEBP'))
    return bool(signature and hashlib.sha256(data).hexdigest() == shot['sha256'])


def evaluate(data, base):
    """固定40镜分母；待执行、未评分、被替换证据均不能变成通过。"""
    expected = template()
    if data.get('schema') != 1 or not isinstance(data.get('stories'), list):
        raise ValueError('不支持的基准格式')
    if [s.get('id') for s in data['stories']] != list(STORIES):
        raise ValueError('必须保留3个初筛故事与1个留出故事，且不可重复或删减')
    reviewers = data.get('reviewers', [])
    if (not isinstance(reviewers, list) or len(reviewers) not in (0, 2)
            or any(not isinstance(x, str) or not x.strip() for x in reviewers)
            or len(set(reviewers)) != len(reviewers)):
        raise ValueError('必须登记两名不同评审者；空表只用于未执行模板')
    report = {'stories': [], 'status': 'pending', 'currency': data.get('currency'),
              'known_cost': 0, 'unknown_cost_items': 0, 'human_minutes': 0,
              'unknown_human_items': 0,
              'scope': '首轮首帧人工可用性；不证明成片质量、评审身份或授权真实性'}
    request_ids = set()
    for story, planned in zip(data['stories'], expected['stories']):
        shots = story.get('shots', [])
        if [s.get('id') for s in shots] != [s['id'] for s in planned['shots']]:
            raise ValueError('每个故事必须保留预定10镜：' + story['id'])
        passed, pending, issues = 0, 0, []
        for shot in shots:
            for field in ('cost', 'retry_cost', 'human_minutes'):
                value = shot.get(field)
                if value is not None and not _number(value):
                    raise ValueError('用量必须非负有限数或null：' + shot['id'] + '/' + field)
                total = 'human_minutes' if field == 'human_minutes' else 'known_cost'
                unknown = 'unknown_human_items' if field == 'human_minutes' else 'unknown_cost_items'
                if value is None:
                    report[unknown] += 1
                else:
                    report[total] += value
            state = shot.get('status')
            if state not in ('not_run', 'failed', 'not_returned', 'generated'):
                raise ValueError('未知执行状态：' + shot['id'])
            request = shot.get('request_id')
            if request:
                if request in request_ids:
                    raise ValueError('首选候选请求ID重复：' + request)
                request_ids.add(request)
            if state == 'not_run' or not request or not shot.get('model'):
                pending += 1
                issues.append(shot['id'] + '：未执行或缺请求／模型证据')
                continue
            if shot.get('attempt') != 1 or type(shot.get('attempt')) is not int:
                raise ValueError('首轮记录不能用重试结果替换：' + shot['id'])
            if state in ('failed', 'not_returned'):
                continue
            if not shot.get('artifact') or not _media(Path(base), shot):
                pending += 1
                issues.append(shot['id'] + '：媒体缺失、格式不支持或摘要不符')
                continue
            reviews = shot.get('reviews', [])
            if (len(reviewers) != 2 or len(reviews) != 2
                    or {r.get('reviewer') for r in reviews} != set(reviewers)
                    or not all(_rating(r) for r in reviews)):
                pending += 1
                issues.append(shot['id'] + '：待两名独立评审逐维评分及说明')
                continue
            ratings = reviews[0]['ratings']
            if ratings != reviews[1]['ratings']:
                ruling = shot.get('adjudication') or {}
                if not ruling.get('reviewer') or ruling['reviewer'] in reviewers or not _rating(ruling):
                    pending += 1
                    issues.append(shot['id'] + '：评分分歧待独立复核')
                    continue
                ratings = ruling['ratings']
            passed += int(all(value == 2 for value in ratings.values()))
        state = 'pending' if pending else ('pass' if passed >= 7 else 'fail')
        report['stories'].append({'id': story['id'], 'role': planned['role'],
                                  'usable': passed, 'denominator': 10, 'rate': passed / 10,
                                  'pending': pending, 'status': state, 'issues': issues})
    if all(s['status'] == 'pass' for s in report['stories']) and data.get('application_commit'):
        report['status'] = 'pass'
    elif any(s['status'] == 'fail' for s in report['stories']):
        report['status'] = 'fail'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('init', 'evaluate'))
    parser.add_argument('file', type=Path)
    args = parser.parse_args()
    if args.command == 'init':
        with args.file.open('x', encoding='utf-8') as stream:
            json.dump(template(), stream, ensure_ascii=False, indent=2)
        print('已创建40镜待执行表；不会调用模型或覆盖已有文件。')
        return 0
    report = evaluate(json.loads(args.file.read_text(encoding='utf-8')), args.file.parent)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'pass' else 2


if __name__ == '__main__':
    raise SystemExit(main())
