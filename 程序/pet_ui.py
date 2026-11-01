"""宠物窗口（方案 A：主窗口内贴片）＋与现有制作链路的三个接缝。

设计取舍：
- 贴片挂在标题栏右上角（place relx=1.0 anchor='ne'），随主窗口移动、不参与布局计算；标题栏两行文字
  按贴片宽度留白，文字不会被盖住。
- 手绘 Canvas（Q 版橙虎＋大眼＋眨眼），闲置 2fps、忙时 8fps；设计稿另存 assets/sanhu_chibi_avatar.png，运行时仍不加载位图资源。
- 气泡与进度面板是窗口内浮层（place），不是 Toplevel：ui_theme.install_window_placement 会给新建的
  Toplevel 设 -alpha 0 并在 <Map> 时 grab_set，浮层没有这些问题，也天然随窗移动。
- 原逻辑一行不改，只加薄封装：自动任务队列套 StageQueue（get_nowait 时顺手记一笔结果）、状态栏经
  watch_status() 挂一层（原文照旧写进变量，宠物顺手记一笔）、页面按钮经 tap() 调用（成功后上报「用户点了什么」）。
- 第 13 期再加两处：右键菜单／托盘菜单的动作一律经 act() 出去——先把事做完，再把结果说给用户听；
  过去只写 self.notice，而 notice 只有气泡打开时才看得见，「重试失败项」「切换自动化等级」这类动作
  看起来就是没反应。
- 第 14 期：说要说的那句话改成贴片旁边的云朵框（pet_cloud，同样是窗口内浮层）。上一版的对话窗是
  Toplevel，ui_theme 会给新 Toplevel 设 -alpha 0 并在 <Map> 时 grab_set：抓取留在手里，主窗口点哪都
  没反应（「卡死、关不掉」）。云朵框不新建窗口、不抓键盘，顺带承担播报：忙时 12 秒、闲时 60 秒说一次
  进度，未采用的分镜／缺首帧这类缺口一出现就立刻说。
- 第 15 期：云朵框挪到助手界面内容区的左上角（不再压住右上角的标题／状态文字），尾巴三点朝猫咪脑袋指；
  宠物一说话就自动冒出来（不抢焦点），交互结束后自动收起——用户不必再手动打开。头像颜色＝自动化等级：
  全自动红、半自动蓝、只提示黄（由 LEVEL_COLORS 决定，心情色只留给托盘图标与动画快慢）。
- 宠物自己不新建任何 Tk 变量：Tk 变量若在 worker 线程被 GC 回收，__del__ 会跨线程调 Tcl，轻则报
  main thread is not in main loop，重则与正在 update() 的界面线程互相等待而卡死。
- 所有分发都在既有 150ms 心跳里 pump，不开新线程、不加新轮询。
- 第 22 期：独立小窗与自绘气泡两个功能整个删掉（pet_window.py／pet_toast.py 连同用例一起删）。
  对用户说话只剩一条出口——三虎的云朵框；进度与待确认明细也在这儿展示。
- 第 43 期：模型设置从「换模型」那个硬编码档位下拉升级成模型池（规格《三虎模型设置》）：
  右键「三虎设置 → 模型…」配三虎四个任务维度，「切换模型」列出池里每一条、当前那条打 ✓，
  末项「+ 新增模型…」跳模型管理；改完写盘 ＋ 就地生效，不用重启。
"""
from ui_tokens import PET_PALETTE
import os
import queue
import datetime
import random
import sys
import time
from pathlib import Path
from tkinter import TclError

