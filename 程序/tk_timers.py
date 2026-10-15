"""窗口定时器：窗口销毁时自动取消，避免退出后控制台出现
invalid command name "…poll" ("after" script)。

Tkinter 销毁窗口时会删除 after 回调对应的 Tcl 命令，却不会取消已登记的定时器；
定时器到期后执行已删除的命令，就在 Tcl 里报错。凡是「按固定间隔重复刷新自己窗口」
的地方都应改用 repeat()，不要在回调里直接再 after 一次。
"""
import app_logging
import queue
import threading
import time


def repeat(widget,interval,callback):
    """每 interval 毫秒调用 callback，直到 widget 被销毁或调用返回的 stop()。

    callback 里调用 stop() 可以提前结束循环（例如批次已经没有待处理项）。
    """
    state={'id':None,'stopped':False}
    def stop(event=None):
        if event is not None and event.widget is not widget:return
        state['stopped']=True
        pending,state['id']=state['id'],None
        if pending:
            try:widget.after_cancel(pending)
            except Exception:app_logging.swallowed()
    def tick():
        state['id']=None
        if state['stopped'] or not widget.winfo_exists():return
        try:callback()
        finally:
            if not state['stopped'] and widget.winfo_exists():state['id']=widget.after(interval,tick)
    widget.bind('<Destroy>',stop,add='+')
    state['id']=widget.after(interval,tick)
    return stop

def watch_changes(widget,snapshot,refresh,interval=1500,errors=(OSError,ValueError,KeyError)):
    """观察快照变化：同一快照连续出现两次、且与上次已应用的不同，才调用一次 refresh()。

    连续两次相同是为了跳过「文件正写到一半」的中间态；refresh() 返回 False 表示本轮
    没有真正处理，保留已应用快照，下一轮继续重试。snapshot 抛 errors 时按本轮无变化处理。
    widget 销毁时定时器随之下线（与 repeat() 同一套机制）。
    """
    state={'applied':None,'observed':None}
    try:
        value=snapshot();state['applied']=value;state['observed']=value
    except errors:
        pass
    def tick():
        try:
            value=snapshot()
            if value!=state['applied'] and value==state['observed']:
                if refresh() is not False:state['applied']=value
            state['observed']=value
        except errors:
            pass
    return repeat(widget,interval,tick)


def watch_changes_async(widget,snapshot,refresh,interval=1500,errors=(OSError,ValueError,KeyError)):
    """后台取得文件快照；Tk 主线程只处理结果和必要的 UI 刷新。"""
    state={'applied':None,'observed':None,'busy':False,'next_due':0.0,'stopped':False}
    results=queue.Queue(maxsize=1)

    def read_snapshot():
        try:result=(True,snapshot())
        except Exception:result=(False,None)
        try:results.put_nowait(result)
        except queue.Full:pass

    def start_snapshot():
        if state['busy'] or state['stopped']:return
        state['busy']=True
        threading.Thread(target=read_snapshot,daemon=True,name='file-change-snapshot').start()

    def tick():
        try:ok,value=results.get_nowait()
        except queue.Empty:ok=None
        if ok is not None:
            state['busy']=False;state['next_due']=time.monotonic()+interval/1000.0
            if ok:
                if state['applied'] is None:state['applied']=value
                elif value!=state['applied'] and value==state['observed']:
                    if refresh() is not False:state['applied']=value
                state['observed']=value
        if not state['busy'] and time.monotonic()>=state['next_due']:start_snapshot()

    timer_stop=repeat(widget,max(20,min(100,interval//4)),tick)
    def stop(event=None):
        if event is not None and event.widget is not widget:return
        state['stopped']=True;timer_stop()
    widget.bind('<Destroy>',stop,add='+')
    start_snapshot()
    return stop
