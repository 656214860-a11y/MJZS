"""Natural-script auxiliary reports: one envelope, version-bound publication, no model calls."""
import hashlib
import json
import math
import re
from pathlib import Path
from file_cache import read_json
from service_contract import success

REPORTS = {
    'screenplay_gates': ('五阶门控', 5),
    'emotion_curve': ('情绪节拍', 12),
    'dialogue_diagnosis': ('台词诊断', 7),
    'dialogue_speed_check': ('台词语速自检', None),
}
REFERENCES = ('screenplay-gate-engine.md', 'emotion-beat-curve.md',
              'dialogue-doctor-7d.md', 'dialogue-speed-check.md')
OPEN, CLOSE = '<script_quality>', '</script_quality>'


def enabled(instructions):
    return all(name in str(instructions) for name in REFERENCES)


def prompt():
    return '''
【四项辅助质检交付】仅适用于阶段④自然剧本，不改变前三阶段确认流程。
编剧角色审核五阶门控（有「本项目编剧风格」时按该风格审核）；编辑角色审核 12 个情绪节拍；演员角色完成台词七维诊断与语速检查。
三个角色在同一次回复内依次自检并直接修订正文，不输出角色对话、审核过程或修改说明；正文定稿后必须根据最终正文重新汇总四项报告。
附块缺失或格式问题由程序单独提示，不得仅因此要求重写整篇剧本。
完整自然剧本后追加 <script_quality>{JSON}</script_quality>，不要放入对白或 Markdown 代码围栏。
桌面/CLI 将同一正文和此附块写入任务指定的自然剧本文件；助手负责拆分保存辅助报告。
JSON 顶层四键：screenplay_gates、emotion_curve、dialogue_diagnosis、dialogue_speed_check。
每键为 {"status":"pass或fail","items":[...]}，不得空报、伪造通过或遗漏不合格项。
items 每项有 id（从1连续编号）、evidence（最终正文中的逐字非空短引文）、reason（检查依据）、status（pass或fail）。
screenplay_gates 恰好5项，对应原规则 Gate 1～5；emotion_curve 恰好12项，对应12节拍，另有 intensity（0～10数字）。
dialogue_diagnosis 恰好7项，依次对应角色辨识度、潜台词、冲突推进、题材语感、信息效率、节奏、记忆点。
dialogue_speed_check 逐句覆盖所有可发声台词，items 另有 text（原句）、seconds（可发声秒数）、rate（字/秒）；
顶层该报告另有 coverage（逐句核对的范围说明）。无台词也明确说明，不可假造台词。
按原技能判断情绪峰值、常速与快速短促例外；缺少时长依据应报 fail 并说明，不能编造时长。
辅助 JSON 不替代正文，不属于02输入，不另起创作阶段，不在正文中粘贴诊断模板。
'''


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('重复 JSON 字段')
        result[key] = value
    return result


def strip_envelope(text):
    """去掉正文末尾的质检附块，返回干净正文；附块未闭合或损坏也照常剥离。

    只认最后一次出现的 ``<script_quality>`` 作为附块起点，之前的内容一律视为正文，
    因此即使附块被截断、缺少 ``</script_quality>``，正文也能干净地保留下来。
    """
    raw = str(text or '')
    if OPEN not in raw:
        return raw.strip()
    return raw.rsplit(OPEN, 1)[0].strip()


