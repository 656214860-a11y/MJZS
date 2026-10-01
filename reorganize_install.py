"""Move the installed program into one folder on the next clean launch."""
import json, shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PROGRAM=ROOT/'程序'
KEEP={'程序','启动漫剧制作助手.pyw','启动制作助手.lnk','reorganize_install.py','使用说明.md'}

def _project_configs():
    base=Path('D:/漫剧下载/项目')
    if not base.is_dir():return []
    result=[]
    for d in base.iterdir():
        if not d.is_dir() or d.is_symlink() or d.is_junction():continue
        result.append(d/'config.json')
        result.extend((d/'cloud_video').glob('*/config.json'))
    return [p for p in result if p.is_file()]

def _fix_app_absolute_paths():
    old=str(ROOT);new=str(PROGRAM)
    for path in _project_configs():
        try:
            cfg=json.loads(path.read_text(encoding='utf-8-sig'))
            def fix(value):
                if isinstance(value,str) and value.lower().startswith(old.lower()+'\\'):
                    suffix=value[len(old)+1:]
                    while suffix.lower().startswith('程序\\'):
                        suffix=suffix[len('程序\\'):]
                    return str(PROGRAM/suffix)
                if isinstance(value,dict):return {k:fix(v) for k,v in value.items()}
                if isinstance(value,list):return [fix(v) for v in value]
                return value
            updated=fix(cfg)
            if updated!=cfg:
                temp=path.with_suffix('.move.tmp');temp.write_text(json.dumps(updated,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
        except (OSError,ValueError):continue

def arrange():
    PROGRAM.mkdir(exist_ok=True)
    for source in ROOT.iterdir():
        if source.name in KEEP:continue
        if source.is_symlink() or source.is_junction():continue
        destination=PROGRAM/source.name
        if destination.exists():continue
        shutil.move(str(source),str(destination))
    # Remove confirmed duplicate documentation and obsolete builder/test copies.
    duplicate=PROGRAM/'使用说明_V03.md';main=ROOT/'使用说明.md'
    if duplicate.is_file() and main.is_file() and duplicate.read_bytes()==main.read_bytes():duplicate.unlink()
    obsolete=('package_release.py','package_v03.py','test_engine.py','test_local_video.py','test_workspace.py','test_writing.py','文件校验清单.json')
    for name in obsolete:
        file=PROGRAM/name
        if file.is_file():file.unlink()
    docs=PROGRAM/'说明';docs.mkdir(exist_ok=True)
    for name in ('编剧功能说明.md','维护约定.md'):
        file=PROGRAM/name
        if file.is_file():shutil.move(str(file),str(docs/name))
    old=PROGRAM/'__pycache__'
    if old.is_dir():shutil.rmtree(old)
    _fix_app_absolute_paths()
    return PROGRAM

if __name__=='__main__':arrange()
