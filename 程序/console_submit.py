"""Submit once to an owned CLI console, only while its input line is empty."""
import json,re,subprocess,sys,tempfile,time
from pathlib import Path
from agent.core import save_text

def empty_prompt(line):
    return bool(re.fullmatch(r'\s*[>›❯]\s*',line))

def send(pid,message):
    with tempfile.TemporaryDirectory(prefix='drama_cli_send_') as folder:
        payload=Path(folder)/'input.json'
        save_text(payload, json.dumps({'pid':pid, 'message':message}, ensure_ascii=False))
        try:
            result=subprocess.run([sys.executable,str(Path(__file__).resolve()),str(payload)],capture_output=True,text=True,
                encoding='utf-8',errors='replace',timeout=15,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            lines=[line for line in result.stdout.splitlines() if line.startswith('{')]
            if lines:return json.loads(lines[-1])
        except OSError:
            return {'ok':False,'send_dispatched':False,'reason':'自动输入工具未启动；任务文件已保存，可重试。'}
        except (subprocess.TimeoutExpired,ValueError):pass
    return {'ok':False,'send_dispatched':True,'reason':'未确认 Agent 自动发送结果，请检查对应窗口；本次未重发。'}

def deliver(payload):
    import ctypes as c
    from ctypes import wintypes as w
    class COORD(c.Structure):_fields_=[('X',w.SHORT),('Y',w.SHORT)]
    class RECT(c.Structure):_fields_=[('Left',w.SHORT),('Top',w.SHORT),('Right',w.SHORT),('Bottom',w.SHORT)]
    class INFO(c.Structure):_fields_=[('size',COORD),('cursor',COORD),('attributes',w.WORD),('window',RECT),('maximum',COORD)]
    class KEY(c.Structure):_fields_=[('down',w.BOOL),('repeat',w.WORD),('virtual',w.WORD),('scan',w.WORD),('char',w.WCHAR),('control',w.DWORD)]
    class EVENT(c.Union):_fields_=[('key',KEY),('padding',c.c_byte*16)]
    class INPUT(c.Structure):_fields_=[('kind',w.WORD),('event',EVENT)]
    kernel=c.WinDLL('kernel32',use_last_error=True)
    kernel.AttachConsole.argtypes=[w.DWORD];kernel.AttachConsole.restype=w.BOOL
    kernel.GetStdHandle.argtypes=[w.DWORD];kernel.GetStdHandle.restype=w.HANDLE
    kernel.GetConsoleScreenBufferInfo.argtypes=[w.HANDLE,c.POINTER(INFO)]
    kernel.ReadConsoleOutputCharacterW.argtypes=[w.HANDLE,w.LPWSTR,w.DWORD,COORD,c.POINTER(w.DWORD)]
    kernel.WriteConsoleInputW.argtypes=[w.HANDLE,c.POINTER(INPUT),w.DWORD,c.POINTER(w.DWORD)]
    kernel.FreeConsole()
    if not kernel.AttachConsole(int(payload['pid'])):
        return {'ok':False,'send_dispatched':False,'reason':'该 Agent 终端不支持自动输入；任务文件已保存，请在对应窗口继续。'}
    dispatched=False
    try:
        handle=kernel.GetStdHandle(-10 & 0xffffffff);screen=kernel.GetStdHandle(-11 & 0xffffffff)
        until=time.monotonic()+8;ready=False
        while time.monotonic()<until:
            info=INFO()
            if not kernel.GetConsoleScreenBufferInfo(screen,c.byref(info)):break
            buffer=c.create_unicode_buffer(info.size.X+1);count=w.DWORD()
            if not kernel.ReadConsoleOutputCharacterW(screen,buffer,info.size.X,COORD(0,info.cursor.Y),c.byref(count)):break
            # A draft, permission question or a running-task screen is not an empty prompt.
            if empty_prompt(buffer.value):ready=True;break
            time.sleep(.25)
        if not ready:return {'ok':False,'send_dispatched':False,'reason':'Agent 输入框忙碌、已有草稿或等待确认；未覆盖内容，请在对应窗口处理后重试。'}
        message=payload['message']
        if any(ord(ch)<32 for ch in message):raise ValueError('自动输入必须是单行任务入口')
        records=[]
        for char in message+'\r':
            for down in (True,False):
                item=INPUT();item.kind=1;item.event.key=KEY(down,1,13 if char=='\r' else 0,0,char,0);records.append(item)
        data=(INPUT*len(records))(*records);written=w.DWORD();dispatched=True
        if not kernel.WriteConsoleInputW(handle,data,len(records),c.byref(written)) or written.value!=len(records):
            return {'ok':False,'send_dispatched':True,'reason':'Agent 输入未完整确认，请检查对应窗口；为避免重复未再次发送。'}
        return {'ok':True,'send_dispatched':True,'reason':'已自动填入任务入口并发送到对应 Agent 终端。'}
    except Exception:
        return {'ok':False,'send_dispatched':dispatched,'reason':'Agent 自动发送未完成，任务文件已保留；请检查对应窗口。'}
    finally:kernel.FreeConsole()

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(deliver(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))),ensure_ascii=False))
