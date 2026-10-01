# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class BlenderLaunchTests(unittest.TestCase):
    def test_blender_launch_uses_platform_process_boundary(self):
        import native_apps

        class Process:
            def poll(self):
                return None

        with tempfile.TemporaryDirectory() as td:
            executable = Path(td) / 'blender.exe'
            executable.write_bytes(b'')
            original_process = native_apps._blender_process
            self.addCleanup(setattr, native_apps, '_blender_process', original_process)
            native_apps._blender_process = None
            with patch('white_model.find_blender', return_value=executable), \
                 patch.object(native_apps, 'launch_windows_app', return_value=Process()) as launch:
                self.assertEqual(native_apps.open_blender(), executable)
            self.assertEqual(launch.call_args.args, (executable, 'Blender'))
            self.assertEqual(launch.call_args.kwargs['args'], [str(executable)])
            self.assertEqual(launch.call_args.kwargs['cwd'], executable.parent)
