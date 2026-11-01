# -*- coding: utf-8 -*-
"""第 54 期：手动按钮状态化 ＋ 手动制作弹窗的摘要 ＋ 三虎自动推进的队长。

三件事合成一份，因为它们读的是同一组事实（每个阶段此刻在不在跑、缺什么）：

- 手动按钮：三虎正在跑某一步 → 那颗按钮写「自动执行中」并置灰；没在跑写
  「手动制作{阶段简称}」、可点。状态由总线上的 stage.executing／stage.completed／
  stage.failed／stage.paused 驱动——listen 把它们记进 RUNNING，follow 照着刷按钮。
- 弹窗那三行摘要：模型／SKILL 数量／预计（耗时与付费），外加依赖警告（step_summary）。
- 三虎自动推进：剧本做完（script.completed）之后，semi／auto 两档按依赖图逐阶段往下推
  （Auto）。hint（只提醒）档只通知，等用户自己动手。

纯标准库、不 import Tk：界面层只调 button_text／button_state／apply_text／follow，
自检里可以直接喂假控件。
"""
import app_logging
from pathlib import Path

import stage_parallel
from pet_bus import STAGES, STAGE_NAMES

# 「自动」那一档在模型池里的 id（挑不出来时弹窗就写「自动」）。
model_router_AUTO = 'auto'

# 阶段简称 → 按钮名（附件二第 3 条那张对照表，一个字都不改）。
MANUAL_LABELS = {'script': '手动制作剧本', 'script_structure': '手动制作结构剧本',
                 'storyboard': '手动制作分镜', 'animatic': '手动制作分镜预演',
                 'assets': '手动制作资产',
                 'continuity': '手动生成连贯性清单',
                 'final': '手动同步资产', 'keyframe': '手动制作首帧', 'previs': '手动制作白模',
                 'video': '手动制作视频', 'audio': '手动制作配音', 'edit': '手动制作剪辑',
                 'delivery': '手动制作交付'}
RUNNING_LABEL = '自动执行中'          # 三虎（自动）正在跑这一步
RECOVERY_HINTS = {
    'script': '人工修改并保存自然剧本；确认故事后再结构化。',
    'script_structure': '对照原稿修正结构剧本，校验通过再拆镜。',
    'storyboard': '人工修正镜头和对白时长，确认初稿再继续。',
    'animatic': '导入临时音频与参考图预演，等您确认节奏；预演不能用作成片。',
    'assets': '导入有授权的角色／场景素材，人工核对外观与许可。',
    'continuity': '可按冲突清单人工裁决角色、服装及场景锚点（可选、建议；不阻塞 SG-02）。',
    'final': '修正分镜及资产引用，重新校验并明确采用版本。',
    'keyframe': '导入／替换选中首帧；只重试失败项，保留已采用图片。',
    'previs': '人工调整白模或导入可播放预演，确认后再生成视频。',
    'video': '先查询未知任务，再重试确定失败项；可在剪辑软件用静帧运镜替代并人工审核。',
    'audio': '导入自行录制或有授权的配音，逐句试听并核对字幕时间。',
    'edit': '改用剪辑软件人工剪辑；静帧替代镜头须明确审核，不当作AI视频成功。',
    'delivery': '导入外部最终成片并重新核验；商用授权与内容审查单独完成。',
}
MANUAL_RUNNING_LABEL = '手动执行中'   # 用户自己点的那一次还在跑
TRIGGERS = ('manual', 'auto')

# 驱动器认的事件：前四个来自附件二第 5 条，script.completed 是附件四第 3 条的起点。
WATCH = {'stage.executing': 'start', 'stage.started': 'start',
         'stage.completed': 'stop', 'stage.failed': 'stop', 'stage.paused': 'stop'}
RUNNING = {}                          # stage -> trigger（'auto'／'manual'）
OWN_ORDER = list(STAGES)

