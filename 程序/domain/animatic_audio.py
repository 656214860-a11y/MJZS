"""REQ-S04-74/75/76/77：分镜预演三轨临时声音。纯 L2：零同层 import，合成、签名与探针能力全部由调用方注入。"""
from pathlib import Path

SUBDIRS = {'dialogue': '声音/对白', 'track': '声音/整轨', 'music': '声音/音乐'}
OVERLONG_TOLERANCE_SECONDS = 0.1
OVERLONG_MESSAGE = '对白超长，请调长本镜时长或回初步分镜拆镜'


def dialogue_text(raw):
    """S03 多形态 dialogue 归一：dict 取 text/line，列表滤空项以「。」连接，空白返回 ''。"""
    if raw is None:
        return ''
    if isinstance(raw, dict):
        return dialogue_text(raw.get('text') or raw.get('line'))
    if isinstance(raw, (list, tuple)):
        return '。'.join(part for part in (dialogue_text(item) for item in raw) if part)
    return str(raw).strip()


def _live_file(path):
    """存在的非空文件才算可用音源；缺失或 0 字节一律按未导入处理。"""
    if path is None:
        return None
    path = Path(path)
    return path if path.is_file() and path.stat().st_size else None


def _shot_seconds(shot):
    return float(shot.get('seconds') or shot.get('duration')
                 or shot.get('estimated_duration') or 0)


def _shot_id(shot):
    return str(shot.get('id') or shot.get('shot_id'))


def plan(shots, *, full_track=None, music=None):
    """决定预演声音模式：整轨配音优先；否则按有对白的镜头排逐镜临时 TTS；全无音源时静音。"""
    track = _live_file(full_track)
    bgm = _live_file(music)
    if track is not None:
        return {'mode': 'full_track', 'full_track': track, 'music': bgm, 'tts_shots': []}
    pending = []
    start = 0.0
    for shot in shots:
        seconds = _shot_seconds(shot)
        text = dialogue_text(shot.get('dialogue'))
        if text:
            pending.append({'id': _shot_id(shot), 'text': text,
                            'start_seconds': start, 'seconds': seconds})
        start += seconds
    return {'mode': 'per_shot_tts' if pending else 'silent',
            'full_track': None, 'music': bgm, 'tts_shots': pending}


def shot_tts(shot, output_dir, settings, *, synthesize, signature_fn, write_temporary,
             **options):
    """逐镜临时 TTS：dialogue 为空返回 None；同签名非空文件直接复用，不调合成器。

    options 可含 ``project``（计费上下文）与 ``persistent``（默认 True；为真时按
    ``tts-previs:<镜头ID>:<签名>`` 生成 request_id 供幂等计费）。
    """
    text = dialogue_text(shot.get('dialogue')) or dialogue_text(shot.get('text'))
    if not text:
        return None
    if not callable(synthesize) or not callable(signature_fn) or not callable(write_temporary):
        raise TypeError('逐镜 TTS 需要由 L3 注入合成器、签名器与暂存写入器。')
    project = options.pop('project', None)
    persistent = options.pop('persistent', True)
    if options:
        raise TypeError('未知逐镜 TTS 参数：' + ', '.join(sorted(options)))
    shot_id = _shot_id(shot)
    signature = signature_fn(text, settings)
    target = Path(output_dir) / ('%s_temp_%s.mp3' % (shot_id, signature))
    if target.is_file() and target.stat().st_size:
        return target
    request_id = 'tts-previs:%s:%s' % (shot_id, signature) if persistent else None
    write_temporary(target, synthesize(text, settings=settings, project=project,
                                       request_id=request_id))
    return target


def detect_overlong(shots, clip_paths, *, probe_duration,
                    tolerance=OVERLONG_TOLERANCE_SECONDS):
    """逐镜核对实测对白时长：超过镜头时长加容差即告警；不截断、不加速、不改镜头时长。"""
    if not callable(probe_duration):
        raise TypeError('时长探针需要由 L3 注入。')
    paths = dict(clip_paths)
    warnings = []
    for shot in shots:
        shot_id = _shot_id(shot)
        path = paths.get(shot_id)
        if path is None:
            continue
        audio_seconds = float(probe_duration(path))
        shot_seconds = _shot_seconds(shot)
        if audio_seconds > shot_seconds + float(tolerance):
            warnings.append({'shot_id': shot_id, 'audio_seconds': audio_seconds,
                             'shot_seconds': shot_seconds, 'message': OVERLONG_MESSAGE})
    return warnings


def _seconds_text(value):
    text = ('%.3f' % float(value)).rstrip('0').rstrip('.')
    return text or '0'


def _clip_delay_ms(clip):
    if 'start_ms' in clip:
        return int(round(float(clip['start_ms'])))
    return int(round(float(clip.get('start_seconds', 0)) * 1000))


def build_audio_mix_command(output_path, total_seconds, *, full_track=None,
                            dialogue_clips=(), music=None, ffmpeg='ffmpeg'):
    """拼一条 ffmpeg 混音命令：整轨直接铺满；逐镜对白按 adelay 放置后 amix；音乐 -12dB 垫底。"""
    clips = list(dialogue_clips or ())
    if full_track is None and not clips and music is None:
        return [str(ffmpeg), '-nostdin', '-y', '-v', 'error',
                '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                '-t', _seconds_text(total_seconds), '-c:a', 'aac', str(output_path)]
    sources = []
    if full_track is not None:
        sources.append(str(full_track))
    else:
        sources.extend(str(clip['path']) for clip in clips)
    music_index = len(sources) if music is not None else None
    if music is not None:
        sources.append(str(music))
    command = [str(ffmpeg), '-nostdin', '-y', '-v', 'error']
    for source in sources:
        command += ['-i', source]
    filters, voices = [], []
    if full_track is not None:
        voices.append('[0:a]')
    elif clips:
        for index, clip in enumerate(clips):
            delay = _clip_delay_ms(clip)
            filters.append('[%d:a]adelay=%d|%d[d%d]' % (index, delay, delay, index))
        if len(clips) == 1:
            voices.append('[d0]')
        else:
            filters.append(''.join('[d%d]' % index for index in range(len(clips)))
                           + 'amix=inputs=%d:duration=longest:normalize=0[voice]' % len(clips))
            voices.append('[voice]')
    if music_index is not None:
        filters.append('[%d:a]volume=-12dB[bgm]' % music_index)
        voices.append('[bgm]')
    if len(voices) > 1:
        filters.append(''.join(voices)
                       + 'amix=inputs=%d:duration=longest:normalize=0[mix]' % len(voices))
        mixed = '[mix]'
    else:
        mixed = voices[0]
    filters.append(mixed + 'apad[out]')
    command += ['-filter_complex', ';'.join(filters), '-map', '[out]',
                '-t', _seconds_text(total_seconds), '-c:a', 'aac', str(output_path)]
    return command
