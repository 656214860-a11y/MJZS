"""离线全链夹具：装载 recovery_to_delivery_baseline 脚本，供 E2E 与 soak 共用。

供应商是离线替身、媒体是合成测试源、评审是脚本模拟；只证明代码路径与落盘事实，
不证明真实供应商可用性、人工验收或付费行为（见 docs/process/联调测试出口基线.md §1）。
"""
import importlib.util
import subprocess
from pathlib import Path

from agent.core import save
from stage_config import put_workflow

SCRIPT = Path(__file__).resolve().parents[1] / "维护记录/基准脚本/recovery_to_delivery_baseline.py"
SPEC = importlib.util.spec_from_file_location("recovery_to_delivery_baseline", SCRIPT)
baseline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(baseline)

FFMPEG = baseline.FFMPEG
FFPROBE = baseline.FFPROBE
main = baseline.main
scope = baseline.scope
accept = baseline.accept


def missing_external_programs():
    """缺失的外部编码程序路径；空列表表示齐全。"""
    return [path for path in (FFMPEG, FFPROBE) if not Path(path).exists()]


def prepare_project(root, shot_ids, duration=2, budget_seconds=300):
    """最小离线项目：真配置与工作流锁＋合成源片与首帧；目录必须不存在。"""
    root.mkdir(parents=True, exist_ok=False)
    save(root / 'config.json', {'episode_file': 'episode.json', 'live_enabled': True,
                                'budget_seconds': budget_seconds, 'reserve_seconds': 0,
                                'ffmpeg': FFMPEG, 'ffprobe': FFPROBE,
                                'model': 'offline-fixture', 'require_audio': True})
    put_workflow(root, {'name': 'offline-soak', 'lock': {'offline-soak': {
        'aspect_ratio': '9:16', 'resolution': '1080x1920', 'fps': 25}}})
    shots = [{'id': sid, 'duration': duration, 'video_prompt': 'Original soak fixture ' + sid,
              'frame': 'frame.png', 'post_overlay': 'OFFLINE SOAK ' + sid} for sid in shot_ids]
    save(root / 'episode.json', {'shots': shots})
    save(root / 'offline-provider.json', {'attempts': {}, 'tasks': {}})
    subprocess.run([FFMPEG, '-v', 'error', '-y', '-f', 'lavfi', '-i',
                    'testsrc2=size=180x320:rate=25:duration=%d' % duration, '-f', 'lavfi', '-i',
                    'sine=frequency=1000:sample_rate=48000:duration=%d' % duration, '-c:v', 'libx264',
                    '-threads', '2', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-shortest', str(root / 'source.mp4')], check=True, capture_output=True)
    subprocess.run([FFMPEG, '-v', 'error', '-y', '-i', str(root / 'source.mp4'),
                    '-frames:v', '1', str(root / 'frame.png')], check=True, capture_output=True)
    return root