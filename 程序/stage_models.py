# -*- coding: utf-8 -*-
"""第 46 期第 7／8 条：首帧／资产两个阶段的「生产模型」也收进「阶段配置 → 模型」。

第 54 期附件三：点「手动制作XX」先弹一扇精简窗（模型／SKILL 数量／预计 ＋ 三个折叠
项 ＋ 修改配置／直接执行／取消），这一份就是那扇窗与那颗按钮的外套。

用户的要求：
- 首帧管理 → 手动制作首帧 → 把「生成模型与接口」下拉框里的模型搬到「阶段配置 → 模型」右侧那个
  下拉框，删掉重复的模型；
- 资产管理 → 手动制作资产 → 把「生图模型」下拉框里的模型照同一条搬过去。

于是这一份登记每个阶段有哪些「生产模型」（本地 ComfyUI／云端生图／首帧 Agent 引擎）：
阶段配置的模型下拉＝模型池 ＋ 这一份，制作窗口里那个重复的下拉框整条撤掉，只剩一行只读的
「当前模型」——挑模型的地方只有一处。值仍然落在项目自己那份配置里（skill_config.json 的
[阶段]['model']），面板、制作窗口、无人值守勾选框读到的都是同一格；skill_panel.stage_context
会把生产模型挡在 SKILL 编排之外（它不是模型池里的模型 id）。
"""
import app_logging
from pet_bus import STAGES
from stage_flow import manual_label as manual_label_for


# L4 在应用组合时注入窗口和确认呈现器；阶段层仅决定文案、阻断条件和返回选择。
_PLAN_WINDOW_PRESENTER = None
_CONFIRMATION_PRESENTER = None


def set_plan_window_presenter(presenter):
    """登记 L4 手动制作窗口呈现器，避免本层反向导入 UI 组件。"""
    global _PLAN_WINDOW_PRESENTER
    _PLAN_WINDOW_PRESENTER = presenter


def set_confirmation_presenter(presenter):
    """登记统一确认呈现器，避免阶段层反向依赖 UI 组件。"""
    global _CONFIRMATION_PRESENTER
    _CONFIRMATION_PRESENTER = presenter


def assets_choices():
    """资产管理这一阶段的生产模型：(值, 文案)——与生图窗口原来那份清单同源（第 46 期第 8 条）。"""
    from cloud_assets import LOCAL, MODELS
    return tuple([(LOCAL, LOCAL)] + [(name, name) for name in MODELS])


def keyframe_choices(project=None):
    """首帧这一阶段的生产模型：本地 ComfyUI、Seedream 云接口，加上首帧 Agent 的三个引擎（第 46 期第 7 条）。

    引擎那几条的名字跟着「Skill 调用设置」里那一档走（与 keyframe_comfy 原来那个合并下拉框
    用的是同一份算法），所以没给项目时只列前两条。
    """
    from production_model_contract import LOCAL_KEYFRAME_MODEL, SEEDREAM_KEYFRAME_MODEL
    items = [(LOCAL_KEYFRAME_MODEL, LOCAL_KEYFRAME_MODEL),
             (SEEDREAM_KEYFRAME_MODEL, SEEDREAM_KEYFRAME_MODEL)]
    if not project:
        return tuple(items)
    try:
        from importlib import import_module
        settings = import_module('workflow_settings')
        ENGINES, load = settings.ENGINES, settings.load
        cfg = load(project, 'assets')
        for engine_name, display in ENGINES.items():
            name = str(cfg['profiles'][engine_name].get('model', '') or '').strip() or display
            while any(name == value for value, _label in items):
                name += ' · ' + display
            items.append((name, name))
    except Exception:
        app_logging.swallowed()
    return tuple(items)



# ── 第 60 期第 6 条：自检／探针里一律不冒真窗（用户报的「卡在这里」） ──────────
# 用户截了张图说「卡在这里」：一扇「手动制作：资产管理」停在桌面上，状态栏那串
# %TEMP%/tmpXXXX/p 正是用例的临时项目——这扇窗是**单独跑某个测试文件**时冒出来的。
# 「不弹真窗」原来只装在 run_selftests 那层假函数里（PLANNER／ASKER），直接
# `python test_manual_gate.py` 就没有：用例一点「手动制作资产」，这扇窗真的冒出来，
# 停在 wait_window 上把用例连同自己一起卡死，窗于是留在用户桌面上再也不走。
# 现在把这条保险装进模块自己：这一趟跑的是测试／探针文件，这两处弹窗一律不冒。
SELF_TEST = None                # None＝按进程自己认；自检里也可以显式写 True／False


