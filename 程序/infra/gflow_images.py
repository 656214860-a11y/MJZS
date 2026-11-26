"""Flow image generation using the named profiles managed by gflow-cli."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from PIL import Image


def executable():
    bundled = Path(os.environ.get('LOCALAPPDATA', '')) / 'MJZS/tools/gflow/Scripts/gflow.exe'
    return str(bundled) if bundled.is_file() else shutil.which('gflow') or ''


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
        output = Path(folder) / 'result.png'
        for index, profile in enumerate(config['profiles']):
            if stop.is_set():
                raise ValueError('已停止制作')
            args = [program, 'image', 'i2i' if refs else 't2i', '--json',
                    '--model', config['model'], '--profile', profile, '--out-file', str(output)]
            if config.get('flow_project'):
                args.extend(['--project', config['flow_project']])
            for ref in refs:
                args.extend(['--ref', str(ref)])
            args.extend(['--', prompt])
            with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
                with subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                      creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)) as child:
                    deadline = time.monotonic() + 600
                    while child.poll() is None:
                        if stop.wait(.25) or time.monotonic() > deadline:
                            child.kill()
                            raise ValueError('Flow 已中断，请核对远端任务结果')
                if child.returncode:
                    error = {}
                    for stream in (stdout, stderr):
                        stream.seek(0)
                        try:
                            error = json.loads(stream.read(65536)).get('error') or {}
                        except (ValueError, AttributeError):
                            continue
                        if error:
                            break
                    kind = str(error.get('type', '')).rsplit('/', 1)[-1]
                    if (kind in ('rate-limit', 'insufficient-credits') and error.get('charged') == 'no'
                            and not error.get('operation_id') and not error.get('completed_media_ids')):
                        output.unlink(missing_ok=True)
                        continue
                    raise ValueError(f'Flow 账号 {profile} 出图失败（{kind or child.returncode}）')
            with Image.open(output) as image:
                image.load()
                png = Path(folder) / 'verified.png'
                image.save(png, 'PNG')
            png.replace(destination)
            config['profiles'] = config['profiles'][index:] + config['profiles'][:index]
            return
    raise ValueError('所有 Flow 账号均已达到限额')
