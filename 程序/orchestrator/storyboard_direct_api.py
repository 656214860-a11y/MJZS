# -*- coding: utf-8 -*-
"""初步分镜选 API 模型时的直连执行器（REQ-S03-53，DES-S03-52）。

模型池里的 API 模型不再经 Qwen Code：一集一次请求，模型只回一个 JSON，程序提取、
用 validate_episode 校验（不合格带错误清单重试一次），合格才经 stage_publication 发布。
手动按钮与三虎自动都从 desktop_idea_chat._FlowAgentLaunch 进入这里，分流点只有一处。
"""
import json
import logging
import re
import time
from pathlib import Path

import contract.error_codes as error_codes
import infra.app_logging as app_logging
import infra.business_log as business_log
import infra.executors as executors
from contract.file_naming import generate_existing

logger = logging.getLogger(__name__)

MAX_TOKENS = 32768
REQUEST_TIMEOUT = 600
HISTORY_KEEP = 2
STAGE_LABEL = '初步分镜'
MAX_FORMAT_RETRIES = 2
FORMAT_RETRY_BASE_SECONDS = 0.25


def direct_model(config):
    """引擎为 qwen、所选模型在模型池里且调用方式不是桌面程序时返回 (模型名, 记录)，否则 None。"""
    import infra.model_pool as model_pool
    config = config or {}
    chosen = str(config.get('model') or '').strip()
    if config.get('engine') != 'qwen' or not chosen or chosen == model_pool.AUTO:
        return None
    record = model_pool.pool(program=Path(__file__).resolve().parents[1]).get(chosen)
    if not record or model_pool.call_mode(record, chosen) == 'Desktop':
        return None
    return chosen, record


