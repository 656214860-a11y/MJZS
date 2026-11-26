# -*- coding: utf-8 -*-
"""宠物云朵框（第 14 期；第 16 期改成贴着三虎脑袋的漫画对话框浮窗）。

为什么是浮窗（第 16 期）：
- 用户要的是漫画对话框：云朵从三虎头上朝左上铺开，尾巴尖落在它脑袋上，允许伸到助手界面外面。
  界面里的浮层做不到——贴片在窗口右上角，往左上铺的云身大半落在窗口之外，被窗口边界裁掉。
- 所以这里是一扇无边框、置顶、自己管 -alpha 的 Toplevel，位置按「贴片脑袋的屏幕坐标」算：
  云身右下角贴着脑袋的左上，尾巴三点从云身右下角朝脑袋连过去。
- 第 13 期那个「卡死」的坑照旧绕开：建窗后立刻 _positioned_once=True（ui_theme 不接手），
  自己在 <Map> 时 grab_release（ui_theme 会 grab_set），绝不调用 grab_set。

怎么画的：
- Tk 没有「圆角描边」：先把同一圈圆整体放大两像素画一遍当描边，再按原尺寸画一遍当填充，
  就是干净的云边；外面那层底色用 -transparentcolor 透掉，看着是一朵飘在桌面／界面上的云。

怎么看（第 16 期）：
- 记录带序号、编号与正文同一行、段间不空行；比云身长时用滚轮上下翻，一有新的就自动落到最新
  那一段（第 24 期：行末自动换行，每行放满再断）。
- 一亮就淡入（浮出），说完留够读完的时间再淡出去（第 24 期：按字数算，见 read_hold），
  交互没结束就不收。

第 24 期（用户这一轮的十条里落在这一朵云上的那几条）：
- 云朵对话框改成方框（用户要的「正方形」：四角只留一点点圆）；
  第 25 期起这一格改成用户给的那张图上的云朵框；
- 四种形状共用一根「斜向外伸、两边带弧度」的尖角尾巴（第 24 期：弧是用二次贝塞尔折线画的，
  Tk 的多边形画不了曲边），尖角落在三虎的**脸颊**上（第 22 期指的是嘴边）；
- 记录里只有三虎的播报与用户自己说的话：编号和正文同一行，行末自动换行，段间不再空一行
  （用户要的「每行文字尽量放满后再自动换行」）；用户的操作步骤由 pet_ui 拦在外面，不进这朵云；
- 收场一律延时淡出，停留时间按字数算（读得完才收）；界面缩放时尾巴尖钉在脸颊上不动，
  云身自己让开三虎（可以压住界面里的文字，不许压住猫）。

第 25 期（用户给的那张图：云朵框）：
- 爱心框下线，换成图上那种**云朵框**：一圈小鼓包拼出云边、凹口是真的凹进去，尾巴从右下角挑出来，
  尖头照旧钉在三虎的脸颊上（用户要的「统一用图一样式的云朵框，尾巴指向脸颊」）；
- 开机招呼、做动作时的可爱话都用它；方框留给对话、圆留给进度、标签留给日报周报；
- 云身离三虎最多 MAX_GAP 那么远、界面一缩放整朵马上重画（尾巴立刻指到猫的新位置）。

一句话交给 pet_agent.Agent.dispatch：规则命中不花 Token，未命中才问一次 Flash；请求放后台线程，
结果只进 queue.Queue，由宠物既有的 150ms 心跳（Pet.cloud_drain）贴回来——worker 里一行 Tk 都不碰。
"""
import infra.app_logging as app_logging
import queue
import re
import threading
import time
import tkinter as tk
from tkinter import ttk
from ui_widgets import BaseDialog, CloseButton, LineInput

from contract.pet_bus import ErrorLog
from ui.pet_ui_support import accepts_keyword
from pet_agent import PET_NAME as SPEAKER     # 猫咪的名字（三虎）：云朵里每句话都挂在它名下
from ui.pet_cloud_text import reply_lines as _reply_lines, tight
from ui.pet_cloud_geometry import inflate, inside_parts as _inside_parts, rounded_parts, shift_part, square_parts as _square_parts
from ui.pet_cloud_shape import (SHAPE_CLOUD, SHAPE_PUFF, SHAPE_ROUND, SHAPE_TAG, SHAPES,
                             configured_value as _configured_value,
                             normalized as _normalized_shape, text_box as _shape_text_box)
from ui.ui_motion import blend
from ui.pet_cloud_tail import tail_points
from ui_tokens import (CLOSE_BUTTON_ACTIVE_BG, CLOSE_BUTTON_ACTIVE_FG, CLOSE_BUTTON_BG, CLOSE_BUTTON_FG, CLOSE_BUTTON_FONT, CLOSE_BUTTON_MARK, CLOSE_BUTTON_SIZE, COLORS, FONTS, PET_PALETTE, PET_CLOUD_AUTO_CLOSE_MS)
from ui.pet_cloud_timing import ALPHA, FADE_OUT_STEPS, GROW_STEPS, HOLD_MS, READ_MAX_MS, WATCH_RECHECK_MS, CloudTimingMixin
from ui.pet_cloud_move_guard import CloudMoveGuardMixin
from ui.pet_cloud_hint import (HINT_MS, HINT_STEP_PX, HINT_X, REPLY_HINTS, CloudHintMixin, CloudHintState)
from ui.pet_cloud_place import ANCHOR_DROP, CHEEK_X, CHEEK_Y, MARGIN, MAX_BODY, MAX_BODY_DOWN, MAX_GAP, MIN_BODY, PET_GAP, PET_SIZE, POSITION_RETRY_MAX, SHAPE_MIN_BODY, TAIL, TIP_IN, shape_min_body, shape_root, CloudPlaceMixin

WIDTH = 288                       # 方框对话框的宽度（第 21 期收窄；第 28 期随字号放大一档；第 30 期第 4 条再收窄）
PAD = 12                          # 云身内边距
ROW_H = 30                        # 输入行高度
# 第 45 期：用户要「三虎对话框右上角有颗关闭按钮」。带输入行的那一方框对话框顶上因此空出一条
# CLOSE_H（云身跟着长高这么多，正文那块的大小与原来分毫不差），×就摆在那一格的右端。
CLOSE_H = 26                      # 顶上给「关闭」空出的那一条（第 59 期第 9 条：按钮放大，这一条跟着高一点）
CLOSE_SIZE = CLOSE_BUTTON_SIZE    # 那颗×的边长（UX-CLOSE-X 统一 24px 紧凑关闭按钮）
CLOSE_MARK = CLOSE_BUTTON_MARK    # 按钮上画什么：统一乘号 ×
GUTTER = 46                       # 云身右边留给尾巴的那条空档：云身整个站在三虎左边，尾巴从这儿指过去
WRAP = WIDTH - 2 * PAD - 12       # 文字换行宽度（方框这一形状的兜底值）
STARTUP_LAYOUT_SETTLE_SECONDS = 8 # 首帧后的 Tk 空闲布局窗口；期间不能嵌套 spin
FILL = COLORS['background_card']  # 云朵填充：与文字底色一致，看不出框
EDGE = COLORS['border_default']   # 云朵描边
STATUS_INK = COLORS['text_secondary']
BG = COLORS['background_primary'] # 云外那层底色：用 -transparentcolor 透掉
# 第 18 期：四种形状。方框＝平时说话的对话框；云朵框＝打招呼／夸一句这类「与工作无关的可爱话」；
# 圆＝进度；标签＝关软件前的日报／周报。形状只改「云身怎么画、能写字的那块框有多大、用哪两个颜色」。
# 第 24 期：云从「一堆圆叠出来的云」改成方框（用户要的「正方形」）——对话框本来就该是个规矩的框，
# 画成一朵云反倒看不出边界在哪；四角只留一点点圆（SQUARE_ROUND），看着是方框，不是刀切的板子。
# 第 25 期：爱心框下线，换成用户给的那张图上的**云朵框**（一圈小鼓包 ＋ 右下角挑出来的弯尾巴）：
# 打招呼与随口一句的可爱话都用它，尾巴照旧指三虎的脸颊。
# 第 57 期第 1 条：四种框**外形统一成方框**（就是第 24 期对话框那一种）——云朵框那圈鼓包、
# 进度那个椭圆、标签那个大圆角都下线了，只保留颜色的区分（绿＝对话／红＝可爱话／蓝＝提示／
# 清绿＝标签）与各自的宽窄。四个名字留着，是指「用哪两个颜色、多宽」，不再是四种外形。
# 四个名字本身定义在 pet_cloud_shape——pet_cloud_timing 也要用，见那边的说明。
# 第 26 期第 5 条：三种常用框按用途分色——云朵框红、提示框蓝、对话框绿。都取浅底 ＋
# 深一档的描边：底浅才压得住深色正文（正文是 #243247），描边深才在浅色界面上立得住。
# 标签框（关软件那一眼的日报／周报）不在用户点名的那三种里，沿用原来那抹清绿。
SHAPE_COLORS = {SHAPE_CLOUD: (COLORS['background_card'], COLORS['success']),
                SHAPE_PUFF: (COLORS['background_card'], COLORS['danger']),
                SHAPE_ROUND: (COLORS['primary_subtle'], COLORS['primary']),
                SHAPE_TAG: (COLORS['background_card'], COLORS['warning'])}
