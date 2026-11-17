import hashlib
import json
import os
import time
import uuid
import threading
from pathlib import Path
# 第 34 期第 9 条：`urllib.request` 会连 ssl 一起拉起来（libssl＋libcrypto 常驻约 4.4 MB），
# 而 core 在启动路径上被到处 import——改成真要发请求时再 import（只有下面两处用到）。


def read(path):
    from agent.publication import access
    with access():
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def read_json(path, default=None):
    """宽松版 read：文件不存在、读不动、格式坏都返回 default。

    全程序「读得出来就用、读不出来就当没有」只有这一份实现——各写一遍 try 最容易漏的是
    「文件不存在」这一种。它**不**区分「内容为空」与「内容坏掉」：要区分（例如设置文件被
    手工改坏必须报错）时用 read()，或走 project_settings.read_prefs。
    """
    try:
        return read(path)
    except (OSError, ValueError):
        return default


_PUBLISH_LOCKS = tuple(threading.RLock() for _ in range(64))

def replace(source, target):
    """同路径发布串行化，避免本进程多个写线程争抢 Windows 替换句柄。"""
    key = os.path.normcase(os.path.abspath(target))
    from agent.publication import access, before_replace
    with access(), _PUBLISH_LOCKS[hash(key) % len(_PUBLISH_LOCKS)]:
        before_replace(target)
        _replace_locked(source, target)


def _replace_locked(source, target):
    """把临时文件原子换到正式路径；Windows 上目标正被别的线程读着时短暂重试。

    Windows 的 os.replace 需要能独占目标（Python 的 open 不带 FILE_SHARE_DELETE），而界面线程
    每 150ms 就在读 ui_settings.json、进度.json 这类文件；后台线程恰好这时保存，就会拿到
    WinError 5「拒绝访问」——明明不是错误，却让整步制作报「未完成」。读方几毫秒内就关掉句柄，
    这里退避重试；真的换不动（被外部程序锁住）最后仍然抛出，调用方照常报告失败。
    """
    source = Path(source)
    target = Path(target)
    for attempt in range(5):
        try:
            os.replace(source, target)
            # 所有原子成果发布都在这里收口；页面无需靠刷新或 mtime 轮询猜测新内容。
            from infra.file_cache import published
            published(target)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.05)


def rename_with_references(source, target, prepare):
    """排他改名及已验证引用更新共用事务；竞争目标绝不覆盖。"""
    from agent import publication
    from infra.file_cache import published
    source, target = Path(source), Path(target)
    linked = False
    try:
        with publication.transaction():
            updates = prepare()
            os.link(source, target)
            linked = True
            publication.before_replace(source)
            for path, payload in updates:
                save(path, payload)
            source.unlink()
            published(source)
            published(target)
    except BaseException:
        if linked:
            target.unlink(missing_ok=True)
            published(target)
        raise


def save(path, obj, *, durable=True):
    save_text(path, json.dumps(obj, ensure_ascii=False, indent=2), durable=durable)


def temporary_path(path, suffix='.tmp'):
    """返回与目标同目录、仅属于本次写入的临时路径。

    临时文件必须在目标目录内，`os.replace` 才能保持同卷原子替换；也不能固定叫
    ``*.tmp``，否则两个后台任务同时写同一成果会互相删除对方的暂存文件。
    """
    path = Path(path)
    return path.with_name(path.name + '.' + uuid.uuid4().hex + suffix)


def save_text(path, text, encoding="utf-8", *, durable=True):
    """原子保存用户可见文本，避免崩溃或并发读取留下半份创作文件。

    JSON 和 Markdown 都应走同一个替换入口；否则 Windows 上界面正在读取文件时，
    只有部分产物会重试，用户就会看到“保存成功”但磁盘上的剧本不完整。

    ``durable=False`` 只给本机可重建的运行记录（后台排队、执行记录）用：照样先写临时文件
    再原子替换，进程崩溃后读到的仍是完整的旧版或新版；但不等落盘，断电后可能读出全零或
    半份，读的一方必须能把坏文件当空记录重建。用户成果一律用默认值。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = temporary_path(path)
    try:
        with temp.open('w', encoding=encoding) as stream:
            stream.write(str(text))
            stream.flush()
            if durable:
                os.fsync(stream.fileno())
        replace(temp, path)
    finally:
        # replace 成功后临时文件已不存在；失败时清理本轮残留，旧正式文件不受影响。
        if temp.exists():
            temp.unlink()


def save_bytes(path, data):
    """二进制成果的原子保存版本（PNG/媒体下载等）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = temporary_path(path)
    try:
        with temp.open('wb') as stream:
            stream.write(bytes(data))
            stream.flush()
            os.fsync(stream.fileno())
        replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def save_file(path, source, digest=None):
    """文件级原子保存：按块复制，大媒体不进内存；可选摘要校验。

    与 ``save_bytes`` 共用 ``temporary_path`` + ``replace``，因此同样登记发布事务
    与缓存失效。复制期间计算 sha256 并核对来源长度：来源仍在增长或内容与调用方
    预期不符时放弃发布，旧成果不受影响。
    """
    path = Path(path)
    source = Path(source)
    path.parent.mkdir(parents=True, exist_ok=True)
    expected = source.stat().st_size
    temp = temporary_path(path)
    written = 0
    actual = hashlib.sha256()
    try:
        with source.open('rb') as src, temp.open('wb') as dst:
            for block in iter(lambda: src.read(1024 * 1024), b''):
                written += len(block)
                actual.update(block)
                dst.write(block)
            dst.flush()
            os.fsync(dst.fileno())
        if written != expected:
            raise ValueError('来源文件在复制期间发生变化，未发布成果。')
        if digest is not None and str(digest) != actual.hexdigest():
            raise ValueError('来源文件摘要与预期不一致，未发布成果。')
        replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()
    return actual.hexdigest()


