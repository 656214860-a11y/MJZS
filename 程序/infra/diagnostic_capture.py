"""程序级可导出的脱敏诊断采集。

这里只处理程序拥有的 ``logs/``；不遍历项目目录，也不读取私有配置。所有落盘经
``agent.core`` 原子发布，导出时仅打包白名单文件并逐行剔除凭据。

轮 3B（任务书 D3-g～D3-m）：本模块同时是启动自检的 L1 检查组装点与崩溃预算
账本——账本并入本文件的 ``latest.json`` 状态（G6，不新建 ``startup_ledger.json``）。
乙类检查只碰固定路径与单文件直读，零递归扫描（规则 33）、不读用户项目。
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import tempfile
import traceback
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import infra.app_logging as app_logging
from infra import config_snapshot, diagnostic_state
from agent.core import read_json, save_bytes, save_text
from infra.log_maintenance import RETENTION_DAYS


PROGRAM = Path(__file__).resolve().parents[1]
LOGS = PROGRAM / "logs"
ERROR_LOG = LOGS / "启动错误.log"
STATE_FILE = diagnostic_state.STATE_FILE
SUPPRESS_DIAGNOSTICS_ENV = diagnostic_state.SUPPRESS_DIAGNOSTICS_ENV
_SECRET = app_logging._SECRET
_PRIVATE_NAME = re.compile(r"(?i)(?:\.env$|\.dpapi$|private|credential|secret)")
_LOCK = diagnostic_state.STATE_LOCK


def redact(value: object) -> str:
    """给别的模块共用的脱敏入口：同样的规则，同样的替换词。"""
    return _clean(value)

def _state() -> dict:
    return diagnostic_state.read_state(STATE_FILE)


def _save_state(value: dict) -> None:
    diagnostic_state.save_state(STATE_FILE, value)


def flush_artifact_states() -> None:
    """把 ``artifact_schema`` 的读取分类计数并入 ``latest.json``（导出前调用）。

    计数由各属主读取点记入 ``artifact_schema`` 内存；这里只负责落盘收走，
    任何一步失败都静默，不影响诊断主流程。
    """
    rows = diagnostic_state.artifact_state_rows()
    if not rows:
        return
    with _LOCK:
        try:
            state = _state()
            if state.get("artifact_versions") == rows:
                return
            state["artifact_versions"] = rows
            _save_state(state)
        except Exception:
            app_logging.swallowed()


def _clean(value: object) -> str:
    return app_logging.redact(value)


def record_degradation(exc: BaseException, *, page: str = "", stage: str = "",
                       project: str = "", automatic_daily_open: bool = False,
                       error_code: str = "") -> None:
    """记录一次已降级异常；调用方仍保持原有容错/返回语义。``error_code`` 用 L0 码表已有码（如 E-IO-WRITE）。"""
    diagnostic_state.record_degradation(
        exc, page=page, stage=stage, project=project, automatic_daily_open=automatic_daily_open,
        error_code=error_code, state_file=STATE_FILE,
    )


def record_startup_timing(name: str, elapsed_ms: float) -> None:
    """启动阶段仅记耗时，不触碰目录扫描或项目内容。"""
    with _LOCK:
        state = _state()
        timings = dict(state.get("startup_timings") or {})
        timings[str(name)] = round(float(elapsed_ms), 2)
        state["startup_timings"] = timings
        _save_state(state)


def record_gate_result(name: str, result: str) -> None:
    with _LOCK:
        state = _state()
        state["last_gate"] = {"name": _clean(name), "result": _clean(result),
                              "at": datetime.now().isoformat(timespec="seconds")}
        _save_state(state)


def record_temporary_sweep(removed: int, remaining: int) -> None:
    """轮 2 清扫线程写回最近一次结果；启动自检的遗留临时文件项只读这里，不现场扫目录。"""
    with _LOCK:
        state = _state()
        state["temporary_sweep"] = {"removed": int(removed), "remaining": int(remaining),
                                    "at": datetime.now().isoformat(timespec="seconds")}
        _save_state(state)


def record_crash(exc: BaseException, trace=None) -> None:
    """追加到既有启动错误日志，不另建崩溃日志。"""
    with _LOCK:
        previous = ERROR_LOG.read_text(encoding="utf-8", errors="replace") if ERROR_LOG.exists() else ""
        detail = "".join(traceback.format_exception(type(exc), exc, trace or exc.__traceback__))
        save_text(ERROR_LOG, previous + "\n[diagnostics] " + _clean(detail) + "\n")


def export_candidates() -> tuple[Path, ...]:
    """固定白名单，避免在启动或导出时递归枚举日志目录。"""
    return tuple(path for path in (ERROR_LOG, LOGS / "sanhu_progress.log", STATE_FILE) if path.is_file())


def preview() -> tuple[str, ...]:
    return tuple(str(path) for path in export_candidates())


def retention_note() -> str:
    """把保留期限说清楚：程序日志按 log_maintenance 的政策保留这么多天。"""
    return "程序日志保留 %d 天（按 log_maintenance 政策）；导出只含下面白名单文件，不含项目与密钥。" % RETENTION_DAYS


def preview_detail() -> tuple[dict, ...]:
    """诊断预览：白名单文件 ＋ 大小／修改时间／保留期限；只看不动文件。"""
    now = datetime.now()
    rows = []
    for path in export_candidates():
        try:
            stat = path.stat()
        except OSError:
            continue
        modified = datetime.fromtimestamp(stat.st_mtime)
        expires = modified + timedelta(days=RETENTION_DAYS)
        rows.append({"name": path.name, "path": str(path), "bytes": stat.st_size,
                     "modified": modified.isoformat(timespec="seconds"),
                     "keep_days": RETENTION_DAYS,
                     "expires_at": expires.isoformat(timespec="seconds"),
                     "expired": expires <= now})
    return tuple(rows)

def _safe_member(path: Path) -> str:
    if _PRIVATE_NAME.search(path.name):
        raise ValueError("诊断包包含受保护文件，已拒绝导出：" + path.name)
    return "logs/" + path.name if path.parent == LOGS else "logs/diagnostics/" + path.name


def export(destination: str | Path) -> Path:
    """把脱敏后的白名单日志写成单个 ZIP；任一受保护项立即拒绝。"""
    flush_artifact_states()      # 先把产物版本分类计数并进 latest.json 再打包
    bundle = io.BytesIO()
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        manifest = []
        for source in export_candidates():
            member = _safe_member(source)
            text = source.read_text(encoding="utf-8", errors="replace")
            cleaned = "\n".join(_clean(line) for line in text.splitlines())
            if _SECRET.search(cleaned):
                raise ValueError("诊断包仍含凭据形态，已拒绝导出。")
            archive.writestr(member, cleaned)
            manifest.append(member)
        archive.writestr("manifest.json", json.dumps({"included": manifest, "secret_policy": "redacted"}, ensure_ascii=False))
    output = Path(destination)
    if output.suffix.lower() != ".zip":
        output = output.with_suffix(".zip")
    save_bytes(output, bundle.getvalue())
    return output



# ---- 轮 3B：启动自检组装与崩溃预算（任务书 D3-g～D3-m，决策 G3/G4/G6/G12、H1/H2）----
#
# 分层：L0 ``contract.selfcheck.run`` 只收可调用对象；甲类两项由
# ``selfcheck.default_checks()`` 提供，乙类六项由本模块 ``startup_checks()``
# 组装（L1 检查注入 L0 运行器，G3）。启动器（.pyw／desktop_launcher）在建 Tk
# 之前调 ``run_startup_selfcheck`` 一次；FATAL → MessageBoxW 后退出，
# 其余暂存到 ``window._selfcheck_degraded``，主窗口状态栏播报（H2）。

FORGIVE_MINUTES = 5      # 仿 Chromium kForgiveGpuCrashMinutes（附 3b-2）
CRASH_LIMIT = 3          # 仿 Chromium Windows 分支 GetFallbackCrashLimit
_GUARD_KEY = 'startup_guard'
_SELFTEST_FLAG = 'selfcheck_failopen.flag'   # G12：data/ 下存在即甲类全部降级放行
_DISK_MIN_FREE_MB = 500                     # H1：只查 程序\\data 所在盘
_BUNDLED_TOOLS = ('ffmpeg', 'ffprobe')
_LOCKED_REQUIREMENTS = 'requirements.txt'
_DEP_LINE = re.compile(r'([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.!+_-]*)')
# Win32 MessageBox 按钮（仅本文件内使用，避免 import ctypes 常驻）
_MB_ICONSTOP = 0x10
_MB_ICONWARNING = 0x30
_MB_YESNO = 0x4
_IDYES = 6


def _degraded(scope, code, message, remedy=''):
    from contract.diagnostics import Diagnostic, Severity, StartupPhase
    value = getattr(scope, 'value', scope)      # StartupPhase.CONFIG → 'config'；'CONFIG' → 'config'
    if isinstance(value, str) and value in StartupPhase.__members__:
        value = StartupPhase[value].value
    return Diagnostic(severity=Severity.DEGRADED, scope=str(value), code=code,
                      message=message, remedy=remedy)


# ---------- 乙类检查项（D3-g；各返回 Diagnostic 或 None；只读固定路径、零递归） ----------

def _check_data_writable(root):
    """乙类：``data``／``logs`` 目录必须可写（建目录＋临时文件写删探针）。

    探针用 ``tempfile.TemporaryFile``：关闭时由系统回收，不在本模块留删除调用
    （物理删除只允许生命周期／file_cache／tempfile 自有清理，删除权威门禁）。
    """
    from contract.diagnostics import StartupPhase
    problems = []
    for name in ('data', 'logs'):
        path = Path(root) / name
        try:
            path.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryFile(dir=str(path)) as probe:
                probe.write(b'x')
                probe.flush()
        except OSError as exc:
            problems.append('%s（%s）' % (name, exc))
    if problems:
        return _degraded(StartupPhase.RESOURCE, 'data-logs-writable',
                         '程序数据目录不可写：' + '；'.join(problems),
                         '检查目录权限、磁盘状态或安全软件占用后重启')
    return None


def _check_disk_space(root):
    """乙类（H1）：只查 ``程序\\data`` 所在盘，剩余 <500MB 报 DEGRADED；不查用户项目盘。"""
    from contract.diagnostics import StartupPhase
    try:
        target = Path(root) / 'data'
        if not target.is_dir():
            target = Path(root)
        free_mb = shutil.disk_usage(target).free / 1048576.0
    except OSError:
        return None                       # 量不出来不算发现：交给可写性检查兜底
    if free_mb < _DISK_MIN_FREE_MB:
        return _degraded(StartupPhase.RESOURCE, 'disk-space-low',
                         '程序数据盘剩余空间约 %d MB，低于 %d MB 下限'
                         % (int(free_mb), _DISK_MIN_FREE_MB),
                         '清理磁盘空间后重启；空间不足会导致配置与日志写入失败')
    return None


def _check_model_pool(root):
    """空池报告 Q7，读取异常由自检运行器记录为降级。"""
    from contract.diagnostics import StartupPhase
    if config_snapshot.has_stored_models(root):
        return None
    return _degraded(StartupPhase.CONFIG, 'model-pool-empty',
                     '模型池为空：还没有配置任何模型，制作阶段会缺模型可用',
                     '登录后在「模型管理」里「+ 新增模型…」并保存 API Key')


def _check_bundled_tools(root):
    """乙类（Q7）：随包 FFmpeg／FFprobe 缺失 → DEGRADED（复用 ``platform_tools.tool_path``）。

    ``tool_path`` 自带「显式配置 > 随包 > 系统 PATH」解析；程序级没有
    ffmpeg 配置项（配置在项目 config.json），这里只按默认解析判可用性。
    """
    from contract.diagnostics import StartupPhase
    from contract import platform_tools
    missing = []
    for name in _BUNDLED_TOOLS:
        try:
            found = platform_tools.tool_path(name)
        except Exception:
            found = None
        if not found:
            missing.append(name)
    if missing:
        return _degraded(StartupPhase.RESOURCE, 'bundled-tools-missing',
                         '媒体工具缺失：' + '、'.join(missing) + '（随包与系统 PATH 均未找到）',
                         '成片合成与质检依赖 FFmpeg/FFprobe；请重装程序，'
                         '或在项目 config.json 配置「ffmpeg」「ffprobe」可执行文件路径')
    return None


def _canon_dist_name(name):
    return re.sub(r'[-_.]+', '-', str(name).strip()).lower()


def _parse_dependency_lock(text):
    """解析 requirements.txt 为 {规范名: 版本}；遇无法解析的非空行返回 None。

    与 ``tests/architecture/test_dependency_whitelist.parse_production_lock``
    同口径（包名==精确版本、忽略注释），但把「锁文件损坏」表达成返回值而非异常。
    """
    locked = {}
    for raw in str(text).splitlines():
        line = raw.partition('#')[0].strip()
        if not line:
            continue
        match = _DEP_LINE.fullmatch(line)
        if not match:
            return None
        name = _canon_dist_name(match.group(1))
        if name in locked:
            return None
        locked[name] = match.group(2)
    return locked


def _installed_distributions():
    """当前解释器 purelib 内第三方 distribution：{规范名: 版本}。

    只列目录名解析 ``*.dist-info``（目录名即「名-版本」，规范名里的 - 归一为 _），
    一次扁平 ``os.listdir`` 枚举、不读 METADATA；刻意不走 ``importlib.metadata``
    ——其首次导入约 40ms，会吃掉自检的 50ms 预算。权威核对仍是架构门禁测试。
    """
    import sysconfig
    try:
        purelib = Path(sysconfig.get_paths()['purelib'])
        names = os.listdir(purelib)
    except (OSError, KeyError):
        return {}
    found = {}
    for entry in names:
        if not entry.endswith('.dist-info'):
            continue
        name, sep, version = entry[:-10].rpartition('-')
        if sep and name and version:
            found[_canon_dist_name(name)] = version
    return found


def _check_dependency_lock(root):
    """乙类（Q7，R0-d 存在时做）：requirements.txt 锁定的生产包在 purelib 缺失或版本不符 → DEGRADED。

    分发副本不带 requirements.txt 时本项不适用（返回 None）；锁文件损坏单独报
    ``dependency-lock-invalid``，同样是 DEGRADED 不升级。
    """
    from contract.diagnostics import StartupPhase
    lock = Path(root) / _LOCKED_REQUIREMENTS
    try:
        text = lock.read_text(encoding='utf-8')
    except OSError:
        return None
    expected = _parse_dependency_lock(text)
    if expected is None:
        return _degraded(StartupPhase.RESOURCE, 'dependency-lock-invalid',
                         'requirements.txt 依赖锁格式异常，无法核对生产依赖',
                         '请用官方安装包重装，或把 requirements.txt 恢复为「包名==精确版本」逐行格式')
    if not expected:
        return None
    installed = _installed_distributions()
    missing = sorted(name for name in expected if name not in installed)
    mismatched = sorted('%s（实得 %s，锁定 %s）' % (name, installed[name], expected[name])
                        for name in expected
                        if name in installed and installed[name] != expected[name])
    if missing or mismatched:
        detail = []
        if missing:
            detail.append('缺少：' + '、'.join(missing))
        if mismatched:
            detail.append('版本不符：' + '；'.join(mismatched))
        return _degraded(StartupPhase.RESOURCE, 'dependency-lock-mismatch',
                         '生产依赖与白名单锁不符（' + '；'.join(detail) + '）',
                         '请用官方安装包重装程序，恢复 requirements.txt 锁定的运行环境')
    return None


def _check_settings_corrupt(root):
    """乙类（G11/§5.3）：desktop_settings.json 损坏或曾回落 → DEGRADED，永不升级。

    两个信号任一即报：① 文件此刻读不出／不是对象（本次启动就会回落——判定口径与
    ``desktop_settings_service`` 一致：严格 ``agent.core.read`` ＋必须为 dict）；
    ② 上次回落留下的 ``desktop_settings.json.corrupt`` 侧车仍在（服务的既有
    preserve 产物）。只读探测，不改配置、不解析内容。
    """
    from agent.core import read as _strict_read
    from contract.diagnostics import StartupPhase
    settings = Path(root) / 'desktop_settings.json'
    corrupt_now = False
    try:
        if settings.is_file() and not isinstance(_strict_read(settings), dict):
            corrupt_now = True
    except (OSError, ValueError):
        corrupt_now = True
    try:
        had_fallback = (Path(root) / 'desktop_settings.json.corrupt').is_file()
    except OSError:
        had_fallback = False
    if corrupt_now or had_fallback:
        return _degraded(StartupPhase.CONFIG, 'settings-corrupt',
                         '桌面设置文件损坏：已回落默认值，原文件保留为 desktop_settings.json.corrupt'
                         if had_fallback else '桌面设置文件损坏：本次启动将回落默认值并保留 .corrupt 副本',
                         '确认设置无误后可删除 .corrupt 副本；需要找回请手动合并')
    return None


# ---------- L1 任务书轮 6（R6-a）：L1 自有四项检查，级别一律 DEGRADED ----------
#
# 口径纪律（任务书轮 6）：检查函数不得扫描目录（规则 33）——「遗留临时文件数」
# 取自轮 2 清扫线程经 ``record_temporary_sweep`` 写回的最近一次结果，不现场统计；
# 「当前项目」取 ``projects.json`` 的 ``active`` 登记，不递归找项目。

_LEDGER_UNKNOWN_STALE_LIMIT = 3    # 挂起转 unknown 条目累计超过即报：结算系统性失效信号
_TEMP_LEFTOVER_LIMIT = 10          # 清扫后仍残留的超期临时文件数上限


def _active_project_root(program):
    """``projects.json`` 登记的当前项目根；读不出／未登记返回 None（按「无法确认」放行）。"""
    try:
        data = read_json(Path(program) / 'projects.json', default={})
    except Exception:
        return None
    active = data.get('active') if isinstance(data, dict) else None
    return Path(active) if active else None


def _check_request_ledger(program):
    """台账损坏：当前项目 ``请求台账.json`` 存在但读不出／形状不符 → DEGRADED。

    只读探测：用 ``agent.core.read`` 严格读＋形状核对，不走 ``RequestLedger.load()``
    （load 会顺带清扫 reserved、写日备份，检查项不许有副作用）。
    """
    from agent.core import read as _strict_read
    from contract.diagnostics import StartupPhase
    project = _active_project_root(program)
    if project is None:
        return None
    import infra.request_ledger as request_ledger
    path = request_ledger.request_ledger_path(project)
    try:
        if not path.is_file():
            return None
    except OSError:
        return None
    try:
        data = _strict_read(path)
        ok = (isinstance(data, dict) and isinstance(data.get('entries'), list)
              and all(isinstance(row, dict) for row in data['entries']))
    except (OSError, ValueError):
        ok = False
    if ok:
        return None
    return _degraded(StartupPhase.RESOURCE, 'request-ledger-corrupt',
                     '请求台账文件损坏：用量结算与预算核对可能不完整',
                     '请保留原文件排查；程序按空台账继续，已产生的远端费用不受影响')


def _check_ledger_unknown_stale(program):
    """挂起转 ``unknown`` 的台账条目数超阈值 → DEGRADED。

    只数 ``request_ledger`` 两处「reserved→unknown」转换打过 ``unknown_via``
    标记的条目（陈旧预留清扫／结算等锁超时）；正常 ``mark_unknown`` 结算不计。
    """
    from agent.core import read as _strict_read
    from contract.diagnostics import StartupPhase
    project = _active_project_root(program)
    if project is None:
        return None
    import infra.request_ledger as request_ledger
    path = request_ledger.request_ledger_path(project)
    try:
        if not path.is_file():
            return None
        data = _strict_read(path)
    except (OSError, ValueError):
        return None                       # 损坏已由 request-ledger-corrupt 报，这里不重复
    entries = data.get('entries') if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return None
    count = sum(1 for row in entries
                if isinstance(row, dict) and row.get('state') == 'unknown' and row.get('unknown_via'))
    if count <= _LEDGER_UNKNOWN_STALE_LIMIT:
        return None
    return _degraded(StartupPhase.RESOURCE, 'request-ledger-unknown-stale',
                     '请求台账有 %d 笔挂起请求转为「待对账」unknown，超过阈值 %d'
                     % (count, _LEDGER_UNKNOWN_STALE_LIMIT),
                     '多为进程中途退出或结算等锁超时所致；请在用量页核对远端账单后重启')


def _check_ui_settings_corrupt(program):
    """当前项目存在 ``ui_settings.json.corrupt`` 侧车 → DEGRADED（``project_settings`` 的既有保留产物）。"""
    from contract.diagnostics import StartupPhase
    project = _active_project_root(program)
    if project is None:
        return None
    try:
        if not (project / 'ui_settings.json.corrupt').is_file():
            return None
    except OSError:
        return None
    return _degraded(StartupPhase.CONFIG, 'ui-settings-corrupt',
                     '项目设置文件 ui_settings.json 曾损坏，原文件保留为 ui_settings.json.corrupt',
                     '确认设置无误后可删除 .corrupt 副本；需要找回请手动合并')


def _check_temporary_leftovers(program):
    """遗留临时文件数超阈值 → DEGRADED；数据来自轮 2 清扫最近一次写回，不扫描目录。"""
    from contract.diagnostics import StartupPhase
    try:
        record = _state().get('temporary_sweep')
    except Exception:
        return None
    if not isinstance(record, dict):
        return None                       # 还没跑过清扫：无从确认，放行
    try:
        remaining = int(record.get('remaining') or 0)
    except (TypeError, ValueError):
        return None
    if remaining <= _TEMP_LEFTOVER_LIMIT:
        return None
    return _degraded(StartupPhase.RESOURCE, 'temporary-files-leftover',
                     '项目内仍有 %d 个超期遗留临时文件（清扫后未删净），超过阈值 %d'
                     % (remaining, _TEMP_LEFTOVER_LIMIT),
                     '多为被占用或权限拒绝的文件；可手动清理项目目录下的 *.tmp/*.download 残留')


# ---------- §3c-3 族开关（A1111 同构；GUI 等价物＝旗标文件） ----------
#
# 乙类 L1 检查按「族」命名开关，每族一个、只认自己那族；甲类 FATAL 仍只有全局
# ``selfcheck_failopen.flag``（G12 不变），族开关管不到甲类：
#   ``data/selfcheck_skip_<族>.flag``    跳过该族检查（探针不执行），并留一条
#                                       DEGRADED 诊断 ``selfcheck-skip-<族>`` 注明已跳过；
#   ``data/selfcheck_disable_<族>.flag`` 该族检查照跑，但产出与自身异常一并抑制
#                                       （关掉该族告警，完全静默）。
# 旗标在 ``data/`` 下、与 failopen 同为零依赖旗标文件；读取失败按未开处理不挡自检。
_SKIP_FLAG_PREFIX = 'selfcheck_skip_'
_DISABLE_FLAG_PREFIX = 'selfcheck_disable_'
_FLAG_SUFFIX = '.flag'
_SELFTEST_SCOPE = 'selfcheck'

# 启动自检乙类检查的「族」登记：顺序与 ``startup_checks`` 的检查元组一一对应；
# 新增检查须同轮在此登记族名（族名只用 [a-z0-9_]，即旗标文件名 ``selfcheck_{skip,disable}_<族>.flag`` 的 <族>）。
_STARTUP_CHECK_FAMILIES = (
    'data_writable', 'disk_space', 'model_pool', 'bundled_tools',
    'dependency_lock', 'settings_corrupt',
    'request_ledger_corrupt', 'ledger_unknown_stale',
    'ui_settings_corrupt', 'temporary_leftovers',
)


def _family_flag_enabled(root, prefix, family):
    """``data/<前缀><族名>.flag`` 存在即开；OSError 按未开（旗标读不出不挡自检）。"""
    try:
        return (Path(root) / 'data' / (prefix + family + _FLAG_SUFFIX)).is_file()
    except OSError:
        return False


def _skip_diagnostic(family):
    """skip 旗标的可见诊断：DEGRADED、scope=selfcheck、码随族名（状态栏按码去重不串族）。"""
    return _degraded(_SELFTEST_SCOPE, 'selfcheck-skip-' + family.replace('_', '-'),
                     '启动自检族「%s」已按 data/selfcheck_skip_%s.flag 跳过'
                     % (family, family),
                     '如需恢复该项检查，请删除对应旗标文件后重启')


def _family_check(root, family, check):
    """给一个零参乙类检查包上族开关：skip→返回跳过诊断（探针不执行）；
    disable→检查照跑、产出与异常一并抑制（返回 None，完全静默）；无旗标→原样返回。"""
    if _family_flag_enabled(root, _SKIP_FLAG_PREFIX, family):
        def skipped():
            return _skip_diagnostic(family)
        skipped.__name__ = 'skip_' + family
        return skipped
    if _family_flag_enabled(root, _DISABLE_FLAG_PREFIX, family):
        def disabled():
            try:
                check()
            except Exception:
                app_logging.swallowed()
            return None
        disabled.__name__ = 'disable_' + family
        return disabled
    return check


def startup_checks(program=None):
    """L1 环境检查项（D3-g 乙类六项＋L1 任务书轮 6 四项）：返回零参数可调用对象元组，由启动器注入 ``selfcheck.run``。

    每项检查对应一个「族」开关（§3c-3）：``data/selfcheck_skip_<族>.flag`` 跳过该族并留诊断，
    ``data/selfcheck_disable_<族>.flag`` 关闭该族告警（产出被抑制）。族名见 ``_STARTUP_CHECK_FAMILIES``。
    """
    root = Path(program or PROGRAM)

    def data_writable():
        return _check_data_writable(root)

    def disk_space():
        return _check_disk_space(root)

    def model_pool_empty():
        return _check_model_pool(root)

    def bundled_tools():
        return _check_bundled_tools(root)

    def dependency_lock():
        return _check_dependency_lock(root)

    def settings_corrupt():
        return _check_settings_corrupt(root)

    def request_ledger_corrupt():
        return _check_request_ledger(root)

    def ledger_unknown_stale():
        return _check_ledger_unknown_stale(root)

    def ui_settings_corrupt():
        return _check_ui_settings_corrupt(root)

    def temporary_leftovers():
        return _check_temporary_leftovers(root)

    checks = (data_writable, disk_space, model_pool_empty,
              bundled_tools, dependency_lock, settings_corrupt,
              request_ledger_corrupt, ledger_unknown_stale,
              ui_settings_corrupt, temporary_leftovers)
    return tuple(_family_check(root, family, check)
                 for family, check in zip(_STARTUP_CHECK_FAMILIES, checks))


# ---------- G12 关闭开关与自检入口 ----------

def _failopen_enabled(root):
    """G12：``data/selfcheck_failopen.flag`` 存在 → 甲类 FATAL 全部降为 DEGRADED。"""
    try:
        return (Path(root) / 'data' / _SELFTEST_FLAG).is_file()
    except OSError:
        return False


def _downgrade_fatal(item):
    """把一条 FATAL Diagnostic 降级为 DEGRADED（dataclasses.replace 重建，枚举归一照旧）。"""
    import dataclasses
    from contract.diagnostics import Diagnostic, Severity
    if not isinstance(item, Diagnostic) or item.severity is not Severity.FATAL:
        return item
    hint = str(item.escape_hint or '')
    if _SELFTEST_FLAG not in hint:
        hint = (hint + '；' if hint else '') + '已通过 data/%s 降级放行' % _SELFTEST_FLAG
    return dataclasses.replace(item, severity=Severity.DEGRADED, escape_hint=hint)


def run_startup_selfcheck(program=None):
    """启动器自检唯一入口（D3-h/D3-i 复用）：L0 甲类两项＋L1 乙类六项 → ``Diagnostic`` 列表。

    G12 开关存在时甲类 FATAL 一律降为 DEGRADED；结果经 ``record_selfcheck``
    写进诊断状态文件（随 ``export()`` 带走）。本函数自身不弹窗、不退出。
    """
    from contract import selfcheck
    root = Path(program or PROGRAM)
    items = selfcheck.run(tuple(selfcheck.default_checks()) + startup_checks(root))
    if _failopen_enabled(root):
        items = [_downgrade_fatal(item) for item in items]
    record_selfcheck(items)
    return items


def _diagnostic_row(item):
    severity = getattr(item, 'severity', '')
    severity = getattr(severity, 'value', severity)
    return {'severity': str(severity), 'scope': str(getattr(item, 'scope', '')),
            'code': str(getattr(item, 'code', '')),
            'message': _clean(getattr(item, 'message', '')),
            'remedy': _clean(getattr(item, 'remedy', '')),
            'escape_hint': _clean(getattr(item, 'escape_hint', ''))}


def record_selfcheck(items) -> None:
    """把一次启动自检结果写进诊断状态文件；任何失败静默（诊断不挡启动）。"""
    try:
        with _LOCK:
            state = _state()
            state['selfcheck'] = {
                'at': datetime.now().isoformat(timespec='seconds'),
                'items': [_diagnostic_row(item) for item in (items or [])],
            }
            _save_state(state)
    except Exception:
        app_logging.swallowed()


# ---------- 崩溃预算（D3-j/D3-k，G6；账本＝本文件 latest.json 的 startup_guard 段） ----------

def _instant(value):
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _guard_state(state):
    raw = state.get(_GUARD_KEY)
    return dict(raw) if isinstance(raw, dict) else {}


def startup_guard() -> str:
    """崩溃预算闸（G6／附 3b-2）：结清上一次未完成的启动并按时间窗计一次崩溃，
    窗口内满 ``CRASH_LIMIT`` 返回 ``'safe_start'``，否则写入本次「进行中」返回 ``'proceed'``。

    语义对齐 Chromium ``IncrementCrashCount``：每 ``FORGIVE_MINUTES`` 赦免一次；
    时钟回拨（差值为负）按 0 处理；状态文件损坏或不可写一律按「无历史」继续
    启动（D3-j），绝不因此启动失败。二次启动在到达本函数前已 ``sys.exit(0)``，
    天然不计数不清零；系统关机走 ``record_startup_closed`` 结清。
    """
    try:
        now = datetime.now()
        with _LOCK:
            state = _state()
            guard = _guard_state(state)
            try:
                count = int(guard.get('crash_count'))
            except (TypeError, ValueError):
                count = 0
            count = max(0, min(count, CRASH_LIMIT))
            last_crash = _instant(guard.get('last_crash_at'))
            if _instant(guard.get('attempt_at')) is not None:
                # 上一次启动没走到 READY／正常关闭就没了下文＝崩了一次：先按时间窗赦免再 +1。
                forgiven = 0
                if last_crash is not None:
                    minutes = (now - last_crash).total_seconds() / 60.0
                    forgiven = int(max(0.0, minutes) // FORGIVE_MINUTES)
                count = min(max(0, count - forgiven) + 1, CRASH_LIMIT)
                last_crash = now
            exceeded = count >= CRASH_LIMIT
            state[_GUARD_KEY] = {
                'attempt_at': now.isoformat(timespec='seconds'),
                'crash_count': count,
                'last_crash_at': last_crash.isoformat(timespec='seconds') if last_crash else None,
            }
            _save_state(state)
        return 'safe_start' if exceeded else 'proceed'
    except Exception:
        return 'proceed'


def record_startup_ready() -> None:
    """到达 READY（含登录闸出现）或正常构造完成：结清「进行中」并把崩溃计数清零（G6）。"""
    try:
        with _LOCK:
            state = _state()
            guard = _guard_state(state)
            if not guard.get('attempt_at') and not guard.get('crash_count'):
                return
            guard['attempt_at'] = None
            guard['crash_count'] = 0
            state[_GUARD_KEY] = guard
            _save_state(state)
    except Exception:
        app_logging.swallowed()


def record_startup_closed() -> None:
    """正常关闭（含系统关机／会话结束）：把「进行中」结清为非崩溃；崩溃计数不动。"""
    try:
        with _LOCK:
            state = _state()
            guard = _guard_state(state)
            if not guard.get('attempt_at'):
                return
            guard['attempt_at'] = None
            state[_GUARD_KEY] = guard
            _save_state(state)
    except Exception:
        app_logging.swallowed()


def _app_title():
    try:
        from contract.app_metadata import APP_NAME
        return APP_NAME
    except Exception:
        return '漫剧助手'


def _win32_message_box(text, title, flags):
    """Win32 ``MessageBoxW``；任何失败返回 0（当作用户关闭，按「否」处理）。"""
    try:
        import ctypes
        return int(ctypes.windll.user32.MessageBoxW(0, str(text), str(title), int(flags)))
    except Exception:
        return 0


_SAFE_START_TEXT = (
    '程序最近多次启动失败，可能陷入崩溃循环。\n\n'
    '选择「是」以安全模式启动：不恢复上次项目、设置按默认值（不覆盖您的设置文件）。\n'
    '选择「否」仍按正常方式启动。'
)


def confirm_safe_start(ask=None) -> bool:
    """崩溃预算耗尽后的二选一（G6）：``True``＝安全启动。``ask(text,title,flags)`` 可注入。"""
    ask = ask or _win32_message_box
    try:
        return int(ask(_SAFE_START_TEXT, _app_title(), _MB_YESNO | _MB_ICONWARNING)) == _IDYES
    except Exception:
        return False


def startup_gate(ask=None) -> bool:
    """启动器统一入口：写「进行中」并结清上次崩溃；预算耗尽时弹二选一。

    返回 ``True`` 表示本次按安全模式启动；任何内部失败都按正常启动继续
    （崩溃预算自身出问题不得挡住启动）。
    """
    try:
        if startup_guard() != 'safe_start':
            return False
        return confirm_safe_start(ask=ask)
    except Exception:
        return False


def fatal_diagnostics_text(items) -> str:
    """FATAL 自检结果的可操作文本：每条 message＋remedy＋escape_hint，附 G12 关闭开关用法。"""
    lines = []
    for item in items:
        lines.append('【%s】%s' % (getattr(item, 'code', ''), getattr(item, 'message', item)))
        remedy = str(getattr(item, 'remedy', '') or '')
        if remedy:
            lines.append('处理建议：' + remedy)
        escape = str(getattr(item, 'escape_hint', '') or '')
        if escape:
            lines.append('可选：' + escape)
    lines.append('')
    lines.append('临时跳过自检（仅限排查）：在 程序\\data\\ 目录新建 %s 文件后重启，'
                 '甲类检查会降级放行；问题修复后请删除该文件。' % _SELFTEST_FLAG)
    return '\n'.join(lines)


def notify_startup_fatal(items) -> None:
    """FATAL 自检结果的弹窗（建 Tk 之前可用，D3-h）；弹窗失败不抛异常。"""
    try:
        _win32_message_box(fatal_diagnostics_text(items), _app_title(), _MB_ICONSTOP)
    except Exception:
        app_logging.swallowed()
