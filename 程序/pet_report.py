# -*- coding: utf-8 -*-
"""宠物日报与优化建议：把状态机进度、Token 台账、失败清单与通知流水合成一份可读报告。

设计文档 §13 第 6 期「日报与优化建议」的落地，全部是确定性汇总与规则判定：
数字只来自传入的对象与已落盘的汇总文件，缺数据一律写「信息不足」，不猜也不编。

- gather(...)：把各来源归一成固定键的报告数据（同一输入永远得到同一份）；
- advice(data)：规则表 → 优化建议，每条都带上触发它的数字；
- render(data)：日报 Markdown 正文；
- write(project, data)：落盘 <项目>/工作流任务/宠物/日报/YYYY-MM-DD.md，并把当日数字并入 汇总.json；
- weekly(project, at)：读 汇总.json 汇总最近 7 天（不足 7 天就按实际天数）；
- prune(project)：过期及重复日报／周报移入项目回收站；默认保留最近 90 个自然日。
纯标准库＋既有 pet_llm／pet_state／pet_bus，再借 pet_agent 的类目中文名，不联网、不起线程，
界面线程可直接调用。
"""
import datetime
import re
import time
from pathlib import Path
from agent.core import save, save_text
import pet_llm
import pet_state, stage_layout
from pet_agent import CATEGORY_NAMES
from pet_bus import STAGES, STAGE_NAMES, read_json

REPORT_DIR = (stage_layout.WORKFLOW_DIR, '宠物', '日报')
SUMMARY_NAME = '汇总.json'
KEEP = 90                                   # 报表与汇总保留最近 90 个自然日
WEEK_DAYS = 7
TARGETS = {'hit_rate': 0.8, 'flash_share': 0.9, 'budget_share': 0.8}
# 盘上一眼能数出来的物料：剧本／分镜／已采用／镜头／首帧／资产／已有图的资产。
# 这些数字由调用方（pet_ui.counts）数好传进来，pet_report 只负责归一，自己不读盘。
COUNT_KEYS = ('scripts', 'storyboards', 'adopted', 'shots', 'frames', 'assets', 'ready_assets')
SETTLED = pet_state.SETTLED                   # 与状态机共用同一份口径，不另抄一遍
STAGE_ORDER = {stage: index for index, stage in enumerate(STAGES)}
RATE_UNITS = {'storyboard': '/镜', 'keyframe': '/镜', 'video': '/镜', 'assets': '/项', 'continuity': '/镜',
              'audio': '/条', 'edit': '/集', 'delivery': '/项'}


# ── 路径与工具 ──────────────────────────────────────────────────────────────
def day_key(at=None):
    """北京时间日期：与错峰窗口、Token 台账同一条时间轴。"""
    return time.strftime('%Y-%m-%d', time.gmtime(pet_llm.beijing(at)))


def report_dir(project):
    return Path(project).joinpath(*REPORT_DIR)


def report_path(project, day):
    return report_dir(project).joinpath(str(day) + '.md')


def as_day(at=None):
    """把「时间戳／日期串／None」统一成北京时间的 YYYY-MM-DD；认不出来就当今天。"""
    value = str(at if at is not None else '').strip()
    if len(value) == 10 and value.count('-') == 2:
        return value
    if value:
        try:
            return day_key(float(value))
        except (TypeError, ValueError):
            pass
    return day_key(None)


