# -*- coding: utf-8 -*-
"""任务书 M6：离线语音包下载的宿主侧控制器（L2，标准库＋``contract.platform_tools``）。

下载链＝``voice_engine/bootstrap.py`` 建独立 venv 并装依赖 → venv 解释器跑
``python -m voice_engine.download_models`` 下模型（modelscope 自带分块校验与断点
续传，已下载分块不重来）。两阶段都以 JSON Lines 往 stdout 打进度；本模块在后台
线程拉起并逐行转发事件，UI 线程只做 ``after`` 消费，不阻塞。

取消／失败的半成品处理：模型分块由 modelscope 原子落盘（校验失败不留坏文件）；
venv 侧只在「连解释器都没生成」时整目录清掉，已建好的 venv 与模型缓存原样留下
——下次点「下载」从断点继续。
"""
import os
import json
import subprocess
import sys
import threading
from json import loads as _loads
from pathlib import Path

import contract.platform_tools as platform_tools
import infra.storage_maintenance as storage_maintenance
from domain.offline_asr_client import VENV_DIR, venv_python

PROGRAM = Path(__file__).resolve().parents[1]
BOOTSTRAP = PROGRAM / 'voice_engine' / 'bootstrap.py'
MODELS_DIR = PROGRAM / 'data' / 'voice_models'
PROBE_TIMEOUT = 25
MIN_PYTHON = (3, 10)
MAX_PYTHON = (3, 12)          # 与 bootstrap.py 同口径：依赖无更高版本预编译轮子
MODEL_LOCK = PROGRAM / 'voice_engine' / 'models.lock.json'
MODEL_ENV = {'asr': 'FUNASR_ASR_MODEL', 'vad': 'FUNASR_VAD_MODEL',
             'punc': 'FUNASR_PUNC_MODEL'}


def base_candidates(settings=None):
    """基座解释器候选（argv 前缀列表）：环境变量 > 显式设置 > py 启动器 > PATH。"""
    out = []
    env_exe = str(os.environ.get('VOICE_ASR_PYTHON') or '').strip()
    if env_exe:
        out.append([env_exe])
    offline = (settings or {}).get('offline') or {}
    explicit = str(offline.get('python') or '').strip()
    if explicit:
        out.append([explicit])
    if os.name == 'nt':
        out += [['py', '-3.12'], ['py', '-3.11'], ['py', '-3.10']]
    out += [['python3.12'], ['python3.11'], ['python3.10'], ['python3'], ['python']]
    return out


def _probe(argv_prefix):
    """跑 ``<prefix> -c`` 拿真实解释器路径与版本；不合格或失败返回 None。"""
    command = list(argv_prefix) + [
        '-c', 'import sys;print(sys.executable);print("%d.%d" % sys.version_info[:2])']
    try:
        proc = platform_tools.run_process(command, capture_output=True, timeout=PROBE_TIMEOUT,
                                          encoding='utf-8', errors='replace')
    except Exception:  # noqa: BLE001 —— 候选不存在属预期
        return None
    if proc.returncode != 0:
        return None
    lines = (proc.stdout or '').strip().splitlines()
    if len(lines) < 2:
        return None
    exe, version = lines[-2].strip(), lines[-1].strip()
    try:
        major, minor = (int(part) for part in version.split('.')[:2])
    except ValueError:
        return None
    if major != 3 or not (MIN_PYTHON[1] <= minor <= MAX_PYTHON[1]):
        return None
    if not Path(exe).is_file():
        return None
    return exe


def resolve_base_python(settings=None, probe=None):
    """第一个 3.10–3.12 的可用基座解释器真实路径；找不到返回 None。"""
    probe = probe or _probe
    for candidate in base_candidates(settings):
        exe = probe(candidate)
        if exe:
            return exe
    return None


def environment_ready(settings=None):
    """离线语音包是否已就绪：venv 解释器在且至少一个模型目录有 onnx。"""
    if not venv_python(VENV_DIR).is_file():
        return False
    return models_ready(settings)


def models_ready(settings=None):
    """锁定的 ASR/VAD/标点三个模型均有 ONNX 文件才算可用。"""
    cache = Path(_cache_root(settings))
    try:
        model_names = _configured_models()
    except (OSError, ValueError, KeyError, TypeError):
        return False
    for name in model_names.values():
        parts = name.split('/', 1)
        if len(parts) != 2:
            return False
        model_dir = cache / 'hub' / 'models' / parts[0] / parts[1]
        if not ((model_dir / 'model_quant.onnx').is_file()
                or (model_dir / 'model.onnx').is_file()):
            return False
    return True


def _configured_models():
    data = json.loads(MODEL_LOCK.read_text(encoding='utf-8'))
    locked = data['models']
    return {kind: os.environ.get(MODEL_ENV[kind]) or locked[kind]
            for kind in ('asr', 'vad', 'punc')}


def _cache_root(settings=None):
    """模型缓存根：设置里的 offline.cache_dir 优先，否则 ``data/voice_models``。"""
    offline = (settings or {}).get('offline') or {}
    explicit = str(offline.get('cache_dir') or '').strip()
    return explicit or str(MODELS_DIR)


def cleanup_incomplete_venv(venv_dir=VENV_DIR):
    """清「没建完整」的半成品：目录在但解释器缺失才收进回收站；已建好的 venv 留下续跑。"""
    venv_dir = Path(venv_dir)
    if venv_dir.is_dir() and not venv_python(venv_dir).is_file():
        storage_maintenance.recycle_paths(venv_dir.parent, [venv_dir], '离线语音包半成品清理')
        return True
    return False