def _main_module_name():
    """主模块的文件名（小写）；认不出来就是空串。"""
    import os as _os
    import sys as _sys
    main = _sys.modules.get('__main__')
    return _os.path.basename(str(getattr(main, '__file__', '') or '')).lower()


def self_test():
    """这会儿是不是在跑自检／探针：主模块是 test_xxx／probe_xxx 就算。

    判据照抄本项目的约定（每个用法说明都写着「运行：python test_xxx.py」），
    不依赖 run_selftests 装没装假函数——单独跑一个文件同样不冒真窗。
    """
    if SELF_TEST is not None:
        return bool(SELF_TEST)
    return _main_module_name().startswith(('test_', 'probe'))


def tests_active():
    """这会儿是不是在跑代码测试（第 65 期任务 11）。

    用户原话：「优化全部页面点击按钮『手动制作XX』的弹窗逻辑，代码测试阶段无需弹窗」。
    全程序的「手动制作XX」（九个页面、九个入口）都从 manual_command 这一处过，所以这一处
    认出来是测试，那些窗就一律不冒，直接照「直接执行」往下走，连第 47 期那句模型提醒也免了。

    判据比 self_test() 再宽一档：`python -m unittest test_x`／pytest 这些入口的主模块名字都不是
    test_xxx，但它们同样是测试。（程序自身不 import unittest，所以「unittest 已经在
    sys.modules 里」这一条，真跑应用时不会命中。）
    """
    if SELF_TEST is not None:
        return bool(SELF_TEST)
    import sys as _sys
    if 'unittest' in _sys.modules or 'pytest' in _sys.modules:
        return True
    name = _main_module_name()
    return name.startswith(('test_', 'probe')) or name == 'run_selftests.py'


# ── 第 47 期第 3 条：点「手动XX」以前先问一句「模型配了吗」 ──────────────────
ASKER = None                # 自检里换成假函数；默认走 L4 注册的统一 ConfirmDialog


def _ask(title, message, parent=None):
    """弹一次确认框（返回 True＝用户要现在就去配）。自检把 ASKER 换掉，不弹真窗。"""
    if ASKER is None and tests_active():
        return False            # 第 60 期第 6 条：自检里不冒窗，按「先不配、照旧开始」走
    asker = ASKER or _CONFIRMATION_PRESENTER
    if asker is None:
        # 未完成 L4 组合时不能把“无法确认”误作同意，按拒绝处理。
        return False
    return bool(asker(title, message, parent=parent))


def _status(desktop, text):
    setter = getattr(desktop, 'status', None)
    if setter is not None and hasattr(setter, 'set'):
        try:
            setter.set(text)
        except Exception:
            app_logging.swallowed()
    return text


# ── 第 54 期附件三：「手动制作XX」精简窗 ────────────────────────────────────
# 现状问题（用户原话）：点「手动制作XX」弹窗内容过多。改成分层展示——只摆三行核心信息
# （模型／SKILL 数量／预计），底下三个按钮。
# 第 55 期第 4 条：三个「查看…详情」折叠项也删了（用户点名要删）——那三行本来就只是
# 「这一步怎么走」的参考，真要细看有「阶段配置」面板与次级执行页，弹窗只留该做的选择。
PLANNER = None                 # 自检里换成假函数；默认弹 plan_window（自检进程里也不弹，见 self_test）
PLAN_CHOICES = ('run', 'configure')


def plan(desktop, stage, parent=None):
    """点「手动制作XX」先问一句怎么走：'run' 直接执行／'configure' 去改配置／None 取消。"""
    if PLANNER is None and tests_active():
        return 'run'                      # 第 60 期第 6 条：自检里不冒窗，照「直接执行」走
    planner = PLANNER or plan_window
    try:
        choice = planner(desktop, stage, parent)
    except Exception:
        # 确认窗坏了不能替用户同意生产动作；停止本次并给既有状态栏可行动反馈。
        _status(desktop, '未能打开操作确认窗口，请稍后重试。')
        return None
    return choice if choice in PLAN_CHOICES else None