# 依赖图（附件四第 5 条那条链）：后一步要看前一步有没有成。只登记硬依赖——
# 「视频生成」要首帧，「配音」要定稿资产，「剪辑」要成片，「交付」要粗剪。
DEPENDS = {'script': (), 'script_structure': ('script',), 'storyboard': ('script_structure',),
           'animatic': ('storyboard',), 'assets': ('animatic',),
           'continuity': ('assets',), 'final': ('storyboard',), 'keyframe': ('final',),
           'previs': ('keyframe',), 'video': ('keyframe',), 'audio': ('final',),
           'edit': ('video', 'audio'), 'delivery': ('edit',)}

# 预算：编排一次 SKILL 的往返按半分钟粗估——弹窗写的就是「约」。
SECONDS_PER_SKILL = 30
# 自动推进两阶段之间的最小间隔（比心跳节流短：链路上每一步做完就接着走）。
AUTO_GAP_SECONDS = 1.0
AUTO_LEVELS = ('semi', 'auto')        # 附件四第 4 条：这两档自动跑全流程；hint 只通知
# 第 67 期任务 5：已经收场的两种状态（与 pet_state.SETTLED 同一口径）——用户切到自动档时
# 直接跳过这几步，队长从第一个还没做完的阶段接手。
DONE_STATES = ('success', 'skipped')
# 第 67 期任务 5：会花钱的三步（生图／视频／配音，与 pet_agent.PAID_ACTIONS 同一口径）。
# 半自动档只叫醒、要用户点一下确认；全自动档才由三虎自己按下。
PAID_STAGES = ('assets', 'video', 'audio')


def manual_label(stage):
    """这一步的「手动制作XX」按哪几个字写（没登记的阶段退回阶段名）。"""
    return MANUAL_LABELS.get(stage, '手动制作' + str(STAGE_NAMES.get(stage, stage or '')))


def stage_name(stage):
    return STAGE_NAMES.get(stage, str(stage or ''))


# ── 一、跑没跑：事件进、按钮出 ──────────────────────────────────────────────
def reset():
    """清空「正在跑」的清单（自检用）。"""
    RUNNING.clear()


def mark(stage, kind, trigger=''):
    """一条阶段事件落到 RUNNING 上；返回这条事件算不算数。"""
    if not stage or kind not in WATCH:
        return False
    if WATCH[kind] == 'start':
        value = str(trigger or '')
        RUNNING[stage] = value if value in TRIGGERS else 'auto'
    else:
        RUNNING.pop(stage, None)
    return True


def running(stage):
    return stage in RUNNING


def trigger_of(stage):
    return RUNNING.get(stage, '')


def button_text(stage):
    """这一刻这颗按钮该写什么：在跑就写执行中，没跑就写手动制作XX。"""
    if running(stage):
        return RUNNING_LABEL if trigger_of(stage) == 'auto' else MANUAL_RUNNING_LABEL
    return manual_label(stage)


def button_state(stage):
    return 'disabled' if running(stage) else 'normal'


def apply_text(widget, stage):
    """把一颗按钮的字与可点状态按当前这一刻刷一遍；返回有没有改动。

    置灰只认自己按下去的那一次（_stage_flow_forced）——页面上别的闸（比如资产页
    「没勾选就不能按」）管着的置灰照旧归它们，两边不互相顶。
    """
    text = button_text(stage)
    forced = bool(getattr(widget, '_stage_flow_forced', False))
    changed = False
    try:
        if str(widget.cget('text')) != text:
            widget.configure(text=text)
            changed = True
    except Exception:
        return False
    if running(stage):
        if not forced:
            try:
                widget.configure(state='disabled')
                widget._stage_flow_forced = True
                changed = True
            except Exception:
                app_logging.swallowed()
    elif forced:
        try:
            widget.configure(state='normal')
            widget._stage_flow_forced = False
            changed = True
        except Exception:
            app_logging.swallowed()
    return changed


