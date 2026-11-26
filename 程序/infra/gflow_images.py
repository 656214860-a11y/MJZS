"""Flow image generation using the named profiles managed by gflow-cli."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from PIL import Image
from agent.core import replace
from infra.workflow_process_registry import spawn


def executable():
    bundled = Path(os.environ.get('LOCALAPPDATA', '')) / 'MJZS/tools/gflow/Scripts/gflow.exe'
    return str(bundled) if bundled.is_file() else shutil.which('gflow') or ''


def _error_from(stream):
    if stream.seek(0, os.SEEK_END) > 65536:
        return {}
    stream.seek(0)
    try:
        envelope = json.load(stream)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return envelope.get('error', {}) if isinstance(envelope, dict) else {}


def _invoke(args, stop, folder):
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        child = spawn('engine_cli', args, project=folder, stage='Flow 生图', timeout=600,
                      stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, pump_stderr=False)
        deadline = time.monotonic() + 600
        try:
            while child.poll() is None:
                if stop.wait(.25) or time.monotonic() > deadline:
                    raise ValueError('Flow 已中断，请核对远端任务结果')
            return child.poll(), _error_from(stdout) or _error_from(stderr)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)


def generate(config, prompt, references, destination, stop):
    if not prompt.strip():
        raise ValueError('缺少图片提示词')
    program = config['program']
    if Path(program).name.lower() != 'gflow.exe' or not Path(program).is_file():
        raise ValueError('请在模型管理的 Google Flow 设置中选择 gflow.exe')
    destination = Path(destination)
    refs = [Path(path) for path in references]
    if any(not path.is_file() for path in refs):
        raise ValueError('Flow 图片任务缺少参考图')
    with tempfile.TemporaryDirectory(dir=destination.parent) as folder:
        for index, profile in enumerate(config['profiles']):
            output = Path(folder) / f'result-{index}.png'
            if stop.is_set():
                raise ValueError('已停止制作')
            args = [program, 'image', 'i2i' if refs else 't2i', '--json',
                    '--model', config['model'], '--profile', profile, '--out-file', str(output)]
            if config.get('flow_project'):
                args.extend(['--project', config['flow_project']])
            for ref in refs:
                args.extend(['--ref', str(ref)])
            args.extend(['--', prompt])
            code, error = _invoke(args, stop, folder)
            if code:
                kind = str(error.get('type', '')).rsplit('/', 1)[-1]
                if (kind in ('rate-limit', 'insufficient-credits') and error.get('charged') == 'no'
                        and not error.get('operation_id') and not error.get('completed_media_ids')):
                    continue
                raise ValueError(f'Flow 账号 {profile} 出图失败（{kind or code}）')
            with Image.open(output) as image:
                image.load()
                png = Path(folder) / 'verified.png'
                image.save(png, 'PNG')
            replace(png, destination)
            config['profiles'] = config['profiles'][index:] + config['profiles'][:index]
            return
    raise ValueError('所有 Flow 账号均已达到限额')
