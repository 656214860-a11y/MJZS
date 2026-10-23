"""Validate and import completed prompt files, independently of the active shot."""
import hashlib
import json
from pathlib import Path
import re
import time
from contextlib import ExitStack
from file_cache import read_json_shared as read_cached
from agent.core import read, restore_bytes, save_bytes, fingerprint

def parse_result(raw):
    """Repair only unescaped quotes/newlines in the final video_prompt string."""
    fixed = False
    try:
        record = json.loads(raw)
    except json.JSONDecodeError as original:
        match = re.fullmatch(r'(?s)(\s*\{.*?)"video_prompt"\s*:\s*"(.*)"\s*\}\s*', raw)
        if not match:
            raise ValueError(f'结果 JSON 格式错误（第 {original.lineno} 行）；请让 Agent 修正后保存。') from original
        try:
            metadata = json.loads(match[1] + '"video_prompt":null}')
            if set(metadata) - {'shot_id', 'source_signature', 'episode_id', 'video_prompt'}:
                raise ValueError('unexpected metadata')
            text = match[2]; pieces = []; index = 0
            if re.search(r'"\s*,\s*"\w+"\s*:', text): raise ValueError('unexpected trailing field')
            while index < len(text):
                char = text[index]
                if char == '\\':
                    if index+1 >= len(text): raise ValueError('unfinished escape')
                    pieces.append(text[index:index+2]); index += 2; continue
                pieces.append(json.dumps(char, ensure_ascii=False)[1:-1]); index += 1
            metadata['video_prompt'] = json.loads('"' + ''.join(pieces) + '"')
            record = metadata; fixed = True
        except (ValueError, TypeError) as exc:
            raise ValueError(f'结果 JSON 格式错误（第 {original.lineno} 行）；请让 Agent 修正后保存。') from exc
    if not isinstance(record, dict): raise ValueError('结果须为包含 video_prompt 的 JSON 对象')
    text = record.get('video_prompt')
    if not isinstance(text, str) or not 0 < len(text.strip()) <= 1500:
        raise ValueError('结果中的提示词须为 1–1500 字，原提示词保留。')
    if not isinstance(record.get('shot_id'), str) or not re.fullmatch(r'[a-f0-9]{64}', str(record.get('source_signature', ''))):
        raise ValueError('结果缺少有效镜头编号或分镜校验值，原提示词保留。')
    return record, fixed

def import_result(studio, sid, path):
    path = Path(path)
    if path.stat().st_size > 1024*1024: raise ValueError('提示词文件超过 1MB，未自动导入。')
    raw = path.read_bytes(); record, fixed = parse_result(raw.decode('utf-8-sig'))
    text = record['video_prompt'].strip()
    if record['shot_id'] != sid: raise ValueError('结果属于其他镜头，未自动导入。')
    with ExitStack() as stack:
        try: stack.enter_context(studio.lock())
        except ValueError as exc: raise BlockingIOError('项目正被其他操作使用') from exc
        from video_task_state import generation_active
        if generation_active(studio,sid):raise BlockingIOError('视频生成期间暂缓导入提示词')
        episode = read(studio.episode_path)
        shot = next((item for item in episode['shots'] if item['id'] == sid), None)
        if shot is None: raise ValueError('当前分镜没有此镜头，未自动导入。')
        if record.get('episode_id') and record['episode_id'] != episode.get('episode_id'):
            raise ValueError('结果属于其他分集，未自动导入。')
        previous = shot.get('video_prompt', '')
        if previous != text and record['source_signature'] != fingerprint(shot):
            raise ValueError('生成期间分镜或资产选项已变化，结果已保留，请核对后通过“导入提示词”采用。')
        if path.read_bytes() != raw: raise OSError('Agent 正在更新结果，稍后重试')
        backup = None
        if fixed:
            backup = path.parent/'历史版本'/(path.stem+'_格式修复_'+hashlib.sha256(raw).hexdigest()[:12]+'.txt')
            if not backup.exists(): save_bytes(backup, raw)
        if previous != text or fixed:
            try:
                from stage_execution_service import publish_video_prompt
                publish_video_prompt(studio, sid, text)
            except Exception:
                if backup is not None:
                    restore_bytes(backup, None)
                raise
    return {'text': text, 'previous': previous, 'changed': previous != text, 'fixed': fixed}

class PromptResults:
    def __init__(self):
        self.next_poll = 0; self.seen = {}; self.observed = {}; self.pending = {}; self.messages = {}

    def begin(self, sid, draft):
        self.pending[sid] = draft
        self.seen.pop(sid, None); self.observed.pop(sid, None); self.next_poll = 0

    def poll(self, app, force=False):
        now = time.monotonic()
        if not force and now < self.next_poll: return
        self.next_poll = now + 1.2
        if app.busy or getattr(app, 'optimizer_busy', False): return
        episode = read_cached(app.studio.episode_path)
        for shot in episode['shots']:
            sid = shot['id']; path = app.studio.media_dir/'video_prompts'/(sid+'.json')
            if not path.is_file(): continue
            from video_task_state import prompt_locked
            if prompt_locked(app,sid):continue
            stat = path.stat(); key = (stat.st_mtime_ns, stat.st_size, fingerprint(shot))
            if self.seen.get(sid) == key: continue
            # Wait for one unchanged poll; do not read the middle of an Agent write.
            if not force and self.observed.get(sid) != key:
                self.observed[sid] = key; continue
            try:
                result = import_result(app.studio, sid, path)
            except (ValueError, UnicodeError) as exc:
                self.seen[sid] = key
                message = sid+' 提示词未导入：'+str(exc)
                if self.messages.get(sid) != message:
                    app.write(message); self.messages[sid] = message
                continue
            except OSError:
                continue  # A lock or an in-progress write can resolve on the next poll.
            stat = path.stat(); current = app.studio.shot(sid)
            self.seen[sid] = (stat.st_mtime_ns, stat.st_size, fingerprint(current))
            self.messages.pop(sid, None)
            if not result['changed'] and not result['fixed']: continue
            selected = app.tree.selection()
            draft_preserved = False
            if selected and selected[0] == sid and app.editing_sid == sid:
                draft = app.prompt.get('1.0','end').strip()
                if draft in (result['previous'].strip(), result['text'], self.pending.get(sid)):
                    app.prompt.delete('1.0', 'end'); app.prompt.insert('1.0', result['text'])
                else: draft_preserved = True
            self.pending.pop(sid, None)
            app.write(sid+' 提示词已自动导入并保存。'+('已修复文件中的引号格式。' if result['fixed'] else '')+
                      ('当前手动编辑的草稿已保留。' if draft_preserved else ''))
