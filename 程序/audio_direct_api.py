# -*- coding: utf-8 -*-
"""配音与字幕阶段选 API 模型时的音频脚本直连执行器（REQ-S11-50，DES-S11-50）。

骨架复用 storyboard_direct_api（模型判定、_Batch、_ask、Job／launch、取消登记）；本模块只写音频专属部分：
一次请求让模型同时回 配音脚本.md 与整集 SRT，程序校验（编号、时间码、重叠、总时长、对白覆盖）
通过后才经 stage_publication 发布，不合格带问题清单重试一次，仍不合格不落盘。
"""
import re
import time
from pathlib import Path

import storyboard_direct_api as _base
from storyboard_direct_api import direct_model  # noqa: F401  同一份判定，不另立第二套

SCRIPT_MARK = '=====配音脚本.md====='
SRT_MARK = '=====SRT====='
HISTORY_KEEP = 2
STAGE_LABEL = '配音与字幕'
TOLERANCE = 0.5
_TIME = re.compile(r'^(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})\s*$')


def audio_direct_rules():
    return ('【直连输出格式】只回复下面两段，不要任何解释：\n'
            '%s\n（配音脚本 Markdown：按镜头编号分节，每句台词一行，字段为 说话人｜语气/情绪、语速、停顿、重音｜台词原文；'
            '无对白的镜头只写环境声与动作音建议）\n%s\n（整集 SRT：编号从 1 连续，时间码 HH:MM:SS,mmm --> HH:MM:SS,mmm，'
            '每条结束晚于开始、不与上一条重叠、不超过总时长，每句台词原文必须出现）\n'
            '只处理分镜里已有的对白，不编造台词、不改说话人；不调用语音合成、不生成音频。' % (SCRIPT_MARK, SRT_MARK))