def _extract_json(text):
    """去掉 Markdown 围栏，取第一个 { 到最后一个 }。"""
    text = re.sub(r'```(?:json)?', '', str(text or ''), flags=re.I)
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end <= start:
        raise _DirectError('回复里没有找到 JSON 对象', code='E-CONTRACT-VIOLATION')
    data = json.loads(text[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError('回复的 JSON 不是对象')
    return data


def _relative(project, path):
    try:
        return Path(path).resolve().relative_to(Path(project).resolve()).as_posix()
    except ValueError:
        return str(path)


def _shot_number(shot_id):
    match = re.search(r'SH(\d+)', str((shot_id or {}).get('id', '') if isinstance(shot_id, dict) else shot_id))
    return int(match.group(1)) if match else 0


def _first_shot_number(project, episode_number, exclude=None):
    """集号更小的已有分镜里最大的镜头编号 +1（镜头编号按集号连续，REQ-S03-14）。"""
    from agent.core import read
    from orchestrator.project_context_factory import project_context
    from domain.storyboard_catalog_service import file_order, working_dir
    folder = working_dir(project_context(project))
    last = 0
    for path in folder.glob('*_分镜.json') if folder.is_dir() else ():
        if exclude is not None and Path(path).resolve() == Path(exclude).resolve():
            continue
        try:
            data = read(path)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and file_order(path, data)[0] < episode_number:
            last = max([last, *(_shot_number(shot) for shot in data.get('shots', []) if isinstance(shot, dict))])
    return last + 1


def _markdown(data):
    lines = ['# %s %s' % (data.get('episode_id', ''), data.get('title', '')), '',
             '总时长：%s 秒　镜头数：%s' % (data.get('duration', ''), len(data.get('shots', []))), '']
    for shot in data.get('shots', []):
        lines += ['## %s %s（%s 秒）' % (shot.get('id', ''), shot.get('title', ''), shot.get('duration', '')),
                  '- 场景：%s' % shot.get('location', ''),
                  '- 人物：%s' % '、'.join(str(x) for x in shot.get('characters', []) or []),
                  '- 首帧提示词：%s' % shot.get('frame_prompt', ''),
                  '- 视频提示词：%s' % shot.get('video_prompt', ''), '']
    return '\n'.join(lines).encode('utf-8')


def _messages(script_text, number, start, existing=None, prior=None, request_text=''):
    code = 'EP%03d' % number
    head = ('请为下面这一集制作分镜。集号：%s，episode_id 必须是 %s；镜头编号从 SH%03d 起连续编号。'
            '只回复一个 JSON 对象，不要任何解释，不要 Markdown 围栏。' % (code, code, start))
    if str(request_text or '').strip():
        head += '\n用户补充与修改要求：' + str(request_text).strip()
    if existing is not None:
        head += '\n这一集已有分镜，请在它的基础上修订并返回完整的新版 JSON：\n<已有分镜>\n%s\n</已有分镜>\n' % (
            json.dumps(existing, ensure_ascii=False))
    messages = [{'role': 'user', 'content': head + '\n<剧本正文>\n' + script_text + '\n</剧本正文>'}]
    if prior:
        messages += [{'role': 'assistant', 'content': prior[0]},
                     {'role': 'user', 'content': '上一版没有通过本地校验，请修正下列全部问题后重新回复完整 JSON：\n' + prior[1]}]
    return messages


class _Stopped(Exception):
    pass


class _DirectError(ValueError):
    """直连执行器里已标好错误码的失败；code 必须是 error_codes 已登记码。"""

    def __init__(self, message, *, code):
        self.code = code
        super().__init__(message)


def _failure(error, default_code):
    """失败 → ``(错误码, 用户可读文字)``：异常自带已登记码优先，文字一定以 ``[E-`` 开头。"""
    code = getattr(error, 'code', None)
    if code not in error_codes.CODES:
        code = 'E-FILE-NOT-FOUND' if isinstance(error, FileNotFoundError) else str(default_code or '')
    if code not in error_codes.CODES:
        code = 'E-UNKNOWN'
    text = error_codes.user_text(error, fallback=code)
    if not text.startswith('[E-'):
        text = error_codes.describe(code) + '：' + text
    return code, text


def _ask(batch, messages):
    """发一次请求；返回回复文本。取消、失败、被截断都抛出带原因的异常。"""
    import infra.model_pool as model_pool
    from infra.model_router import failure_policy, record_circuit_failure, record_circuit_success
    from contract.workflow_context_budget import ensure_request_context
    ensure_request_context(batch.system + '\n'.join(str(m['content']) for m in messages), STAGE_LABEL,
                           context_limit=model_pool.context_length_of((batch.record or {}).get('context_length')) or None,
                           output_reserved=MAX_TOKENS, report=True)
    if batch.cancelled():
        raise _Stopped()
    import infra.stage_model_value as stage_model_value
    options = {'max_tokens': MAX_TOKENS}
    options.update(stage_model_value.reasoning_options(batch.project, batch.stage))
    result = batch.adapter.stream(messages, options=options, model=batch.chosen, system=batch.system,
                            on_chunk=lambda _chunk: None, cancelled=batch.cancelled)
    if result.get('ok'):
        record_circuit_success(batch.chosen)
    elif failure_policy(result).get('retryable'):
        record_circuit_failure(batch.chosen)
    if batch.cancelled() or result.get('error_class') == 'cancelled':
        raise _Stopped()
    if not result.get('ok'):
        policy = failure_policy(result)
        if policy.get('retryable'):
            from infra.model_metering import chat_metered
            from infra.model_router import PoolAdapter
            from infra.pet_llm import RequestLedger
            records = model_pool.pool(program=Path(__file__).resolve().parents[1])
            for candidate in batch.group_candidates:
                if candidate == batch.chosen:
                    continue
                if batch.cancelled():
                    raise _Stopped()
                record = records.get(candidate)
                if not record:
                    continue
                fallback_adapter = PoolAdapter(record, candidate, program=Path(__file__).resolve().parents[1],
                                               timeout=REQUEST_TIMEOUT)
                fallback = chat_metered(
                    fallback_adapter, RequestLedger(batch.project), batch.stage, messages,
                    options, candidate, batch.system)
                if batch.cancelled():
                    raise _Stopped()
                if fallback.get('ok'):
                    record_circuit_success(candidate)
                    finish = str((fallback.get('response_meta') or {}).get('finish_reason') or '')
                    if finish in model_pool.TASK_TRUNCATED:
                        raise _DirectError('模型回复被截断（超过输出上限），没有写入任何文件',
                                           code='E-CONTRACT-VIOLATION')
                    return str(fallback.get('text') or '')
                if failure_policy(fallback).get('retryable'):
                    record_circuit_failure(candidate)
        raise _DirectError('模型请求失败：' + str(result.get('error') or '未知原因'),
                           code=error_codes.from_http_result(result) or 'E-NET-CLIENT')
    if str((result.get('response_meta') or {}).get('finish_reason') or '') in model_pool.TASK_TRUNCATED:
        raise _DirectError('模型回复被截断（超过输出上限），没有写入任何文件', code='E-CONTRACT-VIOLATION')
    return str(result.get('text') or '')


def _validated(text, project, number, start, target_hint, source):
    data = _extract_json(text)
    data['source_script'] = _relative(project, source)
    problems = []
    if str(data.get('episode_id') or '') != 'EP%03d' % number:
        problems.append('episode_id 必须是 EP%03d' % number)
    shots = [shot for shot in data.get('shots', []) if isinstance(shot, dict)]
    if shots and _shot_number(shots[0]) != start:
        problems.append('第一个镜头编号必须是 SH%03d' % start)
    from contract.episode_contract import validate_episode
    try:
        validate_episode(data, target_hint)
    except ValueError as error:
        problems.append(str(error))
    if problems:
        raise ValueError('\n'.join(problems))
    return data


def _episode(batch, script, existing_board, request_text=''):
    from agent.core import read
    from infra.integrations import script_text
    from orchestrator.project_context_factory import project_context
    from domain.storyboard_catalog_service import document_dir, file_order, working_dir
    from domain.storyboard_storage import canonical_name
    project = batch.project
    context = project_context(project)
    number = file_order(script)[0]
    if number >= 10 ** 9:
        raise _DirectError('无法从文件名识别集号（需要 EPxxx 或 第N集）：' + Path(script).name,
                           code='E-FILE-NOT-FOUND')
    old = read(existing_board) if existing_board else None
    start = _first_shot_number(project, number, exclude=existing_board)
    hint = Path(existing_board) if existing_board else working_dir(context) / generate_existing('storyboard_hint', number=number)
    text = script_text(script)
    prior, data = None, None
    for attempt in range(1, MAX_FORMAT_RETRIES + 1):
        reply = _ask(batch, _messages(text, number, start, old, prior, request_text=request_text))
        try:
            data = _validated(reply, project, number, start, hint, script)
            break
        except ValueError as error:
            if attempt == MAX_FORMAT_RETRIES:
                raise _DirectError('两次回复都没有通过校验：' + str(error), code='E-CONTRACT-VIOLATION')
            prior = (reply, str(error))
            if batch.cancelled():
                raise _Stopped()
            time.sleep(FORMAT_RETRY_BASE_SECONDS * (2 ** (attempt - 1)))
    target = Path(existing_board) if existing_board else working_dir(context) / canonical_name(data)
    if not existing_board and target.exists():
        raise _DirectError('同名分镜已存在，不覆盖：' + target.name, code='E-IO-WRITE')
    document = document_dir(context) / (target.stem + '.md')
    artifacts = {target: json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'), document: _markdown(data)}
    history = target.parent / '历史版本' / ('EP%03d' % number)
    if existing_board:
        stamp = time.strftime('%Y%m%d_%H%M%S')
        artifacts[history / generate_existing('storyboard_history', stem=target.stem, stamp=stamp)] = Path(existing_board).read_bytes()
    import infra.file_cache as file_cache
    from orchestrator.stage_publication import publish_stage_bundle

    def allowed(_items):
        return not batch.cancelled() and (bool(existing_board) or not target.exists())
    publish_stage_bundle(artifacts, allowed, lambda: [file_cache.published(path) for path in artifacts],
                         origin='模型产出')
    if existing_board and history.is_dir():
        older = sorted(history.glob('*.json'), key=lambda p: p.name, reverse=True)[HISTORY_KEEP:]
        if older:
            from infra.storage_maintenance import recycle_paths
            recycle_paths(project, older, '分镜历史版本超过 %d 份' % HISTORY_KEEP)
    return target, data


class _Batch:
    """一批直连请求共用的服务：项目、适配器、模型、system 文本与取消探针。"""

    def __init__(self, project, config, skill_text, adapter=None, record=None, cancelled=None, profile=None):
        from orchestrator.workflow_tasks import storyboard_direct_rules
        stage, rules = profile or ('storyboard', storyboard_direct_rules())
        self.project = Path(project).resolve()
        self.chosen = str((config or {}).get('model') or '')
        self.stage = stage
        self.record = record
        self.cancelled = cancelled or (lambda: False)
        self.system = str(skill_text or '') + '\n\n' + rules
        if adapter is None:
            import infra.model_pool as model_pool
            from infra.model_router import PoolAdapter
            from infra.model_pool import model_admission_error, health_is_blocked
            from writing_api import WritingRequestAdapter
            self.record = record or direct_model(config)[1]
            problem = model_admission_error(
                self.record, require_context_length=True,
                require_certified=model_pool.require_certified(program=Path(__file__).resolve().parents[1]), stage=stage)
            if problem:
                raise _DirectError(problem, code='E-CONFIG-INVALID')
            if health_is_blocked(self.record, program=Path(__file__).resolve().parents[1]):
                raise _DirectError('该模型最近一次完整任务未通过，已暂停无人值守直连；请先重新做小样本验证。',
                                   code='E-CONFIG-INVALID')
            adapter = WritingRequestAdapter(PoolAdapter(self.record, self.chosen, program=Path(__file__).resolve().parents[1],
                                                        timeout=REQUEST_TIMEOUT), self.record, self.chosen,
                                            project=self.project, stage=stage)
        self.adapter = adapter
        import infra.model_pool as model_pool
        self.group_candidates = model_pool.group_candidates(
            (self.record or {}).get('group'), self.chosen, program=Path(__file__).resolve().parents[1])


def _jobs(batch, scripts, existing):
    from agent.core import read
    from orchestrator.project_context_factory import project_context
    from domain.storyboard_catalog_service import resolve_source
    context = project_context(batch.project)
    jobs = [(path, None) for path in scripts]
    for board in existing:
        data = read(board)
        source = resolve_source(context, (data or {}).get('source_script')) if isinstance(data, dict) else None
        jobs.append((source, board))
    return jobs


def run_batch(project, config, skill_text, *, scripts=(), existing=(), report=None, **services):
    """同步处理一批：每集一次请求。services 可给 adapter／record／cancelled／request_text。
    返回 [{'source','ok','path','error','stopped'}]；report(text) 播报每集结果。"""
    from orchestrator.workflow_tasks import storyboard_batch_plan
    report = report or (lambda _text: None)
    request_text = services.pop('request_text', '') or (config or {}).get('request_text', '')
    batch = _Batch(project, config, skill_text, **services)
    scripts, existing, _skipped = storyboard_batch_plan(batch.project, list(scripts), list(existing))
    results = []

    def record(entry):
        results.append(entry)
        business_log.log_event('storyboard_direct.episode', stage='storyboard',
                               outcome='ok' if entry['ok'] else 'failed')

    for source, board in _jobs(batch, scripts, existing):
        label = Path(board or source).name
        if batch.cancelled():
            record({'source': str(source), 'ok': False, 'stopped': True, 'path': '', 'error': '已停止', 'code': ''})
            continue
        try:
            if source is None or not Path(source).is_file():
                raise _DirectError('找不到这份分镜的来源剧本', code='E-FILE-NOT-FOUND')
            target, data = _episode(batch, source, board, request_text=request_text)
            record({'source': str(source), 'ok': True, 'path': str(target), 'error': '', 'stopped': False, 'code': ''})
            report('%s 分镜已生成：%s（%d 镜）' % (data.get('episode_id', ''), target.name, len(data.get('shots', []))))
        except _Stopped:
            record({'source': str(source), 'ok': False, 'stopped': True, 'path': '', 'error': '已停止', 'code': ''})
        except Exception as error:
            code, text = _failure(error, 'E-IO-WRITE' if isinstance(error, OSError) else 'E-UNKNOWN')
            logger.error('初步分镜直连失败 code=%s source=%s', code, label, exc_info=True)
            record({'source': str(source), 'ok': False, 'stopped': False, 'path': '', 'error': text, 'code': code})
            report('%s 的分镜没有生成：%s' % (label, text))
    return results


class Job:
    """后台任务：跑一批并登记取消句柄；结果在 results（I11 起经 infra.executors 调度）。"""

    thread_name = 'storyboard-direct'
    busy_text = '正在直连制作初步分镜，请等当前这批完成，或先点「强制停止制作」。'

    def __init__(self, project, config, skill_text, **kwargs):
        from contract.platform_tools import ExecutionControl
        self.project, self.config, self.skill_text, self.kwargs = Path(project).resolve(), config, skill_text, kwargs
        self.control = ExecutionControl(timeout=6 * 3600)
        self.results = []
        self.error = ''
        self.done = None
        self.name = self.thread_name
        self._future = None

    def cancel(self):
        self.control.cancel()

    def execute(self, **services):
        return run_batch(self.project, self.config, self.skill_text, **services, **self.kwargs)

    def start(self):
        if self._future is not None:
            raise RuntimeError('threads can only be started once')
        self._future = executors.submit('io', self.run, label=self.thread_name)
        return self._future

    def is_alive(self):
        return self._future is not None and not self._future.done()

    def join(self, timeout=None):
        """兼容 threading.Thread.join：等结束或超时；工作异常已由 run() 收进 self.error。"""
        if self._future is None:
            return
        try:
            self._future.result(timeout=timeout)
        except TimeoutError:
            return
        except Exception:
            app_logging.swallowed('storyboard-direct join 等待收尾')

    def run(self):
        from contract.platform_tools import execution_scope
        from infra.workflow_process_registry import forget_request
        try:
            with execution_scope(self.control):
                self.results = self.execute(cancelled=self.control.stopped.is_set)
        except Exception as error:
            code, self.error = _failure(error, 'E-CONFIG-INVALID')
            logger.error('初步分镜直连失败 code=%s source=%s', code, self.project.name, exc_info=True)
            business_log.log_event('storyboard_direct.episode', stage='storyboard', outcome='failed')
            self.results = [{'source': '', 'ok': False, 'stopped': False, 'path': '',
                             'error': self.error, 'code': code}]
        finally:
            forget_request(self.project, self)
            if callable(self.done):
                self.done(self)


def launch(project, config, skill_text, *, done=None, job_class=None, **kwargs):
    """启动后台直连作业；同一项目已有作业时拒绝（正在直连制作）。"""
    from infra.workflow_process_registry import register_request
    job = (job_class or Job)(project, config, skill_text, **kwargs)
    job.done = done
    if not register_request(job.project, job):
        raise ValueError(job.busy_text)
    job.start()
    return job


# ── 通用阶段文件直连 API 执行器（S02 剧本结构及各制作阶段：只按 SKILL 输出阶段文件，不对话）──
STAGE_FILE_ONLY_RULES = (
    '【直连文件输出模式】你是漫剧制作阶段的文件生成与修订引擎，不需要对话。'
    '请严格遵循上方 SKILL 规范和用户要求，只直接输出本阶段目标文件的完整正文内容：\n'
    '1. 严禁输出任何开场白、寒暄、修改说明、步骤解释或追问；\n'
    '2. 不要在整篇内容最外层包裹多余的 Markdown 代码围栏（如 ```markdown ... ```）；\n'
    '3. 若提供了本阶段已有文件，请在其基础上按用户要求修订并输出完整的新版正文；\n'
    '4. 你的回复全文将直接保存为本阶段成果文件。'
)
_STAGE_FILE_CONTEXT_CAP = 36000
_STAGE_TEXT_SUFFIXES = frozenset({'.md', '.txt', '.json', '.srt', '.ass', '.csv', '.yaml', '.yml'})
_STAGE_DEFAULT_FILENAMES = {
    'script_structure': '结构剧本.md',
    'animatic': '分镜预演方案.md',
    'assets': '资产制作清单.md',
    'continuity': '连贯性清单.md',
    'final': '分镜定稿修订.md',
    'keyframe': '首帧提示词方案.md',
    'previs': '白模预演方案.md',
    'video': '视频提示词方案.md',
    'audio': '配音与字幕稿.md',
    'edit': '后期剪辑方案.md',
    'delivery': '质检与交付报告.md',
}


def strip_outer_code_fence(text):
    """去掉模型偶然包在整篇正文最外层的单一代码围栏，保留正文内部代码块。"""
    cleaned = str(text or '').strip()
    match = re.match(r'^```[A-Za-z0-9_-]*\r?\n([\s\S]*?)\r?\n```\s*$', cleaned)
    return match.group(1).strip() if match else cleaned


def _read_context_file(path, limit=_STAGE_FILE_CONTEXT_CAP):
    try:
        raw = Path(path).read_text(encoding='utf-8-sig', errors='replace').strip()
    except OSError:
        return ''
    return raw[:limit]


def _latest_stage_text_file(project, stage):
    from contract.stage_path_service import read_dirs
    best = None
    best_mtime = -1.0
    for folder in read_dirs(project, stage):
        if not folder.is_dir():
            continue
        for entry in folder.rglob('*'):
            if (not entry.is_file() or entry.suffix.lower() not in _STAGE_TEXT_SUFFIXES
                    or '历史版本' in entry.parts or entry.name.startswith('.')):
                continue
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                continue
            if mtime > best_mtime:
                best, best_mtime = entry, mtime
    return best


def collect_stage_file_context(project, stage, *, active_path=None):
    """收集本阶段模型执行所需的输入上下文（来源原稿 + 本阶段当前文件），不涉及对话历史。"""
    from contract import pet_bus, script_contract
    root = Path(project).resolve()
    blocks = []
    source_path = None
    seen = set()

    def add_block(label, path):
        if path is None:
            return
        resolved = Path(path).resolve()
        if resolved in seen or not resolved.is_file():
            return
        body = _read_context_file(resolved)
        if not body:
            return
        seen.add(resolved)
        blocks.append('<%s path="%s">\n%s\n</%s>' % (label, _relative(root, resolved), body, label))

    if stage == 'script_structure':
        source_path = script_contract.resolve_script_source(root) or _latest_stage_text_file(root, 'script')
        add_block('自然剧本原稿', source_path)
        existing_list = script_contract.structured_script_paths(root)
        current_struct = existing_list[0] if existing_list else None
        if active_path and Path(active_path).is_file():
            add_block('当前编辑器文档', active_path)
        add_block('现有结构剧本', current_struct)
    else:
        if active_path and Path(active_path).is_file():
            add_block('当前阶段文件', active_path)
        own = _latest_stage_text_file(root, stage)
        add_block('本阶段最新文件', own)
        if stage in pet_bus.STAGES:
            idx = pet_bus.STAGES.index(stage)
            if idx > 0:
                upstream = pet_bus.STAGES[idx - 1]
                up_file = _latest_stage_text_file(root, upstream)
                add_block('上游阶段参考文件', up_file)
                source_path = up_file
    return '\n\n'.join(blocks), source_path


def publish_stage_file_output(project, stage, content, *, model_name='', source_path=None,
                              active_path=None, cancelled=None):
    """把模型输出的纯阶段文件正文原子发布到本阶段目录，并同步项目文件索引。"""
    from contract import script_contract
    from contract.stage_path_service import write_dir
    from infra import file_cache, file_index
    from orchestrator.stage_publication import publish_stage_bundle

    root = Path(project).resolve()
    cleaned = strip_outer_code_fence(content)
    if not cleaned:
        raise _DirectError('模型未返回有效的文件正文内容', code='E-CONTRACT-VIOLATION')
    if callable(cancelled) and cancelled():
        raise _Stopped()

    if stage == 'script_structure':
        source = source_path or script_contract.resolve_script_source(root)
        if source is not None and Path(source).is_file():
            def supersede(paths):
                from infra.storage_maintenance import recycle_paths
                recycle_paths(root, list(paths), 'API 重新生成同源结构剧本，回收旧份')
            target = script_contract.write_structured_script(
                root, cleaned + '\n', source=source, vendor=model_name or 'API', supersede=supersede)
            file_index.update(root, [target])
            return target
        target = write_dir(root, 'script_structure') / _STAGE_DEFAULT_FILENAMES['script_structure']
        artifacts = {target: (cleaned + '\n').encode('utf-8')}
        if target.is_file():
            history = target.parent / '历史版本' / ('%s_%s%s' % (target.stem, time.strftime('%Y%m%d_%H%M%S'), target.suffix))
            artifacts[history] = target.read_bytes()
        publish_stage_bundle(artifacts, lambda _items: not (callable(cancelled) and cancelled()),
                             lambda: [file_cache.published(path) for path in artifacts], origin='模型产出')
        script_contract.write_structure_manifests(root, cleaned)
        file_index.update(root, [target])
        return target

    stage_dir = write_dir(root, stage).resolve()
    target = None
    if active_path is not None:
        candidate = Path(active_path).resolve()
        if candidate.is_file() and candidate.is_relative_to(stage_dir) and candidate.suffix.lower() in ('.md', '.txt'):
            target = candidate
    if target is None:
        target = stage_dir / _STAGE_DEFAULT_FILENAMES.get(stage, '%s_成果.md' % stage)
    artifacts = {target: (cleaned + '\n').encode('utf-8')}
    if target.is_file():
        history = target.parent / '历史版本' / ('%s_%s%s' % (target.stem, time.strftime('%Y%m%d_%H%M%S'), target.suffix))
        artifacts[history] = target.read_bytes()
    publish_stage_bundle(artifacts, lambda _items: not (callable(cancelled) and cancelled()),
                         lambda: [file_cache.published(path) for path in artifacts], origin='模型产出')
    file_index.update(root, [target])
    return target


def run_stage_file_batch(project, stage, config, skill_text, *, instruction='', report=None, **services):
    """通用阶段直连 API 文件生成：单次请求只输出阶段文件正文并原子落盘，不做聊天对话。"""
    from contract import pet_bus
    report = report or (lambda _text: None)
    active_path = services.pop('active_path', None)
    stage_label = pet_bus.stage_name(stage)
    batch = _Batch(project, config, skill_text, profile=(stage, STAGE_FILE_ONLY_RULES), **services)
    try:
        if batch.cancelled():
            raise _Stopped()
        context_text, source_path = collect_stage_file_context(project, stage, active_path=active_path)
        task = str(instruction or '').strip() or ('请按本阶段 SKILL 规范生成或完善「%s」阶段文件。' % stage_label)
        parts = ['目标阶段：%s' % stage_label, '用户要求：%s' % task]
        if context_text:
            parts.append('当前项目材料：\n' + context_text)
        messages = [{'role': 'user', 'content': '\n\n'.join(parts)}]
        reply = _ask(batch, messages)
        target = publish_stage_file_output(
            project, stage, reply, model_name=batch.chosen,
            source_path=source_path, active_path=active_path, cancelled=batch.cancelled)
        report('「%s」阶段文件已输出：%s' % (stage_label, target.name))
        business_log.log_event('stage_file_direct.done', stage=stage, outcome='ok')
        return {'ok': True, 'stage': stage, 'path': str(target), 'error': '', 'stopped': False, 'code': ''}
    except _Stopped:
        return {'ok': False, 'stage': stage, 'path': '', 'error': '已停止', 'stopped': True, 'code': ''}
    except Exception as error:
        code, text = _failure(error, 'E-IO-WRITE' if isinstance(error, OSError) else 'E-UNKNOWN')
        logger.error('阶段文件直连失败 stage=%s code=%s', stage, code, exc_info=True)
        business_log.log_event('stage_file_direct.done', stage=stage, outcome='failed')
        report('「%s」文件未生成：%s' % (stage_label, text))
        return {'ok': False, 'stage': stage, 'path': '', 'error': text, 'stopped': False, 'code': code}


class StageFileJob(Job):
    thread_name = 'stage-file-direct'
    busy_text = '当前已有直连制作任务在运行，请等本轮完成再发送。'

    def execute(self, **services):
        kwargs = dict(self.kwargs)
        stage = kwargs.pop('stage')
        return [run_stage_file_batch(self.project, stage, self.config, self.skill_text, **services, **kwargs)]


def launch_stage_file(project, stage, config, skill_text, *, done=None, **kwargs):
    """启动通用阶段文件直连 API 后台作业（只输出文件，不对话）。"""
    return launch(project, config, skill_text, done=done, job_class=StageFileJob, stage=stage, **kwargs)
