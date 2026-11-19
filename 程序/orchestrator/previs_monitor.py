"""白模预演的制作监视页（第 47 期第 2 条）。

用户这一轮的要求：白模预演里点「手动制作白模」时，要在浏览器里看制作（HTTP 监视页），
不要再另外弹一个桌面 Blender 窗口出来。这一页就是那个浏览器页面：进程内起一个只读的本地
HTTP 服务，按这一批的 state（状态、Blender 脚本写出来的进度 JSON）现场生成 HTML——不落模板
文件、不依赖第三方库、只监听 127.0.0.1，端口由系统分配（撞不上端口）。

工作线程只写 state（status／progress／progress JSON），这一页只读；两边不共享 Tk 上下文。
"""
import infra.app_logging as app_logging
import infra.executors as executors
import html,time,webbrowser
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from infra.file_cache import read_json

TITLE = '白模预演 · 制作监视页'
NOTE = ('这一页由助手在本机生成：只看不改，每 %d 秒自己刷一次。关掉浏览器不影响制作；'
        '这一批结束它就停在最后一次结果上，继续看成品请回白模页用「播放视频」「打开工程调整」。')
REFRESH_SECONDS = 5
STAGE_LABELS = {'scene': '准备场景', 'render': '渲染中', 'encoding': '合成视频', 'cancelled': '渲染已停止'}


def progress_of(state, sid):
    """这一镜的进度原文（Blender 脚本写出来的那份 JSON）；没有就返回 '制作中'。"""
    directory = str((state or {}).get('log_dir') or '')
    if not directory:
        return '制作中'
    path = Path(directory) / (str(sid) + '_进度.json')
    try:
        data = read_json(path)
    except (OSError, ValueError):
        return '制作中'
    if not isinstance(data, dict) or str(data.get('shot_id')) != str(sid):
        return '制作中'
    step = str(data.get('stage') or '')
    if step == 'render':
        done, total = data.get('completed'), data.get('total')
        if isinstance(done, bool) or isinstance(total, bool):
            return STAGE_LABELS['render']
        if isinstance(done, int) and isinstance(total, int) and total > 0 and 0 <= done <= total:
            return '渲染 %d/%d 帧（%d%%）' % (done, total, round(done * 100.0 / total))
        return STAGE_LABELS['render']
    return STAGE_LABELS.get(step, '制作中')


def rows(state, project):
    """这一批的镜头行：(镜头, 状态, 进度)。只摆本项目的记录，别的项目不往这一页上放。"""
    prefix = str(project) + '|'
    result = []
    for key, status in sorted(((state or {}).get('status') or {}).items()):
        if not str(key).startswith(prefix):
            continue
        sid = str(key)[len(prefix):]
        text = str(status)
        progress = progress_of(state, sid)
        # 收尾状态没有「进度」可言：写了百分比反而像还在跑。
        if text == '已就绪' or text.startswith('失败') or '停止' in text:
            progress = '—'
        result.append((sid, text, progress))
    return result


def render(state, project, title=TITLE):
    """整页 HTML：抬头 ＋ 这批的结局那句话 ＋ 镜头表 ＋ 页脚。纯字符串拼出来，自检直接读它。"""
    state = state or {}
    parts = ['<!doctype html>', '<html lang="zh-CN"><head><meta charset="utf-8">',
             '<meta http-equiv="refresh" content="%d">' % REFRESH_SECONDS,
             '<title>%s</title>' % html.escape(str(title)),
             '<style>body{font-family:"Microsoft YaHei UI",sans-serif;margin:24px;color:#1f2a37}'
             'h1{font-size:20px;margin:0 0 6px}p{color:#4b5563;margin:4px 0}'
             'table{border-collapse:collapse;margin-top:12px;min-width:660px}'
             'th,td{border:1px solid #d6dde6;padding:6px 10px;font-size:13px;text-align:left}'
             'th{background:#f2f5f9}td.on{color:#1a7f37}td.bad{color:#b3261e}'
             'pre.engine-log{background:#0f172a;color:#cbd5e1;padding:10px 12px;'
             'font-family:Consolas,"Courier New",monospace;font-size:12px;'
             'white-space:pre-wrap;word-break:break-all;max-height:320px;overflow:auto;margin-top:16px}'
             'footer{margin-top:16px;color:#718196;font-size:12px}</style></head><body>',
             '<h1>%s</h1>' % html.escape(str(title)),
             '<p>%s</p>' % html.escape(NOTE % REFRESH_SECONDS)]
    summary = str(state.get('summary') or '')
    if summary:
        parts.append('<p><b>%s</b></p>' % html.escape(summary))
    parts.append('<p>%s</p>' % html.escape('正在制作' if state.get('busy') else '这一批已经收工'))
    table = rows(state, project)
    if not table:
        parts.append('<p>这一批还没有镜头记录。</p>')
    else:
        parts.append('<table><tr><th>镜头</th><th>状态</th><th>进度</th></tr>')
        for sid, status, progress in table:
            style = ' class="bad"' if status.startswith('失败') else (
                ' class="on"' if status == '已就绪' else '')
            parts.append('<tr><td>%s</td><td%s>%s</td><td>%s</td></tr>' % (
                html.escape(sid), style, html.escape(status), html.escape(progress or '—')))
        parts.append('</table>')
    engine_log = state.get('engine_log')
    if engine_log:
        parts.append('<pre class="engine-log">%s</pre>' % html.escape('\n'.join(str(x) for x in engine_log[-200:])))
    parts.append('<footer>%s</footer>' % html.escape('刷新于 ' + time.strftime('%Y-%m-%d %H:%M:%S')))
    parts.append('</body></html>')
    return '\n'.join(parts)


def handler(page):
    """把「现场生成这一页」绑成一个只读的 GET 处理器；只答 GET，别的什么都不做。"""
    class Monitor(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.0'

        def do_GET(self):
            try:
                body = page().encode('utf-8')
            except Exception as exc:
                body = ('白模监视页读取失败：' + str(exc)).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            return None
    return Monitor


def start(state, project, title=TITLE, opener=None):
    """起监视页并用浏览器打开：返回 (url, server)。

    已经在跑就沿用同一个（手动连点两次不会开两扇窗）；起不来时返回 None——制作照旧跑，
    页面那一行状态会说清没有监视页，绝不因为一个监视页把整批制作挡下来。
    """
    if not isinstance(state, dict):
        return None
    existing = state.get('monitor')
    if existing:
        return existing
    try:
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler(lambda: render(state, project, title)))
    except OSError:
        return None
    server.daemon_threads = True
    url = 'http://127.0.0.1:%d/' % server.server_address[1]
    executors.submit('stream', server.serve_forever, label='previs-monitor')
    try:
        (opener or webbrowser.open)(url)
    except Exception:
        app_logging.swallowed()
    state['monitor'] = (url, server)
    return state['monitor']


def url_of(state):
    """这一批的监视页地址（没有就返回空串）。"""
    monitor = (state or {}).get('monitor') if isinstance(state, dict) else None
    return str(monitor[0]) if monitor else ''


def stop(state):
    """收摊：把监视页的服务停掉（强制停止或关程序时调用；已经停了是空操作）。"""
    if not isinstance(state, dict):
        return None
    monitor = state.pop('monitor', None)
    if not monitor:
        return None
    try:
        monitor[1].shutdown()
        monitor[1].server_close()
    except Exception:
        return None
    return monitor[0]
