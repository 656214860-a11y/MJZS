"""分镜启动的纯文件决策服务。

本模块不导入 Tk，也不调用 Agent。页面层的文件扫描暂由 ``storyboard_files``
提供；L3 阶段命令只依赖这里的稳定计划契约，后续可独立替换扫描实现。
"""
from pathlib import Path


def build_work_plan(scripts, boards, made, adopted):
    """由已扫描的路径生成分镜待办与待采用集合。"""
    scripts = list(dict.fromkeys(Path(path).resolve() for path in scripts))
    boards = list(dict.fromkeys(Path(path).resolve() for path in boards))
    made = {Path(path).resolve() for path in made if path is not None}
    used = {Path(path).resolve() for path in adopted if path is not None}
    return {
        'scripts': scripts,
        'existing': boards,
        'made': made,
        'used': used,
        'todo': [path for path in scripts if path not in made],
        'revise': [path for path in boards if path not in used],
    }


def storyboard_work_plan(project):
    """兼容当前扫描实现；L3 调用方不再直接依赖 UI 文件。"""
    # 延迟导入是服务边界的适配，不是 UI 调用方的任意动态导入；扫描迁出后可删除。
    from stage_execution_service import storyboard_produced_scripts
    from orchestrator.storyboard_selection import selected_many
    from orchestrator.storyboard_selection import adopted
    root = Path(project).resolve()
    scripts = selected_many(root, 'script')
    boards = selected_many(root, 'storyboard')
    return build_work_plan(scripts, boards, storyboard_produced_scripts(root), adopted(root))
