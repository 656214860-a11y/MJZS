# -*- coding: utf-8 -*-
"""总控包（00 全流程 SKILL）scripts 机检的受控桥（L1 基础设施，无 Tk、无第三方依赖）。

把上游 ``skills/00全流程SKILL/AIGC创作全流程/.../scripts/`` 里的确定性机检脚本接进
本应用的 skill_tools，让「提示词质检 / 六道闸门 / 画风锁推荐」从「靠模型自觉」变成
「机器断言」。三类脚本入口：

- subprocess 桥：``validate_prompt.py``（C1~C30 / H1~H12，吃投喂稿 md，``--json`` 输出）、
  ``gate_check.py``（六道闸门 + 素材形态一致性，吃投喂稿 md）、
  ``audit_contract.py``（全流程交付契约核销）。它们都吃文件路径、退出码语义化
  （0=PASS / 1=FAIL / 2=参数错 / 3=非投喂稿），用自带解释器 ``sys.executable -B`` 隔离开跑。
- import 桥：``style-lock-ladder.py`` / ``style-lock-recommend.py`` 的 ``recommend`` 纯函数
  （只 import re），按需 importlib 加载，不额外起进程。

设计边界（遵循 AGENTS.md 硬约束）：

- 零第三方依赖：脚本本身只用标准库；桥也只 import 标准库。
- 不裸抛：子模块未挂载、参数非法、超时、非投喂稿，都转成结构化 dict，由 skill_tools
  的 ``ToolError``／返回契约统一承接，绝不让 Traceback 漏到界面或编排器。
- 只读：桥只读脚本、不写任何项目数据；临时投喂稿 md 用后即删。
- 不越层：本模块只依赖标准库与文件系统，不 import 任何 L2/L3/L4 模块；skill_tools（L3）
  向下 import 本模块是合法方向。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from json import loads
from pathlib import Path

from infra.file_cache import remove_temporary_file

# 相对「程序」根目录的总控包路径；子模块未初始化时这些文件不存在，桥返回友好错误。
_PACKAGE = Path(__file__).resolve().parents[1] / 'skills' / '00全流程SKILL' / 'AIGC创作全流程'
_VALIDATE = _PACKAGE / 'short-drama-director' / 'scripts' / 'validate_prompt.py'
_GATE = _PACKAGE / 'sd-feed-engine' / 'scripts' / 'gate_check.py'
_AUDIT = _PACKAGE / 'short-drama-director' / 'scripts' / 'audit_contract.py'
_LADDER = _PACKAGE / 'short-drama-director' / 'scripts' / 'style-lock-ladder.py'
_RECOMMEND = _PACKAGE / 'short-drama-director' / 'scripts' / 'style-lock-recommend.py'

# 单次机检超时上限：C 系全码 + 契约核销在 400KB 脚本上实测秒级，60s 是宽裕兜底。
_TIMEOUT = 60
# 未知视频模型锁 → 沿用 workflow_settings 的口径：未适配模型回退默认格式（2.5），不报错。
_MODEL_ALIASES = {
    'seedance 2.5': '2.5', 'seedance2.5': '2.5', '2.5': '2.5',
    'seedance 2.0': '2.0', 'seedance2.0': '2.0', '2.0': '2.0',
    'minimax h3': 'h3', 'h3': 'h3',
}
# track 是〇·0 赛道分流锁：国内/海外/解说/其他 → 1/2/3/4（缺省按 1 国内剧）。
_TRACK_ALIASES = {
    '国内剧': '1', '海外剧': '2', '解说叙事类': '3', '解说': '3', '其他': '4',
    '1': '1', '2': '2', '3': '3', '4': '4',
}

# 总控包 scripts 未挂载（子模块未初始化）时的统一友好错误文案。
_SCRIPTS_MISSING = 'SKILL scripts 未挂载（子模块未初始化）'


def _scripts_root():
    """总控包 scripts 根；子模块未挂载返回 None（不抛，交给调用方报友好错误）。"""
    if _VALIDATE.is_file():
        return _PACKAGE
    return None


def _model_arg(lock_value):
    """把项目锁里的视频模型版本映射成脚本 ``--model`` 值；未知值回退 2.5（与 skill_prompt 同口径）。"""
    return _MODEL_ALIASES.get(str(lock_value or '').strip().lower(), '2.5')


def _track_arg(lock_value):
    """把项目锁里的赛道映射成脚本 ``--track`` 值；未知/空值回退 1 国内剧。"""
    return _TRACK_ALIASES.get(str(lock_value or '').strip(), '1')


def _run_script(script, argv):
    """跑一个吃文件路径的机检脚本，返回 (returncode, stdout, stderr)。

    用 ``sys.executable -B`` 隔离运行（脚本间 ``import sd_core`` 依赖同目录，cwd 设为脚本
    所在目录保证相对 import 命中）。捕获输出而非继承，避免脚本 print 冲进宿主 stdout。
    """
    completed = subprocess.run(
        [sys.executable, '-B', str(script), *argv],
        cwd=str(script.parent), capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=_TIMEOUT)
    return completed.returncode, completed.stdout or '', completed.stderr or ''


def _write_temp(text):
    """把投喂稿正文写成临时 md；调用方负责 finally 删除。"""
    handle = tempfile.NamedTemporaryFile('w', suffix='.md', encoding='utf-8', delete=False)
    try:
        handle.write(text)
    except BaseException:
        handle.close()
        remove_temporary_file(handle.name)
        raise
    handle.close()
    return Path(handle.name)


@contextmanager
def _feed_path(text):
    """临时投喂稿 md：``with`` 块内可用，退出即删（删除失败忽略）。"""
    path = _write_temp(text)
    try:
        yield path
    finally:
        remove_temporary_file(path)


def _parse_json(stdout):
    """脚本 ``--json`` 输出为单行/多行 JSON，稳健解析；解析不出返回 None。"""
    if not stdout:
        return None
    try:
        return loads(stdout)
    except (ValueError, TypeError):
        # validate_prompt --json 输出带缩进多行，仍是一个合法 JSON 对象；兜底取首行起始到结尾。
        try:
            return loads(stdout.strip().split('\n', 1)[-1] if stdout.strip().startswith('{') else stdout)
        except (ValueError, TypeError):
            return None


def validate_prompt(feed_text, *, model=None, track=None, aspect=None):
    """投喂稿机检（C1~C30 / H1~H12）。返回结构化 dict，不抛。

    ``model``/``track`` 传项目锁原始值即可（本函数做别名映射）；``aspect`` 是画幅锁。
    """
    if _scripts_root() is None:
        return {'ok': False, 'exit': None, 'error': _SCRIPTS_MISSING}
    argv = ['--model', _model_arg(model), '--track', _track_arg(track), '--json']
    if aspect and str(aspect).strip():
        argv += ['--aspect', str(aspect).strip()]
    with _feed_path(feed_text) as path:
        try:
            code, stdout, stderr = _run_script(_VALIDATE, [str(path), *argv])
        except (subprocess.SubprocessError, OSError) as exc:
            return {'ok': False, 'exit': None, 'error': '机检脚本运行失败：%s' % exc}
    data = _parse_json(stdout) or {}
    return {'ok': code == 0, 'exit': code,
            'issues': data.get('issues') or [], 'warnings': data.get('warnings') or [],
            'stats': data.get('stats') or {},
            'track': data.get('track'), 'c14_exempt': data.get('c14_exempt'),
            'combat_checked': data.get('combat_checked'), 'c23_checked': data.get('c23_checked'),
            'style_source': data.get('style_source'),
            'stderr': stderr.strip()[:2000] if stderr else ''}


def gate_check(feed_text, *, model=None, assets=None, mode='auto'):
    """投喂层六道闸门 + 素材形态一致性。返回结构化 dict，不抛。"""
    if _scripts_root() is None:
        return {'ok': False, 'exit': None, 'error': _SCRIPTS_MISSING}
    argv = ['--model', _model_arg(model)]
    if assets is not None:
        argv += ['--assets', str(int(assets))]
    if mode and str(mode).strip():
        argv += ['--mode', str(mode).strip()]
    with _feed_path(feed_text) as path:
        try:
            code, stdout, stderr = _run_script(_GATE, [str(path), *argv])
        except (subprocess.SubprocessError, OSError) as exc:
            return {'ok': False, 'exit': None, 'error': '闸门脚本运行失败：%s' % exc}
    # gate_check 无 --json，退出码即结论；stdout 里含 FAIL/WARN 明细，保留尾部供人读。
    return {'ok': code == 0, 'exit': code,
            'summary': (stdout or '').strip()[-2000:],
            'stderr': stderr.strip()[:2000] if stderr else ''}


def audit_contract(markdown_text, *, mode='auto', director=None):
    """全流程交付契约与权威源核销。返回结构化 dict，不抛。"""
    if _scripts_root() is None:
        return {'ok': False, 'exit': None, 'error': _SCRIPTS_MISSING}
    argv = ['--mode', str(mode or 'auto')]
    if director and str(director).strip():
        argv += ['--director', str(director).strip()]
    with _feed_path(markdown_text) as path:
        try:
            code, stdout, stderr = _run_script(_AUDIT, [str(path), *argv])
        except (subprocess.SubprocessError, OSError) as exc:
            return {'ok': False, 'exit': None, 'error': '契约核销脚本运行失败：%s' % exc}
    return {'ok': code == 0, 'exit': code,
            'summary': (stdout or '').strip()[-2000:],
            'stderr': stderr.strip()[:2000] if stderr else ''}


def _load_module(script):
    """importlib 加载一个只依赖标准库的脚本模块（画风锁两个纯函数脚本）。"""
    spec = importlib.util.spec_from_file_location(script.stem, str(script))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def style_ladder(text, top=4):
    """画风锁递进引擎（style-lock-ladder.recommend）→ 文本阶梯。返回 dict，不抛。"""
    if _scripts_root() is None:
        return {'ok': False, 'error': _SCRIPTS_MISSING}
    try:
        module = _load_module(_LADDER)
        return {'ok': True, 'text': module.recommend(text, top=top)}
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        return {'ok': False, 'error': '画风锁引擎加载失败：%s' % exc}


def style_recommend(text):
    """画风锁推荐引擎（style-lock-recommend.recommend）→ 结构化候选池。返回 dict，不抛。"""
    if _scripts_root() is None:
        return {'ok': False, 'error': _SCRIPTS_MISSING}
    try:
        module = _load_module(_RECOMMEND)
        combat, why, vfx_high, pool, excluded, route_key = module.recommend(text)
        return {'ok': True, 'combat': combat, 'why': why, 'vfx_high': vfx_high,
                'pool': [list(item) for item in pool], 'excluded': [list(item) for item in excluded],
                'route_key': route_key}
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        return {'ok': False, 'error': '画风锁推荐引擎加载失败：%s' % exc}