# 第 57 期第 1 条：四种聊天框（对话框／可爱话／提示／标签）**外形统一成方形框**——原来分四种
# 外形（方框／一圈鼓包叠出来的云／椭圆／大圆角的标签），用户要的是「全部改成方形框，保留颜色的
# 区分」。外形只剩这一份几何，不分工的只剩颜色（SHAPE_COLORS）与宽窄（SHAPE_WIDTH）。
# 四角留一点点圆（SQUARE_ROUND，占云身高）是为了不割手，看着仍是规矩的方框。
SQUARE_ROUND = 0.10                # 方框四角的圆角半径（占云身高）
# 第 27 期第 3 条给圆留的那一档宽度：提示框比对话框瘦一点，进度的字少、框不必那么宽。
ROUND_WIDTH = 336                  # 提示框的宽度
SHAPE_WIDTH = {SHAPE_CLOUD: WIDTH, SHAPE_PUFF: 400, SHAPE_ROUND: ROUND_WIDTH, SHAPE_TAG: 316}
# 第 28 期第 1 条：可爱话那一档从 320 加宽到 400——那句话拆成三行，最大那档字号才装得下。
# 第 58 期第 5 条：量高度只剩这一份口径——「装得下这一条内容」加上一个最小高度（MIN_BODY）。
# 原来 PUFF 200／ROUND 188／TAG 110 各是「一圈鼓包／椭圆／大圆角」内接写字框留下的底数，
# 第 57 期外形统一成方框之后它们就只剩一个效果：一句话也留一大片空白——开机招呼那朵 374×230 的框里
# 只有两行字（用户报的「打招呼的聊天框没有按内容自动调整大小」）。
# 可爱话／提示／标签是「一句话」的贴纸：只带最新那一条（第 21 期把提示框也归到这一类——进度那
# 一段本身就好几行，再把前几条一起搬进来就会挤成一坨，用户报的就是「过大、排版乱」）。
WHISPER_MS = 5200                 # 云朵框（做动作时随口一句）停留多久（第 24 期起还与阅读时间取大）
BANNER_MS = 6000                  # 标签框（关软件前的日报／周报）渐入后停留多久
PROGRESS_MS = 12000               # 进度圆气泡停留多久（与 pet_ui.PROGRESS_MS 同一口径）
GREETING_MS = 5500                # 开机招呼的云朵框停留多久（用户要求再缩短一半，原 11000）；招呼只有两句，直接按它定，不与阅读时间底线取大
WHEEL_PX = 30                     # 滚轮一格翻多少像素
LINE_LIMIT = 40                   # 只留最近这些段，云朵不当地志
NUMBER_GAP = '\u00a0'             # 编号与正文之间那个空档：用不换行空格。普通空格在圆／标签／云朵框这
                                  # 些窄框里会被 Tk 当成换行点，整句正文挪到下一行、头一行只剩一个孤零零
                                  # 的编号（用户第 24 期第 7 条要「编号和文字要在同一行」）。不换行空格
                                  # 把编号和正文粘成一串：框多窄都先把这一行排满，再自动换行。
# 第 49 期第 3 条：用户要「三虎聊天框文字适当缩小」——正文 15 → 13 号；贴纸那一串（下面
# STICKER_FONTS）跟着一起收，不然贴纸还按 15 号排，框的大小跟正文对不上。
FONT = FONTS['pet_body']
# 第 26 期第 7 条：「云朵框内文字不能完整显示」——贴纸（云朵／圆／标签）长不高的时候，
# 字号往下收一档再排，收到装得下为止：从 13 号起（与正文同一个量级），一路收到 9 号兜底——
# 那几档只在「云顶到屏幕上沿、实在没地方」时才用得上，正常情况都停在 13 号。
# 对话框是滚动的记录列表，不参与。
STICKER_FONTS = (13, 12, 11, 10, 9, 8, 7, 6)   # 第 49 期第 3 条：跟着正文从 13 号起试，6 号兜底
TITLE_FONT = FONTS['title']
WELCOME = SPEAKER + '：我在呀。右键菜单能做的事，这里说一句同样能办。'
# 第 37 期第 3 条：用户把招呼改成一／二两句换行：先叫人，再说自己是谁、来干什么。
GREETING = ('哈喽~创造者!\n'
            '我是宠物agent, 三虎! 协助您完成漫剧制作.')
# 第 36 期第 13 条：用户要「删掉最后那串波浪号」——招呼就到此为止。
BUSY = SPEAKER + '正在想…'
EMPTY = '三虎还没问什么，先等等它开口'
TALK_TIP = '点我说一句'
# 第 35 期第 2 条：用户报「确认按钮点了没反应」——那颗按钮整颗删掉，这一行改回回复框：
# 在这儿回一句、按回车发送，走的是原来那条路（有正在等回话的事就照它办，没有就办「这一页
# 该做的那件事」）。三虎要发出去的那句话仍由说话的那一方给（见 Pet.chat_task 与 Cloud.propose）。
REPLY_TIP = '在这儿回我一句，回车发送'          # 回复框空着时提示行写这一句
REPLY_FONT = FONTS['pet_body']                   # 回复框的字号：比正文小一档，一行正好装得下
# 第 37 期第 4 条：基础操作提示放进回复框内的小字。第 88 期改为整句从左向右平移：
# 不再按字符循环截取，避免滚到接缝时把一句话断在中间。
# 第 39 期第 1 条：每一扇对话框的回复框都挂这条小字（见 _render），从最左侧起步、慢慢挪；
# 底用回复框自己的白底——原来刷的是云身色，在框里像贴了一块色片。
HINT_FONT = FONTS['pet_hint']
HINT_FG = COLORS['text_muted']          # 灰：与状态行同一个色系，不抢眼
HINT_BG = COLORS['background_card']     # 小字的底：与 ttk.Entry 的底色一致（量不到时才用这个兜底）
# UX-CLOSE-X：统一关闭按钮契约——常温中性融入卡片底，悬停切清晰红底白 ×。
CLOSE_FG = CLOSE_BUTTON_FG
CLOSE_BG = CLOSE_BUTTON_BG
CLOSE_HOVER = CLOSE_BUTTON_ACTIVE_BG
CLOSE_HOVER_FG = CLOSE_BUTTON_ACTIVE_FG
CLOSE_FONT = CLOSE_BUTTON_FONT
CHAT_KEEP = 6                           # 第 37 期第 6 条：对话框最多留这几段（及时清理）
# 对话框只展示最近五个操作步骤；完整记录仍保留到 CHAT_KEEP，避免浮窗挡住页面操作。
CHAT_VISIBLE_STEPS = 5
MIN_WIDTH = 200                                 # 云身宽度的下限（第 36 期第 12 条：跟着文字收窄，太窄没法读）
# 第 40 期第 3 条：用户要「根据文字内容多少，动态放大缩小云朵框／方形框／圆形框」——四种框
# 都跟着文字收（见 Cloud._fit_width）；第 57 期第 1 条改成统一的方框之后，这里只是各自的
# 宽度下限：可爱话与提示这两种贴纸比对话框瘦一点，再窄一句三五个字就折成两行了。
PUFF_MIN_WIDTH = 240
ROUND_MIN_WIDTH = 216
# 第 57 期第 1 条：四种方框各自收窄时的宽度下限（对话框与标签同一档，可爱话与提示各一档）。
SHAPE_MIN_WIDTH = {SHAPE_CLOUD: MIN_WIDTH, SHAPE_PUFF: PUFF_MIN_WIDTH,
                   SHAPE_ROUND: ROUND_MIN_WIDTH, SHAPE_TAG: MIN_WIDTH}
CONFIRM_PREFIX = '暂时不动手——'   # 回答里带这一句＝这一步要用户点头（drain 会另外弹通知气泡）
# 第 21 期：尾巴从「三个由大到小的圆点」改成漫画对话框那样的一根尖角（用户要的
# 「不使用圆形气泡，尖角处指向三虎耳朵」）——底边长在云身里，只把尖角露在外面。


def reply_lines(result):
    """把 Agent.dispatch 的结构化结果说成人话：回复原文 ＋（没放行时）为什么没动手。

    第 23 期：放行的那一条不再补一句「这一步我可以接着做」——那是句空话，而且放行之后
    真的会动手，做什么由 Pet.run_plan 的结果来说（见 drain）。两句话叠在一起反而看不清
    到底做了没有。
    """
    return _reply_lines(result, SPEAKER, CONFIRM_PREFIX)


def centered_popup_origin(parent_rect, popup_size, work_area):
    """按父窗口中心计算浮窗左上角，并钳在该窗口所在显示器的工作区内。"""
    left, top, width, height = (int(value) for value in parent_rect)
    popup_width, popup_height = (int(value) for value in popup_size)
    work_left, work_top, work_right, work_bottom = (int(value) for value in work_area)
    if width <= 1 or height <= 1:
        return None
    x = left + (width - popup_width) // 2
    y = top + (height - popup_height) // 2
    max_x = max(work_left, work_right - popup_width)
    max_y = max(work_top, work_bottom - popup_height)
    return max(work_left, min(x, max_x)), max(work_top, min(y, max_y))


