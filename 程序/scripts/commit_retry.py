"""显式提交的本地回执。锁随进程退出释放，记录仅保存版本与摘要。"""
from contextlib import contextmanager
import hashlib
import json
import os
import subprocess
from pathlib import Path
import tempfile
import uuid


class RetryConflict(ValueError):
    pass


@contextmanager
def exclusive(path):
    """永久保留锁文件；删除锁文件会令两个进程分别持有不同的锁。"""
    stream = path.open('a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            if path.stat().st_size == 0:
                stream.write(b'x')
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RetryConflict('另一执行者持有当前工作树或轮次的提交锁') from exc
        else:
            import fcntl
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RetryConflict('另一执行者持有当前工作树或轮次的提交锁') from exc
        yield
    finally:
        stream.close()


def _digest(path):
    if path.is_symlink():
        return 'link:' + os.readlink(path)
    if not path.exists():
        return None
    if path.is_dir():
        raise RetryConflict('显式续接暂不支持目录型索引项：' + str(path))
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def _changed(old, new):
    return sorted(k for k in old.keys() | new.keys() if old.get(k) != new.get(k) or k not in old or k not in new)


class Receipt:
    def __init__(self, git, files, tests, message, key, evidence):
        self.git = git
        self.files = files
        self.temp_input = None
        self.evidence = evidence
        self.root = Path(self.output('rev-parse', '--show-toplevel')).resolve()
        common = Path(self.output('rev-parse', '--path-format=absolute', '--git-common-dir'))
        per_worktree = Path(self.output('rev-parse', '--absolute-git-dir'))
        self.directory = common / 'explicit-commit-receipts'
        self.directory.mkdir(exist_ok=True)
        self.path = self.directory / (key + '.json')
        self.round_lock = self.path.with_suffix('.lock')
        self.worktree_lock = per_worktree / 'explicit-commit.lock'
        self.identity = {'root': str(self.root), 'branch': self.output('symbolic-ref', 'HEAD'),
                         'files': sorted(set(files)), 'message': message, 'tests': sorted(set(tests))}
        self.data = {}

    def _private_tree(self, *args):
        # 先在私有索引计算期望树。崩溃恢复只接受操作前或本轮预先登记的版本。
        cwd = self.root / self.output('rev-parse', '--show-prefix')
        with tempfile.TemporaryDirectory(dir=self.directory) as tmp:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / 'index'))
            def run(*command):
                return subprocess.check_output(['git', *command], cwd=cwd, env=env,
                                               encoding='utf8', errors='strict').strip()
            run('read-tree', self.data['index'])
            run(*args)
            return run('write-tree')

    def _prepare(self, inputs, tree):
        self.check()
        self.data['next'] = {'inputs': inputs, 'index': tree}
        self.data['ready'] = False
        self.save()

    def _reconcile(self):
        nxt = self.data.get('next')
        if nxt is None:
            return
        current = self.index()
        inputs = self.inputs()
        before = self.data['inputs']
        if not ((inputs == before and current == self.data['index'])
                or (inputs == nxt['inputs'] and current in (self.data['index'], nxt['index']))):
            raise RetryConflict('中断期间输入或索引已变化：' +
                                '、'.join(_changed(before, inputs) or ['暂存区']))
        self.data.update(inputs=inputs, index=current)
        del self.data['next']
        self.save()

    def stage_inputs(self):
        tree = self._private_tree('add', '--', *self.files)
        self._prepare(self.data['inputs'], tree)
        self.output('add', '--', *self.files)
        self._finish(tree)

    def _finish(self, tree):
        if self.index() != tree or self.inputs() != self.data['next']['inputs']:
            raise RetryConflict('发布期间输入或暂存内容发生变化，保留现场')
        self._reconcile()

    def publish(self, relative, payload):
        # 证据和结果头必须由这一调用生成；不能凭路径收编之前留下的任意内容。
        self.check()
        path = self.root / relative
        if path.is_symlink():
            raise RetryConflict('输出路径为符号链接：' + relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
            temp = Path(tmp.name)
            tmp.write(payload)
            tmp.flush()
            os.fsync(tmp.fileno())
        try:
            pathspec = ':(top,literal)' + relative
            entry = self.output('ls-files', '--stage', '--', pathspec)
            mode = entry.split()[0] if entry else '100644'
            if mode not in ('100644', '100755'):
                raise RetryConflict('凭据或结果需为普通文件：' + relative)
            oid = self.output('hash-object', '-w', '--path=' + relative, str(temp))
            args = ('update-index', '--add', '--cacheinfo', mode + ',' + oid + ',' + relative)
            # cacheinfo 相对 Git 仓库根；在根下执行以避免程序目录被重复前缀。
            tree = self._private_tree('-C', str(self.root), *args)
            inputs = dict(self.data['inputs'])
            inputs[relative] = hashlib.sha256(payload).hexdigest()
            self.temp_input = temp.relative_to(self.root).as_posix()
            self._prepare(inputs, tree)
            os.replace(temp, path)
            self.output('-C', str(self.root), *args)
            self._finish(tree)
        finally:
            temp.unlink(missing_ok=True)
            self.temp_input = None

    def output(self, *args):
        result = self.git(*args)
        result.check_returncode()
        return result.stdout.rstrip('\r\n')

    def index(self):
        return self.output('write-tree')

    def head(self):
        proc = self.git('rev-parse', '-q', '--verify', 'HEAD')
        if proc.returncode not in (0, 1):
            proc.check_returncode()
        return proc.stdout.strip()

    def inputs(self):
        names = self.output('ls-files', '--full-name', '-z', '--cached', '--others', '--exclude-standard',
                            '--', *self.files).split('\0')
        changed = self.output('diff', '--cached', '--name-only', '--no-renames', '-z', '--', *self.files)
        names.extend(changed.split('\0'))
        if self.evidence:
            names.append(self.evidence)
        return {n: self._input_digest(n) for n in set(names) if n and n != self.temp_input}

    def _input_digest(self, name):
        path = self.root / name
        if path.is_dir() and not path.is_symlink():
            # Git tracks a submodule directory by its checked-out commit.
            return 'gitlink:' + self.output('-C', str(path), 'rev-parse', '--verify', 'HEAD')
        return _digest(path)

    def save(self):
        with tempfile.NamedTemporaryFile(dir=self.directory, delete=False, mode='w', encoding='utf8') as f:
            temp = Path(f.name)
            try:
                json.dump(self.data, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            finally:
                f.close()
        try:
            os.replace(temp, self.path)
        finally:
            temp.unlink(missing_ok=True)

    def open(self):
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding='utf8'))
            if self.data.get('identity') != self.identity:
                raise RetryConflict('轮次已归属其他工作树、分支或命令参数：' + self.path.name)
            if self.head() != self.data['parent']:
                if self.data.get('ready'):
                    return self.find_commit()
                raise RetryConflict('HEAD 已变化，尚无可核实的提交回执')
            if self.data.get('completed'):
                raise RetryConflict('已完成的提交已离开当前分支，拒绝再次提交：' + self.data['completed'])
            self._reconcile()
            self.check()
        return None

    def start(self):
        if not self.data:
            self.data = {'identity': self.identity, 'parent': self.head(), 'id': uuid.uuid4().hex}
            self.checkpoint()

    def checkpoint(self, ready=False):
        self.data.update(index=self.index(), inputs=self.inputs(), ready=ready)
        self.save()

    def check(self):
        if self.output('symbolic-ref', 'HEAD') != self.identity['branch'] or self.head() != self.data['parent']:
            raise RetryConflict('分支或 HEAD 已变化')
        problems = _changed(self.data['inputs'], self.inputs())
        current = self.index()
        if self.data['index'] != current:
            diff = self.output('diff-tree', '-r', '--name-only', '--no-renames', '-z', self.data['index'], current)
            problems.extend(filter(None, diff.split('\0')))
        if problems:
            raise RetryConflict('输入、证据或暂存区已变化：' + '、'.join(sorted(set(problems))))

    def find_commit(self):
        # 只认当前分支首父链中的真实提交，独立生成的同轮同树提交不能冒领。
        marker = 'Commit-Attempt: ' + self.data['id']
        matches = self.output('log', '--first-parent', '--fixed-strings', '--grep=' + marker, '--format=%H', 'HEAD')
        for oid in matches.splitlines():
            parents, tree, body = self.output('show', '-s', '--format=%P%x00%T%x00%B', oid).split('\0', 2)
            if (parents == self.data['parent'] and tree == self.data['index']
                    and body.splitlines()[0] == self.identity['message'].splitlines()[0]
                    and marker in body.splitlines()):
                if self.data.get('completed') not in (None, oid):
                    raise RetryConflict('已留存的提交号与当前候选不符')
                if not self.data.get('completed'):
                    self.data['completed'] = oid
                    self.save()
                return oid
        raise RetryConflict('HEAD 已移动，当前分支历史中没有可核实的原提交')
