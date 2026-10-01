"""Launch the installed ComfyUI backend invisibly and open its local UI."""
import os,subprocess,time,urllib.request,json
from pathlib import Path
ROOT=Path('D:/漫剧下载/MiniMaxH3')
BASE=Path.home()/'AppData/Local/Comfy-Desktop/ComfyUI-Installs/ComfyUI/ComfyUI'
def ready():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8189/system_stats',timeout=2) as r:return r.status==200
    except Exception:return False
try:
    if not ready():
        for folder in ('input','output','user'): (ROOT/folder).mkdir(parents=True,exist_ok=True)
        python=BASE/'.venv/Scripts/python.exe'
        if not python.exists():raise RuntimeError('未找到现有ComfyUI环境，请检查安装位置')
        args=[str(python),str(BASE/'main.py'),'--listen','127.0.0.1','--port','8189','--lowvram','--reserve-vram','1','--disable-all-custom-nodes','--disable-api-nodes','--preview-method','none','--extra-model-paths-config',str(ROOT/'model_paths.yaml'),'--input-directory',str(ROOT/'input'),'--output-directory',str(ROOT/'output'),'--user-directory',str(ROOT/'user'),'--database-url','sqlite:///'+(ROOT/'user/comfyui.db').as_posix()]
        with (ROOT/'server.log').open('a',encoding='utf-8') as log:
            subprocess.Popen(args,cwd=BASE,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW,env={**os.environ,'PYTHONIOENCODING':'utf-8'})
        for _ in range(180):
            if ready():break
            time.sleep(1)
        else:raise RuntimeError('服务尚未就绪，请查看 D:/漫剧下载/MiniMaxH3/server.log')
    from integrations import comfy_executable
    settings_path=Path(__file__).resolve().parent/'desktop_settings.json'
    settings=json.loads(settings_path.read_text(encoding='utf-8-sig')) if settings_path.is_file() else {}
    executable=comfy_executable(settings)
    if executable is None:raise RuntimeError('H3 后台已启动，但未找到 ComfyUI 桌面应用，请在助手设置中指定桌面程序路径')
    os.startfile(str(executable))
except Exception as e:
    import ctypes
    ctypes.windll.user32.MessageBoxW(0,str(e),'H3本地服务',16)