def follow(widget, stage, interval=400):
    """按钮建好之后挂上：按当前状态刷字与置灰，按钮拆了就自己停。

    换页会把整页控件连这颗按钮一起销毁，而 widget.after 是挂在解释器上的——不显式
    after_cancel 的话，那一拍回来时命令已经没了，Tcl 会刷一串「invalid command name
    ...tick」。所以这里把拍子记下来，按钮一拆就取消。
    """
    handle = {'id': None}

    def tick():
        handle['id'] = None
        try:
            if not widget.winfo_exists():
                return
        except Exception:
            return
        apply_text(widget, stage)
        try:
            handle['id'] = widget.after(interval, tick)
        except Exception:
            app_logging.swallowed()

    def stop(event=None):
        if handle['id'] is not None:
            try:
                widget.after_cancel(handle['id'])
            except Exception:
                app_logging.swallowed()
            handle['id'] = None

    try:
        widget.bind('<Destroy>', stop, add='+')
    except Exception:
        app_logging.swallowed()
    tick()
    return tick


def listen(bus):
    """把总线接上：阶段事件 → RUNNING。没总线就什么都不挂。"""
    if bus is None:
        return None

    def listener(item):
        item = item or {}
        mark(item.get('stage'), item.get('kind'), item.get('trigger') or '')

    try:
        return bus.subscribe('*', listener)
    except Exception:
        return None


# ── 二、手动制作弹窗要的三行摘要 ────────────────────────────────────────────
def project_of(desktop):
    root = getattr(desktop, 'root', None)
    return Path(root) if root else None


def selected_skills(project, stage):
    """这一步勾上的 SKILL 名字（读不出来就是空表）。"""
    if project is None:
        return []
    try:
        import stage_config
        return [str(name) for name in (stage_config.get(project, stage).get('skills') or [])]
    except Exception:
        return []


def model_label(desktop, project, stage):
    """弹窗「模型」那一行：挑过的写模型名，没挑过写「自动」。"""
    try:
        import stage_config
        chosen = str(stage_config.get(project, stage).get('model') or '')
    except Exception:
        chosen = ''
    if not chosen or chosen == model_router_AUTO:
        return '自动'
    try:
        import model_pool
        return str(model_pool.label_of(chosen, program=getattr(desktop, 'app', None) or None))
    except Exception:
        return chosen


def paid_count(stage, names=None):
    """这一步会花钱的 SKILL 有几个（表读不出来就按 0）。"""
    try:
        import skill_registry
        known = {skill.name: skill for skill in skill_registry.default_registry().getByStage(stage)}
    except Exception:
        return 0
    if names is None:
        return sum(1 for skill in known.values() if skill.paid)
    return sum(1 for name in names if name in known and known[name].paid)


def state_of(project):
    """项目里那份阶段状态（读不出来就当空：一律按「没失败」算）。"""
    if project is None:
        return {}
    try:
        import pet_state
        machine = pet_state.Machine(project, persist=False).load()
        return {stage: entry.get('state') for stage, entry in machine.stages.items()}
    except Exception:
        return {}


def blockers(project, stage):
    """这个阶段缺哪些前置：明确失败的前置，加上门禁挡住的上游。

    旧阶段没状态文件、前置还没开始时不拦——用户想先做哪一步就做哪一步，这条规矩从第 47 期
    起一直是这样；只有前置真的翻了车才把「直接执行」按下去，让他先回去收拾。

    第 63 期任务 3.2 又加了一条同样的口径：上游**真的做了却没做全**（资产没锁完、台账没
    生成、批次没划完……）时也挡住，并说清缺什么、去哪儿补；旧门禁上游没开始时照旧放行。
    新增 SG-A / SG-B 为强制门禁：缺初稿不能预演，缺预演确认不能投入资产。

    没打开项目时没有状态可看，门禁也无从查起（各门禁检查要读项目文件，传 None 会抛
    TypeError），按「读不出来就当空」处理，与 state_of／selected_skills 同一口径。
    """
    if project is None:
        return []
    states = state_of(project)
    out = []
    for dep in DEPENDS.get(stage, ()):
        if states.get(dep) == 'failed':
            out.append(dep)
    for dep in stage_parallel.blocked_stages(project, stage):
        if dep not in out:
            out.append(dep)
    return out