def week_key(at=None):
    """这一天所在那一周的周一日期（YYYY-MM-DD）。

    第 21 期：一份周报一周只留一份，就用「本周周一」当文件名——原来按生成日命名，同一个星期
    里周五、周六、周日各写一份，一周攒出好几份周报（用户报「每周只保存一份」）。
    """
    day = as_day(at)
    try:
        date = datetime.datetime.strptime(day, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return day
    return (date - datetime.timedelta(days=date.weekday())).isoformat()


def weekly_path(project, day):
    """周报路径：一周一份（文件名＝本周周一，同周重跑就是覆盖同一份）。"""
    return report_dir(project).joinpath('周报-' + str(week_key(day)) + '.md')


def reminder_seen(project, kind, period):
    """按项目记住已显示的日报日期／周报周一，重启后仍有效。"""
    return (read_json(report_dir(project) / '提醒记录.json') or {}).get(kind) == period


def mark_reminder_seen(project, kind, period):
    """仅在提醒实际显示后调用；两类报表各保留最近一次，记录不随运行增长。"""
    path = report_dir(project) / '提醒记录.json'
    data = read_json(path) or {}
    data[kind] = period
    save(path, data)


def written_at(path):
    """这一份是什么时候写下去的（清理时按它挑「最后一次」）。拿不到就当最旧。"""
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def retention_start(at=None, keep=KEEP):
    """最近 keep 个自然日（含指定当日）；0 表示不按年龄清理。"""
    if not keep:
        return None
    if int(keep) < 0:
        raise ValueError('报表保留天数不能为负数')
    return datetime.date.fromisoformat(as_day(at)) - datetime.timedelta(days=int(keep) - 1)


def prune(project, at=None, keep=KEEP):
    """回收过期与重复报表；正名优先，缺正名时保留最后写入的副本。

    只识别日期名及数字副本名；周报保留与窗口有交集的整周。
    返回成功回收的原路径；文件占用不影响已生成的报告。
    """
    import storage_maintenance

    folder = report_dir(project)
    start = retention_start(at, keep)
    removed = []
    if (not folder.is_dir() or folder.is_symlink() or folder.is_junction()
            or not folder.resolve().is_relative_to(Path(project).resolve())):
        return removed
    groups = {}
    for path in sorted(folder.glob('*.md')):
        match = re.fullmatch(r'(周报-)?(\d{4}-\d{2}-\d{2})(?: \(\d+\))?\.md', path.name)
        if not match or not path.is_file() or path.is_symlink() or path.is_junction():
            continue
        try:
            date = datetime.date.fromisoformat(match[2])
        except ValueError:
            continue
        weekly = bool(match[1])
        key = date - datetime.timedelta(days=date.weekday()) if weekly else date
        groups.setdefault((weekly, key), []).append(path)
    for (weekly, date), paths in groups.items():
        end = date + datetime.timedelta(days=6) if weekly else date
        canonical = folder / (('周报-' if weekly else '') + date.isoformat() + '.md')
        keeper = canonical if canonical in paths else max(paths, key=written_at)
        for path in paths:
            if path == keeper and (start is None or end >= start):
                continue
            try:
                records = storage_maintenance.recycle_paths(project, [path], '日报周报保留期与重复副本清理')
            except OSError:
                continue
            removed.extend(Path(project) / record['source'] for record in records)
    return removed


def summary_path(project):
    return report_dir(project).joinpath(SUMMARY_NAME)


def _int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _ratio(part, whole):
    return round(float(part) / float(whole), 3) if whole else 0.0


def _percent(value):
    return '%.0f%%' % (float(value or 0.0) * 100)


def _seconds(value):
    """秒数归一：布尔、坏值、负数一律当 0，不让一个脏数字毁掉整行报告。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return round(max(0.0, float(value)), 1)


def span(seconds):
    """秒 → m:ss（满一小时写 h:mm:ss）。"""
    total = int(round(_seconds(seconds)))
    if total >= 3600:
        return '%d:%02d:%02d' % (total // 3600, total % 3600 // 60, total % 60)
    return '%d:%02d' % (total // 60, total % 60)


def normalize_timings(raw):
    """阶段停留归一：stages 只留有停留的、units 只留非 0 的、rates 只留正数。"""
    raw = raw if isinstance(raw, dict) else {}
    stages = {}
    for name, value in (raw.get('stages') or {}).items():
        seconds = _seconds(value)
        if seconds > 0:
            stages[str(name)] = seconds
    units = {}
    for name, value in (raw.get('units') or {}).items():
        count = _int(value)
        if count > 0:
            units[str(name)] = count
    rates = {}
    for name, value in (raw.get('rates') or {}).items():
        seconds = _seconds(value)
        if seconds > 0:
            rates[str(name)] = seconds
    return {'stages': stages, 'units': units, 'rates': rates}


def _stage_items(mapping):
    """按阶段顺序（不是字典序）列出，报告读起来跟页面顺序一致。"""
    return sorted(mapping.items(), key=lambda item: (STAGE_ORDER.get(item[0], len(STAGES)), item[0]))


# ── 归一 ────────────────────────────────────────────────────────────────────
def gather(progress=None, ledger=None, failures=None, notices=None, project=None, budget=None,
           stages=None, at=None, counts=None, timings=None):
    """归一成固定键的数据：所有入参都可缺省，缺就写 0／空串，不抛异常。

    counts 是「盘上真实数出来的物料」（剧本／分镜／镜头／首帧／资产）；timings 是状态机的
    「各阶段停留秒数＋产出单位＋平均单位耗时」。两者不传就是空表，既有键一个不动，老调用方照旧。
    """
    progress = progress if isinstance(progress, dict) else {}
    entries = [entry for entry in (getattr(ledger, 'entries', None) or []) if isinstance(entry, dict)]
    prompt = sum(_int(entry.get('prompt_tokens')) for entry in entries)
    completion = sum(_int(entry.get('completion_tokens')) for entry in entries)
    cached = sum(_int(entry.get('cached_tokens')) for entry in entries)
    flash = sum(1 for entry in entries if entry.get('tier') == 'flash')
    notices = notices if isinstance(notices, dict) else {}
    counts = counts if isinstance(counts, dict) else {}
    rows = []
    for item in (failures or []):
        if not isinstance(item, dict):
            continue
        rows.append({'stage': str(item.get('stage') or ''), 'category': str(item.get('category') or ''),
                     'error': str(item.get('error') or ''), 'hint': str(item.get('hint') or '')})
    try:
        today = _int(ledger.today_tokens(at)) if ledger is not None else 0
    except Exception:
        today = 0
    return {'day': day_key(at), 'project': str(getattr(project, 'name', project) or ''),
            'counts': {key: _int(counts.get(key)) for key in COUNT_KEYS},
            'timings': normalize_timings(timings),
            'percent': round(float(progress.get('percent') or 0.0), 1),
            'stage': str(progress.get('stage') or ''), 'stage_name': str(progress.get('stage_name') or ''),
            'done_stages': _int(progress.get('done_stages')),
            'total_stages': _int(progress.get('total_stages')) or len(STAGES),
            'stages': {str(stage): str((entry or {}).get('state') or '')
                       for stage, entry in (stages or {}).items() if isinstance(entry, dict)},
            'failures': rows,
            'notices': {'sent': len(notices.get('sent') or []), 'pending': len(notices.get('pending') or []),
                        'recorded': len(notices.get('recorded') or [])},
            'tokens': {'prompt': prompt, 'completion': completion, 'cached': cached,
                       'entries': len(entries), 'flash_entries': flash,
                       'hit_rate': _ratio(cached, prompt), 'flash_share': _ratio(flash, len(entries)),
                       'today': today, 'budget': _int(budget)}}


# ── 建议规则表 ──────────────────────────────────────────────────────────────
def advice(data):
    """每条建议都带上触发它的数字；没有可说的就说「状态正常」。"""
    items = []
    tokens = data.get('tokens') or {}
    hit, flash = float(tokens.get('hit_rate') or 0.0), float(tokens.get('flash_share') or 0.0)
    if not _int(tokens.get('entries')):
        items.append('还没有 Token 台账记录：命中率与 Flash 占比要跑过模型请求之后才有得评估。')
    else:
        if hit < TARGETS['hit_rate']:
            items.append('缓存命中率 %s（目标 ≥%s）：固定前缀必须逐字稳定，改一次全量缓存就失效。'
                         % (_percent(hit), _percent(TARGETS['hit_rate'])))
        if flash < TARGETS['flash_share']:
            items.append('Flash 占比 %s（目标 ≥%s）：除拆分／诊断／多步规划外都留在 Flash。'
                         % (_percent(flash), _percent(TARGETS['flash_share'])))
    budget, today = _int(tokens.get('budget')), _int(tokens.get('today'))
    if budget and float(today) / budget >= TARGETS['budget_share']:
        items.append('当日 Token 已用 %d／%d（%s）：非紧急批量请推到北京时间 23:00-07:00 的折扣时段。'
                     % (today, budget, _percent(float(today) / budget)))
    for stage, rows in _by_stage(data.get('failures') or []).items():
        hint = next((row['hint'] for row in rows if row.get('hint')), '')
        items.append('%s 有 %d 条未自动收尾的失败（%s）：先手动跑一次看现场，再决定是否放宽重试。'
                     % (STAGE_NAMES.get(stage, stage), len(rows), hint or rows[0].get('error') or '原因未知'))
    total, done = _int(data.get('total_stages')), _int(data.get('done_stages'))
    if total and done < total:
        items.append('还有 %d 个阶段没有收尾（%d／%d）：当前停在「%s」。'
                     % (total - done, done, total, data.get('stage_name') or '尚未开始'))
    recorded, pending = _int((data.get('notices') or {}).get('recorded')), _int((data.get('notices') or {}).get('pending'))
    if recorded:
        items.append('免打扰窗口里有 %d 条更新只记账没打扰：出窗口会自动补一条汇总，不用手动翻。' % recorded)
    if pending:
        items.append('还有 %d 条通知攒在队列里等一次性说完。' % pending)
    counted = data.get('counts') or {}
    shots, frames = _int(counted.get('shots')), _int(counted.get('frames'))
    if shots and frames < shots:
        items.append('首帧 %d／%d 还没补齐：先按分镜顺序把缺的镜头补上，再谈批量重跑。' % (frames, shots))
    measured = data.get('timings') or {}
    dwell = measured.get('stages') or {}
    if dwell:
        stage, seconds = sorted(dwell.items(), key=lambda item: (-float(item[1]), item[0]))[0]
        items.append('耗时最长的阶段是 %s（%s）：怀疑卡住就先看这一段，别整链一起动。'
                     % (STAGE_NAMES.get(stage, stage), span(seconds)))
    if (measured.get('rates') or {}).get('keyframe'):
        items.append('平均单镜首帧耗时 %s：批量排期按这个数估，别按手工试跑的那一张算。'
                     % span(measured['rates']['keyframe']))
    if not items:
        items.append('状态正常：进度、命中率、Flash 占比与当日预算都在目标内。')
    return items


def _by_stage(failures):
    groups = {}
    for row in failures:
        stage = row.get('stage') or ''
        if stage:
            groups.setdefault(stage, []).append(row)
    return groups


# ── 渲染 ────────────────────────────────────────────────────────────────────
def render(data, items=None, title=None):
    """日报正文：先事实后建议，数字与 data 完全一致（同一输入两遍得到同一份）。"""
    tokens = data.get('tokens') or {}
    notices = data.get('notices') or {}
    total = _int(data.get('total_stages')) or len(STAGES)
    lines = ['# ' + (title or ('制作日报 · ' + str(data.get('day') or ''))), '']
    if data.get('project'):
        lines.append('- 项目：' + str(data['project']))
    lines.append('- 进度：%.1f%%（%d／%d 阶段）' % (float(data.get('percent') or 0.0),
                                                 _int(data.get('done_stages')), total))
    lines.append('- 当前阶段：' + (str(data.get('stage_name') or '') or '全部阶段已完成'))
    todo = [STAGE_NAMES.get(stage, stage) + '（' + state + '）' for stage, state in (data.get('stages') or {}).items()
            if state not in SETTLED]
    if todo:
        lines.append('- 没有收尾的阶段：' + '、'.join(todo))
    lines.append('- Token：prompt %d／completion %d／命中缓存 %d，共 %d 次请求；命中率 %s，Flash 占比 %s'
                 % (_int(tokens.get('prompt')), _int(tokens.get('completion')), _int(tokens.get('cached')),
                    _int(tokens.get('entries')), _percent(tokens.get('hit_rate')), _percent(tokens.get('flash_share'))))
    if _int(tokens.get('budget')):
        lines.append('- 当日 Token：%d／%d（%s）' % (_int(tokens.get('today')), _int(tokens.get('budget')),
                                                     _percent(float(_int(tokens.get('today'))) / _int(tokens.get('budget')))))
    else:
        lines.append('- 当日 Token：%d（未设置日上限）' % _int(tokens.get('today')))
    lines.append('- 未自动收尾的失败：%d 条' % len(data.get('failures') or []))
    lines.append('- 通知：已发 %d，免打扰记账 %d，待发 %d'
                 % (_int(notices.get('sent')), _int(notices.get('recorded')), _int(notices.get('pending'))))
    counted = data.get('counts') or {}
    if any(_int(value) for value in counted.values()):
        lines.append('- 素材：剧本 %d · 分镜 %d（已采用 %d）· 镜头 %d · 首帧 %d · 资产 %d（已有图 %d）'
                     % (_int(counted.get('scripts')), _int(counted.get('storyboards')),
                        _int(counted.get('adopted')), _int(counted.get('shots')),
                        _int(counted.get('frames')), _int(counted.get('assets')),
                        _int(counted.get('ready_assets'))))
    measured = data.get('timings') or {}
    dwell = measured.get('stages') or {}
    if dwell:
        lines.append('- 阶段停留：' + ' · '.join('%s %s' % (STAGE_NAMES.get(name, name), span(seconds))
                                                 for name, seconds in
                                                 sorted(dwell.items(), key=lambda item: (-float(item[1]), item[0]))))
    rates = measured.get('rates') or {}
    if rates:
        lines.append('- 平均耗时：' + ' · '.join('%s %s%s' % (STAGE_NAMES.get(name, name), span(seconds),
                                                            RATE_UNITS.get(name, '/单位'))
                                                for name, seconds in _stage_items(rates)))
    lines.extend(['', '## 建议', ''])
    for item in (advice(data) if items is None else items):
        lines.append('- ' + str(item))
    lines.append('')
    return '\n'.join(lines)


# ── 落盘与汇总 ──────────────────────────────────────────────────────────────
def load_rows(project):
    data = read_json(summary_path(project))
    rows = data.get('rows') if isinstance(data, dict) else None
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def merge_rows(rows, data, keep=KEEP):
    """把当天这行并入汇总：同一天覆盖旧值，按日期升序，只留最近 keep 天。"""
    kept = [row for row in (rows or []) if isinstance(row, dict) and row.get('day') and row.get('day') != data.get('day')]
    kept.append(dict(data))
    kept.sort(key=lambda row: str(row.get('day')))
    return retained_rows(kept, data['day'], keep)


def retained_rows(rows, at=None, keep=KEEP):
    """汇总与 Markdown 使用同一个自然日保留窗口。"""
    start = retention_start(at, keep)
    kept = []
    for row in rows:
        try:
            date = datetime.date.fromisoformat(str(row.get('day', '')))
        except ValueError:
            kept.append(row)  # 无法识别的历史记录不按猜测删除。
            continue
        if start is None or date >= start:
            kept.append(row)
    return kept


def write(project, data, items=None, keep=KEEP):
    """落盘日报并把当日数字并入 汇总.json；返回（日报路径，汇总路径）。"""
    path = report_path(project, data['day'])
    path.parent.mkdir(parents=True, exist_ok=True)
    save_text(path, render(data, items=items))
    summary = summary_path(project)
    save(summary, {'updated_at': time.time(), 'rows': merge_rows(load_rows(project), data, keep=keep)})
    prune(project, data['day'], keep=keep)
    return path, summary


def daily(project, progress=None, ledger=None, failures=None, notices=None, budget=None, stages=None,
          at=None, keep=KEEP, counts=None, timings=None):
    """一句话跑完：归一 → 建议 → 落盘。返回（数据，日报路径）。"""
    data = gather(progress=progress, ledger=ledger, failures=failures, notices=notices, project=project,
                  budget=budget, stages=stages, at=at, counts=counts, timings=timings)
    path, _ = write(project, data, keep=keep)
    return data, path


# ── 周报 ────────────────────────────────────────────────────────────────────
def weekly_rows(rows, at=None, days=WEEK_DAYS):
    """最近 days 天（含今天）的行，按日期升序；不足就按实际条数。"""
    now = time.time() if at is None else float(at)
    start, end = day_key(now - (int(days) - 1) * 86400), day_key(now)
    picked = [row for row in (rows or []) if isinstance(row, dict) and start <= str(row.get('day') or '') <= end]
    picked.sort(key=lambda row: str(row.get('day')))
    return picked


def weekly_totals(rows):
    """周汇总：Token 求和后重算命中率（不是把每天的比例再平均）。"""
    rows = [row for row in (rows or []) if isinstance(row, dict)]
    prompt = sum(_int((row.get('tokens') or {}).get('prompt')) for row in rows)
    completion = sum(_int((row.get('tokens') or {}).get('completion')) for row in rows)
    cached = sum(_int((row.get('tokens') or {}).get('cached')) for row in rows)
    entries = sum(_int((row.get('tokens') or {}).get('entries')) for row in rows)
    flash = sum(_int((row.get('tokens') or {}).get('flash_entries')) for row in rows)
    stages, categories, counts, measured = {}, {}, {}, {}
    for row in rows:
        for item in (row.get('failures') or []):
            item = item if isinstance(item, dict) else {}
            stage = str(item.get('stage') or '')
            if stage:
                stages[stage] = stages.get(stage, 0) + 1
            category = str(item.get('category') or '')
            if category:
                categories[category] = categories.get(category, 0) + 1
        material = row.get('counts')
        if isinstance(material, dict) and any(_int(material.get(key)) for key in COUNT_KEYS):
            counts = {key: _int(material.get(key)) for key in COUNT_KEYS}   # rows 已按日期升序，留下最近一天
        timing = normalize_timings(row.get('timings'))
        if timing['stages'] or timing['rates']:
            measured = timing                            # 停留是累计量，只能取最近一天，不能跨天相加
    return {'days': len(rows), 'first_day': str(rows[0].get('day') or '') if rows else '',
            'last_day': str(rows[-1].get('day') or '') if rows else '',
            'prompt': prompt, 'completion': completion, 'cached': cached, 'entries': entries,
            'hit_rate': _ratio(cached, prompt), 'flash_share': _ratio(flash, entries),
            'percent_best': round(max([float(row.get('percent') or 0.0) for row in rows] or [0.0]), 1),
            'failures': sum(len(row.get('failures') or []) for row in rows),
            'notices': sum(_int((row.get('notices') or {}).get('sent')) for row in rows),
            'failure_stages': stages, 'failure_categories': categories, 'counts': counts,
            'timings': measured}


def weekly_advice(totals):
    """周报建议：只看整周量级，避免被单日噪声带着走。"""
    if not totals.get('days'):
        return ['本周还没有日报：日报每天生成一次，攒够一天的数字才有得汇总。']
    items = []
    if totals.get('prompt') and float(totals.get('hit_rate') or 0.0) < TARGETS['hit_rate']:
        items.append('本周命中率 %s（%d 天）：前缀一改就是整周偏低，先核对固定前缀有没有被拼上时间戳。'
                     % (_percent(totals.get('hit_rate')), totals['days']))
    if totals.get('entries') and float(totals.get('flash_share') or 0.0) < TARGETS['flash_share']:
        items.append('本周 Flash 占比 %s：把非推理任务从 Pro 挪回 Flash，一天能省下大头。'
                     % _percent(totals.get('flash_share')))
    top = sorted(totals.get('failure_stages', {}).items(), key=lambda item: (-item[1], item[0]))
    if top:
        stage, count = top[0]
        items.append('本周失败集中在 %s（%d 次）：先把这一个阶段的现场固定下来，别一次改多处。'
                     % (STAGE_NAMES.get(stage, stage), count))
    mixed = totals.get('failure_categories') or {}
    if mixed:
        category, count = sorted(mixed.items(), key=lambda item: (-item[1], item[0]))[0]
        items.append('失败里「%s」占 %d 次：这一类按同一套处置走一遍，别逐条改。'
                     % (CATEGORY_NAMES.get(category, category), count))
    dwell = (totals.get('timings') or {}).get('stages') or {}
    if dwell:
        stage, seconds = sorted(dwell.items(), key=lambda item: (-float(item[1]), item[0]))[0]
        items.append('整周耗时最长的是 %s（%s）：把它前面的等待改成自动，或提前一批跑。'
                     % (STAGE_NAMES.get(stage, stage), span(seconds)))
    if not items:
        items.append('本周一切正常：命中率、Flash 占比与失败数都在目标内。')
    return items


def render_weekly(totals, at=None, rows=None):
    """周报正文；日期区间按实际有的日报来写，不编没有的天数。"""
    lines = ['# 制作周报 · ' + str(totals.get('first_day') or '') + ' ~ ' + str(totals.get('last_day') or ''), '']
    lines.append('- 覆盖天数：%d 天%s' % (_int(totals.get('days')),
                                       '（本周还没有日报）' if not totals.get('days') else ''))
    lines.append('- 最高进度：%.1f%%' % float(totals.get('percent_best') or 0.0))
    lines.append('- Token：prompt %d／completion %d／命中缓存 %d，共 %d 次请求；命中率 %s，Flash 占比 %s'
                 % (_int(totals.get('prompt')), _int(totals.get('completion')), _int(totals.get('cached')),
                    _int(totals.get('entries')), _percent(totals.get('hit_rate')), _percent(totals.get('flash_share'))))
    lines.append('- 未自动收尾的失败：%d 条；发出的通知：%d 条' % (_int(totals.get('failures')), _int(totals.get('notices'))))
    counted = totals.get('counts') or {}
    if any(_int(value) for value in counted.values()):
        lines.append('- 素材（最近一天）：剧本 %d · 分镜 %d（已采用 %d）· 镜头 %d · 首帧 %d · 资产 %d（已有图 %d）'
                     % (_int(counted.get('scripts')), _int(counted.get('storyboards')),
                        _int(counted.get('adopted')), _int(counted.get('shots')),
                        _int(counted.get('frames')), _int(counted.get('assets')),
                        _int(counted.get('ready_assets'))))
    mixed = totals.get('failure_categories') or {}
    if mixed:
        lines.append('- 失败分类：' + '、'.join(
            '%s %d' % (CATEGORY_NAMES.get(name, name), count)
            for name, count in sorted(mixed.items(), key=lambda item: (-item[1], item[0]))))
    measured = totals.get('timings') or {}
    dwell = measured.get('stages') or {}
    if dwell:
        lines.append('- 阶段停留（截至最近一天）：' + ' · '.join(
            '%s %s' % (STAGE_NAMES.get(name, name), span(seconds))
            for name, seconds in sorted(dwell.items(), key=lambda item: (-float(item[1]), item[0]))))
    rates = measured.get('rates') or {}
    if rates:
        lines.append('- 平均耗时（截至最近一天）：' + ' · '.join(
            '%s %s%s' % (STAGE_NAMES.get(name, name), span(seconds), RATE_UNITS.get(name, '/单位'))
            for name, seconds in _stage_items(rates)))
    if rows:
        lines.append('- 每日进度：' + '、'.join(str(row.get('day')) + ' %.1f%%' % float(row.get('percent') or 0.0)
                                               for row in rows))
    lines.extend(['', '## 建议', ''])
    for item in weekly_advice(totals):
        lines.append('- ' + str(item))
    lines.append('')
    return '\n'.join(lines)


def weekly(project, at=None, days=WEEK_DAYS):
    """读汇总文件算周报：返回（汇总数字，周报正文）。"""
    rows = weekly_rows(load_rows(project), at=at, days=days)
    totals = weekly_totals(rows)
    return totals, render_weekly(totals, at=at, rows=rows)


def write_weekly(project, at=None, days=WEEK_DAYS):
    """落盘周报（一周一份：按本周周一命名，同周重跑覆盖同一份）；返回（路径，汇总数字）。

    写完回收超期和重复报表，并同步裁剪汇总；不依赖另一次日报生成。
    """
    totals, text = weekly(project, at=at, days=days)
    path = weekly_path(project, day_key(at))
    path.parent.mkdir(parents=True, exist_ok=True)
    save_text(path, text)
    rows = load_rows(project)
    retained = retained_rows(rows, at)
    if retained != rows:
        save(summary_path(project), {'updated_at': time.time(), 'rows': retained})
    prune(project, at)
    return path, totals
