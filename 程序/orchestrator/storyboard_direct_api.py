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


def _messages(script_text, number, start, existing=None, prior=None):
    code = 'EP%03d' % number
    head = ('请为下面这一集制作分镜。集号：%s，episode_id 必须是 %s；镜头编号从 SH%03d 起连续编号。'
            '只回复一个 JSON 对象，不要任何解释，不要 Markdown 围栏。' % (code, code, start))
    if existing is not None:
        head += '这一集已有分镜，请在它的基础上修订并返回完整的新版 JSON：\n<已有分镜>\n%s\n</已有分镜>\n' % (
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


def _episode(batch, script, existing_board):
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
        reply = _ask(batch, _messages(text, number, start, old, prior))
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
    """同步处理一批：每集一次请求。services 可给 adapter／record／cancelled。
    返回 [{'source','ok','path','error','stopped'}]；report(text) 播报每集结果。"""
    from orchestrator.workflow_tasks import storyboard_batch_plan
    report = report or (lambda _text: None)
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
            target, data = _episode(batch, source, board)
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