def _summary_data(desktop, stage, project):
    """弹窗摘要要的那几个数，只算一遍：blockers 每调一次就要按门禁读一遍资产索引、台账与批次。"""
    names = selected_skills(project, stage)
    paid = paid_count(stage, names)
    seconds = max(SECONDS_PER_SKILL, SECONDS_PER_SKILL * max(1, len(names))) if names else 0
    blocked = blockers(project, stage)
    return {'model': model_label(desktop, project, stage), 'skills': len(names),
            'skillNames': names, 'paid': paid, 'seconds': seconds, 'blocked': blocked,
            'blocked_text': ('依赖：' + '、'.join(stage_name(dep) for dep in blocked) + '未完成')
                            if blocked else ''}


def step_summary(desktop, stage, project=None):
    """手动制作弹窗那几行：模型／SKILL 数量／预计＋付费／依赖警告。纯读，不碰界面。"""
    project = project if project is not None else project_of(desktop)
    data = _summary_data(desktop, stage, project)
    return {'stage': stage, 'title': '手动制作：' + stage_name(stage),
            'model': data['model'], 'skills': data['skills'],
            'skillNames': data['skillNames'], 'paid': data['paid'], 'seconds': data['seconds'],
            'blocked': data['blocked'],
            'parallel': parallel_text(stage),
            'gate': stage_parallel.gate_text(project, stage),
            'blocked_text': data['blocked_text'],
            'lines': _lines(stage, data)}


def parallel_text(stage):
    """这一步并行怎么起的一句人话（第 63 期任务 3.1／3.2 的弹窗版）。"""
    return stage_parallel.degree_label(stage)


def summary_lines(desktop, stage, project=None):
    """弹窗默认那三行（最多四行）：模型／SKILL／预计；有依赖问题再补一行警告。

    没打开项目时也按空项目出这几行：从前这里转去 step_summary、step_summary 又以同一个
    None 转回来，两边互相调用直到 RecursionError。"""
    project = project if project is not None else project_of(desktop)
    return _lines(stage, _summary_data(desktop, stage, project))


def _lines(stage, data):
    money = ('付费：约 %d 次调用' % data['paid']) if data['paid'] else '费用未估算，以实际模型调用为准'
    # 第 63 期任务 3.1：并行怎么起并进 SKILL 那一行——弹窗还是最多四行，不另起一行挤掉警告。
    lines = ['模型：' + str(data['model']),
             'SKILL：%d 个已选　并行：%s' % (data['skills'], parallel_text(stage))]
    if data['seconds']:
        lines.append('预计：约 %d 秒，%s' % (data['seconds'], money))
    else:
        lines.append('预计：' + money)
    hint = RECOVERY_HINTS.get(stage, '')
    if data['blocked_text'] or hint:
        lines.append('；'.join(text for text in (data['blocked_text'], '人工／失败处理：' + hint if hint else '') if text))
    return lines[:4]


