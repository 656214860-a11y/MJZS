"""扫描并登记 Comfy 资产生成目录中的已完成图片；不依赖 Tk。"""
import re
import time
from pathlib import Path
from file_cache import remove_temporary_file

from agent.core import read, save_bytes


def cleanup_batches(folder, days=7):
    """清理过期且已失败或结果不确定的批次记录。"""
    folder = Path(folder)
    cutoff = time.time() - days * 86400
    for root in (folder, folder / 'seedream'):
        if not root.is_dir():
            continue
        for path in root.glob('*.json'):
            try:
                if path.stat().st_mtime < cutoff and read(path).get('state') in ('failed', 'uncertain'):
                    remove_temporary_file(path)
            except (OSError, ValueError):
                pass


def generated_plan(base):
    """生成目录对应的资产清单；缺失或格式不符时返回空表。"""
    base = Path(base).resolve()
    path = base / 'assets/资产清单/assets.json'
    plan = read(path) if path.is_file() else {}
    return plan if isinstance(plan, dict) else {}


def pending_generated_files(project, base, plan=None):
    """返回尚未登记、可自动导入的 (目录, 文件, 资产编号)；只扫描不写盘。"""
    from asset_context import generated_dir
    from asset_batch_service import image_ready
    project = Path(project)
    base = Path(base).resolve()
    plan = generated_plan(base) if plan is None else plan
    if not plan:
        return []
    folders = [folder for folder in (generated_dir(base), project / 'workflows/Comfy资产批次',
               project / 'workflows/Comfy资产批次/seedream') if folder.is_dir()]
    found = []
    for folder in folders:
        for path in sorted(folder.glob('*.png')):
            match = re.search(r'(CHAR|LOC|PROP)_\d{3,}', path.stem)
            if not match:
                continue
            aid = match.group(0)
            if aid not in plan or image_ready(base, aid):
                continue
            found.append((folder, path, aid))
    return found


def pending_generated(project, base):
    """返回尚未登记的生成图资产编号。"""
    return [aid for _, _, aid in pending_generated_files(project, base)]


def import_pending_generated(project, base, report=None):
    """自动导入未登记生成图；JPEG 等格式统一转换为 PNG。"""
    from asset_batch_service import register_image
    from native_asset_codec import to_png
    plan = generated_plan(base)
    done = []
    for folder, path, aid in pending_generated_files(project, base, plan):
        try:
            tmp = folder / (aid + '_autoimport.png')
            save_bytes(tmp, to_png(path.read_bytes()))
            result = register_image(base, aid, plan[aid], tmp)
            remove_temporary_file(tmp)
            done.append(aid)
            if report:
                report(aid + '：' + result)
        except Exception as exc:
            if report:
                report(aid + '：自动导入未完成 ' + str(exc))
    return done
