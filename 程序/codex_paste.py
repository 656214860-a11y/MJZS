"""Paste into the desktop composer; the user submits manually."""
import json
import subprocess
import tempfile
from pathlib import Path
from agent.core import save_text


def paste_existing(title,prompt,draft='',project='',deadline_seconds=15,*,program='',app_name=''):
    payload={'title':title,'prompt':prompt,'draft':draft,'project':str(project),
             'deadline':deadline_seconds,'program':str(program),'app_name':str(app_name)}
    return _run(payload)


def paste_attachment(title,prompt,attachment,*,program,app_name,deadline_seconds=45):
    """先以文件形式粘贴任务文件作附件，再粘贴短指令（REQ-S01-70）；返回形状同 paste_existing。"""
    payload={'title':title,'prompt':prompt,'draft':'','project':'','deadline':deadline_seconds,
             'program':str(program),'app_name':str(app_name),'attachment':str(attachment)}
    return _run(payload)


def _run(payload):
    deadline_seconds=payload['deadline']
    script=Path(__file__).with_name('codex_paste.ps1')
    program=payload['program']
    app = payload['app_name'].strip() or ('Claude Desktop' if program else 'GPT')
    try:
        # Full episode prompts routinely exceed Windows' command-line limit.
        # Only filenames go in argv; immutable UTF-8 data stays out of shell code.
        with tempfile.TemporaryDirectory(prefix='drama_codex_send_') as folder:
            source=Path(folder)/'input.json'
            save_text(source, json.dumps(payload, ensure_ascii=False))
            result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-STA','-File',str(script),'-PayloadFile',str(source)],
                capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=max(55,deadline_seconds+40),
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        lines=[line for line in result.stdout.splitlines() if line.startswith('{')]
        if lines:return json.loads(lines[-1])
        error=result.stderr.lower()
        if any(marker in error for marker in ('unauthorizedaccess','pssecurityexception','running scripts is disabled')):
            return {'ok':False,'reason':'Windows 执行策略阻止了自动填入脚本；未粘贴或发送，任务文本已保留。','send_dispatched':False}

        return {'ok':False,'reason':'自动填入工具未返回结果（退出码 '+str(result.returncode)+'）；任务文本已保留，未自动重试。','send_dispatched':False}
    except subprocess.TimeoutExpired:
        return {'ok':False,'reason':f'自动填入等待超时；内容已复制，请在 {app} 窗口中粘贴并手动发送。','send_dispatched':False}
    except OSError as exc:
        return {'ok':False,'reason':f'自动填入工具未启动（系统错误 {getattr(exc,"winerror",None) or exc.errno}）；未粘贴或发送，请在 {app} 窗口中手动粘贴并发送。'}
    except ValueError:
        return {'ok':False,'reason':f'无法读取自动填入结果；内容已复制，请检查 {app} 窗口并手动发送。','send_dispatched':False}