def _untop(window):
    """把置顶脉冲收回来（窗口可能已经被用户关掉了，那就什么都不做）。"""
    try:
        if window.winfo_exists():
            window.attributes('-topmost', False)
    except Exception:
        app_logging.swallowed()


def _cancel_popup_jobs(window, event=None):
    """窗口销毁时撤掉这一张阶段配置弹窗自己的延迟回调。"""
    if event is not None and event.widget is not window:
        return
    jobs = getattr(window, '_stage_model_popup_jobs', None)
    if not jobs:
        return
    for job in tuple(jobs):
        try:
            window.after_cancel(job)
        except Exception:
            app_logging.swallowed()
    jobs.clear()


def _schedule_popup_job(window, delay, callback):
    """为阶段配置弹窗登记一个会随窗口销毁自动取消的延迟动作。"""
    jobs = getattr(window, '_stage_model_popup_jobs', None)
    if jobs is None:
        jobs = set()
        window._stage_model_popup_jobs = jobs
        window.bind('<Destroy>',
                    lambda event, owner=window: _cancel_popup_jobs(owner, event),
                    add='+')

    job = None

    def run():
        jobs.discard(job)
        callback()

    job = window.after(delay, run)
    jobs.add(job)
    return job


def activate_popup(window):
    """把弹窗点活并顶到最前（第 59 期第 13 条）。

    这一层自己摆位（不走 ui_theme 那一套），置顶窗在 Windows 上不会自己变成活动窗，
    用户的第一下点击只被当成「点活这扇窗」——按钮于是要点两三下才生效（用户报的
    「卡在这里」就是这个）。脉冲一下置顶，再交还焦点；与 skill_panel.show 同一套做法。
    """
    try:
        window.attributes('-topmost', True)
        window.lift()
        window.focus_force()
        _schedule_popup_job(window, 1200, lambda: _untop(window))
    except Exception:
        app_logging.swallowed()


def plan_window(desktop, stage, parent=None):
    """「手动制作XX」精简窗：三行核心信息 ＋ 三个按钮（第 55 期第 4 条起就这几样）。

    第 65 期任务 11：这一扇窗本身照旧随时可建（用例直接建它看控件树）；「代码测试阶段
    不许冒窗」那条保险装在上一层 plan()／manual_command 上——按钮那条路上它根本走不到这儿。
    """
    import stage_flow
    host = parent if parent is not None else getattr(desktop, 'win', None)
    if host is None:
        return 'run'                      # 没有窗口可挂：不拦，照旧动手
    lines = stage_flow.summary_lines(desktop, stage)
    blocked = stage_flow.blockers(stage_flow.project_of(desktop), stage)
    # 这一窗里用户已经看过「模型」那一行了（没配就是「自动」），第 47 期那句提醒不再补一刀。
    remember_model_asked(desktop, stage)
    if _PLAN_WINDOW_PRESENTER is None:
        raise RuntimeError('手动制作窗口呈现器尚未安装。')
    return _PLAN_WINDOW_PRESENTER(host, '手动制作：' + stage_flow.stage_name(stage), lines, blocked)


def open_config(desktop, stage):
    """「修改配置」：跳到这一阶段页面的阶段配置区（就是那颗「阶段配置」按钮打开的面板）。"""
    try:
        from ui_plugin_registry import module
        return module('skill_panel').show(desktop, stage)
    except Exception:
        # 面板加载失败不能静默吞掉，否则用户只会看到按钮没有反应。
        _status(desktop, '未能打开阶段配置，请稍后重试。')
        return None


def _model_asked(desktop):
    """取得本会话已提示模型配置的阶段集合。"""
    asked = getattr(desktop, '_manual_model_asked', None)
    if asked is None:
        asked = set()
        try:
            desktop._manual_model_asked = asked
        except Exception:
            app_logging.swallowed()
    return asked


def remember_model_asked(desktop, stage):
    """记下「这一步的模型提醒已经给过」——第 47 期那句提醒同一个阶段只问一次。"""
    try:
        _model_asked(desktop).add(stage)
    except Exception:
        app_logging.swallowed()


