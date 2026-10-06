"""Paste into a verified Codex composer; optionally submit the exact task once."""
import json
import subprocess
import tempfile
from pathlib import Path
from agent.core import save_text


def paste_existing(title,prompt,draft='',project='',diagnostic=False,auto_send=False,confirmation=None,deadline_seconds=15):
    script=Path(__file__).with_name('codex_paste.ps1')
    payload={'title':title,'prompt':prompt,'draft':draft,'project':str(project),
             'diagnostic':bool(diagnostic),'auto_send':bool(auto_send),'confirmation':confirmation,'deadline':deadline_seconds}
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

        return {'ok':False,'reason':'自动填入工具未返回结果（退出码 '+str(result.returncode)+'）；任务文本已保留，未自动重试。','send_dispatched':True}
    except subprocess.TimeoutExpired:
        return {'ok':False,'reason':'自动填入或发送等待超时；请查看 Codex，本次未重复发送。','send_dispatched':True}
    except OSError as exc:
        return {'ok':False,'reason':'自动填入工具未启动（系统错误 '+str(getattr(exc,'winerror',None) or exc.errno)+'）；任务文本已保留。'}
    except ValueError:
        return {'ok':False,'reason':'无法读取自动发送结果；请查看 Codex，本次未重复发送。','send_dispatched':True}

def confirm_existing(title,prompt,confirmation,draft='',project=''):
    """Send only the unchanged composer snapshot approved in the assistant dialog."""
    if not isinstance(confirmation,dict) or not all(confirmation.get(key) for key in ('handle','editor_id','text_sha256')):
        return {'ok':False,'reason':'未取得可确认的输入框，未发送。'}
    return paste_existing(title,prompt,draft,project,auto_send=True,confirmation=confirmation)