class OfflineSetupRunner:
    """两阶段下载的后台控制器：``on_event`` 收 ``progress|done|error|cancelled``。

    ``launcher`` 默认 ``platform_tools.launch_text_process``（已登记的后台进程边界），
    测试注入假进程验证命令与事件流；``probe`` 同理注入基座探测。
    """

    def __init__(self, settings=None, on_event=None, *, launcher=None, probe=None):
        self._settings = settings or {}
        self._on_event = on_event or (lambda event: None)
        self._launcher = launcher or platform_tools.launch_text_process
        self._probe = probe or _probe
        self._lock = threading.Lock()
        self._proc = None
        self._cancelled = False
        self._thread = None

    def start(self):
        """后台启动下载链；已有任务在跑返回 False（按钮态由 UI 防重点）。"""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._cancelled = False
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            return True

    def cancel(self):
        """取消：杀掉当前阶段子进程；模型分块由 modelscope 续传，venv 半成品收尾清理。"""
        with self._lock:
            self._cancelled = True
            proc = self._proc
        if proc is not None:
            try:
                proc.kill()
            except OSError:
                pass

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def _notify(self, event):
        try:
            self._on_event(event)
        except Exception:  # noqa: BLE001 —— 界面回调失败不拖垮下载线程
            import infra.app_logging as app_logging
            app_logging.swallowed()

    def _is_cancelled(self):
        with self._lock:
            return self._cancelled

    def _run(self):
        try:
            base = resolve_base_python(self._settings, probe=self._probe)
            if base is None:
                self._notify({'type': 'error', 'message':
                            '需要 Python %s–%s 才能安装离线语音包：请安装后重试，'
                            '或改用云端识别（模型管理里配置语音密钥）'
                            % ('.'.join(map(str, MIN_PYTHON)), '.'.join(map(str, MAX_PYTHON)))})
                return
            stages = [
                ('venv', '离线语音环境', [sys.executable, str(BOOTSTRAP),
                                       '--python', base, '--venv', str(VENV_DIR)]),
                ('models', '离线语音模型', [str(venv_python(VENV_DIR)),
                                          '-m', 'voice_engine.download_models',
                                          '--cache', _cache_root(self._settings)]),
            ]
            completed = True
            for stage, label, command in stages:
                if self._is_cancelled():
                    break
                if not self._phase(stage, label, command):
                    completed = False
                    break
            if self._is_cancelled():
                cleanup_incomplete_venv(VENV_DIR)
                self._notify({'type': 'cancelled', 'message': '已取消下载；已下载部分保留，下次继续'})
                return
            if not completed:
                return                      # 失败原因已由 _phase 给出
            if not models_ready(self._settings):
                self._notify({'type': 'error', 'message':
                            '模型下载未完整（校验未通过或被中断），请重试；已下载部分会自动续传'})
                return
            self._notify({'type': 'done', 'message': '离线语音包安装完成'})
        except Exception as exc:  # noqa: BLE001 —— 绝不把异常穿透到界面线程
            cleanup_incomplete_venv(VENV_DIR)
            self._notify({'type': 'error', 'message': '离线语音包安装失败：%s' % exc})

    def _phase(self, stage, label, command):
        """跑一个阶段子进程并转发 JSON Lines 进度；返回是否进入下一阶段。"""
        env = dict(os.environ)
        cache = _cache_root(self._settings)
        env['VOICE_ASR_MODEL_CACHE'] = cache
        self._notify({'type': 'progress', 'stage': stage,
                    'message': '正在安装%s…' % label})
        try:
            proc = self._launcher(command, cwd=str(PROGRAM),
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
        except OSError as exc:
            self._notify({'type': 'error', 'message': '无法启动安装进程：%s' % exc})
            return False
        with self._lock:
            self._proc = proc
        failure = ''
        try:
            for line in proc.stdout or ():
                if self._is_cancelled():
                    return False
                message = self._translate(stage, line, label)
                if message is not None:
                    self._notify(message)
                    if message['type'] == 'error':
                        failure = message['message']
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                platform_tools.terminate_process_tree(proc)
                proc.wait(timeout=3)
        finally:
            with self._lock:
                self._proc = None
        if failure or proc.returncode not in (0, None):
            if not failure:
                self._notify({'type': 'error', 'message':
                            '%s安装中断（退出码 %s），请重试；已完成部分会自动续传'
                            % (label, proc.returncode)})
            if stage == 'venv':
                cleanup_incomplete_venv(VENV_DIR)
            return False
        return True

    def _translate(self, stage, line, label):
        """bootstrap／download_models 的 JSON Lines → 统一事件；坏行当普通进度。"""
        text = (line or '').strip()
        if not text:
            return None
        try:
            obj = _loads(text)
        except ValueError:
            return {'type': 'progress', 'stage': stage,
                    'message': '%s：%s' % (label, text[:160])}
        kind = obj.get('type')
        if kind == 'done':
            return None                      # 阶段结束由 returncode 判定
        if kind == 'error':
            return {'type': 'error', 'stage': stage,
                    'message': obj.get('message') or '%s安装失败' % label}
        model = obj.get('model')
        note = ('（%s）' % model) if model else ''
        return {'type': 'progress', 'stage': stage,
                'message': '%s%s：%s' % (label, note,
                                         obj.get('message') or obj.get('stage') or '进行中…')}