def before_manual(desktop, stage, parent=None):
    """点「手动XX」之前的那一句提醒：这一阶段的模型还是「自动」就请用户去「阶段配置 → 模型」。

    返回 True＝照旧动手（本来就配好了，或用户说「先不配」）；False＝这一次不开始，改去打开
    「阶段配置」面板挑模型。

    用户要的「同步到其他页面」说的就是这里：模型只存一份（项目的 skill_config.json 里
    [阶段]['model']），各页那颗「阶段配置」按钮与制作窗口读的都是这一格，改一次处处生效——
    面板里那句提示写的也是这句话。同一个阶段一个会话里只提醒一次，别让每次点都弹一遍。
    """
    if ASKER is None and tests_active():
        return True                                   # 第 65 期任务 11：测试阶段免弹窗，也不拦
    import model_router
    project = getattr(desktop, 'root', None)
    if not project:
        return True                                   # 还没选项目：交给原来的流程去提示
    try:
        import stage_config
        chosen = str(stage_config.get(project, stage).get('model') or '')
    except Exception:
        return True                                   # 配置读不出来就不拦
    if chosen and chosen != model_router.AUTO:
        return True                                   # 已经挑过模型，不再啰嗦
    asked = _model_asked(desktop)
    if stage in asked:
        return True
    asked.add(stage)
    from pet_bus import STAGE_NAMES
    label = STAGE_NAMES.get(stage, stage)
    if not _ask('先挑一下模型',
                '「%s」这一步的模型还是「自动」。\n\n'
                '每一页的「阶段配置 → 模型」是同一份配置：在那里挑一次，'
                '所有页面和制作窗口都跟着变，不用一页一页改。\n\n'
                '现在就打开「阶段配置」挑模型吗？\n'
                '（选「否」照旧开始，模型仍按「自动」走。）' % label, parent):
        return True
    _status(desktop, '模型还是「自动」：先在「阶段配置 → 模型」里挑一个，挑完再点「手动××」。')
    try:
        from ui_plugin_registry import module
        module('skill_panel').show(desktop, stage)
    except Exception:
        app_logging.swallowed()
    return False


def manual_command(desktop, stage, action, parent=None, trigger='manual'):
    """「手动XX」那颗按钮的外套：先弹精简窗（第 54 期附件三），再问一句模型配没配。

    「修改配置」→ 打开这一阶段的阶段配置，这一次不动手；「直接执行」→ 照旧往下走
    （闸放行才真的开动）；「取消」→ 什么都不做。trigger 是这一趟的身份，手动按钮
    与三虎自动共用同一台编排器，只有它不同。
    """
    def run():
        choice = plan(desktop, stage, parent)
        if choice == 'configure':
            open_config(desktop, stage)
            return False
        if choice != 'run':
            return False
        if before_manual(desktop, stage, parent):
            action()
            return True
        return False
    return run


def production_choices(stage, project=None):
    """这一阶段的生产模型选项（不是这两个阶段就是空的）。"""
    if stage == 'assets':
        return assets_choices()
    if stage == 'keyframe':
        return keyframe_choices(project)
    return ()


def default_model(stage):
    """没挑过（「自动」）时按哪一个生产模型走：都是本地免费的那一个。"""
    if stage == 'assets':
        from cloud_assets import LOCAL
        return LOCAL
    from production_model_contract import LOCAL_KEYFRAME_MODEL
    return LOCAL_KEYFRAME_MODEL


def chosen(project, stage):
    """阶段配置里挑的生产模型；「自动」与认不出来的值一律退回这一阶段的默认。"""
    from stage_config import get
    try:
        value = str(get(project, stage).get('model') or '').strip()
    except Exception:
        value = ''
    if value in [item[0] for item in production_choices(stage, project)]:
        return value
    return default_model(stage)


def is_production(stage, value):
    """这个值是不是生产模型（不是模型池里的模型 id）。"""
    text = str(value or '').strip()
    return bool(text) and any(text == item[0] for item in production_choices(stage))


def belongs_to_other_stage(stage, value):
    """这个值是不是别的阶段的生产模型（第 58 期第 5 条）。

    预设是跳阶段存的（预设里记着自己是哪一步，但套用时可以套到别的步上），
    «首帧管理」那一档里的「本地 ComfyUI」被套到「剧本准备」上就是这种不对口的值——
    它不是发请求的模型 id，留着只会让路由器报「指定的模型现在用不了」。
    """
    text = str(value or '').strip()
    if not text or is_production(stage, text):
        return False
    return any(is_production(other, text) for other in STAGES if other != stage)
