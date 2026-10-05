"""Exit dispatch contract with fake launchers: never start maintenance workers."""
import contextlib
import io
import unittest
from unittest.mock import patch

import exit_maintenance


class ExitMaintenanceTests(unittest.TestCase):
    def run_dispatch(self, forced=False, failure=None):
        events = []
        output = io.StringIO()
        def launcher(name):
            def launch(program):
                events.append(name)
                self.assertIs(program, self.program)
                if failure and failure[0] == name:
                    raise failure[1]
            return launch
        self.program = object()
        with contextlib.ExitStack() as stack:
            for module, name in [('storage_maintenance', 'storage'),
                                 ('log_maintenance', 'logs'),
                                 ('workspace_maintenance', 'workspace')]:
                stack.enter_context(patch(module + '.launch_cleanup', launcher(name)))
            stack.enter_context(contextlib.redirect_stdout(output))
            result = exit_maintenance.launch_cleanup(self.program, forced=forced)
        return result, events, output.getvalue()

    def test_normal_dispatch_is_not_completion(self):
        result, events, output = self.run_dispatch()
        self.assertEqual(events, ['storage', 'logs', 'workspace'])
        self.assertEqual(set(result.values()), {'scheduled'})
        self.assertIn('completion=unobserved', output)
        self.assertLess(len(output), 256)

    def test_forced_dispatch_summary(self):
        result, events, output = self.run_dispatch(forced=True)
        self.assertEqual(events, ['storage'])
        self.assertEqual(result, dict(storage='scheduled', logs='skipped-force',
                                      workspace='skipped-force'))

    def test_optional_errors_are_sanitized_and_independent(self):
        for name in ('logs', 'workspace'):
            with self.subTest(name=name):
                result, events, output = self.run_dispatch(
                    failure=(name, OSError('SECRET D:/private/project')))
                self.assertEqual(events, ['storage', 'logs', 'workspace'])
                self.assertEqual(result[name], 'launch-failed')
                self.assertNotIn('SECRET', output)
                self.assertNotIn('private', output)

    def test_storage_exception_is_preserved_and_summarized(self):
        error = OSError('SECRET')
        output = io.StringIO()
        with patch('storage_maintenance.launch_cleanup', side_effect=error), \
             patch('log_maintenance.launch_cleanup') as logs, \
             contextlib.redirect_stdout(output), self.assertRaises(OSError) as caught:
            exit_maintenance.launch_cleanup(object())
        self.assertIs(caught.exception, error)
        logs.assert_not_called()
        self.assertIn('storage=launch-failed', output.getvalue())
        self.assertIn('logs=not-attempted', output.getvalue())
        self.assertNotIn('SECRET', output.getvalue())

    def test_broken_summary_stream_does_not_mask_storage_error(self):
        error = OSError('original')
        with patch('storage_maintenance.launch_cleanup', side_effect=error), \
             patch('builtins.print', side_effect=OSError('closed')), \
             self.assertRaises(OSError) as caught:
            exit_maintenance.launch_cleanup(object())
        self.assertIs(caught.exception, error)


if __name__ == '__main__':
    unittest.main()
