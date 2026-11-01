# -*- coding: utf-8 -*-
"""R2178 J13／J14：重定向拒绝与子进程登记各只有一份实现，各适配器共用。"""
import subprocess
import sys
import unittest
from unittest import mock
from urllib.request import HTTPRedirectHandler

import api_endpoints
import local_video
import seedream_api
import tts_api
import workflow_engines
import workflow_process_registry
from agent.video import VideoAdapter
from agent.wan import WanAdapter


class NoRedirectSharedTests(unittest.TestCase):
    def test_every_adapter_uses_the_one_implementation(self):
        for module in (local_video, seedream_api, tts_api):
            self.assertIs(module.no_redirect, api_endpoints.no_redirect, module.__name__)

    def test_redirects_are_refused(self):
        handler = api_endpoints.no_redirect()
        self.assertIsInstance(handler, HTTPRedirectHandler)
        self.assertIsNone(handler.redirect_request(None, None, 302, 'Found', {}, 'http://elsewhere/'))


class RunRegisteredSharedTests(unittest.TestCase):
    def test_engine_run_delegates_and_unregisters(self):
        done = workflow_engines._run([sys.executable, '-c', 'import sys;sys.exit(3)'], '.', '', subprocess.DEVNULL,
                                     subprocess.DEVNULL, 30)
        self.assertEqual(done, 3)
        self.assertEqual(workflow_process_registry.processes('.'), [])

    def test_timeout_kills_and_names_the_caller(self):
        with self.assertRaises(ValueError) as caught:
            workflow_process_registry.run_registered(
                [sys.executable, '-c', 'import time;time.sleep(30)'], '.', '',
                (subprocess.DEVNULL, subprocess.DEVNULL), 0.3, timeout_label='某引擎运行超时')
        self.assertIn('某引擎运行超时', str(caught.exception))
        self.assertEqual(workflow_process_registry.processes('.'), [])


class WanAdapterContractTests(unittest.TestCase):
    def test_wan_adapter_is_a_video_adapter(self):
        self.assertTrue(issubclass(WanAdapter, VideoAdapter))


if __name__ == '__main__':
    unittest.main()