def _seconds(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def _squash(text):
    return re.sub(r'[\W_]+', '', str(text or ''))


def _strip_fence(text):
    return re.sub(r'```(?:markdown|md|srt)?', '', text, flags=re.I).strip()


def _split(reply):
    reply = str(reply or '')
    a, b = reply.find(SCRIPT_MARK), reply.find(SRT_MARK)
    if a < 0 or b < 0 or b < a:
        raise ValueError('回复里没有找到分隔行 %s 与 %s' % (SCRIPT_MARK, SRT_MARK))
    return _strip_fence(reply[a + len(SCRIPT_MARK):b]), _strip_fence(reply[b + len(SRT_MARK):])


def _parse_srt(srt, total):
    problems, cues, last_end = [], [], 0.0
    blocks = [b for b in re.split(r'\n\s*\n', srt.replace('\r\n', '\n').strip()) if b.strip()]
    if not blocks:
        raise ValueError('SRT 是空的')
    for index, block in enumerate(blocks, 1):
        lines = block.strip().split('\n')
        if lines[0].strip() != str(index):
            problems.append('字幕编号应为 %d，实际是 %s' % (index, lines[0].strip()[:20]))
        match = _TIME.match(lines[1].strip()) if len(lines) > 1 else None
        if not match:
            problems.append('第 %d 条时间码格式不对' % index)
            continue
        start, end = _seconds(*match.groups()[:4]), _seconds(*match.groups()[4:])
        text = ' '.join(x.strip() for x in lines[2:]).strip()
        if not text:
            problems.append('第 %d 条没有字幕文字' % index)
        if end <= start:
            problems.append('第 %d 条结束时间不晚于开始时间' % index)
        if start < last_end - 1e-6:
            problems.append('第 %d 条与上一条重叠' % index)
        if end > total + TOLERANCE:
            problems.append('第 %d 条超过分镜总时长 %.1f 秒' % (index, total))
        last_end = max(last_end, end)
        cues.append(text)
    if problems:
        raise ValueError('\n'.join(problems))
    return cues


def validate_reply(reply, episode):
    """拆分并校验模型回复；返回 (配音脚本文本, SRT 文本)，不合格抛 ValueError（多条问题换行连接）。"""
    from subtitle_timing import _shot_duration, timed_entries
    script, srt = _split(reply)
    shots = [s for s in (episode or {}).get('shots', []) if isinstance(s, dict)]
    total = sum(_shot_duration(s) for s in shots)
    problems = []
    if not script:
        problems.append('配音脚本是空的')
    try:
        cues = _parse_srt(srt, total)
    except ValueError as error:
        problems.append(str(error))
        cues = []
    entries, _estimated = timed_entries(episode)
    joined_srt, joined_script = _squash(''.join(cues)), _squash(script)
    for sid, _speaker, text, _a, _b in entries:
        key = _squash(text)
        if cues and key and key not in joined_srt:
            problems.append('对白未出现在字幕中：' + text)
        if script and key and key not in joined_script:
            problems.append('对白未出现在配音脚本中：' + text)
    for sid in sorted({e[0] for e in entries}):
        if script and sid not in script:
            problems.append('配音脚本缺少镜头 ' + str(sid))
    if problems:
        raise ValueError('\n'.join(problems))
    return script, srt


def _messages(episode, entries, prior=None):
    lines, current = [], None
    for sid, speaker, text, start, end in entries:
        if sid != current:
            shot = next((s for s in episode.get('shots', []) if isinstance(s, dict) and s.get('id') == sid), {})
            lines.append('### %s %s（%s秒）' % (sid, shot.get('title', ''), shot.get('duration', '')))
            current = sid
        lines.append('- %s %.1f-%.1fs：%s' % (speaker or '未注明', start, end, text))
    head = ('请为下面这一集制作配音脚本与字幕。集号：%s。本地草稿时间轴按镜头时长均分，仅供参考，'
            '请按台词实际时长、停顿与说话人交替微调。\n<分镜对白>\n%s\n</分镜对白>'
            % (episode.get('episode_id', ''), '\n'.join(lines)))
    messages = [{'role': 'user', 'content': head}]
    if prior:
        messages += [{'role': 'assistant', 'content': prior[0]},
                     {'role': 'user', 'content': '上一版没有通过本地校验，请修正下列全部问题后按原格式重新回复：\n' + prior[1]}]
    return messages


def _publish(batch, episode, script, srt):
    import uuid
    from project_stages import audio, subtitles
    from stage_publication import publish_stage_bundle
    import file_cache
    folder, history = audio(batch.project), audio(batch.project) / '历史版本'
    target = folder / '配音脚本.md'
    code = re.sub(r'[^\w-]+', '', str(episode.get('episode_id') or '')) or 'EP'
    srt_path = subtitles(batch.project) / ('配音_%s_%s.srt' % (code, uuid.uuid4().hex[:6]))
    artifacts = {target: (script.rstrip() + '\n').encode('utf-8'),
                 srt_path: (srt.rstrip() + '\n').encode('utf-8-sig')}
    if target.is_file():
        artifacts[history / ('配音脚本_%s.md' % time.strftime('%Y%m%d_%H%M%S'))] = target.read_bytes()
    publish_stage_bundle(artifacts, lambda _items: not batch.cancelled(),
                         lambda: [file_cache.published(path) for path in artifacts])
    older = sorted(history.glob('配音脚本_*.md'), key=lambda p: p.name, reverse=True)[HISTORY_KEEP:] if history.is_dir() else []
    if older:
        from storage_maintenance import recycle_paths
        recycle_paths(batch.project, older, '配音脚本历史版本超过 %d 份' % HISTORY_KEEP)
    return target, srt_path


def _episode(batch, source):
    from agent.core import read
    from subtitle_timing import timed_entries
    episode = read(source) if source and Path(source).is_file() else None
    if not isinstance(episode, dict):
        raise ValueError('找不到可读取的分镜 JSON：' + str(source))
    entries, _estimated = timed_entries(episode)
    if not entries:
        raise ValueError('这份分镜没有对白，无需生成配音脚本与字幕')
    prior = None
    for attempt in range(1, _base.MAX_FORMAT_RETRIES + 1):
        reply = _base._ask(batch, _messages(episode, entries, prior))
        try:
            script, srt = validate_reply(reply, episode)
            break
        except ValueError as error:
            if attempt == _base.MAX_FORMAT_RETRIES:
                raise ValueError('两次回复都没有通过校验：' + str(error).replace('\n', '；'))
            prior = (reply, str(error))
            if batch.cancelled():
                raise _base._Stopped()
            time.sleep(_base.FORMAT_RETRY_BASE_SECONDS * (2 ** (attempt - 1)))
    target, srt_path = _publish(batch, episode, script, srt)
    try:
        from stage_execution_service import refresh_audio_manifests
        refresh_audio_manifests(batch.project)
    except Exception:  # 声明产出清单刷新失败不影响已发布的成果
        import app_logging
        app_logging.swallowed()
    return target, srt_path


def run_batch(project, config, skill_text, *, source=None, report=None, **services):
    """同步处理一份分镜：一次请求（不合格重试一次）。返回 {'ok','paths','error','stopped'}；report(text) 播报结果。"""
    report = report or (lambda _text: None)
    batch = _base._Batch(project, config, skill_text, profile=('audio', audio_direct_rules()), **services)
    try:
        if batch.cancelled():
            raise _base._Stopped()
        target, srt_path = _episode(batch, source)
        report('配音脚本与字幕已生成：%s、%s' % (target.name, srt_path.name))
        return {'ok': True, 'paths': [str(target), str(srt_path)], 'error': '', 'stopped': False}
    except _base._Stopped:
        return {'ok': False, 'paths': [], 'error': '已停止', 'stopped': True}
    except Exception as error:
        report('配音脚本没有生成：%s' % error)
        return {'ok': False, 'paths': [], 'error': str(error), 'stopped': False}


class Job(_base.Job):
    thread_name = 'audio-direct'
    busy_text = '正在直连制作配音脚本，请等当前这批完成，或先点「强制停止制作」。'

    def execute(self, **services):
        return [run_batch(self.project, self.config, self.skill_text, **services, **self.kwargs)]


def launch(project, config, skill_text, *, done=None, **kwargs):
    return _base.launch(project, config, skill_text, done=done, job_class=Job, **kwargs)