def square_parts(width, height):
    """方框的云身：一个圆角矩形（第 24 期用户要的「正方形」那种对话框）。

    第 57 期第 1 条：四种聊天框（对话框／可爱话／提示／标签）**外形统一成这一个方框**，
    只保留颜色与宽窄的区分；原来那朵「一圈鼓包叠出来的云」、椭圆、大圆角的标签都下线了。
    四角的圆角由 SQUARE_ROUND 定，很小一档——留一点点圆是为了不割手，看着仍是规矩的方框。
    返回的还是圆角矩形那一套图元（两条去掉端头的矩形 ＋ 四个角圆），两遍描边法对它们一样管用。
    """
    return _square_parts(width, height, SQUARE_ROUND)




def shape_parts(shape, width, height):
    """这一形状的云身由哪些图元拼出来：('oval', cx, cy, r)／('rect', x0, y0, x1, y1)。

    第 57 期第 1 条：四种聊天框一律是同一个方框（圆角矩形）——形状不再分工，只由 SHAPE_COLORS
    分出颜色、SHAPE_WIDTH 分出宽窄。认不出来的名字照旧当对话框。
    """
    return square_parts(width, height)


def inside_shape(shape, width, height, x, y):
    """这个点是不是落在云身里（尾巴的底边得在里面，接缝才会被云身盖住）。

    云身本来就是「一堆图元叠出来」的（方框＝两条矩形 ＋ 四个角圆），所以判定就是
    「落在其中任何一个图元里」——与画出来的
    形状同一口径。描边那 2 像素不算在内，底边往内缩着放，这点余量用不着。
    """
    shape = _normalized_shape(shape, SHAPES, SHAPE_CLOUD)
    return _inside_parts(shape_parts(shape, width, height), x, y)


def shape_colors(shape):
    """这一形状的 (填充色, 描边色)。"""
    return _configured_value(shape, SHAPES, SHAPE_CLOUD, SHAPE_COLORS)


def shape_width(shape):
    return _configured_value(shape, SHAPES, SHAPE_CLOUD, SHAPE_WIDTH)




def shape_min_width(shape):
    """这一形状收窄时的宽度下限（第 57 期第 1 条：四种方框各自的那一档，见 SHAPE_MIN_WIDTH）。"""
    return _configured_value(shape, SHAPES, SHAPE_CLOUD, SHAPE_MIN_WIDTH)


def text_box(shape, width, height, pad=PAD, long=False):
    """能写字的那块矩形（画布坐标 x, y, w, h）。

    第 57 期第 1 条：四种聊天框都是方框，写字框也就只有这一份——云身四边各让开 pad，
    框在云身里横竖都居中，四角离圆角还有富余（字压不到框边上）。shape 与 long 只是签名参数，
    留着是为了调用方（含自检）不必改。
    """
    return _shape_text_box(width, height, pad)