import model_pool
import model_router
from app_metadata import APP_NAME
from broadcaster import Broadcaster, PREFIX_PATTERNS
import pet_agent
import pet_cloud
from pet_chat_coordinator import ChatCoordinator
import pet_bus
import pet_llm
import pet_report
import pet_state
import stage_handler_registry
import stage_flow
import stage_parallel
import token_saver
from pet_settings_contract import LEVEL_NOTES
from ui_widgets import ContextMenu, ask_confirmation
from ui_tokens import PET_LAYOUT
from pet_broadcast_state import PetBroadcastAliasesMixin, PetBroadcastState, PetOfferState
from pet_ui_stages import PetStagesMixin
from pet_ui_settings import PetSettingsMixin
from pet_ui_voice import PetVoiceMixin
from pet_ui_view import PetViewMixin
from pet_ui_popup import PetPopupMixin
from pet_ui_support import ACTIVE_MS, ADVANCE_SECONDS, AUTOSTART_KEY, AUTOSTART_NAME, AUTO_STAGE_VARIABLES, AUTO_VARIABLE_NAMES, AWAY_PAUSE_SECONDS, Autostart, BANNER_HOUR, BROADCAST_BUSY, BROADCAST_IDLE, BUSY_TAPS, BUSY_WINDOW, CANVAS_BG, CAPTION_INK, CAPTION_RIGHT, CAPTION_ROOM, CAPTION_Y, CHAT_HINT, CHAT_MUTE_SECONDS, CONFIRM_NEED, CONFIRM_TITLE, DETAIL_MENU_LABEL, FALLBACK_ASK, GAP_SECONDS, GEAR_COLOR, GEAR_HOVER, GEAR_SIZE, GEAR_TIP, GREET_DELAY_MS, GREET_QUIET_SECONDS, GearButton, HEAD_PAD, ICE, IDLE_MS, INK_SOFT, LEVEL_CAPTIONS, LEVEL_COLORS, LEVEL_SWITCH_NOTES, MOODS, OFFER_NO, OFFER_REPEAT, OFFER_SECONDS, OFFER_YES, ONE_CLICK_ASK, ONE_CLICK_TITLE, PAGE_ASKS, PANEL_DIVIDER, PANEL_HEAD, PANEL_MENU_LABEL, PANEL_SECTIONS, PATCH_ROOM, PATCH_X, PAUSED_CAPTION, PAW_ARC, PAW_COL_GAP, PAW_COL_HEIGHT, PAW_COL_WIDTH, PAW_COL_X, PAW_COL_Y, PAW_COLORS, PAW_GAP, PAW_GAP_Y, PAW_HOVER, PAW_IDLE, PAW_LEVELS, PAW_SIZE, PAW_STEP, PROGRAM, PROGRESS_GAPS, PROGRESS_SECONDS, PROJECT_CACHE_SECONDS, PROJECT_CLOSED, PROJECT_LIMIT, PROJECT_OPEN, QUIT_LABEL, REPORT_QUIET_SECONDS, SANHU_BLUSH, SANHU_EAR, SANHU_FUR, SANHU_INK, SANHU_MODES, SANHU_MUZZLE, SANHU_STAR, SETTINGS_ENTRIES, SETTINGS_LABEL, SIZE, SNOOZE_SECONDS, SPEAK_GAP_SECONDS, SPOKEN_KEEP, STAGE_ASK_SECONDS, TONGUE, WEEKLY_FROM, _BooleanFlag, _UNSET, _settings_entries, asset_counts, autostart_command, duration, flourish, gear_parts, paint, palette, paw_dy, paw_parts, shot_stats, startup_api






def should_auto_run(owner, project, stage_id):
    """页面唯一的自动执行判定入口。"""
    pet = getattr(owner, 'pet', None)
    return bool(pet is not None and pet.should_auto_run(stage_id))
                                                  # 中间那只最低、两边各抬 PAW_ARC 像素（猫爪落地的样子）。
KEEP = 20
BLUSH = PET_PALETTE['blush_cool']                 # 撒娇时的腮红：冷玫瑰蓝，不是粉
# 第 25 期第 3 条：三虎自己看着制作进度，到了该收尾的时候主动问一句「要不要一键自动执行」，
# 并把选择项摆出来。问得比播报稀一点：同一批缺口最短隔 OFFER_SECONDS 才问，缺口一直不变也过
# OFFER_REPEAT 再提一次；用户答「好」就照一键执行那条路走（会花钱的步骤照旧只由他自己按）。
OFFER_TITLE = '要不要一键执行'

PROGRESS_MS = 12000                               # 进度圆气泡停留多久
# 第 37 期第 6 条：用户要「切回助手界面时不用弹聊天框」——回来只把自动执行接上，一个字都不说。
# 第 18 期：模型档位改成一张登记表——「切换模型」栏按它生成。第 43 期起这张表里的模型来自
# 模型池（模型管理）：池里加一条，子菜单里立刻多一项；这里只剩「自动」这一条出厂项，
# 以及 register_tier() 那个「把外部模型接进这一栏」的接口。
TIER_MODELS = {'auto': ('自动', {'force_tier': ''})}
TIER_CYCLE = tuple(TIER_MODELS)                   # 登记表里的档位顺序（池里的模型另按池的顺序排）
TIER_NAMES = {tier: label for tier, (label, _override) in TIER_MODELS.items()}


def tier_models():
    """登记表的只读快照：现在有哪几档模型，接新模型之后这里自动多一项。"""
    return {tier: label for tier, (label, _override) in TIER_MODELS.items()}


def register_tier(tier, label, override=None):
    """预留接口（第 18 期）：把另一个模型登记成「换模型」栏里的一档。

    tier 是内部代号（客户端配置里 force_tier 用的就是它），label 是菜单上的人话，override 是
    要合并进客户端 config 的键值对（不给就按 force_tier=tier）。重名就改那一行。
    """
    global TIER_CYCLE, TIER_NAMES
    name = str(tier or '').strip()
    if not name:
        return tier_models()
    pairs = {'force_tier': name} if override is None else dict(override)
    TIER_MODELS[name] = (str(label or name), pairs)
    TIER_CYCLE = tuple(TIER_MODELS)
    TIER_NAMES = {key: value[0] for key, value in TIER_MODELS.items()}
    return tier_models()
