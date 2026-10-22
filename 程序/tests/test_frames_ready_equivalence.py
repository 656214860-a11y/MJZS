"""frames_ready 的逐镜头判定抽成 _shot_frame_problem：与原内联循环体逐例对照。"""
import tempfile
import unittest
from pathlib import Path

import stage_parallel


def _legacy(source, episode, shot, base, aspect, frame_problem):
    problems = []
    any_frame = False
    sid = shot.get('id') or '?'
    frame = shot.get('frame')
    if shot.get('frame_deleted'):
        return ['%s 的首帧已删除，请恢复或重新指定首帧' % sid], False
    if not isinstance(frame, str) or not frame.strip():
        return ['%s 未配置首帧路径' % sid], False
    try:
        path = (base / frame).resolve()
        if not path.is_relative_to(base):
            problems.append('%s 的首帧路径越界' % sid)
        elif not path.is_file():
            problems.append('%s 缺首帧：%s' % (sid, path.name))
        else:
            any_frame = True
            if not path.stat().st_size:
                problems.append('%s 的首帧是空文件：%s' % (sid, path.name))
            else:
                problem = frame_problem(source, episode, shot, path, aspect_ratio=aspect)
                if problem:
                    problems.append('%s：%s' % (sid, problem))
    except (OSError, ValueError, RuntimeError):
        problems.append('%s 的首帧路径无法读取' % sid)
    return problems, any_frame


class ShotFrameProblemEquivalence(unittest.TestCase):
    def test_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            (base / 'ok.png').write_bytes(b'x')
            (base / 'empty.png').write_bytes(b'')

            def fp_none(*a, **k):
                return None

            def fp_msg(*a, **k):
                return '比例不符'

            def fp_oserror(*a, **k):
                raise OSError('boom')

            shots = [
                {'id': 'S1', 'frame_deleted': True, 'frame': 'ok.png'},
                {'id': 'S2'}, {'id': 'S3', 'frame': '  '}, {'frame': 5},
                {'id': 'S4', 'frame': '../outside.png'},
                {'id': 'S5', 'frame': 'missing.png'},
                {'id': 'S6', 'frame': 'empty.png'},
                {'id': 'S7', 'frame': 'ok.png'},
                {'id': 'S8', 'frame': 'a\0b.png'},
            ]
            n = 0
            for shot in shots:
                for fp in (fp_none, fp_msg, fp_oserror):
                    old_p, old_f = _legacy('src', {}, shot, base, '9:16', fp)
                    problem, found = stage_parallel._shot_frame_problem('src', {}, shot, base, '9:16', fp)
                    self.assertEqual(([problem] if problem else []), old_p, shot)
                    self.assertEqual(found, old_f, shot)
                    n += 1
            self.assertEqual(n, 27)


if __name__ == '__main__':
    unittest.main()
