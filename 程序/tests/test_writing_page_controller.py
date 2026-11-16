from __future__ import annotations

from dataclasses import dataclass
import unittest

from writing_page_controller import ScriptListLoadController


@dataclass
class Row:
    item_id: str
    category: str
    modified_at: int


class ScriptListLoadControllerTests(unittest.TestCase):
    def test_batches_keep_rows_and_finish_only_after_iterator_exhausts(self):
        controller = ScriptListLoadController(('setting', 'script'))
        generation = controller.start([
            Row('a', 'setting', 1), Row('b', 'script', 3), Row('c', 'script', 2),
        ])

        first, first_done = controller.take_batch(2)
        second, second_done = controller.take_batch(2)

        self.assertEqual([row.item_id for row in first], ['a', 'b'])
        self.assertFalse(first_done)
        self.assertEqual([row.item_id for row in second], ['c'])
        self.assertTrue(second_done)
        self.assertTrue(controller.is_current(generation))
        self.assertEqual(controller.item_ids(), {'a', 'b', 'c'})

    def test_invalidation_rejects_old_generation_and_sorting_is_newest_first(self):
        controller = ScriptListLoadController(('setting', 'script'))
        old_generation = controller.start([Row('old', 'setting', 1)])
        controller.take_batch(24)
        new_generation = controller.start([
            Row('older', 'script', 1), Row('newer', 'script', 2),
        ])
        controller.take_batch(24)

        self.assertFalse(controller.is_current(old_generation))
        self.assertTrue(controller.is_current(new_generation))
        self.assertEqual(
            [row.item_id for row in controller.ordered_rows()['script']],
            ['newer', 'older'],
        )


class CancelScriptLoadTests(unittest.TestCase):
    def test_cancel_invalidates_batches_and_forgets_a_dead_after_job(self):
        """页面销毁时窗口已不在，after_cancel 抛 TclError 也要把待办批次清掉。"""
        import tkinter as tk
        import types
        from desktop_files_panel import ProjectFilesPanel

        def dead_cancel(job):
            raise tk.TclError('application has been destroyed')
        page = ProjectFilesPanel.__new__(ProjectFilesPanel)
        page.script_loader = ScriptListLoadController(('setting',))
        generation = page.script_loader.start([])
        page.script_load_job = 'after#1'
        page.page = types.SimpleNamespace(win=types.SimpleNamespace(after_cancel=dead_cancel))
        page.cancel_script_load()
        self.assertIsNone(page.script_load_job)
        self.assertFalse(page.script_loader.is_current(generation))


if __name__ == '__main__':
    unittest.main()