PANEL_TITLE = '进度面板'                           # 第 68 期任务 4：用户要它就叫「进度面板」，不再挂「三虎」
CLICK_MS = 220                    # 单击贴片：等这么久没有第二下就弹功能下拉栏（双击＝说话）
# 第 17 期：三虎的猫样。右上角那只猫不再是一张定住的脸——随机做点猫的事：
# 爬行（整只轻轻挪＋多两只爪子）／舔爪／打哈欠／摇尾巴／撒娇。独立窗开着时还会沿桌面右上角漫游。
POSES = ('sit', 'walk', 'lick', 'yawn', 'wag', 'nuzzle')
POSE_NAMES = {'sit': '端坐', 'walk': '爬行', 'lick': '舔爪', 'yawn': '打哈欠',
              'wag': '摇尾巴', 'nuzzle': '撒娇'}
POSE_MIN, POSE_MAX = 6, 24        # 一个动作持续 6~24 帧（闲置 2fps ≈ 3~12 秒；忙时换得更快）

















class Cat:
    """三虎的猫样：随机换动作，一段动作持续若干帧。

    第 17 期：右上角那只猫不再是一张定住的脸——过一阵就自己换个动作（爬行／舔爪／打哈欠／
    摇尾巴／撒娇）。接缝设计：
    - rand 可注入（默认 random.random）：用例不必跟真随机较劲，注入固定序列就能复现；
    - 换动作绝不与上一个重复：连着两次一样就等于没换，看着像卡住了；
    - rand 坏掉（抛异常／NaN／负数／大于 1）一律当 0 处理，绝不把界面线程带崩。
    """

    def __init__(self, rand=None, span=(POSE_MIN, POSE_MAX), poses=POSES):
        self.rand = rand or random.random
        self.span = (max(1, int(span[0])), max(1, int(span[1])))
        self.poses = tuple(poses) or POSES
        self.pose = self.poses[0]
        self.until = 0                # 到这一帧就换下一个动作
        self.changes = 0              # 换过几次动作（日志与用例用）

    def roll(self, size):
        """把 rand() 夹成 [0, size-1] 的整数：坏值一律当 0，绝不让它冒到调用方。"""
        size = int(size)
        if size <= 1:
            return 0
        try:
            value = float(self.rand())
        except Exception:
            return 0
        if value != value or value < 0.0:      # NaN 与负数
            return 0
        return max(0, min(size - 1, int(value * size)))

    def pick(self, exclude=None):
        """随机挑一个动作：绝不与 exclude（上一个动作）重复。"""
        pool = [name for name in self.poses if name != exclude] or list(self.poses)
        return pool[self.roll(len(pool))]

    def next(self, frame, force=False):
        """返回这一帧该摆的姿态；到点（或 force=True）就换一个并重新计时。"""
        frame = int(frame)
        if force or frame >= self.until:
            self.pose = self.pick(exclude=self.pose)
            self.changes += 1
            low, high = self.span
            self.until = frame + low + self.roll(high - low + 1)
        return self.pose

    def describe(self):
        """给日志与用例的一眼快照。"""
        return {'pose': self.pose, 'name': POSE_NAMES.get(self.pose, self.pose),
                'until': self.until, 'changes': self.changes, 'span': self.span}


