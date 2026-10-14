"""O35 之后：显式采用某个已验收版本（回退）与交付页版本选择窗。"""
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

import engine
from engine import adopted_edit_version, adoption_summary


def version(number, review='pass', qc=True):
    return {'version': number, 'review': review, 'state': 'downloaded', 'qc_pass': qc,
            'file': 'v%d.mp4' % number, 'sha256': ''}


class FakeStudio:
    """只带 Studio 用到的最小状态，复用真实 version_rows／pin_version。"""
    version_rows = engine.Studio.version_rows
    pin_version = engine.Studio.pin_version

    def __init__(self, folder, versions):
        self.root, self.db = Path(folder), Path(folder) / 'state.json'
        for item in versions:                       # 采用判定会核对文件存在与摘要
            target = self.root / item['file']
            target.write_bytes(item['file'].encode())
            item['sha256'] = engine.file_hash(target)
        self.data = {'schema': 1, 'shots': {'SH001': versions}}
        self.episode = {'shots': [{'id': 'SH001'}]}

    @contextmanager
    def lock(self):
        yield

    def state(self):
        return json.loads(self.db.read_text(encoding='utf-8')) if self.db.is_file() else self.data


class PinTests(unittest.TestCase):
    def test_pin_selects_older_approved_version_and_unpin_restores_latest(self):
        versions = [version(1), version(2), version(3, review='pending')]
        self.assertEqual(adopted_edit_version(versions)[0]['version'], 2)
        versions[0]['pinned'] = True
        self.assertEqual(adopted_edit_version(versions)[0]['version'], 1)
        summary = adoption_summary(None, versions)
        self.assertTrue(summary['pinned'])
        self.assertFalse(summary['latest_is_adopted'])
        # 锁定落在未验收版本上无效：仍按最后一条已验收版本。
        versions[0].pop('pinned')
        versions[2]['pinned'] = True
        self.assertEqual(adopted_edit_version(versions)[0]['version'], 2)

    def test_studio_pin_only_accepts_approved_and_keeps_every_version(self):
        with tempfile.TemporaryDirectory() as folder:
            studio = FakeStudio(folder, [version(1), version(2), version(3, review='pending')])
            self.assertEqual(studio.pin_version('SH001', 1), 1)
            rows = studio.version_rows('SH001')
            self.assertEqual([row['version'] for row in rows], [1, 2, 3])
            self.assertEqual([row['adopted'] for row in rows], [True, False, False])
            self.assertEqual([row['approved'] for row in rows], [True, True, False])
            with self.assertRaises(ValueError):
                studio.pin_version('SH001', 3)
            with self.assertRaises(ValueError):
                studio.pin_version('SH001', 9)
            studio.pin_version('SH001', 2)
            self.assertEqual([row['pinned'] for row in studio.version_rows('SH001')], [False, True, False])
            studio.pin_version('SH001', None)
            rows = studio.version_rows('SH001')
            self.assertFalse(any(row['pinned'] for row in rows))
            self.assertEqual([row['adopted'] for row in rows], [False, True, False])
            with self.assertRaises(ValueError):
                studio.pin_version('NOPE', 1)


class PickerTests(unittest.TestCase):
    def test_picker_adopts_selected_version_and_restores(self):
        import tkinter as tk
        root = tk.Tk()
        self.addCleanup(root.destroy)
        import version_picker
        with tempfile.TemporaryDirectory() as folder:
            studio = FakeStudio(folder, [version(1), version(2)])

            class App:
                win, status = root, tk.StringVar(master=root)
            App.studio = studio
            win = version_picker.open_picker(App)
            self.addCleanup(win.destroy)
            seams = win._picker
            self.assertEqual(len(seams['table'].get_children()), 2)
            self.assertFalse(seams['adopt']())                       # 未选择
            seams['table'].selection_set('1')
            self.assertTrue(seams['adopt']())
            self.assertEqual(seams['table'].set('1', 'use'), '锁定采用')
            self.assertIn('v1', App.status.get())
            self.assertTrue(seams['restore']())
            self.assertEqual(seams['table'].set('2', 'use'), '当前采用')
            studio.episode['shots'] = []
            with self.assertRaises(ValueError):
                version_picker.open_picker(App)


if __name__ == '__main__':
    unittest.main()
