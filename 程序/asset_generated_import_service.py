"""扫描并登记 Comfy 资产生成目录中的已完成图片；不依赖 Tk。"""
import re
import time
from pathlib import Path
from file_cache import remove_temporary_file

from agent.core import read
from contract.project_context import ProjectContext


def _project_root(project=None, *, context=None):
    if context is None:
        return Path(project).resolve()
    if not isinstance(context, ProjectContext):
        raise TypeError('生成资产导入需要由 L3 注入 ProjectContext。')
    root = context.root.resolve()
    if project is not None and Path(project).resolve() != root:
        raise ValueError('项目路径与注入的 ProjectContext 不一致。')
    return root


def cleanup_batches(folder, days=7):
    """仅回收已明确失败的过期记录；未结算请求永久保留到核实闭环。"""
    from storage_maintenance import recycle_paths
    folder = Path(folder)
    cutoff = time.time() - days * 86400
    expired = []
    for root in (folder, folder / 'seedream'):
        if not root.is_dir():
            continue
        for path in root.glob('*.json'):
            try:
                data = read(path)
                if (path.stat().st_mtime < cutoff and isinstance(data, dict)
                        and data.get('state') == 'failed'):
                    expired.append(path)
            except (OSError, ValueError):
                continue
    if expired:
        recycle_paths(folder, expired, '归档过期已失败资产批次；保留请求核对与恢复记录')


def generated_plan(base):
    """生成目录对应的资产清单；缺失或格式不符时返回空表。"""
    base = Path(base).resolve()
    path = base / 'assets/资产清单/assets.json'
    plan = read(path) if path.is_file() else {}
    return plan if isinstance(plan, dict) else {}


def pending_generated_files(project, base, plan=None, *, context=None):
    """返回尚未登记、可自动导入的 (目录, 文件, 资产编号)；只扫描不写盘。"""
    from asset_context import generated_dir
    from asset_batch_service import image_ready
    project = _project_root(project, context=context)
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


def pending_generated(project, base, *, context=None):
    """返回尚未登记的生成图资产编号。"""
    return [aid for _, _, aid in pending_generated_files(project, base, context=context)]


def import_pending_generated(project, base, report=None, *, gateway=None, context=None):
    """自动导入未登记生成图；JPEG 等格式统一转换为 PNG。"""
    from asset_batch_service import register_image
    from native_asset_codec import to_png
    publish_bytes = gateway.get('publish_bytes') if isinstance(gateway, dict) else None
    if not callable(publish_bytes):
        raise RuntimeError('生成资产导入必须由 L3 注入')
    plan = generated_plan(base)
    done = []
    for folder, path, aid in pending_generated_files(project, base, plan, context=context):
        try:
            tmp = folder / (aid + '_autoimport.png')
            publish_bytes(tmp, to_png(path.read_bytes()))
            result = register_image(base, aid, plan[aid], tmp, gateway=gateway)
            remove_temporary_file(tmp)
            done.append(aid)
            if report:
                report(aid + '：' + result)
        except Exception as exc:
            if report:
                report(aid + '：自动导入未完成 ' + str(exc))
    return done