def split_response(response):
    """Keep prose even when the trailing auxiliary envelope is malformed."""
    raw = str(response or '')
    if OPEN not in raw:
        return raw.strip(), {}, ''
    body = strip_envelope(raw)
    auxiliary = raw.rsplit(OPEN, 1)[1]
    try:
        if not auxiliary.rstrip().endswith(CLOSE):
            raise ValueError('质检附块未完整结束')
        payload = json.loads(auxiliary.rstrip()[:-len(CLOSE)].strip(), object_pairs_hook=_object,
                             parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        if not isinstance(payload, dict):
            raise ValueError('质检附块必须是 JSON 对象')
        return body, payload, ''
    except (ValueError, TypeError) as exc:
        return body, {}, str(exc)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _validate(key, report, body):
    if not isinstance(report, dict):
        return 'missing', '模型未交回该报告'
    items = report.get('items')
    expected = REPORTS[key][1]
    if (report.get('status') not in ('pass', 'fail') or not isinstance(items, list)
            or (expected is not None and len(items) != expected)):
        return 'invalid', '报告状态或检查项数量不符合契约'
    for index, item in enumerate(items, 1):
        if (not isinstance(item, dict) or item.get('id') != index
                or item.get('status') not in ('pass', 'fail')
                or not isinstance(item.get('evidence'), str) or not item['evidence'].strip()
                or item['evidence'] not in body or not str(item.get('reason') or '').strip()):
            return 'invalid', '检查项缺少顺序编号、当前正文证据或依据'
    if key == 'emotion_curve':
        values = [item.get('intensity') for item in items]
        if any(not _number(value) or not 0 <= value <= 10 for value in values):
            return 'invalid', '情绪强度须为0～10有限数字'
        if values[8] < 9.5 or values[8] != max(values):
            return 'fail', '第9节拍未满足峰值≥9.5'
    if key == 'dialogue_speed_check':
        if not items or not str(report.get('coverage') or '').strip():
            return 'incomplete', '缺少可核对的逐句台词及覆盖范围；无台词请人工复核'
        for item in items:
            line, seconds, rate = item.get('text'), item.get('seconds'), item.get('rate')
            if (not isinstance(line, str) or not line or line not in body
                    or not _number(seconds) or seconds <= 0 or not _number(rate) or rate <= 0):
                return 'invalid', '语速检查缺少原句或有效时长/语速'
            count = len(re.findall(r'[\u4e00-\u9fffA-Za-z0-9]', line))
            if abs(count / seconds - rate) > 0.15:
                return 'invalid', '台词字数、发声时长与语速不一致'
            if rate > 5 and seconds > 3:
                return 'fail', '快速台词连续超过3秒'
    if report['status'] == 'fail' or any(item['status'] == 'fail' for item in items):
        return 'fail', '模型报告存在未通过项'
    return 'pass', '模型判定通过，程序已核对格式、正文证据及数值；语义仍需审阅'


def publish_reports(response, script_path, quality_root, *, publish):
    """Caller owns publication and path authority; failed reports never erase prose."""
    body, payload, error = split_response(response)
    digest = hashlib.sha256(body.encode('utf-8')).hexdigest()
    source = str(Path(script_path).resolve())
    identity = hashlib.sha256(source.encode('utf-8')).hexdigest()[:12]
    folder = Path(quality_root) / identity / digest
    statuses = {}
    def publish_text(path, text):
        publish(path, text, lambda value: bool(value.strip()), lambda _target: None)
    # Preserve the original return before interpreting any model claims.
    publish_text(folder / 'model_response.txt', str(response))
    for key, (label, _) in REPORTS.items():
        state, detail = ('invalid', error) if error else _validate(key, payload.get(key), body)
        statuses[key] = state
        value = dict(schema_version=1, script_sha256=digest, script_path=source,
                     status=state, detail=detail, model_report=payload.get(key))
        publish_text(folder / (key + '.json'), json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    labels = {'pass': '模型通过/待审阅', 'fail': '未通过', 'invalid': '格式或证据错误',
              'missing': '缺失', 'incomplete': '待人工复核'}
    summary = '四项质检：' + '；'.join(REPORTS[key][0] + '：' + labels[state] for key, state in statuses.items())
    report_path = folder / '质检报告.md'
    publish_text(report_path, '# 自然剧本辅助质检\n\n' + summary + '\n\n来源剧本：' + source
         + '\n\n正文 SHA256：' + digest
         + '\n\n' + '\n'.join('- [' + label + '](' + key + '.json)' for key, (label, _) in REPORTS.items())
         + '\n\n[模型原始返回](model_response.txt)\n\n报告仅供审阅，未完成项不会触发自动重写。辅助报告不进入02。\n')
    return success(dict(quality_summary=summary, quality_passed=all(state == 'pass' for state in statuses.values()),
                        quality_report_path=str(report_path), quality_statuses=statuses))


def adopted_quality(script_path, quality_root):
    """定位采用稿正文对应的辅助质检状态表；未生成报告返回 None。

    定位口径与 ``publish_reports`` 一致：``sha256(脚本路径)[:12] / sha256(正文)``。
    手动添加、下载收回或未启用质检的采用稿没有报告，返回 None 由调用方按
    「不适用」处理（REQ-S01-22：有报告才门禁，missing／incomplete 不硬卡）。"""
    try:
        body = Path(script_path).read_text(encoding='utf-8').strip()
    except OSError:
        return None
    if not body:
        return None
    digest = hashlib.sha256(body.encode('utf-8')).hexdigest()
    identity = hashlib.sha256(str(Path(script_path).resolve()).encode('utf-8')).hexdigest()[:12]
    folder = Path(quality_root) / identity / digest
    if not folder.is_dir():
        return None
    statuses = {}
    for key in REPORTS:
        path = folder / (key + '.json')
        try:
            statuses[key] = str(read_json(path).get('status') or 'invalid')
        except (OSError, ValueError):
            statuses[key] = 'invalid'
    return statuses


QUALITY_BLOCKING = ('fail', 'invalid')


def list_reports(quality_root):
    """列出质检目录下全部报告，按修改时间倒序，供「质检报告」按钮快速定位。

    每份报告目录里的 ``screenplay_gates.json`` 都记录了 ``script_path``（源剧本绝对路径），
    据此把哈希目录映射回具体剧本，避免用户面对一串无意义的 hash 子目录。返回
    ``[{'report_path', 'script_path', 'updated_at'}, ...]``；目录不存在或条目损坏时跳过。
    """
    root = Path(quality_root)
    if not root.is_dir():
        return []
    rows = []
    for report_md in sorted(root.glob('*/*/质检报告.md')):
        try:
            report_dir = report_md.parent
            gate = report_dir / 'screenplay_gates.json'
            script_path = ''
            if gate.is_file():
                with gate.open('r', encoding='utf-8') as stream:
                    script_path = str(json.load(stream).get('script_path') or '')
            rows.append({'report_path': str(report_md),
                         'script_path': script_path,
                         'updated_at': report_md.stat().st_mtime})
        except (OSError, ValueError):
            continue
    rows.sort(key=lambda row: row['updated_at'], reverse=True)
    return rows