def restore_bytes(path, previous):
    """回滚本轮原子发布：恢复旧字节，或受控清理此前不存在的新文件。"""
    if previous is not None:
        save_bytes(path, previous)
        return
    from infra.file_cache import remove_temporary_file
    remove_temporary_file(path)


def save_bytes_new(path, data):
    """原子创建一个此前不存在的二进制成果，绝不替换同名文件。

    首帧导入和分镜归档会先生成唯一名称，但“名称唯一”不是并发安全保证。先完整写入
    同目录临时文件，再用硬链接原子发布：目标若已存在会抛 ``FileExistsError``，已有
    用户文件不会被覆盖，也不会让读取方看到半个 PNG/JSON。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = temporary_path(path)
    try:
        temp.write_bytes(bytes(data))
        os.link(temp, path)  # 同目录同卷；目标存在时以 FileExistsError 安全失败。
        from infra.file_cache import published
        published(path)
    finally:
        if temp.exists():
            temp.unlink()


def fingerprint(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def copy_file_new(path, source, validate):
    """有界复制、校验临时副本后原子创建；碰撞或失败绝不覆盖旧成果。"""
    if not callable(validate):
        raise TypeError('文件发布需要校验器')
    path, source = Path(path), Path(source)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = temporary_path(path)
    initial = source.stat()
    digest = hashlib.sha256()
    try:
        with source.open('rb') as src, temp.open('xb') as dst:
            for block in iter(lambda: src.read(1024 * 1024), b''):
                dst.write(block)
                digest.update(block)
            dst.flush()
            os.fsync(dst.fileno())
        after = source.stat()
        if (initial.st_size != after.st_size or initial.st_mtime_ns != after.st_mtime_ns
                or temp.stat().st_size != initial.st_size or file_hash(source) != digest.hexdigest()):
            raise OSError('复制期间源文件发生变化，请重试')
        if validate(temp) is False:
            raise ValueError('文件校验未通过，未发布成果')
        if file_hash(temp) != digest.hexdigest():
            raise OSError('校验期间临时文件发生变化，未发布成果')
        os.link(temp, path)
        from infra.file_cache import published
        published(path)
        return path
    finally:
        if temp.exists():
            temp.unlink()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def command(args, cwd=None):
    import contract.platform_tools as platform_tools       # 第 34 期第 9 条：按需加载，保持启动路径轻量
    try:
        r = platform_tools.run_process([str(x) for x in args], capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", cwd=cwd)
    except FileNotFoundError:
        raise RuntimeError(f"找不到程序 {args[0]}，请安装或在 config.json 填绝对路径") from None
    if r.returncode:
        raise RuntimeError(f"本地媒体处理失败：{r.stderr[-1800:]}")
    return r.stdout


def request(url, payload=None, headers=None, raw=False):
    import contract.platform_tools as platform_tools, urllib.error    # 第 34 期第 9 条：HTTP 栈按需加载
    data = None if payload is None else json.dumps(payload).encode()
    h = dict(headers or {})
    if data is not None:
        h["Content-Type"] = "application/json"
    try:
        with platform_tools.open_https(url, data=data, headers=h, timeout=60) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}，请检查服务配置/余额/权限；未打印响应以保护密钥") from None
    except TimeoutError:
        raise RuntimeError("请求超时，请检查网络和服务是否响应") from None
    except urllib.error.URLError:
        raise RuntimeError("网络连接失败，请检查地址、服务是否启动和网络") from None
    return body if raw else json.loads(body)


def download(url, dest):
    import contract.platform_tools as platform_tools                       # 第 34 期第 9 条：HTTP 栈按需加载
    if not url.startswith("https://"):
        raise ValueError("云视频下载链接必须使用 HTTPS")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = temporary_path(dest, '.download')
    try:
        with platform_tools.open_https(url, timeout=120) as r, tmp.open("wb") as f:
            if not r.geturl().startswith("https://"):
                raise ValueError("拒绝非 HTTPS 下载重定向")
            total = 0
            for chunk in iter(lambda: r.read(1024 * 1024), b""):
                total += len(chunk)
                if total > 1024 ** 3:
                    raise ValueError("单镜下载超过 1GB，已停止")
                f.write(chunk)
        if not tmp.stat().st_size:
            raise ValueError("下载文件为空")
        # 下载完成后才把临时文件发布为成果；沿用 Windows 读锁的有界重试规则。
        replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink()
