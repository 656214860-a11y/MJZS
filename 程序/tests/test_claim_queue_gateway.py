"""旧队列 CLI 必须只转发到 common-dir 权威入口。"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


PROGRAM = Path(__file__).resolve().parent.parent
SCRIPT = PROGRAM / "维护记录" / "claim_queue.py"
SPEC = importlib.util.spec_from_file_location("claim_queue_gateway_for_tests", SCRIPT)
legacy = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = legacy
SPEC.loader.exec_module(legacy)


class ClaimQueueGatewayTests(unittest.TestCase):
    def test_legacy_show_forwards_without_a_private_queue_default(self):
        calls = []
        authority = SimpleNamespace(main=lambda argv: calls.append(argv) or 0)
        with mock.patch.object(legacy, "_load_round_claim", return_value=authority):
            self.assertEqual(legacy.main(["show"]), 0)
        self.assertEqual(calls, [["show"]])

    def test_legacy_claim_preserves_arguments_for_authority_validation(self):
        calls = []
        authority = SimpleNamespace(main=lambda argv: calls.append(argv) or 2)
        argv = ["claim", "T1", "--owner", "alice", "--queue", "old-snapshot.json"]
        with mock.patch.object(legacy, "_load_round_claim", return_value=authority):
            self.assertEqual(legacy.main(argv), 2)
        self.assertEqual(calls, [argv])

    def test_legacy_module_has_no_worktree_queue_constant(self):
        self.assertFalse(hasattr(legacy, "DEFAULT"))
        self.assertFalse(hasattr(legacy, "publish"))
