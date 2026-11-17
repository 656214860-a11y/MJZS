"""Offline supplier faults; real Studio persistence, process restart and encoding.

Synthetic media/reviews only. No evidence of provider or human acceptance.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PROGRAM = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROGRAM))
from agent.core import read, save, file_hash
from agent.media import check, probe
from agent.wan import WanAdapter, ArkRejected
from engine import Studio, read_edit_bundle
from video_task_state import assert_prompt_editable

FFMPEG = 'D:/Tools/ffmpeg/bin/ffmpeg.exe'
FFPROBE = 'D:/Tools/ffmpeg/bin/ffprobe.exe'


def expect_error(action, text):
    try:
        action()
    except (ValueError, RuntimeError, TimeoutError) as exc:
        assert text in str(exc), str(exc)
        return str(exc)
    raise AssertionError('Expected failure: ' + text)


class OfflineSupplier:
    def __init__(self, root):
        self.root = root
        self.db = root / 'offline-provider.json'

    def payload(self, shot, frame):
        return WanAdapter({'base_url': 'https://example.invalid', 'model': 'offline-fixture'}).payload(shot, frame)

    def submit(self, shot, frame, request_id, *, payload):
        data = read(self.db)
        sid = shot['id']
        count = data['attempts'].get(sid, 0) + 1
        data['attempts'][sid] = count
        task = f'offline-{sid}-{count:04}'
        if sid == 'SH003' and count == 1:
            save(self.db, data)
            raise ArkRejected('HTTP 429 offline fault')
        data['tasks'][task] = {'sid': sid, 'attempt': count, 'request': request_id}
        save(self.db, data)
        if sid == 'SH002' and count == 1:
            raise ConnectionError('offline disconnect after creation')
        return task

    def poll(self, task):
        data = read(self.db)
        row = data['tasks'][task]
        if row['sid'] == 'SH004' and not row.get('timed_out'):
            row['timed_out'] = True
            save(self.db, data)
            raise TimeoutError('offline poll timeout')
        if row['sid'] == 'SH006' and row['attempt'] == 1:
            return {'status': 'failed', 'provider_status': 'cancelled'}
        return {'status': 'succeeded', 'provider_status': 'SUCCEEDED'}

    def download_video(self, task, destination):
        data = read(self.db)
        row = data['tasks'][task]
        if row['sid'] == 'SH008' and not row.get('download_interrupted'):
            row['download_interrupted'] = True
            save(self.db, data)
            raise TimeoutError('offline partial download')
        shutil.copyfile(self.root / 'source.mp4', destination)


def scope(root):
    stack = ExitStack()
    api = OfflineSupplier(root)
    stack.enter_context(patch.object(Studio, 'client', lambda self: api))
    stack.enter_context(patch('contract.api_models.ensure_cloud_model'))
    stack.enter_context(patch('white_model.validate_video_submission', return_value=None))
    stack.enter_context(patch('agent.shot_assets.prepare', side_effect=lambda path, shot, cfg, **kw:
                              dict(shot, _reference_mode='first_frame', _asset_references=[])))
    return stack


def accept(studio, sid):
    studio.poll(sid)
    studio.review(sid, 'pass', 'OFFLINE FIXTURE: simulated review, not human acceptance')


def main(root):
    root.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    cfg = {'episode_file': 'episode.json', 'live_enabled': True, 'budget_seconds': 300,
           'reserve_seconds': 0, 'ffmpeg': FFMPEG, 'ffprobe': FFPROBE,
           'model': 'offline-fixture', 'require_audio': True}
    save(root / 'config.json', cfg)
    from stage_config import put_workflow
    put_workflow(root, {'name': 'offline-recovery', 'lock': {'offline-recovery': {
        'aspect_ratio': '9:16', 'resolution': '1080x1920', 'fps': 25}}})
    shots = [{'id': f'SH{i:03}', 'duration': 6, 'video_prompt': f'Original fixture shot {i}',
              'frame': 'frame.png', 'post_overlay': f'OFFLINE FIXTURE SH{i:03}'} for i in range(1, 11)]
    save(root / 'episode.json', {'shots': shots})
    save(root / 'offline-provider.json', {'attempts': {}, 'tasks': {}})
    # Deliberately synthetic, no downloaded/user media.
    subprocess.run([FFMPEG, '-v', 'error', '-y', '-f', 'lavfi', '-i',
                    'testsrc2=size=180x320:rate=25:duration=6', '-f', 'lavfi', '-i',
                    'sine=frequency=1000:sample_rate=48000:duration=6', '-c:v', 'libx264',
                    '-threads', '2', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-shortest', str(root / 'source.mp4')], check=True, capture_output=True)
    subprocess.run([FFMPEG, '-v', 'error', '-y', '-i', str(root / 'source.mp4'),
                    '-frames:v', '1', str(root / 'frame.png')], check=True, capture_output=True)
    faults = {}
    with scope(root):
        studio = Studio(root)
        studio.submit('SH001'); accept(studio, 'SH001')
        adopted = studio.state()['shots']['SH001'][0].copy()
        faults['disconnect'] = expect_error(lambda: studio.submit('SH002'), '提交连接中断')
        expect_error(lambda: studio.submit('SH002'), '未完成或结果不确定')
        expect_error(lambda: studio.poll('SH002'), '恢复任务编号')
        studio.attach('SH002', 'offline-SH002-0001'); accept(studio, 'SH002')
        faults['429'] = expect_error(lambda: studio.submit('SH003'), 'HTTP 429')
        studio.submit('SH003'); accept(studio, 'SH003')
        studio.submit('SH004')
        faults['poll_timeout'] = expect_error(lambda: studio.poll('SH004'), '编号已保留')
        expect_error(lambda: studio.submit('SH004'), '未完成或结果不确定')
        accept(studio, 'SH004')
        worker = subprocess.Popen([sys.executable, '-B', __file__, '--submit-wait', str(root)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, encoding='utf-8')
        try:
            worker.communicate(timeout=10)
            raise AssertionError('Submission process exited before forced termination')
        except subprocess.TimeoutExpired:
            worker.kill()
            out, err = worker.communicate(timeout=10)
        finally:
            if worker.poll() is None:
                worker.kill(); worker.wait(timeout=10)
        submitted = json.loads(out)
        assert submitted['pid'] == worker.pid and worker.returncode != 0, (out, err)
        before = studio.state()['shots']['SH005'][-1]['task_id']
        assert submitted['task_id'] == before
        child = subprocess.run([sys.executable, '-B', __file__, '--resume', str(root)],
                               check=True, capture_output=True, text=True, encoding='utf-8')
        facts = json.loads(child.stdout)
        assert facts['pid'] != os.getpid() and facts['task_id'] == before
        faults['process_restart'] = facts
        faults['forced_termination'] = {**submitted, 'exit_code': worker.returncode,
                                        'recovered_task_id': facts['task_id']}
        studio = Studio(root)
        studio.submit('SH006')
        faults['cancelled'] = studio.poll('SH006')
        assert '已取消' in faults['cancelled']
        assert read(root / 'offline-provider.json')['attempts']['SH006'] == 1
        studio.submit('SH006'); accept(studio, 'SH006')
        studio.submit('SH007')
        faults['edit_while_running'] = expect_error(
            lambda: assert_prompt_editable(SimpleNamespace(studio=studio), 'SH007'), '正在生成')
        accept(studio, 'SH007')
        old_file = root / studio.state()['shots']['SH007'][-1]['file']
        old_hash = file_hash(old_file)
        studio.review('SH007', 'revise', 'OFFLINE fixture explicit rework')
        episode = read(root / 'episode.json')
        episode['shots'][6]['video_prompt'] = 'Revised original fixture shot 7'
        save(root / 'episode.json', episode)
        studio = Studio(root)
        studio.submit('SH007'); accept(studio, 'SH007')
        assert file_hash(old_file) == old_hash
        assert len(studio.state()['shots']['SH007']) == 2
        studio.submit('SH008')
        faults['partial_download'] = expect_error(lambda: studio.poll('SH008'), '下载中断')
        assert studio.state()['shots']['SH008'][-1]['state'] == 'succeeded'
        accept(studio, 'SH008')
        for sid in ('SH009', 'SH010'):
            studio.submit(sid); accept(studio, sid)
        expect_error(lambda: studio.submit('SH001'), '已就绪')
        assert studio.state()['shots']['SH001'][0] == adopted
        counts = read(root / 'offline-provider.json')['attempts']
        assert counts == {f'SH{i:03}': (2 if i in (3, 6, 7) else 1) for i in range(1, 11)}, counts
        assert studio.auto_edit_ready()[0]
        master = Path(studio.assemble())
    bundle = read_edit_bundle(master.parent)
    assert [row['shot'] for row in bundle['manifest']] == [f'SH{i:03}' for i in range(1, 11)]
    assert bundle['manifest'][6]['version'] == 2
    spec = studio.output_spec()
    assert (spec['width'], spec['height'], spec['fps']) == (1080, 1920, 25)
    qc = check(master, 60, {**cfg, **spec}, strict=True)
    assert not qc['errors'], qc
    result = {'scope': 'offline provider simulation, synthetic media and simulated reviews; NOT real-provider/human acceptance',
              'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=PROGRAM, text=True).strip(),
              'seconds': round(time.monotonic() - started, 3), 'faults': faults,
              'submissions': counts, 'shots': len(bundle['manifest']), 'qc': qc, 'output_spec': spec,
              'master': str(master), 'sha256': file_hash(master)}
    save(root / 'result.json', result)
    print(json.dumps({'ok': True, 'shots': 10, 'seconds': result['seconds'], 'result': str(root / 'result.json')}, ensure_ascii=False))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('Usage: recovery_to_delivery_baseline.py NEW_OUTPUT_DIRECTORY')
    if sys.argv[1] == '--submit-wait':
        root = Path(sys.argv[2])
        with scope(root):
            studio = Studio(root)
            studio.submit('SH005')
            print(json.dumps({'pid': os.getpid(), 'task_id': studio.state()['shots']['SH005'][-1]['task_id']}), flush=True)
            time.sleep(60)  # Parent deliberately terminates this fixture process after durable submission.
    elif sys.argv[1] == '--resume':
        root = Path(sys.argv[2])
        with scope(root):
            studio = Studio(root)
            accept(studio, 'SH005')
            print(json.dumps({'pid': os.getpid(), 'task_id': studio.state()['shots']['SH005'][-1]['task_id']}))
    else:
        main(Path(sys.argv[1]).resolve())
