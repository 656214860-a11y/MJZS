# -*- coding: utf-8 -*-
"""环境自检：只读核对外部依赖是否就绪，每项给出状态和下一步。

检查 FFmpeg／FFprobe、ComfyUI、Blender、本机 Claude／Codex 程序、API 模型密钥。
只读：不启动任何程序、不联网、不写文件、不返回密钥内容；可选依赖缺失只给「提示」，
不当成故障。每个探测函数可注入，便于测试。
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import infra.comfy_runtime as comfy_runtime
import infra.client_profiles as client_profiles
import file_cache
import infra.model_pool as model_pool
import contract.platform_tools as platform_tools
import domain.white_model_service as white_model_service
import orchestrator.workflow_settings as workflow_settings

OK, WARN, MISSING = 'ok', 'warn', 'missing'
STATUS_TEXT = {OK: '正常', WARN: '提示', MISSING: '缺失'}
PROGRAM = Path(__file__).resolve().parent
DESKTOP_PROGRAMS = (('claude-desktop-app', 'Claude Desktop', '剧本准备可选「Claude Desktop」手动发送'),
                    ('codex', 'ChatGPT / Codex', '剧本准备可选「ChatGPT Desktop · Codex」'),
                    ('claude', 'Claude Code 命令行', '阶段工作流可选「Claude Code」命令行模型'))


# 最低版本（建议值）：低于它只给「提示」，不拦截；版本探测要启动程序，所以只在用户点「环境自检」时做。
MIN_VERSIONS = {'ffmpeg': (4, 4), 'ffprobe': (4, 4), 'blender': (3, 6)}
VERSION_ARGS = {'ffmpeg': ['-version'], 'ffprobe': ['-version'], 'blender': ['--version']}
_VERSION_RE = re.compile(r'(?:version|Blender)\s+[nN]?(\d+)\.(\d+)')


def parse_version(text):
    """从 ``ffmpeg version 6.1.1`` 或 ``Blender 4.2.1`` 的首行取 ``(主, 次)``；认不出（如 git 构建）返回 None。"""
    lines = str(text or '').strip().splitlines()
    matched = _VERSION_RE.search(lines[0]) if lines else None
    return (int(matched.group(1)), int(matched.group(2))) if matched else None


def probe_version(key, exe, run=platform_tools.run_process):
    """启动 ``exe`` 读版本（8 秒超时）；任何失败都返回 None，不抛错。"""
    try:
        done = run([str(exe), *VERSION_ARGS[key]], capture_output=True, text=True, timeout=8, check=False)
    except Exception:
        return None
    return parse_version(done.stdout or done.stderr)


def apply_versions(rows, probe=probe_version):
    """给 FFmpeg／FFprobe／Blender 行补上版本；低于最低版本降为「提示」。返回新行列表。"""
    result = []
    for item in rows:
        key, minimum = item['key'], MIN_VERSIONS.get(item['key'])
        found_it = item['status'] == OK or (item['status'] == WARN and key in ('ffmpeg', 'ffprobe'))
        exe = item['detail'].split('；')[0] if minimum and found_it else ''
        found = probe(key, exe) if exe else None
        if not minimum or not exe:
            result.append(item)
        elif found is None:
            result.append(dict(item, detail=item['detail'] + '；版本无法识别'))
        elif found < minimum:
            need = '.'.join(map(str, minimum))
            result.append(dict(item, status=WARN, detail='%s；版本 %d.%d 低于建议最低 %s' % (item['detail'], *found, need),
                               next='升级 %s 到 %s 以上' % (item['label'], need)))
        else:
            result.append(dict(item, detail='%s；版本 %d.%d' % (item['detail'], *found)))
    return result


def _find_profile(profile_row):
    path = client_profiles.detect_executable(
        profile_row, store_finder=workflow_settings.store_package_program)
    if path:
        return path
    raise ValueError('未找到档案中的程序')


def check_client_profiles(profiles=None, find=_find_profile):
    """Each built-in client profile gets one row; read-only and never launches."""
    rows = []
    for profile_id, item in (profiles or client_profiles.load_profiles()).items():
        kind = '桌面' if item['kind'] == 'desktop' else '命令行'
        use = '%s · 投递 %s' % (kind, item['delivery'])
        try:
            path = find(item)
        except Exception as exc:
            rows.append(row(profile_id, item['display'], WARN, '未找到：%s' % exc,
                            '需要时在模型管理点「检测」或手动选择 .exe；%s' % use))
            continue
        rows.append(row(profile_id, item['display'], OK, str(path), use))
    return rows


def row(key, label, status, detail, next_step=''):
    return {'key': key, 'label': label, 'status': status, 'detail': detail, 'next': next_step}


def _json(path):
    try:
        value = file_cache.read_json(path)
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def check_ffmpeg(config, which=shutil.which, bundled=None):
    """FFmpeg/FFprobe 行：显式有效配置 > 随包版本 > 系统 PATH（R3154，与 tool_path 同序）。"""
    if bundled is None:
        bundled = platform_tools._bundled_tool
    rows = []
    for key, name in (('ffmpeg', 'FFmpeg'), ('ffprobe', 'FFprobe')):
        configured = str(config.get(key) or '').strip()
        if configured and '/' not in configured and '\\' not in configured:
            # 裸命令名与 tool_path 同序：原样下传、exec 时按 PATH 解析。
            rows.append(row(key, name, OK, configured + '；按 PATH 解析'))
            continue
        if configured and Path(configured).is_file():
            rows.append(row(key, name, OK, configured))
            continue
        ship = bundled(key)
        if ship:
            note = '配置的路径不存在，已改用随包版本' if configured else ''
            rows.append(row(key, name, WARN if configured else OK,
                            ship + '；随包版本' + ('；' + note if note else ''),
                            '在 config.json 把「%s」改成实际路径' % key if configured else ''))
            continue
        found = which(key)
        if found:
            note = '配置的路径不存在，已改用系统 PATH 中的程序' if configured else ''
            rows.append(row(key, name, WARN if configured else OK, found + ('；' + note if note else ''),
                            '在 config.json 把「%s」改成实际路径' % key if configured else ''))
        else:
            rows.append(row(key, name, MISSING, ('配置路径不存在：' + configured) if configured else '未配置、随包版本缺失也不在 PATH',
                            '安装 FFmpeg 后在 config.json 填写「%s」，成片合成与质检依赖它' % key))
    return rows


def check_comfy(settings):
    exe = comfy_runtime.executable(settings)
    if exe is not None:
        return row('comfyui', 'ComfyUI 桌面程序', OK, str(exe))
    return row('comfyui', 'ComfyUI 桌面程序', WARN, '未找到',
               '可选依赖：使用本地出图／视频／分镜预演时，在助手点击「桌面打开 ComfyUI」选择程序；只用云端模型可忽略')


def check_blender(find=white_model_service.find_blender):
    exe = find()
    if exe:
        return row('blender', 'Blender', OK, str(exe))
    return row('blender', 'Blender', WARN, '未找到', '可选依赖：需要白模预演时安装 Blender，或在白模设置里指定；不做白模可忽略')


def check_desktop_programs(find=workflow_settings.find_program):
    rows = []
    for engine, label, use in DESKTOP_PROGRAMS:
        try:
            path = find({'engine': engine, 'program': ''})
        except Exception as exc:
            rows.append(row(engine, label, WARN, '未找到：%s' % exc, '需要时在模型管理点「自动搜寻」或手动选择 .exe；%s' % use))
            continue
        status = OK
        detail = str(path)
        if engine == 'claude' and workflow_settings.gui_claude_program(path):
            status, detail = WARN, detail + '（这是图形程序，不能当命令行用）'
        rows.append(row(engine, label, status, detail,
                        workflow_settings.GUI_CLAUDE_CLI_HINT if status == WARN else ''))
    return rows


def check_model_keys(models, program=None, key_of=model_pool.key_of):
    """API 模型的密钥是否可解析；只统计有无，不返回内容。"""
    ready, missing = [], []
    for model_id, item in models.items():
        if str(item.get('provider') or '') == 'desktop' or not str(item.get('key_env') or '').strip():
            continue
        (ready if key_of(item, program) else missing).append(str(item.get('label') or model_id))
    if not ready and not missing:
        return row('keys', 'API 模型密钥', WARN, '模型池里没有需要密钥的 API 模型', '在模型管理添加并保存密钥')
    if missing:
        return row('keys', 'API 模型密钥', WARN if ready else MISSING,
                   '已配置 %d 个；缺少密钥：%s' % (len(ready), '、'.join(missing)),
                   '在模型管理选中对应模型，填写密钥后点「保存这条」；不用的模型可忽略')
    return row('keys', 'API 模型密钥', OK, '%d 个 API 模型均已配置密钥' % len(ready))


def run_checks(program=None, *, config=None, settings=None, models=None, which=shutil.which,
               find_blender=white_model_service.find_blender, find_program=workflow_settings.find_program,
               key_of=model_pool.key_of, profiles=None, find_profile=_find_profile):
    root = Path(program or PROGRAM)
    config = config if config is not None else _json(root / 'config.json')
    settings = settings if settings is not None else _json(root / 'desktop_settings.json')
    models = models if models is not None else model_pool.pool(program=root)
    rows = check_ffmpeg(config, which)
    rows.append(check_comfy(settings))
    rows.append(check_blender(find_blender))
    if profiles is None and find_program is workflow_settings.find_program:
        profiles = client_profiles.load_profiles()
    rows.extend(check_client_profiles(profiles, find_profile) if profiles is not None
                else check_desktop_programs(find_program))
    rows.append(check_model_keys(models, root, key_of))
    return rows


def run_checks_with_versions(program=None, *, probe=probe_version, **kwargs):
    """``run_checks`` 再给 FFmpeg／FFprobe／Blender 补版本；会启动这些程序，只在用户点「环境自检」时用。"""
    return apply_versions(run_checks(program, **kwargs), probe)


def summary(rows):
    counts = {status: sum(1 for item in rows if item['status'] == status) for status in (OK, WARN, MISSING)}
    return '共 %d 项：正常 %d，提示 %d，缺失 %d' % (len(rows), counts[OK], counts[WARN], counts[MISSING])


def report_text(rows=None):
    data = rows if rows is not None else run_checks_with_versions()
    lines = [summary(data), '']
    for item in data:
        lines.append('[%s] %s：%s' % (STATUS_TEXT[item['status']], item['label'], item['detail']))
        if item['next']:
            lines.append('    下一步：' + item['next'])
    return '\n'.join(lines)
