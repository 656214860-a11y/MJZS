"""parse_worktree_list 重构前后等价：旧实现原样留作基准，边界输入逐一对比（R1785）。"""
import unittest
from pathlib import Path

import workspace_maintenance as wm


def legacy_parse(text):
    """重构前的实现（elif 链），仅作对照基准；不要改它。"""
    entries = []
    current = None
    for line in (text or "").splitlines():
        if not line.strip():
            if current and current.get("path"):
                entries.append(current)
            current = None
            continue
        if current is None:
            current = {"path": None, "head": "", "branch": None,
                       "locked": False, "prunable": False}
        if line.startswith("worktree "):
            current["path"] = Path(wm._decode_porcelain_path(line[len("worktree "):]))
        elif line.startswith("HEAD "):
            current["head"] = line[len("HEAD "):].strip()
        elif line.startswith("branch "):
            current["branch"] = wm._decode_porcelain_path(line[len("branch "):])
        elif line == "detached":
            current["branch"] = None
        elif line.startswith("locked"):
            current["locked"] = True
        elif line.startswith("prunable"):
            current["prunable"] = True
    if current and current.get("path"):
        entries.append(current)
    return tuple(entries)


CASES = {
    'empty': '',
    'none-like': '   \n\n',
    'one': 'worktree D:/repo\nHEAD abc\nbranch refs/heads/master\n',
    'quoted-with-space': 'worktree "D:/my repo/.wt/a b"\nHEAD abc \nbranch refs/heads/x\n\n',
    'locked-with-reason': 'worktree D:/r\nlocked 正在用\n\nworktree D:/s\nprunable: gone\n',
    'detached-after-branch': 'worktree D:/r\nbranch refs/heads/m\ndetached\n',
    'head-without-space': 'worktree D:/r\nHEAD\nbranch\n',
    'unknown-lines': 'worktree D:/r\nbare\nfoo bar\n',
    'no-path-entry-dropped': 'HEAD abc\nbranch refs/heads/m\n\nworktree D:/ok\n',
    'multiple-blank-lines': 'worktree D:/a\n\n\n\nworktree D:/b\n',
    'crlf': 'worktree D:/a\r\nHEAD 1\r\n\r\nworktree D:/b\r\nlocked\r\n',
    'no-trailing-newline': 'worktree D:/a\nHEAD 1',
}


class ParseWorktreeListEquivalenceTests(unittest.TestCase):
    def test_new_matches_legacy_on_edge_inputs(self):
        for name, text in CASES.items():
            with self.subTest(case=name):
                self.assertEqual(wm.parse_worktree_list(text), legacy_parse(text))

    def test_none_input(self):
        self.assertEqual(wm.parse_worktree_list(None), legacy_parse(None))


if __name__ == '__main__':
    unittest.main()