# ── 三、三虎自动推进：剧本做完之后按依赖图走 ────────────────────────────────
class Auto:
    """自动推进的队长：认一条起点，按依赖图排好队，一步做完推下一步。

    - ``script_done(level)``：剧本完成时叫一次；semi／auto 两档才武装（hint 只通知）；
    - ``next_stage()``：报下一步该做哪一步（没武装／暂停／走完了都给 None）；
    - ``done(stage, ok)``：这一步成功收场才往下挪一格；失败会阻塞在当前阶段，等用户处理；
    - ``pause()``／``resume()``：用户按的「暂停自动／恢复自动」。
    """

    def __init__(self, order=None, clock=None, gate=None):
        import time as _time
        self.order = list(order or OWN_ORDER)
        self.clock = clock or _time.monotonic
        # 第 63 期任务 3.2：门禁。给的是「这一步能不能走」的判定（返回一句人话或空串）；
        # 没给就是不设闸，行为与第 54 期完全一样。
        self.gate = gate
        self.blocked = None
        self.armed = False
        self.paused = False
        self.level = ''
        self.index = 0
        # 已派发的异步阶段必须先收场；否则心跳每一拍都会把下游也派出去，
        # 剧本结构还在写 script.md 时分镜就开始读，最终表现为自动制作失败。
        self.active = None
        self.at = None
        self.history = []

    def script_done(self, level):
        """剧本做完了：这一档要不要接着往下走。返回有没有武装起来。"""
        self.level = str(level or '')
        self.armed = self.level in AUTO_LEVELS
        self.paused = False
        self.index = 0
        self.active = None
        self.at = self.clock()
        self.history.append(('script.completed', self.level, self.armed))
        return self.armed

    def arm_from(self, level, states=None):
        """第 67 期任务 5：不必等「剧本完成」那一条事件——按项目现状直接武装。

        用户在一个早就做完剧本的项目里切到自动档时，那一条事件永远不会再来（第 54 期起这条
        链只在 script.completed 上武装），于是「自动档什么都不开始」。这里拿项目里每一步的
        状态补上：已经收场的那几步（success／skipped）跳过，队长从第一个没做完的阶段接手。
        states 给不出来时退回 script_done 的老规矩（从头走）。
        """
        self.script_done(level)
        if self.armed and states:
            index = 0
            while index < len(self.order) and str(states.get(self.order[index]) or '') in DONE_STATES:
                index += 1
            self.index = index
        return self.armed

    def pending(self):
        return list(self.order[self.index:]) if self.armed else []

    def next_stage(self):
        """下一步该做哪一步；被门禁挡住时返回 None 并停在这一步（index 不退，等上游补好再走）。"""
        if not self.armed or self.paused or self.blocked or self.active:
            return None
        while self.index < len(self.order):
            stage = self.order[self.index]
            reason = self._gate_reason(stage)
            if reason:
                self.blocked = (stage, reason)
                return None
            self.blocked = None
            self.index += 1
            self.active = stage
            return stage
        self.blocked = None
        return None

    def _gate_reason(self, stage):
        """问一次门禁；门禁自己出错就当没挡住（绝不让一条断言拖住整条链）。"""
        if not callable(self.gate):
            return ''
        try:
            return str(self.gate(stage) or '')
        except Exception:
            return ''

    def done(self, stage, ok=True, reason=''):
        """某一步收场：成功才推进；失败留在原步骤并阻塞整条自动链。"""
        self.history.append((stage, bool(ok), self.at))
        if not self.armed or stage not in self.order:
            return self.index
        position = self.order.index(stage)
        if self.active == stage:
            self.active = None
        if not ok:
            # ``next_stage`` 发出任务时已经先把 index 加一；失败必须退回该步骤，
            # 否则下一次心跳会错误地跳到下游阶段。
            self.index = min(self.index, position)
            self.blocked = (stage, str(reason or '该阶段未完成，等待用户处理'))
            return self.index
        position += 1
        if position > self.index:
            self.index = position
        self.blocked = None
        return self.index

    def pause(self):
        self.paused = True
        return self.paused

    def resume(self):
        self.paused = False
        return self.paused

    def state(self):
        return {'armed': self.armed, 'paused': self.paused, 'level': self.level,
                'index': self.index, 'pending': self.pending(),
                'active': self.active or '', 'blocked': (self.blocked or ('', ''))[0],
                'blocked_text': (self.blocked or ('', ''))[1]}


AUTO = Auto()          # 进程里那一条自动推进的链（Pet 的心跳推它）