class StageQueue:
    """自动任务队列的薄包装：get_nowait 成功时把 (阶段, 结果) 报给 sink，其余接口原样转发。

    sink 里的异常必须吞掉——这里是 _tick_once 的取件路径，抛出去会让整个 150ms 心跳断掉。
    """

    def __init__(self, stage, sink=None, inner=None):
        self.inner = inner if inner is not None else queue.Queue()
        self.stage = stage
        self.sink = sink
        self.errors = pet_bus.ErrorLog()  # 心跳不可中断，但失败必须留下可核记录。

    def get_nowait(self):
        item = self.inner.get_nowait()
        if self.sink is not None:
            try:
                self.sink(self.stage, item)
            except Exception as exc:
                # 此处是队列消费的通知支线，不能让 150ms 心跳停摆；
                # 但不再裸吞，调用方可从队列实例读到失败原因。
                self.errors.append(('sink', str(exc)))
        return item

    def put(self, item, *args, **kwargs):
        return self.inner.put(item, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def __len__(self):
        return self.inner.qsize()


def watch_status(desktop, pet):
    """接缝④：在既有状态栏变量外挂一层 set——原文照旧写进变量，宠物顺手记一笔（同一句话只算一次）。

    只包住这一个实例的 set，不碰 tkinter.Variable 类，也不新建任何 Tk 变量：变量仍由界面线程创建与回收，
    宠物只负责记一笔。重复挂载幂等（_petWatched），没有状态栏变量时原样返回 None。
    """
    var = getattr(desktop, 'status', None)
    if var is None or getattr(var, '_petWatched', False):
        return var
    original = var.set

    def set_(value):
        text = '' if value is None else str(value)
        original(text)
        try:
            pet.say(text)
        except TclError:
            # 关窗后宠物气泡不再可用；普通 pet.say 失败不可吞没。
            pass

    var.set = set_
    var._petWatched = True
    return var


def report_done(host, stage, text):
    """接缝⑤：某一步的手工制作收了尾，说给三虎听（第 47 期第 5 条）。

    宿主没接这条线（自检里的假宿主、还没挂宠物的窗口）就静默返回，页面逻辑一个字不受影响。
    真正的播报在 Pet.report_done 里；这里只负责「找得到就报」。报告器本身故障
    是阶段状态链故障，必须由调用者处理，不能假装这一步已经完成。
    """
    report = getattr(host, 'pet_report', None)
    if not callable(report):
        return None
    return report(str(stage), str(text))










def config(program=PROGRAM):
    """共享配置文件原样读出：pet_llm.load_config 只认它自己的键，宠物自己的开关要另看一眼。

    文件没有、读坏了都当空表——「没配置」与「配置写错」都必须退化成默认（不开），
    不能把异常丢进界面线程。
    """
    try:
        data = pet_bus.read_json(pet_agent.config_file(program))
    except Exception:                      # 连路径都算不出来（程序目录不可用）也当没配置
        data = {}
    return data if isinstance(data, dict) else {}










def our_process_in_front():
    """前台窗口是不是本进程的窗口：用户切到别的应用上去了就返回 False（第 30 期第 3 条）。

    用户报的是「切到其他应用时三虎还弹聊天框」——判据就取「现在最上面那扇窗是谁的」：
    GetForegroundWindow 拿到句柄，再问这个句柄属于哪个进程；不是本进程就是别的应用在前台。
    认不出来（非 Windows、拿不到句柄、调用出错）一律当 True——宁可多说一句，也不能把播报全吞掉。
    """
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = int(user32.GetForegroundWindow())
        if not hwnd:
            return True
        pid = ctypes.c_ulong(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value) == os.getpid()
    except Exception:
        return True


def _click_pause(pet, at):
    pet.agent.pause('您在气泡里按了暂停')
    pet.auto.pause()
    pet.pause_running_stage()
    pet.announce('已暂停自动执行：宠物只报告进度，不再自动推进', at=at)


def _click_resume(pet, at):
    pet.agent.resume()
    pet.auto.resume()
    pet.announce('已继续自动执行：按当前自动化等级推进，会花钱的步骤仍需您确认', at=at)


def _click_level(pet, at):
    # 按一次换一档；子菜单里可以直接点到某一档（set_level），两条路共用同一套实现。
    order = list(pet_agent.LEVELS)
    pet.set_paw_level(order[(order.index(pet.agent.level) + 1) % len(order)], at=at)


def _click_snooze(pet, at):
    pet.snooze()
    pet.notice = '好，安静 %d 分钟：这段时间只记账，出安静期再报一次' % (SNOOZE_SECONDS // 60)


# 一键操作的意图 → (动作, 是否把动作的返回值直接交还调用方)。动作里的 pet 方法都在调用时才取，
# 测试替换宠物上的方法照样生效。
_CLICK_ACTIONS = {
    'pause': (_click_pause, False),
    'resume': (_click_resume, False),
    'retry': (lambda pet, at: pet.retry_failures(), False),
    'oneclick': (lambda pet, at: pet.one_click(at=at), True),
    'level': (_click_level, False),
    'chat': (lambda pet, at: pet.open_chat(), True),
    'skip': (lambda pet, at: pet.skip_failure(), False),
    'model': (lambda pet, at: pet.switch_model(), False),
    'snooze': (_click_snooze, False),
    'details': (lambda pet, at: pet.show_details(), False),
}


class Pet(PetBroadcastAliasesMixin, PetStagesMixin, PetSettingsMixin, PetVoiceMixin, PetViewMixin, PetPopupMixin):
    """贴片宠物：画自己、说人话、把事件喂给父 Agent。界面线程独占，全部方法不抛异常。"""

    def __init__(self, desktop, clock=time.time, front=None):
        self.desktop = desktop
        self.win = desktop.win
        self.clock = clock
        self.errors = pet_bus.ErrorLog()
        self.bstate = PetBroadcastState()  # 播报状态六件（notice／last_status／判重／压住／推进节流）收在这里
        self.frame = 0
        self.attempts = {}
        self.canvas = None
        self.menu = None
        self._timer = None
        self._main_topmost_job = None
        self._project = object()          # 哨兵：第一次访问 core() 一定会重建
        self._core = None
        self._client = None
        self._client_project = object()
        self._flushed = 0
        self._tick_texts = set()
        self.report_path = None
        self.weekly_path = None
        self._autostart = None
        self.snooze_until = 0.0           # 「稍后再说」到什么时候为止（时钟可注入，用例不用真等）
        self._busy_taps = []              # 第 60 期第 1 条：用户刚才那几下动作的钟点（判「人正忙」）
        self._menu_labels = {}            # 已经写进菜单的文字，避免每 150ms 白改一遍
        self.menu_index = {}
        self.program = PROGRAM            # 第 43 期：全局配置在哪个目录（用例里可指到临时目录）
        self.broadcaster = Broadcaster(str(self.program / 'logs' / 'sanhu_progress.log'))
        # 第 67 期任务 4：这一次运行的档位。开机那一下定成「只提醒」，之后换项目重建内核
        # （core 会重读盘上的设置）也照它来——不记下来的话，一打开项目就把用户存档里的
        # 旧档位读回来了，「开机一律只提醒」等于没做。
        self.session_level = ''
        # 三虎模式与既有三档自动化等级并存：模式只决定是否统一接管页面自动开关；
        # 等级仍保留 hint／semi／auto 的细粒度审批语义。
        self.mode = 'manual'
        self._auto_variables = {}
        self.probe_transport = None       # 「测试连接」用的传输函数（None＝真发；用例注入假函数）
        self._agent_file = None           # 上一次写盘写到的配置文件（排查时看得见）
        # 第 43 期：「切换模型」的当前档位＝模型池里的一个 id（或「自动」），开局按盘上的设置对表。
        self.tier = str(self.agent_model_tasks().get('default') or model_pool.AUTO)
        self.chat = None                  # 第 14 期云朵框：开着时是云朵对象，收起是 None
        self._cloud = None                # 云朵框实例（只建一次，收起再开保留记录）
        self._broadcast_at = None         # 上一次播报的钟点（频率控制，注入时钟可测）
        self._menu_open = False           # 第 47 期第 4 条：功能下拉栏正显示着（这期间不冒云朵框）
        self._gap_sig = None              # 上一次算出来的缺口指纹：变了就立刻播报
        self._spoken = {}                 # 第 57 期第 2 条：刚说过的那几件事（key → 钟点）
        self._gap_at = None               # 上一次算缺口的钟点（读盘很贵，按 GAP_SECONDS 节流）
        self._gap_cache = []              # 最近一次算出来的缺口
        self._chat_interaction = ChatCoordinator(
            schedule=lambda delay, callback: self.win.after(delay, callback),
            cancel=self._cancel_chat_click, delay=CLICK_MS,
            visible=lambda: self.cloud_visible(), open_chat=lambda: self.open_chat(),
            close_chat=lambda: self.close_chat(), mute=lambda **kw: self.dismissed(**kw),
            on_error=lambda name, message: self.errors.append((name, message)))
        self._greet_id = None             # 还没到点的开机招呼（关窗比招呼先到时必须收回来）
        self._quiet_until = None          # 招呼之后的安静期到哪一刻（第 68 期任务 11）
        self.cat = Cat()                  # 第 17 期：三虎的猫样（随机做点猫的事，见 Cat）
        self.caption = None               # 第 18 期：贴片左边那行小字（正常／半自动／全自动）
        self.menu_tier = None             # 「换模型」子菜单：接新模型时按登记表整栏重建
        self.menu_mode = None             # 「模式」子菜单：手动／全自动的唯一界面入口
        self.mode_var = None              # 仅绑定菜单单选状态；自动制作变量仍只归三虎管理
        self.paws = None                  # 第 19 期：贴片左边那排猫爪按钮（自动化等级）
        self.gear = None                  # 第 44 期：窗口左上角那颗齿轮（设置入口）
        self._paws_key = None             # 上一次画的样子（档位 ＋ 悬停在哪只爪）：没变就不白画一遍
        self._paw_hover = None            # 鼠标这会儿停在第几只爪上（None＝没停）
        self._paw_focus = None            # 键盘焦点落在第几只爪上（None＝没落）
        self.paw_hits = []                # 三只猫爪各自的 32×32 外层承接区
        self._lifted_at = None            # 上一次把贴片抬到最上层的钟点
        self._progress_at = None          # 上一次冒进度圆气泡的钟点（三虎自己判断时机）
        self._progress_stage = None       # 上一次冒进度气泡时的阶段：换阶段就再说一次
        self._progress_said = ''          # 上一条进度气泡的原文（第 49 期第 3 条：一字不差就不再冒）
        self._mute_until = 0.0            # 云朵框被点掉之后，安静到什么时候（别被自动播报顶回来）
        self._activity = []               # R1948：用户最近几下动作（点按钮、切页）的钟点，定云朵停留多久
        self._dismissals = []             # R1948：用户最近几次主动点掉云朵的钟点，定安静期多长
        self.asker = None                 # 一键执行前的确认弹窗：None＝系统 messagebox（用例可注入）
        self.recovery_asker = None        # 中断恢复选择器：None＝系统输入框（用例可注入）
        self._recovery_from = None        # 开机恢复选择的 (stage, step)，下一次同阶段执行时消费
        # 第 54 期附件四：自动推进那条链的队长。剧本做完（script.completed）且等级是
        # semi／auto 时武装起来，之后逐阶段往下走；暂停／恢复就是它的 pause／resume。
        self.auto = stage_flow.AUTO
        # 第 63 期任务 3.2：自动推进之前先过阶段间门禁——上游真的做了却没做全就停在这一步，
        # 说一句「缺什么、去哪儿补」；上游压根没开始时照旧往下走（第 47 期起的规矩）。
        self.auto.gate = self.gate_reason
        self._gate_said = ''              # 上一次因门禁停住时说过的那句：同一句不重复念
        self.main_view = None             # 注入判据：True＝人在主界面（None＝按焦点所在顶层窗口判，见 in_main_view）
        self.front = front                # 第 30 期第 3 条：前台判据（None＝不设这道闸，见 attending）
        self._away_since = None           # 第 35 期第 1 条：离开助手界面的钟点（None＝人在界面里）
        self._away_paused = False         # 上面那次离开有没有把自动执行暂停下来（只认自己停的那一次）
        self._banner_key = None           # 关软件那张标签框当天的签名：报过一次就不再弹
        self._last_advance = ''           # 上一次推进说的话：同一句不重复念
        self._notice_step = False         # notice 是不是「清一色的操作步骤」（第 24 期第 5 条）
        self._panel_at = None             # 用户上一次自己打开进度面板的钟点（第 24 期第 10 条）
        self.offer = PetOfferState()      # 「要不要一键执行」追问的五件状态（第 25 期第 3 条；R2281 起只由 PetVoiceMixin 写）
        self._stage_page = None           # 第 36 期第 6 条：上一次问过的那一页（换了页才问）
        self._stage_at = None             # 上一次问「这一步要不要我做」的钟点
        self._stage_auto_started = set()  # 已由进页全自动启动过的阶段，切页／刷新不重复派发
        self._work_at = None              # 第 36 期第 5 条：上一次看见制作动静的钟点
        self._report_key = None           # 第 36 期第 5 条：这一天的日报／周报提过没有
        self._projects_rows = None        # 第 37 期第 1 条：全部项目的快照（带 TTL 缓存）
        self._projects_at = 0.0           # 上一次读盘对表的钟点
        self._test_session = None         # P2 测试模式：既有心跳轮询的增量自检子进程
        self._performance_session = None  # P2 优化模式：既有心跳轮询的短基准子进程

    # ── 项目级内核：总线＋状态机＋父 Agent ─────────────────────────────────
    def client(self, project=None):
        """LLM 客户端：同一个项目复用一份；规则未命中才会真的发请求。

        先读配置文件的设置，再把「换模型」按下的档位叠上去：只覆盖 force_tier 一项，
        base_url／密钥来源／错峰窗口这些照旧来自配置文件。
        """
        if self._client is None or self._client_project != project:
            self._client_project = project
            settings = dict(pet_llm.load_config(program=self.program))
            settings.update(self.tier_config())
            self._client = pet_llm.Client(project=project, program=self.program, clock=self.clock,
                                          config=settings)
        return self._client

    def core(self):
        """按当前项目重建内核（换项目时整体换一套，不串台）。"""
        project = Path(self.desktop.root) if getattr(self.desktop, 'root', None) else None
        if self._core is not None and self._project == project:
            return self._core
        self._project = project
        bus = pet_bus.Bus(journal=pet_agent.journal_path(project) if project else None)
        machine = None
        if project is not None:
            machine = pet_state.Machine(project, persist=True).load()
            machine.subscribe(bus)
        # 第 44 期：把 program 递下去——父 Agent 的设置（等级／免打扰／预算／动画）与模型池
        # 落在同一个配置目录里，设置页写下去的那几把键这一份立刻就认。
        agent = pet_agent.Agent(project=project, machine=machine, client=self.client(project),
                                bus=bus, persist=project is not None, program=self.program)
        if self.session_level in pet_agent.LEVELS:
            agent.set_level(self.session_level)      # 第 67 期任务 4：照这一次运行的档来
        # 第 37 期第 1 条：三虎要「记住所有项目」——把这份只读快照供给父 Agent，
        # 它在 context() 里带上（问模型时模型也看得见手上有哪些项目）。
        agent.projects = self.projects_brief
        agent.attach(bus, machine=machine)
        # 第 54 期：把「正在跑哪一步」接到总线上（手动按钮据此写「自动执行中」并置灰），
        # 再把自动推进那条链的起点与收场也挂上——剧本完成就按依赖图往下走，
        # 每一步收场（成或败）都让队长往下挪一格。
        stage_flow.listen(bus)
        bus.subscribe('script.completed',
                      lambda item: self.auto.script_done(self.agent.level))
        bus.subscribe('stage.completed', self._auto_stage_completed)
        bus.subscribe('stage.failed', self._auto_stage_failed)
        # 第 63 期任务 3.3：每一次子 Agent 起手／重试／收场都按统一格式记进
        # <阶段目录>/logs/agent_logs.jsonl；收场时把它手上的并发号全还了，闸门不会漏还卡住。
        bus.subscribe('stage.executing', lambda item: self.log_stage(
            item.get('stage'), 'start', str(item.get('trigger') or '')))
        bus.subscribe('stage.retrying', lambda item: self.log_stage(
            item.get('stage'), 'retry', '第 %s 次，%s 秒后重来' % (item.get('attempt'), item.get('delay'))))
        bus.subscribe('stage.completed', lambda item: self.log_stage(
            item.get('stage'), 'ok', release=True))
        bus.subscribe('stage.failed', lambda item: self.log_stage(
            item.get('stage'), 'failed', str(item.get('error') or ''), release=True))
        bus.subscribe('stage.paused', lambda item: self.log_stage(
            item.get('stage'), 'paused', release=True))
        self._core = (bus, machine, agent)
        self.attempts = {}
        return self._core

    @property
    def bus(self):
        return self.core()[0]

    @property
    def machine(self):
        return self.core()[1]

    @property
    def agent(self):
        return self.core()[2]

    def snapshot(self, at=None):
        """本轮进度快照：动画帧、气泡、面板共用同一份数字（出错也不抛）。"""
        try:
            return self.agent.progress(at=at)
        except Exception as exc:
            self.errors.append(('progress', str(exc)))
            return {}

    def _emit(self, kind, **payload):
        return pet_bus.emit_safe(self.bus, self.errors, kind, **payload)









    # ── 事件分发 ────────────────────────────────────────────────────────────
    def pump(self, limit=200, at=None):
        """把总线上的事件分发掉（状态机与通知聚合各自订阅），再把通知说给气泡。

        第 24 期第 5 条：只有「操作步骤」的那一批汇总（notifier.last_step）不进云朵记录——
        notice 是三虎的口吻，云朵记的是它说的话；操作步骤属于状态栏与进度面板。
        """
        bus, _machine, agent = self.core()
        count = bus.pump(limit)
        flushed = agent.flush(at=at) or agent.catch_up(at=at)
        self._notice_step = bool(flushed) and bool(getattr(agent.notifier, 'last_step', False))
        self.notice = flushed or self.notice
        self._tick_texts.clear()
        self.chat_drain()              # 云朵框的后台回答：在这个既有心跳里贴上，不新增定时器
        self.poll_test_mode(at=at)
        self.poll_performance_mode(at=at)
        self.guard_chat_grab()         # 第 59 期第 8 条：有弹窗抽着指针时，聊天框先自己收起来（那时它点不动）
        self.guard_cloud_away()        # 第 60 期第 4 条：人切去别的应用时，露着的云朵自己收起来
        if not self.modal_grabbed():
            self.say_held()            # 弹窗关了：被它挡住的那一句补说
        self.watch_focus(at=at)        # 第 35 期第 1 条：切出去就暂停、回到界面再恢复
        self.tick_broadcast(at=at)     # 播报：按频率说进度，缺口一变化立刻说（第 14 期）
        if agent.client is not None and agent.client.calls and len(agent.client.calls) != self._flushed:
            self._flushed = len(agent.client.calls)
            try:
                agent.client.flush()
            except Exception as exc:
                self.errors.append(('ledger', str(exc)))
        state = self.snapshot(at=at)
        self.refresh(at=at, state=state)
        self.announce_failures()
        self.progress_voice(state=state, at=at)   # 进度：三虎自己挑时机冒圆气泡（第 19 期）
        self.report_hint(at=at)    # 第 36 期第 5 条：下午／夜里活儿慢下来，把日报周报递上来
        self.offer_oneclick(state=state, at=at)   # 收尾的时机到了就主动问一句（第 25 期第 3 条）
        self.refresh_menu_labels()   # 「稍后再说」的倒计时写在菜单上，跟着心跳走
        self.tune_advance(state=state, at=at)   # 自动推进：把「下一步」提前叫醒（第 23 期）
        return count


    # ── 一键操作 ────────────────────────────────────────────────────────────
    def click(self, intent, at=None):
        """气泡/右键菜单的一键操作：只动宠物自己管得到的，其余记成意图事件。"""
        self.note_work(at=at)              # 第 60 期第 1 条：这一下也是「人在忙」的一笔
        action = _CLICK_ACTIONS.get(intent)
        if action is not None:
            run, hand_back = action
            result = run(self, at)
            if hand_back:                  # 一键制作／聊天自己收尾，不再补意图事件
                return result
        self._emit('intent.command', text=str(intent), source='bubble')
        self.refresh(at=at)
        return intent


    def tier_config(self):
        """当前档位对应的客户端配置覆盖：池里那一条 ＋ 降级模型那一条（「自动」时是空的）。

        第 43 期起档位就是模型池里的 id：根地址／协议／密钥名／模型名一起换过去——「模型管理 →
        测试连接」说好的那一条，三虎真发请求时用的就是同一份配置。登记表里另接进来的档位
        （register_tier）仍按它自己写的那份覆盖走。
        """
        records = self.agent_model_records()
        if self.tier in records:
            patch = dict(model_pool.patch_for(self.tier, records))
            patch['force_tier'] = ''          # 换过服务商就不该再被上一档的 force_tier 拉着走
        else:
            patch = dict(TIER_MODELS.get(self.tier, TIER_MODELS['auto'])[1])
        patch['fallback'] = model_pool.patch_for(self.agent_model_tasks().get('fallback'), records)
        return patch


    def tier_name(self):
        """当前档位的人话：外部接进来的档位按登记表，其余按池里的显示名（「自动」就是「自动」）。"""
        return TIER_NAMES.get(self.tier) or model_pool.label_of(self.tier, self.agent_model_records())


    def set_tier(self, tier):
        """「切换模型」点了某一条：写盘 ＋ 立刻生效（规格：配置修改后不用重启）。"""
        wanted = str(tier or '').strip()
        records = self.agent_model_records()
        external = wanted in TIER_MODELS and wanted != model_pool.AUTO and wanted not in records
        if wanted != model_pool.AUTO and wanted not in records and not external:
            return self.tier
        if external:                          # 外部接进来的档位：不写进模型池，只当场生效
            self.tier = wanted
            self._apply_tier()
            self._fill_model_menu()
            self.refresh_menu_labels()
            self.notice = '已切换到 %s' % self.tier_name()
            return self.tier
        tasks = dict(self.agent_model_tasks())
        tasks['default'] = wanted
        self.save_agent_models(tasks, notice='已切换到 %s' % model_pool.label_of(wanted, records))
        return self.tier

    def register_model(self, tier, label, override=None):
        """预留接口：把别的模型接进「切换模型」栏（登记完这一栏立刻重建，点得到）。"""
        options = register_tier(tier, label, override)
        self._fill_model_menu()
        self.refresh_menu_labels()
        self.notice = '已接入新模型：%s（「切换模型」栏里可以直接点）' % TIER_NAMES.get(tier, label)
        return options




























































































































































    def _fill_model_menu(self):
        """按模型池重排「切换模型」（模型管理里加／删了一条之后调它一次就跟着变）。"""
        sub = self.menu_tier
        if sub is None:
            return None
        sub.clear()
        records = self.agent_model_records()
        entries = [(model_pool.AUTO, model_pool.AUTO_LABEL)]
        entries.extend((model_id, item['label']) for model_id, item in records.items())
        entries.extend((tier, label) for tier, label in tier_models().items()
                       if tier != model_pool.AUTO and tier not in records)
        for model_id, label in entries:
            mark = '✓ ' if model_id == self.tier else ''
            sub.command(mark + label, lambda value=model_id: self.act(lambda: self.set_tier(value)))
        sub.separator()
        sub.command('+ 新增模型…', lambda: self.act(self.open_model_manager))
        return sub






















def attach(desktop, clock=time.time, autostart=None, front=None):
    """接缝总入口：Desktop.__init__ 里调用一次，返回并挂上宠物控制器。

    第 22 期：独立小窗（pet_window）与自绘气泡（pet_toast）两个功能按用户要求整个删除，
    参数里的 window／toast 也跟着去掉——不再有「传了也没用」的空挡。
    autostart：None＝按默认（开机自启默认开着，注册表里没有就补上）、False＝一个字节都不动注册表。
    第 19 期撞掉了系统托盘，参数里不再有 tray。
    """
    pet = Pet(desktop, clock=clock, front=front)
    desktop.pet = pet
    try:
        pet.build()
    except Exception as exc:
        pet.errors.append(('build', str(exc)))
    if autostart is not False:
        pet.autostart_default()
    pet.refresh_menu_labels()
    return pet
def start(desktop, delay_ms=GREET_DELAY_MS):
    """开机那一下（第 18 期）：清掉上一次的对话，再让三虎用云朵框打个招呼。

    退回主循环之后再招呼——Desktop.__init__ 里主窗口还没映射出来，云朵框拿不到贴片的坐标。
    返回挂上的定时器；没有宠物就什么也不做。
    """
    pet = getattr(desktop, 'pet', None)
    if pet is None:
        return None
    try:
        pet.start_level()              # 第 67 期任务 4：开机一律回到「只提醒」档
    except Exception as exc:
        pet.errors.append(('start.level', str(exc)))
    try:
        pet.reset_cloud()
    except Exception as exc:
        pet.errors.append(('start', str(exc)))
        return None
    try:
        pet.recover_project_checkpoint()
    except Exception as exc:
        pet.errors.append(('start.recovery', str(exc)))
    return pet.schedule_greet(delay_ms)


def tap(desktop, label, fn):
    """接缝③：按钮的薄封装——原逻辑照旧先跑，成功后再上报「用户点了什么」。"""
    result = fn()
    pet = getattr(desktop, 'pet', None)
    if pet is not None:
        try:
            pet.tap(label)
        except Exception as exc:
            pet.errors.append(('tap', str(exc)))
    return result


def pump(desktop, limit=200, at=None):
    """接缝①：_tick_once 末尾调用——把事件搬进状态机与宠物（同一个 150ms 心跳，无新线程）。"""
    pet = getattr(desktop, 'pet', None)
    if pet is None:
        return 0
    try:
        return pet.pump(limit=limit, at=at)
    except Exception as exc:
        pet.errors.append(('pump', str(exc)))
        return 0