class Cloud(CloudTimingMixin, CloudHintMixin, CloudPlaceMixin, CloudMoveGuardMixin):
    """三虎的对话框（方框／云朵／圆／标签）：show()/close() 管浮窗，broadcast() 播报，submit()
    说一句，drain() 贴回复。"""

    def __init__(self, pet, parent=None):
        self.pet = pet
        self.parent = parent if parent is not None else pet.win
        self._startup_render_job = None
        self._startup_render_until = time.monotonic() + STARTUP_LAYOUT_SETTLE_SECONDS
        self.win = None                    # 浮窗（Toplevel）：只建一次，收起只是 withdraw
        self.canvas = None
        self.label = None
        self.clip = None
        self.choice, self.choice_stage = '', None   # 三虎刚问的那件事（＋它属于哪一步）：回车就照它去做
        self.reply = None                  # 回复框（第 35 期第 2 条：原来这里是确认按钮）
        self.reply_hint = ''               # 三虎问的那件事的按钮文字：按钮没了，原样记下来
        self.status = None
        self.chat_row = None
        self.hint = None                   # 回复框里那条滚动小字（第 37 期第 4 条）
        self.close_button = None           # 右上角那颗「关闭」（第 45 期）
        self.hint_state = CloudHintState()  # 滚动小字的定时器／开关／左沿／用户聚焦（只由 CloudHintMixin 写）
        self.lines = [WELCOME]
        self.queue = queue.Queue()
        self.busy = False
        self.pinned = False                # 对话形态（带输入框）；False＝播报形态（到点自己收）
        self.visible = False
        self.errors = ErrorLog()
        self._hold = None
        self._fade = None                  # 淡入用的定时器（收窗／销毁都要收回来，见 _expire 的教训）
        self._fade_callback = None         # 与 _fade 成对持有，避免 Tk after 留下悬空 lambda
        self._reset_position_state()       # 定位重试登记（父窗口未布局好时的受限延迟重试）归 CloudPlaceMixin 管
        # 第 27 期第 2 条：鼠标在云里＝用户正在看这一条，到点也不许收（见 _expire／_pointer_inside）。
        self._watching = False
        self._body = MIN_BODY              # 当前云身高度（尾巴根按它算）
        self._scroll = 0                   # 记录往上滚了多少像素
        # 第 36 期第 7／12 条：_down＝这一条内容上方放不下、整朵挪到三虎下面去（全屏／主界面
        # 贴着屏幕上沿时走这条路，框身往下长才装得下）；_fit_width＝量出来的云身宽度（跟着
        # 文字收窄，短句不再拉成一整条）。
        self._down = False
        self._fit_width = 0
        # 第 49 期第 1 条：上一次**量准了**的贴片屏幕矩形。主窗口最小化／收起那一拍，Tk 报出来
        # 的坐标是「窗口没映射」时的相对值（实测贴片会凭空挪到屏幕下半截），拿它算落点，聊天框
        # 就会从画面右边跳到左边（见 _patch_rect）。
        self._last_patch = None
        self.clip = None                   # 文字的取景框（第 22 期）：框外的字被它裁掉
        self.shape = SHAPE_CLOUD           # 云／心／圆／标签（第 18 期）——只改怎么画与写字的框
        self.long = False                  # True＝进度圆气泡（多行明细），不是「一句话」贴纸
        # 主窗口先走一步的话，得把待触发的定时器收回来：after 的 Tcl 命令随控件一起被删，
        # 到点再触发就是一句「invalid command name ..._expire」打到控制台（第 14 期实测到的）。
        try:
            self.parent.bind('<ButtonPress-1>', self._outside_press, add='+')
            self.parent.bind('<Destroy>', self._parent_gone, add='+')
            # 第 18 期：主界面一挪，云也跟着重新摆位（否则聊天框停在原地，人走云不走）
            self.parent.bind('<Configure>', self.follow, add='+')
            # 第 21 期：贴片自己动一下也算——窗口变宽／缩放时贴片往右跟着走，主窗口自己的
            # <Configure> 未必同时到，贴片这一路是最准的（用户要的「跟随助手界面的缩放」）。
            for widget in self._watchers():
                widget.bind('<Configure>', self.follow, add='+')
        except Exception as exc:
            self.errors.append(('bind', str(exc)))

    # ── 建造 ────────────────────────────────────────────────────────────────
    def build(self):
        """建浮窗、画布与文字／输入控件（只建一次，之后反复 show／close）。"""
        if self.win is not None or getattr(self, '_building', False):
            return self.canvas
        self._building = True
        try:
            win = BaseDialog(self.parent, '', modal=False, chrome=False)
            win._positioned_once = True    # 别让 ui_theme 按对话框接管（-alpha 0 ＋ <Map> grab_set）
            win._drama_cloud = True        # 记号：它是三虎的云朵，不是弹窗（自检要把它排除在弹窗统计外）
            # 第 8 轮（收口）：弹窗那两颗「最小化／最大化」全程序都不长了（见 ui_theme），
            # 这一朵云本来就自带一颗 ×，第 67 期任务 1 那段单独摘键的接线一并删掉。
            win.overrideredirect(True)     # 无边框：它就是一朵云，不是一扇窗
            # 第 60 期第 4 条：置顶只在助手界面前台时压——人在别的应用里时这朵云不许压过去
            win.attributes('-topmost', self.attending())
            win.attributes('-alpha', ALPHA)
            try:
                win.attributes('-transparentcolor', BG)   # 云外那层底色透掉，看着就是一朵云
            except Exception as exc:
                self.errors.append(('transparent', str(exc)))   # 透不掉也只是多一块底板，不是错误
            # 不用局部 lambda：销毁竞态下已排队的 Map 事件不能指向悬空 Tcl 命令。
            win.bind('<Map>', self._release_grab_on_map, add='+')
            win.bind('<Destroy>', self._window_gone, add='+')
            canvas = tk.Canvas(win, bg=BG, highlightthickness=0, bd=0,
                               width=self.total_width(), height=TAIL + self._body)
            canvas.pack()
            self.win, self.canvas = win, canvas
            self.release_grab()            # 自己的浮窗绝不抓键盘：抓了就点不动主窗口
            # 第 22 期：文字外面套一层「取景框」——框就是能写字的那块矩形，标签再长也被它裁住，
            # 不会溢出去压到输入行（Tk 的子控件会被父控件裁掉，滚动要的正是这层窗户纸）。
            self.clip = tk.Frame(canvas, bg=self.fill(), bd=0, highlightthickness=0)
            self.label = tk.Label(self.clip, text=self._body_text(), bg=self.fill(), fg=COLORS['text_primary'],
                                  justify='left', anchor='nw', wraplength=WRAP, font=FONT)
            for widget in (self.clip, self.label):
                widget.bind('<Button-1>', lambda event: self.pin())
                widget.bind('<MouseWheel>', self.wheel)
            self._build_chat_row(canvas)
            self._build_close_button(canvas)
            canvas.bind('<Button-1>', lambda event: self.pin())
            # 第 22 期起只剩这个键盘出口；第 45 期起右上角另有一颗看得见的「关闭」，两条路都通。
            win.bind('<Escape>', self.close, add='+')
            canvas.bind('<MouseWheel>', self.wheel)
        except Exception as exc:
            self.errors.append(('build', str(exc)))
            self.win, self.canvas = None, None
        finally:
            self._building = False
        return self.canvas

    def _build_chat_row(self, canvas):
        """回复行（第 35 期第 2 条）：那颗点了没反应的「确认」按钮删掉，这一行留给回复框。

        三虎问「要不要我现在做这件事」，用户在这儿回一句（回车发送）就走原来那条路：有待办
        就照待办办，没有就办「这一页该做的事」——判据与原来那颗按钮一模一样，只是入口从
        「按一下」换成「说一句」。

        回复框铺满这一行：行高仍由 ROW_H 定（提示行 status 照旧挂在上面，说的还是
        「正在想…／已回复」这几句），字号比正文小一号，一行正好装得下。
        """
        row = tk.Frame(canvas, bg=self.fill())
        self.chat_row = row
        self.reply = LineInput(row, font=REPLY_FONT, takefocus=True)
        self.reply.pack(fill='both', expand=True)
        self.reply.bind('<Return>', self.submit)      # 回车＝原来那一下
        # 第 37 期第 4 条：三虎听得懂的那几句做成回复框里的一条小灰字（自己往右滚，见 _hint_tick）。
        # ttk.Entry 没有占位文字这一说，所以它是「贴在框里的一枚小标签」——框里有字就藏起来。
        # 第 39 期第 1 条：贴着左沿、用回复框自己的底色（原来贴右沿又刷云身色，像贴了一块色片）。
        self.hint = tk.Label(row, text='', bg=self.field_bg(), fg=HINT_FG, font=HINT_FONT,
                             anchor='w', justify='left')
        self.hint.place(relx=0.0, rely=0.5, anchor='w', x=HINT_X)
        self.hint.bind('<Button-1>', self._focus_reply)
        for event in ('<KeyRelease>', '<<Paste>>', '<<Cut>>'):
            try:
                self.reply.bind(event, lambda _event: self._sync_hint(), add='+')
            except Exception as exc:
                self.errors.append(('hint.bind', str(exc)))
        self.reply.bind('<FocusOut>', self._restore_hint_after_reply, add='+')
        self.status = ttk.Label(canvas, text='',
                                style='Muted.TLabel')
        try:
            self.status.configure(background=self.fill())
        except Exception:
            app_logging.swallowed()
        return row

    def _build_close_button(self, canvas):
        """创建方框对话与贴纸的统一关闭按钮（CloseButton），按 Esc 或点击均可关闭。"""
        button = CloseButton(
            canvas, text=CLOSE_MARK,
            tooltip='关闭', command=self._hit_close,
        )
        button.bind('<Enter>', self._hover_close_button, add='+')
        button.bind('<Leave>', self._unhover_close_button, add='+')
        self.close_button = button
        self._close_hovered = False
        return button

    def refresh_close_button_theme(self):
        """主题切换后 CloseButton 由 Tokens.Close.TButton 自动刷新，保留兼容入口。"""
        if self.close_button is not None:
            state = ['active'] if getattr(self, '_close_hovered', False) else ['!active']
            self.close_button.state(state)

    def _hover_close_button(self, event=None):
        """关闭钮悬停状态；单列方法使无窗口映射的 UI 回归也可验证。"""
        self._close_hovered = True
        if self.close_button is not None:
            self.close_button.state(['active'])

    def _unhover_close_button(self, event=None):
        """恢复关闭钮的常态色。"""
        self._close_hovered = False
        if self.close_button is not None:
            self.close_button.state(['!active'])

    def _outside_press(self, event):
        if self.visible and event.widget not in self._watchers():
            self.pet.dismissed()
            self.pet.close_chat()

    def _hit_close(self, event=None):
        """点右上角那颗×＝收起对话框（与 Esc／close() 同一条路）。"""
        self.close()
        return 'break'

    def _release_grab_on_map(self, _event=None):
        return self.release_grab()

    def release_grab(self):
        """放开别人（ui_theme 的 <Map> 抓取）可能加在这朵云上的模态抓取：留着主窗口就点不动。"""
        if self.win is None:
            return None
        try:
            self.win.grab_release()
        except Exception as exc:
            self.errors.append(('grab', str(exc)))
        return None

    def attending(self):
        """用户这会儿在看着助手吗：问宠物（没设这道闸的宿主一律当「在」，与 pet_ui 同一个判据）。"""
        judge = getattr(self.pet, 'attending', None)
        if not callable(judge):
            return True
        try:
            return bool(judge())
        except Exception as exc:
            self.errors.append(('attending', str(exc)))
            return True

    def sync_topmost(self, on=None):
        """置顶只看「人在不在助手界面」（第 60 期第 4 条）。

        这朵云是无边框窗，原来一律 -topmost：用户切去别的应用之后它还压在人家界面上，看着就是
        「三虎穿过去了」。现在人在别处就不置顶——它照样在，只是不再压着别人。on 给了就照给的来
        （用例与调用方都能直接指定）；返回值是这一次设成的状态。
        """
        if self.win is None:
            return None
        state = self.attending() if on is None else bool(on)
        try:
            self.win.attributes('-topmost', state)
        except Exception as exc:
            self.errors.append(('topmost', str(exc)))
            return None
        return state

    # ── 显示与收起 ──────────────────────────────────────────────────────────
    def show(self, pinned=None, hold=None, focus=True, shape=None):
        """显示三虎对话框或贴纸。"""
        if getattr(getattr(self, 'pet', None), 'login_locked', lambda: False)() is True or (
                not focus and self._defer_while_moving(pinned=pinned, hold=hold, focus=focus, shape=shape)):
            return None                    # R2051：登录闸挡着不弹；R1976：用户正拖着窗口，自动冒出来的云等松手再出
        if not focus and self.visible and getattr(self.pet, 'chat', None) is self:
            return self.canvas
        if self.win is None and self.build() is None:
            return None
        if shape is not None:
            shape = shape if shape in SHAPES else SHAPE_CLOUD
            if shape != self.shape:
                self._fit_width = 0            # 第 40 期第 3 条：换了形状，上一条量出来的宽度不作数
            self.shape = shape
            if self.shape != SHAPE_ROUND:
                self.long = False              # 圆之外的形状都是「一句话」贴纸
        if pinned is not None:
            self.pinned = bool(pinned)
        self._render()                     # 先排版：尺寸与落点都按排完版的样子算
        try:
            self.win.deiconify()           # 收起来的是同一扇窗：摆回去就行，记录还在
            self._place_window()
            self.win.lift()
            # 第 31 期第 6 条：云是置顶无边框窗，偶尔会被别的窗压住 —— 那时候「确认」怎么点
            # 都没反应。每次冒出来把置顶重新压一遍，别让按钮变成看不到的哑键。
            # 第 60 期第 4 条：压的时机照旧，但只有助手界面在前台时才真置顶（见 sync_topmost）。
            self.sync_topmost()
        except Exception as exc:
            self.errors.append(('show', str(exc)))
            return None
        already_visible = self.visible
        self.visible = True
        if not already_visible:
            self._fade_in()                    # 浮出：淡着冒一下
        if self._replies() and focus:
            # 自动冒出来的云不抢焦点（focus=False）：用户可能正在别处打字，被抢一次就白打一段。
            try:
                self.win.focus_force()
            except Exception:
                app_logging.swallowed()
            try:
                # 打开视图不等于开始输入；用户点击/Tab 进入回复框后才暂停收起。
                self.win.focus_set()
            except Exception:
                app_logging.swallowed()
        if self._replies() and not self.busy:
            # 第 36 期第 11 条：回复框上面那行灰字空着的时候摆出三虎能听懂的指令。
            self.set_status(REPLY_HINTS)
        self._arm_hold(hold)
        return self.canvas

    def close(self, event=None):
        """收起云朵（记录留在 self.lines 里，下次打开照旧看得见）。重复调用是空操作。

        第 24 期：四种形状收场一律先淡下去再收（用户要的「延时淡出效果」）——原来只有圆气泡与
        标签框走渐隐，方框是直接消失的，对话框一眨眼就没了。返回值照旧是 None：调用方只关心
        「收起来了没有」，不关心那个渐隐定时器。
        """
        self.cancel_deferred_render()
        self._cancel_position()
        self._cancel_hold()
        self._cancel_fade()
        self._hint_stop()
        # 第 37 期第 6 条：对话框一收就顺手清一清（只留最近几段），下次打开不是一墙旧话。
        self.trim()
        if not self.visible:
            return self._hide_now()
        return self._fade_out()

    def _pointer_inside(self):
        """鼠标是不是正停在这朵云上（第 27 期第 2 条：用户正在看就别收）。

        故意不用 <Enter>／<Leave>：Tk 的 crossing 事件是按子控件派发的，指针从取景框上移到标签上
        时最外层窗收不到 Leave，会卡在「以为用户还在看」里一直收不掉；直接问
        winfo_pointerxy 比较坐标每次都准，仅在到点时算一次，也不占性能。
        """
        if self.win is None:
            return False
        try:
            px, py = self.win.winfo_pointerxy()
            x, y = self.win.winfo_rootx(), self.win.winfo_rooty()
            w, h = self.win.winfo_width(), self.win.winfo_height()
        except Exception as exc:
            self.errors.append(('pointer', str(exc)))
            return False
        return x <= px < x + w and y <= py < y + h

    def _hide_now(self):
        """立刻收起（渐隐走完也回到这里）。"""
        self.visible = False
        self.busy = False
        self._watching = False             # 收起＝这一轮结束，下次 _expire 从头看。
        if self.win is not None:
            try:
                self.win.attributes('-alpha', ALPHA)   # 下次浮出还是从淡到清，别停在半透明上
                self.win.withdraw()
            except Exception as exc:
                self.errors.append(('close', str(exc)))
        return None


    def toggle(self, at=None):
        """左键点云／再点一次：开着就收，收着就按对话形态打开。"""
        if self.visible and self.pinned:
            self.close()
            return None
        return self.show(pinned=True)

    def pin(self):
        """点一下云：转成对话形态（输入行出来），并把自动收起往后推一次。

        第 40 期第 1 条：贴纸（云朵框／椭圆／标签）不在这里长输入行——用户报「三虎打招呼的云朵框
        里有个回复框」，点一下招呼那朵云就会变成这个带输入行的样子。贴纸点一下＝「我还在看」，
        把它多留一会儿；要跟三虎说话去点三虎自己（单击＝打开对话框）。
        """
        if self.shape != SHAPE_CLOUD:
            self._arm_hold()
            return self.canvas
        if not self.visible:
            return self.show(pinned=True)
        self.pinned = True
        self._render()
        try:
            self.reply.focus_set()
        except Exception:
            app_logging.swallowed()
        self._arm_hold()
        return self.canvas


    # ── 形状尺寸 ────────────────────────────────────────────────────────────
    def width(self):
        """这一形状的云身宽度。

        第 36 期第 12 条：量出来多宽就多宽（夹在下限与原来的宽度之间）——用户要的「紧凑」。
        第 40 期第 3 条：_render 量出「这一条不换行要多宽」记进 _fit_width，这里只把它夹在
        「这一形状的宽度下限」与「原来的宽度」之间；还没量出来（_fit_width<=0）就用原来的宽度。
        第 57 期第 1 条：四种方框走同一条路，下限各按 shape_min_width 取（原先圆那一支还要跟
        云身高比一比，那是椭圆内接写字框带出来的规矩，方框用不着了）。
        """
        cap = shape_width(self.shape)
        if self._fit_width > 0:
            return max(shape_min_width(self.shape), min(cap, int(self._fit_width)))
        return cap

    def _natural_width(self, *, sync=True):
        """这一条文字「不换行」时要多宽（第 40 期第 3 条）：三种框的动态宽度都从这一量出发。

        量之前先把字号放回最大那一档：贴纸在地方不够时会临时收字号（见 _fit_font），残留的小字号
        量出来的自然宽度偏窄，框就会收得比该有的还小。
        """
        try:
            self.label.configure(font=FONT if self.shape == SHAPE_CLOUD else (FONT[0], STICKER_FONTS[0]), wraplength=0)
            if sync:
                self.canvas.update_idletasks()
            return int(self.label.winfo_reqwidth())
        except Exception as exc:
            self.errors.append(('natural', str(exc)))
            return 0

    def _replies(self):
        """这一朵这会儿带不带回复框（第 40 期第 1 条：只有方框对话框带，三种贴纸都不带）。"""
        return bool(self.pinned) and self.shape == SHAPE_CLOUD

    def _closable(self):
        """这一朵这会儿带不带那颗看得见的「关闭」（第 46 期第 4 条）。

        对话框和三种贴纸都带；日报／周报的标签框也应允许用户随手关闭。
        """
        return self._replies() or self.shape in (SHAPE_PUFF, SHAPE_ROUND, SHAPE_TAG)

    def _close_strip(self):
        """顶上给「关闭」让出的那一条（画布坐标）：正文整块往下挪同样多。"""
        return CLOSE_H if self._closable() else 0

    def total_width(self):
        """画布宽度＝云身 ＋ 右边那条留尾巴的空档。"""
        return self.width() + GUTTER

    def fill(self):
        """这一形状的填充色。"""
        level = getattr(getattr(self.pet, 'agent', None), 'level', '')
        color = PET_PALETTE.get('level_' + level)
        return blend(COLORS['background_card'], color, 0.24) if color else shape_colors(self.shape)[0]

    def field_bg(self):
        """回复框里那条滚动小字的底色：跟着 ttk.Entry 自己的底色走。

        第 39 期第 1 条：对话框的云身是浅绿的，小字原来就刷这个色——在白色的输入框里像贴了
        一块色片。用户要的「文字不要有背景填充色」，就是让它和输入框同一个底色。
        """
        try:
            style = ttk.Style(self.win)
            reply = getattr(self, 'reply', None)
            style_name = str(reply.cget('style') or 'Tokens.LineInput.TEntry') if reply is not None else 'TEntry'
            colour = (style.lookup(style_name, 'fieldbackground', '')
                      or style.lookup(style_name, 'background', ''))
            legacy = (style.lookup('TEntry', 'fieldbackground', '')
                      or style.lookup('TEntry', 'background', ''))
            # 回复框自己的样式优先；仍保留旧基样式被显式覆盖时的兼容口径。
            if (style_name != 'TEntry' and colour == COLORS['background_card']
                    and legacy and legacy != colour):
                colour = legacy
            if colour:
                return str(colour)
        except Exception as exc:
            self.errors.append(('field_bg', str(exc)))
        return HINT_BG

    def edge(self):
        """这一形状的描边色。"""
        level = getattr(getattr(self.pet, 'agent', None), 'level', '')
        return PET_PALETTE.get('level_' + level + '_outline', shape_colors(self.shape)[1])

    # ── 记录排版与滚动 ──────────────────────────────────────────────────────
    def _body_text(self):
        """云里的文字：一条一行，行末交给标签自动换行（第 24 期第 7 条）。

        编号与正文写在同一行（'%d.' ＋ NUMBER_GAP），条与条之间不再空一行——原来段间空一行，
        一屏只放得下两三条；用户要的是「每行文字尽量放满后再自动换行」，所以换行宽度取整个
        写字框的宽（见 _render 里的 wraplength）。对话框里装的只有三虎的播报与用户自己说的话。

        第 26 期第 4／6 条：
        - 提示框（进度圆气泡）**每一行都编号**——它一段就有好几行，原来只有头一行带号（号还是
          整份记录的第几条），看着像排版坏了；现在 1.2.3. 一行一个，一眼能数清。
        - 云朵框与标签框是「一句话」的贴纸，**不编号**（用户点名的就是「打招呼与随口一句的
          可爱话不需要排序数字」）。
        """
        if self.shape == SHAPE_CLOUD:
            # 第 37 期第 5 条：空段（只剩空白的那几条）整段不排——框里一条挨着一条，中间不留空行。
            # 只在显示时去重（不分是否相邻），不修改历史。
            rows = [row for row in (tight(line) for line in self.lines) if row]
            rows = [row for index, row in enumerate(rows) if row not in rows[index + 1:]]   # 同一句只留最后一次，交替重复也折叠
            # 三虎对话框是操作入口而非历史日志，最多露出最近五步，避免遮挡用户操作。
            rows = rows[-CHAT_VISIBLE_STEPS:]
            return '\n'.join('%d.%s%s' % (index, NUMBER_GAP, row)
                              for index, row in enumerate(rows, start=1))
        if not self.lines:
            return ''
        latest = tight(self.lines[-1])      # 第 37 期第 5 条：贴纸里也不留空行
        if self.shape == SHAPE_ROUND:
            rows = [row.strip() for row in latest.split('\n') if row.strip()]
            if any(row.startswith('【') for row in rows):
                # 第 26 期第 4 条：这份正文自己就带节名与编号（进度面板的退路只走到这里），
                # 再套一层「1.2.3.」只会把节名也编上号，读起来更乱。
                return '\n'.join(rows)
            return '\n'.join('%d.%s%s' % (index, NUMBER_GAP, row)
                              for index, row in enumerate(rows, start=1))
        return latest

    def _fit_font(self, room, *, sync=True):
        """贴纸把字号收到装得下为止，返回最后用的字号（第 26 期第 7 条）。

        云身高度被「三虎上方还剩多高」封顶时（见 _fit_body），框就那么高，字号不收一档就会有
        几行被裁掉——用户看到的是「云朵框里的话说到一半没了」。每一趟都从最大号试起，
        上一条短话不留着小字号。必要时才收，收到最小 7 号还装不下就只好留着滚轮翻。
        """
        family = FONT[0]
        size = STICKER_FONTS[-1]
        for size in STICKER_FONTS:
            try:
                self.label.configure(font=(family, size))
            except Exception as exc:
                self.errors.append(('font', str(exc)))
                return None
            if sync:
                try:
                    self.canvas.update_idletasks()
                except Exception:
                    app_logging.swallowed()
            if self._content_height() <= room:
                return size
        return size

    def _content_height(self):
        """记录实际有多高（画布坐标）：标签的请求高度（不受取景框影响）。"""
        try:
            return int(self.label.winfo_reqheight())
        except Exception:
            return 0

    def _text_box(self):
        """当前形状里能写字的那块矩形（画布坐标 x, y, w, h）。"""
        box = text_box(self.shape, self.width(), self._body, long=self.long)
        return (box[0], box[1] + self._shift(), box[2], box[3])

    def _room(self):
        """文字真正放得下的高（画布坐标）：按形状的写字框算，带输入行时再让出输入行。

        第 22 期把「能滚多少」和「标签裁几行」收到同一处算——两处各算一遍的话，
        滚到底那一刻总会差几个像素，字就压到输入行上了。
        """
        # 第 57 期第 1 条：写字框＝云身四边各让开 pad，四种方框同一口径（原先圆／云朵框要按
        # 各自的曲边量一遍，方框用不着了）。
        room = max(0, self._body - 2 * PAD)
        if self._replies():
            # 第 45 期：对话框还要让出顶上那条「关闭」——_place_label 把正文整块往下挪同样多。
            room = max(0, room - ROW_H - 6 - self._close_strip())
        elif self._close_strip():
            # 第 46 期第 4 条：云朵框／圆框顶上也是同样一条。
            room = max(0, room - self._close_strip())
        return room

    def _visible_height(self):
        """云身里真正看得见的那一块（老名字，等价于 _room）。"""
        return self._room()

    def _scroll_limit(self):
        """还能往下滚多少像素：内容比看得见的那一块高多少。"""
        return max(0, self._content_height() - self._visible_height())

    def scroll_by(self, pixels):
        """滚轮：上下翻记录（翻到头就不动），返回新的偏移。"""
        limit = self._scroll_limit()
        self._scroll = min(max(0, int(self._scroll) + int(pixels)), limit)
        self._place_label()
        return self._scroll

    def wheel(self, event=None):
        """滚轮事件：向上翻就是负、向下翻是正；返回 'break'——别让主界面跟着一起滚。"""
        try:
            down = int(getattr(event, 'delta', 0)) < 0
        except Exception:
            down = True
        self.scroll_by(WHEEL_PX if down else -WHEEL_PX)
        return 'break'

    def _place_label(self):
        """把文字摆进「能写字的那块框」里（往上滚了多少就抬高多少）。

        第 22 期：改成「取景框 + 上下挪」——原来只给宽度不给高度，记录一长文字就从框里溢出去、
        穿过输入框和「发送」按钮（用户报的就是这个）。现在框就摆在能写字的那块矩形上，标签
        整条挂在框里往上挪，框外的部分自然看不见，滚动照旧能翻到每一条。
        圆／云朵框那两种字少，纵向居中摆才像贴纸；方框／标签从框顶开始排。
        """
        if self.label is None or self.clip is None:
            return None
        try:
            box_x, box_y, box_w, _box_h = self._text_box()
            room = max(1, self._room())
            top = 0
            if self.shape in (SHAPE_ROUND, SHAPE_PUFF):
                top = max(0, (room - self._content_height()) // 2)
            strip = self._close_strip()                   # 第 45／46 期：正文从「关闭」那条下面起步
            self.clip.configure(bg=self.fill())
            self.clip.place(x=box_x, y=box_y + strip, width=box_w, height=room)
            self.label.place(x=0, y=int(top) - int(self._scroll), width=box_w)
        except Exception as exc:
            self.errors.append(('label', str(exc)))
        return None

    def _startup_measurement_wait_ms(self):
        """仅在真实自动续开建页时交还事件循环；普通云朵立即完成布局。"""
        if not bool(getattr(self.parent, '_desktop_loading_project', False)):
            return 0
        remaining = self._startup_render_until - time.monotonic()
        if remaining > 0:
            return max(1, int(remaining * 1000))
        return 50

    def _startup_measurement_pending(self):
        """首帧或项目选择尚未交回事件循环时，不同步推进 Tk idle 队列。"""
        return self._startup_measurement_wait_ms() > 0

    def _defer_startup_render(self):
        """将启动期量测合并为一趟 idle，避免嵌套 spin。"""
        if self._startup_render_job is not None:
            return None
        def render_when_idle():
            self._startup_render_job = None
            wait_ms = self._startup_measurement_wait_ms()
            if wait_ms:
                try:
                    self._startup_render_job = self.parent.after(wait_ms, self._defer_startup_render)
                except Exception:
                    app_logging.swallowed()
                return None
            return self._render(skip_sync=True)
        try:
            self._startup_render_job = self.parent.after_idle(render_when_idle)
        except Exception:
            self._startup_render_job = None
        return None

    def cancel_deferred_render(self):
        """收窗或主窗口退出时撤掉尚未执行的启动期量测。"""
        job, self._startup_render_job = self._startup_render_job, None
        if job is not None:
            try:
                self.parent.after_cancel(job)
            except Exception:
                app_logging.swallowed()
        return None

    def _render(self, *, skip_sync=False):
        """按当前文字量决定云身高度，再画云身、摆控件、摆浮窗（纯计算，出错只记一笔）。"""
        canvas, label = self.canvas, self.label
        if canvas is None or label is None:
            return None
        if not skip_sync and self._startup_measurement_pending():
            return self._defer_startup_render()
        try:
            width, fill = self.width(), self.fill()
            _x, _y, box_w, _h = text_box(self.shape, width, MAX_BODY, long=self.long)
            label.configure(text=self._body_text(), bg=fill, wraplength=max(60, box_w - 8),
                            justify='left')       # 第 22 期：四种形状一律左对齐（用户要的「全部左对齐」）
            if not skip_sync:
                canvas.update_idletasks()
            # 第 40 期第 1 条：贴纸不留输入行的高度；第 45 期：对话框顶上还要留一条给「关闭」。
            # 第 58 期第 5 条：那一条不只对话框有——可爱话／提示这两种贴纸也带那颗×（见 _closable），
            # 一律按 _close_strip 计入；否则框身收到内容高度后，正文会被 _fit_font 误伤成小号字。
            extra = (ROW_H + 6) if self._replies() else 0
            extra += self._close_strip()
            # 第 46 期第 4 条：云朵框／圆框顶上那条「关闭」也得算进框身高度里，
            # 量的时候按各自的写字框比例折回去（见下面两条分支）。
            strip = self._close_strip()
            floor = shape_min_body(self.shape)
            content = self._content_height()     # 量之前先把行数限制撤掉，否则量到的是裁过的
            # 第 57 期第 1 条：四种聊天框都是方框，量尺寸也就只有这一份——
            # 第 36 期第 12 条那条「先量不换行要多宽、把云身收到刚够，再按这个宽度换行量高度」的
            # 规矩（一句「好呀」不再占满一整条）照旧适用于全部四种，收窄的下限各按 shape_min_width。
            natural = self._natural_width(sync=not skip_sync)
            if natural > 0:
                self._fit_width = max(shape_min_width(self.shape),
                                      min(shape_width(self.shape), natural + 2 * PAD + 12))
            label.configure(wraplength=max(60, self._fit_width - 2 * PAD - 12))
            if not skip_sync:
                canvas.update_idletasks()
            content = self._content_height()
            # 写字框＝云身四边各让开 pad（见 text_box），所以这里正好折回去：＋8 是给量宽／换行
            # 留的一点余量（上限交给 _fit_body，第 42 期第 2 条）。
            self._body = self._fit_body(max(floor, content + 2 * PAD + extra + 8))
            canvas.configure(width=self.total_width(), height=self._body + TAIL)
            self._draw(self._body)
            if self.shape != SHAPE_CLOUD:
                # 贴纸先把字号收到装得下（第 26 期第 7 条）：对话框是滚动的记录，不参与
                self._fit_font(max(1, self._room()), sync=not skip_sync)
            self._scroll = self._scroll_limit()     # 永远先落在最新那一段
            self._place_label()
            box_x, box_y, box_w, box_h = self._text_box()
            if self._replies():
                # 第 40 期第 1 条：回复框只长在方框对话框上（三种贴纸都没有这一行）。
                row_y = int(box_y + box_h) - ROW_H
                self.chat_row.configure(bg=fill)
                self.chat_row.place(x=box_x, y=max(0, row_y), width=box_w, height=ROW_H)
                self.status.configure(background=fill)
                self.status.place(x=box_x, y=max(0, row_y - 18))
                self.chat_row.lift()                # 记录再长也压不住输入行
                self.status.lift()
                if self.close_button is not None:
                    # 第 45 期：那颗×摆在云身右上角（就在刚让出来的那一条上）。
                    # 第 59 期第 9 条：底色归它自己（红），不再跟着云身刷成白。
                    self.close_button.place(x=max(0, int(box_x + box_w - CLOSE_SIZE)),
                                            y=max(0, int(box_y + 2)),
                                            width=CLOSE_SIZE, height=CLOSE_SIZE)
                    self.close_button.lift()
                if self.hint is not None:
                    # 第 37 期第 4 条：滚动小字在这一行里，跟着这一行摆。
                    # 第 39 期第 1 条：底跟输入框、位置贴左沿；这一行一露出来就让小字滚起来——
                    # 每一扇对话框的回复框都得有，不能只等 set_status 那一拍。
                    self.hint.configure(bg=self.field_bg())
                    self.hint.place(relx=0.0, rely=0.5, anchor='w', x=self.hint_state.x)
                    self.hint.lift()
                    if not self.busy and not self.hint_state.on:
                        self._hint_show()
            else:
                self.chat_row.place_forget()
                self.status.place_forget()
                if self.hint is not None:
                    self.hint.place_forget()
                if self.close_button is not None:
                    # 三种贴纸都与对话框同样提供右上角「关闭」；点一下＝close()。
                    if self._closable():
                        self.close_button.place(x=max(0, int(box_x + box_w - CLOSE_SIZE)),
                                                y=max(0, int(box_y + 2)),
                                                width=CLOSE_SIZE, height=CLOSE_SIZE)
                        self.close_button.lift()
                    else:
                        self.close_button.place_forget()
            self._place_window()
        except Exception as exc:
            self.errors.append(('render', str(exc)))
        return canvas

    def _draw(self, body):
        """两遍画出云身：先放大两像素的描边，再原尺寸的填充；最后是三个尾巴点。

        形状由 shape_parts 决定（云／心／圆／标签），画法只有这一份——两遍描边对圆、矩形、
        多边形一样管用，所以不必给每种形状各写一套。
        """
        canvas = self.canvas
        fill, edge = self.fill(), self.edge()
        try:
            canvas.delete('cloud')
            parts = [shift_part(part, self._shift())
                     for part in shape_parts(self.shape, self.width(), body)]
            tail = self._tail_polygon()
            for part in parts:
                self._part(canvas, inflate(part, 2), edge, edge)
            self._part(canvas, inflate(tail, 2), edge, edge)      # 尾巴的描边跟云身同一遍
            for part in parts:
                self._part(canvas, part, fill, fill)
            self._part(canvas, tail, fill, fill)                  # 云身这一遍把底边接缝盖掉
            canvas.tag_lower('cloud')
        except Exception as exc:
            self.errors.append(('draw', str(exc)))
        return canvas

    @staticmethod
    def _part(canvas, part, fill, outline):
        """画一个图元：圆／矩形／多边形。"""
        kind = part[0]
        if kind == 'oval':
            _kind, cx, cy, radius = part
            canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                               fill=fill, outline=outline, tags='cloud')
        elif kind == 'ellipse':
            _kind, cx, cy, rx, ry = part
            canvas.create_oval(cx - rx, cy - ry, cx + rx, cy + ry,
                               fill=fill, outline=outline, tags='cloud')
        elif kind == 'rect':
            _kind, x0, y0, x1, y1 = part
            canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, tags='cloud')
        else:
            canvas.create_polygon(list(part[1]), fill=fill, outline=outline, tags='cloud')
        return canvas

    # ── 说话：播报与问答 ────────────────────────────────────────────────────
    def append(self, line, keep=True):
        """往记录里追加一段；云正开着就顺手重排一次。

        第 37 期第 5 条：存进来之前先过 tight——记录里不留空行。
        """
        text = re.sub(r'^\s*(?:【|\[)(?:阶段|步骤)\s*(?:\d+|[Xx])\s*/\s*(?:\d+|[Xx])(?:】|\])\s*',
                      '', tight(line), count=1)
        if keep:
            self.lines.append(text)
            del self.lines[:-LINE_LIMIT]
        if self.visible:
            self._render()
            self._arm_hold()
        return text

    def broadcast(self, text, hold=None, shape=None):
        """宠物说一句：记进记录，并自动把云冒出来（不用用户手动打开）。

        已经开着的时候只把「什么时候收」往后推一下——用户正在看记录／打字时不打断；
        自动冒出来的云不抢焦点（focus=False），说完到点自己收。
        第 27 期第 2 条：鼠标正停在云里（用户在读）时，这一趟连计时都不重启——等它挪开再算。
        shape 只给「特定场合」用（云朵框／圆／标签），平时不传＝方框对话框。
        hold 不传（None）时按这句话要读多久算（第 24 期第 8 条），传了就用传进来的。
        """
        text = ' '.join(str(text or '').split())
        if not text:
            return ''
        hold = self.read_hold(text) if hold is None else hold
        self.append(text)
        if self.visible and (shape is None or shape == self.shape):
            self._arm_hold(hold)           # 正在看：到点也不收，留着等 _expire 发现手指还在云上
            return text
        self.show(pinned=True, hold=hold, focus=False, shape=shape)
        return text

    def reset(self):
        """清空记录（第 18 期：每次重开软件都从干净的一条开始，不带上次的对话）。"""
        self.lines = [WELCOME]
        self._scroll = 0
        if self.win is not None:
            self._render()
        return list(self.lines)

    def trim(self, keep=None):
        """及时清理：只留最近 keep 段（第 37 期第 6 条）。

        对话框是「这一会儿在聊什么」的地方，不是日志：开一次攒一次旧话，翻起来先看到一墙
        过期的问句。收起时顺手收一收，只留最近几段（CHAT_KEEP）够接着聊就够了。
        """
        try:
            keep = CHAT_KEEP if keep is None else int(keep)
        except (TypeError, ValueError):
            keep = CHAT_KEEP
        keep = max(1, keep)
        if len(self.lines) > keep:
            del self.lines[:-keep]
            self._scroll = 0
            if self.visible:
                self._render()
        return list(self.lines)

    def pop(self, count=1):
        """去掉最后几段（第 37 期第 6 条：换页时上一页那句问句让位）。

        记录永远至少留一段——框里空着「三虎还没问什么」就说不出口了（见 EMPTY）。
        """
        try:
            count = max(1, int(count))
        except (TypeError, ValueError):
            count = 1
        for _ in range(count):
            if len(self.lines) <= 1:
                break
            self.lines.pop()
        self._scroll = 0
        if self.visible:
            self._render()
        return list(self.lines)

    def greet(self):
        """开机招呼：云朵框浮出来说一句「哈喽~」（第 18 期；第 25 期起用云朵框）。

        只留这一句：云朵框是个贴纸，字多了就撑到形状外头去（用法说明由方框里第一句 WELCOME 说）。
        """
        self.lines = [GREETING]
        self._scroll = 0
        return self.show(pinned=False, hold=GREETING_MS,
                         focus=False, shape=SHAPE_PUFF)

    def whisper(self, text):
        """三虎做动作时随口一句（可爱话）：云朵框浮出来，到点自己淡下去。

        第 25 期：用户要「与工作无关的可爱话统一用云朵框」——所以随口一句与开机招呼共用这一种
        形状；圆气泡留给进度（那是工作上的数字）。
        """
        text = ' '.join(str(text or '').split())
        if not text:
            return ''
        self.long = False
        self.append(text)
        return self.show(pinned=False, hold=self.hold_for(text, WHISPER_MS),
                         focus=False, shape=SHAPE_PUFF)

    def progress(self, text, hold=PROGRESS_MS):
        """进度圆气泡（第 19 期）：还是圆形，但把整段明细都写进去（不是「一句话」贴纸）。

        与 whisper 的差别只在 self.long：whisper 是随口一句，这里是好几行数字。
        """
        text = str(text or '').strip()
        if not text:
            return ''
        self.long = True
        try:
            self.append(text)
            return self.show(pinned=False, hold=self.hold_for(text, hold),
                             focus=False, shape=SHAPE_ROUND)
        except Exception as exc:
            self.errors.append(('progress', str(exc)))
            return None

    def banner(self, text, hold=BANNER_MS):
        """日报／周报：清新标签框渐入，并允许用户随时关闭。"""
        text = ' '.join(str(text or '').split())
        if not text:
            return ''
        self.append(text)
        return self.show(pinned=False, hold=self.hold_for(text, hold), focus=False, shape=SHAPE_TAG)

    def _watchers(self):
        """云跟着谁走：主窗口 ＋ 三虎贴片（第 21 期）＋ 那排猫爪（拿得到才算）。"""
        out = []
        for name in ('canvas', 'paws'):
            widget = getattr(getattr(self, 'pet', None), name, None)
            if widget is not None:
                out.append(widget)
        return out

    def follow(self, event=None):
        """主窗口或三虎动一下（挪位置、改大小、缩放）：云跟着重新摆位（第 18／21 期）。

        子控件冒泡上来的 <Configure> 不认领——只认主窗口自己与三虎那两个。

        第 25 期第 7 条：界面一缩，尾巴要**马上**指到三虎新的位置——只挪窗口是不够的：那根
        尖角是画在画布上的，窗口一挪，它还停在旧坐标上。所以这里整朵重画一遍（_render 自己会
        摆窗口），缩放过程中每一拍都对得上。
        """
        widget = getattr(event, 'widget', None)
        if widget is not None and widget is not self.parent and widget not in self._watchers():
            return None
        if not self.visible or self.win is None:
            return None
        return self._render()      # _render 自己会摆窗口（见上）

    def propose(self, text, label=REPLY_TIP, stage=None):
        """三虎抛出一个「要不要做这件事」的问句：把回车时要发出去的那句话存下来。

        第 35 期第 2 条：按钮没了，label 不再往控件上写，原样记进 self.reply_hint（用例与提示行
        都看它）。文字为空＝这一句只是个通知，用户空着回车就只说 EMPTY/办这一页的事。
        S-03：问句带来的阶段一并记进 self.choice_stage，空回车派发时按它路由。
        """
        text = ' '.join(str(text or '').split())
        self.choice, self.choice_stage = text, stage
        self.reply_hint = str(label or REPLY_TIP)
        return text

    def page_ask(self):
        """这一页该做的那件事（三虎问过的那句命令）：问不出来就是空串。

        第 31 期第 6 条：提示框（只是播报的那种）也带着同一颗「确认」按钮，用户按下去时
        self.choice 是空的——这里就现场问一次「这一页该做什么」，让按钮永远有个能办的活。
        """
        task = getattr(self.pet, 'chat_task', None)
        if not callable(task):
            return ''
        try:
            ask, command = task()
        except Exception as exc:
            self.errors.append(('page_ask', str(exc)))
            return ''
        return ' '.join(str(command or '').split())

    def submit(self, event=None):
        """回车发送：把这一句话（没有就按三虎问的那件事）交给宠物——记下、禁用、开线程。

        第 35 期第 2 条：入口从「确认」按钮换成回复框。回复框里写着字就用他写的那句；空着回车
        ＝原来按一下按钮的意思。第 31 期第 6 条那条兜底照旧：没有待办时按「这一页该做的那件事」
        办；连那件事都问不出来，才退回 EMPTY 那句说明。
        """
        if self.canvas is None or self.reply is None:
            return ''
        typed = ' '.join(str(self.reply.get()).split())
        stage = None if typed else self.choice_stage     # 记下的问句带着页的阶段；手打的句子不带
        text = typed or ' '.join(str(self.choice or '').split())
        if not text:
            text = self.page_ask()
        if not text:
            self.set_status(EMPTY)         # 连这一页该做什么都问不出来，才只能说这句话
            return ''
        if self.busy:
            self.set_status(BUSY)
            return text
        self.choice, self.choice_stage = '', None
        self.busy = True
        try:
            self.reply.delete(0, 'end')    # 发出去就清空，等着下一句；说过的话留在记录里
        except Exception as exc:
            self.errors.append(('submit', str(exc)))
        if self.reply is not None:
            self.reply.state(['disabled'])
        self._arm_hold()                   # 问答开始了：收起时刻往后推，别问到一半云没了
        self.set_status(BUSY)
        self.append('您：' + text)
        threading.Thread(target=self.ask, args=(text, stage), daemon=True).start()
        return text

    def dispatch(self, text, stage=None):
        """把这句话交给编排器：认得出 confirmed 参数就带上，认不出的实现（老接口、假宠物）
        照旧只吃一句话——按一下「确认」不该因为签名不同而炸掉。先认签名再只调一次：
        实现内部抛的 TypeError 不能被当成签名不符，让同一句话再派发一遍。
        S-03：记下的问句带着阶段，签名认得就一并递过去。"""
        send = self.pet.agent.dispatch
        extra = {'stage': stage} if stage and accepts_keyword(send, 'stage') else {}
        return send(text, confirmed=True, **extra) if accepts_keyword(send, 'confirmed') else send(text, **extra)

    def ask(self, text, stage=None):
        """后台问一句：dispatch 只读状态机与台账、不碰 Tk；出错也要给一句话。

        第 23 期：整份结论（含要执行的动作）一起回队列——动手是界面线程的事（见 drain），
        后台线程只负责「想清楚」；第 25 期起，「要不要一键执行」的回答先由 pet.answer_offer 认一句。
        """
        result = None
        try:
            # 第 25 期第 3 条：三虎刚问过「要不要一键执行」时，先把这一句交给宠物认一下
            # （「好」「先不用」这几种答法只有挂在那个问题上才成立），没认出来才走规则表。
            answer = getattr(self.pet, 'answer_offer', None)
            result = answer(text) if callable(answer) else None
            if result is None:
                result = self.dispatch(text, stage=stage)
            lines = reply_lines(result)
        except Exception as exc:
            lines = [SPEAKER + '：这句话没处理成：' + str(exc)]
        self.queue.put({'text': str(text), 'lines': lines, 'result': result})
        return lines

    def drain(self):
        """界面线程：把后台的回答贴回云里，并真的把这一步做掉（第 23 期）。

        「真的做掉」只能在界面线程：run_plan 要翻页、要开窗口、要动任务队列。做完的那句话
        紧跟在回答后面贴出来——用户看到的就是「听懂了 → 已经做了」两行，而不是一句空承诺。
        返回这一轮贴了几问（没有就是 0）。
        """
        self._interaction_changed()
        count, needs = 0, ''
        try:
            while True:
                item = self.queue.get_nowait()
                text, lines = item['text'], item['lines']
                for line in lines:
                    self.append(line)
                    if CONFIRM_PREFIX in line:
                        needs = line          # 这一步要用户点头：除了记一笔，还要弹一块通知气泡
                done = self.run(item.get('result'))
                if done:
                    self.append(SPEAKER + '：' + done)
                count += 1
                self.report_command(text)
        except queue.Empty:
            pass
        if needs:
            self.ask_confirm(needs)
        if count:
            self.busy = False
            if self.reply is not None:
                self.reply.state(['!disabled'])
            self.set_status(REPLY_HINTS)        # 第 36 期第 11 条：说完了就把能听懂的指令摆回去
            if self.visible:
                self._render()
                self._arm_hold()           # 这一轮问答结束：留够读完的时间再自动收起
        return count

    def run(self, result):
        """把这一步交给宠物在界面线程办掉；返回那句「做了什么」，没做返回空串。

        宠物没有这条能力（用例里的假宠物、或换了实现）就什么都不做——说话永远不能因为
        「做不成」而失败。
        """
        run = getattr(self.pet, 'run_plan', None)
        if not callable(run) or not isinstance(result, dict):
            return ''
        try:
            return str(run(result) or '')
        except Exception as exc:
            self.errors.append(('run', str(exc)))
            # 第三方宠物实现或替身未必遵守 Pet.run_plan 的可见失败契约。云朵作为
            # 最后一层用户入口仍须明确告知动作未完成；具体异常只记入既有 errors，
            # 不直接回显到对话文本。
            return '操作未完成，请稍后重试。'

    def set_status(self, text):
        """回复框上面那行灰字：说的是三虎这会儿在干什么（正在想…／已回复）。

        第 37 期第 4 条：三条基本指令从这一行搬进了回复框（小字、自己往右滚）——所以传进来
        的正好是 REPLY_HINTS（＝「空下来了，把能听懂的摆出来」）时，这一行让位，改由小字露脸。
        """
        if self.status is None or not self._replies():
            return text
        value = str(text)
        if value == REPLY_HINTS:
            self._hint_show()
            value = ''
        else:
            self._hint_stop()
        try:
            self.status.configure(text=value)
        except Exception as exc:
            self.errors.append(('status', str(exc)))
        return text


    def report_command(self, text):
        """把这句话记成「用户下的指令」事件：与气泡／菜单同一类，只是来源是 cloud。"""
        emit = getattr(self.pet, '_emit', None)
        if not callable(emit):
            return None
        try:
            return emit('intent.command', text=str(text), source='cloud')
        except Exception as exc:
            self.errors.append(('emit', str(exc)))
            return None

    def ask_confirm(self, line):
        """回答里带「这一步要你点头」时，除了写进记录，再弹一块通知气泡（第 16 期）。

        这里是界面线程上的轻调用：真正弹什么交给 pet_ui（自绘气泡／托盘气泡／只在云里记一笔）。
        """
        confirm = getattr(self.pet, 'confirm', None)
        if not callable(confirm):
            return None
        text = line[len(SPEAKER) + 1:] if line.startswith(SPEAKER + '：') else line
        try:
            return confirm(text)
        except Exception as exc:
            self.errors.append(('confirm', str(exc)))
            return None

    # ── 记录 ────────────────────────────────────────────────────────────────
    def transcript(self):
        """整份记录（日志与用例读它）。第 24 期起没有「复制」按钮了，这里只读不写剪贴板。"""
        return '\n'.join(self.lines)

    def describe(self):
        """给日志与用例的一眼快照。"""
        return {'open': bool(self.visible), 'pinned': self.pinned, 'busy': self.busy,
                'hold': bool(self._hold), 'scroll': self._scroll, 'body': self._body,
                'lines': list(self.lines), 'errors': len(self.errors)}
