"""云朵气泡的定位（几何）方法集（从 pet_cloud.Cloud 原样迁出，R1804）。

方法体未改、self 语义不变，Cloud 通过继承 CloudPlaceMixin 获得；定位用的常量与 shape_root／shape_min_body 随方法迁出，
由 pet_cloud 按原名转回。仍与 Tk 控件紧耦合，故与 pet_cloud 同属 L4。"""
import infra.app_logging as app_logging
from ui.ui_popup import monitor_bounds
from ui_tokens import PET_LAYOUT
from ui.pet_cloud_shape import (SHAPES, SHAPE_CLOUD, SHAPE_PUFF, SHAPE_ROUND, SHAPE_TAG, configured_value as _configured_value)
from ui.pet_cloud_geometry import shape_root as _shape_root
from ui.pet_cloud_tail import tail_points


MIN_BODY = 96                     # 云身最小高度（第 28 期第 1 条随字号放大一档）
MAX_BODY = 232                    # 云身最大高度（第 30 期第 4 条：框身整体收小一档，再长就交给滚轮翻）
MAX_BODY_DOWN = 448               # 第 42 期第 2 条：贴着屏幕上沿、整朵翻到三虎下面时的上限——下面那一整屏都是空的，
                                  # 框身长到刚好装下这条内容（约 16 行），再长照旧交给滚轮
TAIL = 30                         # 云身下方留给尾巴尖的带子（第 21 期起是一根尖角，不是三个圆点）
TAIL_BASE = 16                    # 尾巴三角形的底边宽（底边长在云身里、被云身盖住，只露尖角）
ANCHOR_DROP = TAIL                # 第 21 期：云身下沿比贴片下沿再低一条尾巴带——用户要的
                                  # 「云朵框还要往下移，底部对齐左侧文字标题」（那张贴片下沿
                                  # 正好是标题行里那行大字的底边）
SHAPE_MIN_BODY = {SHAPE_CLOUD: MIN_BODY, SHAPE_PUFF: MIN_BODY,
                  SHAPE_ROUND: MIN_BODY, SHAPE_TAG: MIN_BODY}
EAR_RATIO = 0.14                  # 贴片耳朵的纵向位置：圆气泡「从耳朵那头长出来」拿它当起点
CHEEK_X = 0.30                    # 第 24 期：尾巴尖统一指三虎的脸颊——横向 0.30（贴着云身那半边脸）
CHEEK_Y = 0.62                    # 脸颊的纵向位置（64 像素的贴片里在 40/64 那一行）
ANCHOR_RATIO = 1.0                # 云身下沿对齐贴片的这个位置（1.0＝贴片下沿；再加 ANCHOR_DROP）
TIP_IN = 6                        # 尾巴尖落在浮窗右下角往内这么多像素的地方
TAIL_SPAN_X = 0.86                # 第 24 期：尾巴根（底边中点）落在云身宽度的这个比例上
TAIL_SPAN_Y = 0.86                # 与云身高度的这个比例上：底边整条被云身盖住，只把尖角露在外面
MARGIN = 8                        # 浮窗离屏幕边留一点，别贴着屏幕边
PET_GAP = 6                       # 第 24 期：云身与三虎之间至少留这么宽一条缝（不许压住猫）
MAX_GAP = 30                      # 第 25 期第 4 条：云身离三虎最多这么远（远了就往回收，别像两块不相干的板子）
POSITION_RETRY_MS = 50              # 主窗口尚未映射完成时，给 Tk 一小拍完成布局
POSITION_RETRY_MAX = 10             # 最多等 500ms；不能无限重试并把 (0,0) 当作有效坐标
PET_SIZE = PET_LAYOUT['avatar_size']  # 贴片画不出来时的兜底边长
DOCK_TOP = 4                                    # 主界面上沿离屏幕上沿不超过这么多像素＝贴着屏幕顶（全屏／最大化）


def shape_root(shape, width, height):
    """尾巴根（云身坐标）：长在框身靠右下那一带，尾巴点才不像是飘在空中的。

    第 57 期第 1 条：四种聊天框都是同一个方框，落点也就只有这一处——根埋在框身偏右下的填充里
    （底边整条被框身盖住，接缝露不出来），只把弯尖角甩到三虎的脸颊上。shape 只是个签名参数，
    留着是为了调用方（含自检）不必改。
    """
    return _shape_root(width, height, TAIL_SPAN_X, TAIL_SPAN_Y)


def shape_min_body(shape):
    return _configured_value(shape, SHAPES, SHAPE_CLOUD, SHAPE_MIN_BODY)


class CloudPlaceMixin:
    # ── 定位：云站在三虎左边，尾巴尖指着它的脸颊 ───────────────────────────
    def _patch_rect(self):
        """贴片在屏幕上的矩形 (left, top, width, height)：量不准就退回上一次可信的那一份。

        第 49 期第 1 条（用户报「从助手切换出来时，聊天框从画面右边跳到画面左边」）：主窗口一
        最小化／收起，winfo_rootx／rooty 就不再是贴片在屏幕上的位置了——Tk 那时报的是「窗口没
        映射」时的相对坐标（实测画布宽 64 却报 left=768、top=1004，凭空挪到屏幕下半截）。任何
        一次重排（播报把框顶出来、界面 Configure 跟一手）赶上这一刻，整朵云就落到屏幕另一边；
        等用户切回来再量又是对的，看着就是「跳」。
        所以这里先核一遍：贴片没映射、尺寸量成 0、坐标落到屏幕外，这一次的量值就都不作数，退回
        上一次量准的那一份；一次都没量准过（开机头几拍）才照原样返回——那会儿 _origin 自己会把
        落点夹进屏幕里。
        """
        try:
            canvas = self.pet.canvas
        except Exception:
            canvas = None
        if canvas is None:
            return getattr(self, '_last_patch', None) or (0.0, 0.0, float(PET_SIZE), float(PET_SIZE))
        width, height = float(PET_SIZE), float(PET_SIZE)
        try:
            width = float(int(canvas.winfo_width()) or int(canvas.cget('width')))
        except Exception:
            app_logging.swallowed()
        try:
            height = float(int(canvas.winfo_height()) or int(canvas.cget('height')))
        except Exception:
            app_logging.swallowed()
        try:
            left, top = float(int(canvas.winfo_rootx())), float(int(canvas.winfo_rooty()))
        except Exception:
            left = top = 0.0
        if self._patch_is_trustworthy(canvas, left, top, width, height):
            self._last_patch = (left, top, width, height)
        elif getattr(self, '_last_patch', None) is not None:
            return self._last_patch
        return (left, top, width, height)

    def _patch_is_trustworthy(self, canvas, left, top, width, height):
        """这一次量出来的贴片矩形可信吗（第 49 期第 1 条）。

        主判据是「贴片映射着没有」：窗口一最小化／收起，winfo_ismapped 当场变假，而那一刻的
        rootx／rooty 全是假的——这一条在真机上实测过（贴片会报成屏幕下半截的位置）。
        不拿「坐标有没有超出屏幕」当判据：多显示器时副屏的横坐标本来就大于主屏宽度，
        那条判据会把好端端的副屏位置判成假的。
        """
        try:
            if not bool(canvas.winfo_ismapped()):
                return False
        except Exception:
            app_logging.swallowed()
        if width < 8.0 or height < 8.0:
            return False
        return left >= 0.0 and top >= 0.0

    def _ear(self):
        """贴片耳朵在屏幕上的位置：圆气泡「从耳朵那头长出来」用它当起点（第 19 期）。"""
        left, top, width, height = self._patch_rect()
        return (left + max(8.0, width) * 0.5, top + max(8.0, height) * EAR_RATIO)

    def _cheek(self):
        """贴片脸颊在屏幕上的位置：四种形状的尾巴尖统一指这里（第 24 期用户要的「指向脸颊」）。

        第 22 期指的是嘴边（脸正中的那一列）；脸颊往云身这一侧偏一点（CHEEK_X），尾巴斜着
        伸过去才不会从整张脸中间穿过——「三虎正在说话」的感觉也正是这条斜尾巴给的。
        """
        left, top, width, height = self._patch_rect()
        return (left + max(8.0, width) * CHEEK_X, top + max(8.0, height) * CHEEK_Y)

    def _anchor(self):
        """整朵云与尾巴共用的那一个锚点：三虎的脸颊（第 24 期起）。

        云身右下沿、尾巴尖都按它算——所以窗口缩放、贴片挪位时，整朵云和那根尖角是**一起**动的，
        不会出现「云跟着走了、尾巴还指着原处」。耳朵只留给圆气泡「长出来」的起点（_grow_to）。
        """
        return self._cheek()

    def _bottom(self):
        """贴片下沿：云身下沿落在这一条线上（第 18 期「底部和三虎对齐」＋第 21 期的 ANCHOR_DROP）。"""
        left, top, width, height = self._patch_rect()
        # 第 21 期：再往下 ANCHOR_DROP 一条尾巴带——云身下沿落在贴片下沿上（也就是标题行里那行
        # 大字的底边），用户要的「云朵框还要往下移，底部对齐左侧文字标题」。
        return top + max(8.0, height) * ANCHOR_RATIO + ANCHOR_DROP

    def _monitor(self):
        """助手主窗口所在显示器的 (left, top, right, bottom)；量不到返回全 0。

        winfo_screenwidth/height 只是主屏尺寸：软件放在副屏时，拿它当边界会把云朵拽回主屏。
        """
        try:
            return monitor_bounds(self.parent)
        except Exception:
            return (0, 0, 0, 0)

    def _work_left(self):
        return self._monitor()[0]

    def _work_top(self):
        return self._monitor()[1]

    def _work_right(self):
        """屏幕右边界：云可以压在主界面之外，但不许整朵跑到屏幕外面去。"""
        return self._monitor()[2]

    def _window_rect(self):
        """助手主窗口在屏幕上的矩形 (left, top, right, bottom)；拿不到就返回 None。"""
        try:
            left, top = int(self.parent.winfo_rootx()), int(self.parent.winfo_rooty())
            width, height = int(self.parent.winfo_width()), int(self.parent.winfo_height())
        except Exception:
            return None
        if width <= 1 or height <= 1:
            return None
        return (left, top, left + width, top + height)

    def _inside_window(self, left, top):
        """整朵云在屏幕外摆不下时把它挪进助手界面里（第 22 期用户要的「调整到界面内」）。

        界面里总放得下——真放不下也还有滚轮。摆得下（原来那个落点已经整朵在屏幕里）就返回
        None，调用方照旧用原落点，界面上看不出任何变化。
        """
        width, height = self.total_width(), self._body + TAIL
        right = self._work_right()
        screen = self._screen_height()
        edge_left, edge_top = self._work_left(), self._work_top()
        fits = (left >= edge_left + MARGIN and (right <= 0 or left + width <= right - MARGIN)
                and top >= edge_top + MARGIN and (screen <= 0 or top + height <= screen - MARGIN))
        if fits:
            return None
        rect = self._window_rect()
        if rect is None:
            return None
        x0, y0, _x1, _y1 = rect
        limit_x = (right - width - MARGIN) if right > 0 else x0 + MARGIN
        inner_left = max(edge_left + MARGIN, min(x0 + MARGIN, max(edge_left + MARGIN, limit_x)))
        limit_y = (screen - height - MARGIN) if screen > 0 else y0 + MARGIN
        inner_top = max(edge_top, min(y0 + MARGIN, max(edge_top, limit_y)))
        return int(inner_left), int(inner_top)

    def _screen_height(self):
        """屏幕下边界（助手所在显示器的下沿，副屏时不是主屏高度）。"""
        return self._monitor()[3] if self.win is not None else 0

    def _room_above(self):
        """三虎上方还剩多高（云身＋尾巴都得从这里排）。"""
        return int(self._bottom() - (self._work_top() + MARGIN) - TAIL)

    def _room_below(self):
        """三虎下方还剩多高：上方放不下时云身翻到它下面去。"""
        screen = self._screen_height()
        if screen <= 0:
            return 0
        return int(screen - MARGIN - self._bottom() - MARGIN - TAIL)

    def _can_align_top(self, height=None):
        if self.shape != SHAPE_CLOUD:
            return False
        left, top, _width, _height = self._patch_rect()
        height = self._body if height is None else height
        return (left >= self._work_left() + self.width() + PET_GAP + MARGIN
                and top >= self._work_top() + MARGIN
                and top + height + TAIL <= self._screen_height() - MARGIN)

    def _flipped(self):
        """上方连最小云身都放不下、下方反而更宽敞时，翻到三虎下面（全屏时就是这么救的）。

        第 36 期第 7 条：_down（这一条内容上方真放不下、主界面又贴着屏幕上沿）也算翻下去——
        判据从「连最小云身都放不下」换成「这条内容放不下」，见 _wants_down。
        """
        if self._can_align_top():
            return False
        if self._down:
            return True
        above = self._room_above()
        return above < shape_min_body(self.shape) and self._room_below() > above

    def _frame_top(self):
        """主窗口**窗体**上沿的屏幕坐标（含标题栏）；量不到返回 None。

        第 42 期第 2 条：winfo_rooty() 给的是客户区上沿——窗口被拖到屏幕上沿时 Windows 还留着一条
        标题栏（实测客户区在屏幕下 31 像素，最大化时 23 像素），按它判「贴不贴顶」会漏判：全屏那一套
        「整朵翻到三虎下面」的判据在「拖到最上面」时整条不生效，用户看到的就是「聊天框只显示一行」。
        这里改问窗口管理器要窗体矩形（GetWindowRect），拿不到（非 Windows／接口不在）退回客户区上沿。
        """
        try:
            import ctypes
            import ctypes.wintypes
            handle = int(self.parent.winfo_id())
            frame = ctypes.windll.user32.GetParent(handle) or handle
            rect = ctypes.wintypes.RECT()
            if ctypes.windll.user32.GetWindowRect(frame, ctypes.byref(rect)):
                return int(rect.top)
        except Exception:
            app_logging.swallowed()
        rect = self._window_rect()
        return None if rect is None else int(rect[1])

    def _docked_top(self):
        """主界面是不是贴在屏幕上沿（全屏／最大化／被拖到最上面）。拿不到窗口矩形当「不是」。"""
        rect = self._window_rect()
        if rect is None:
            return False                       # 窗口还没映射出来（1×1）：别拿没量到的坐标当「贴着顶」
        top = self._frame_top()
        return False if top is None else int(top) <= DOCK_TOP

    def _wants_down(self, wanted):
        """这一条内容要不要整朵挪到三虎下面（第 36 期第 7 条：逐步下移显示更多内容）。

        全屏、或主界面被拖到屏幕上沿时，三虎上方的余量只剩几十像素：原来只按「连最小云身都
        放不下」判，内容稍长就压在那条窄带里、被 _fit_body 压到最小高度，字只能靠滚轮翻。
        现在按**这条内容真正需要的高度**判——上方放不下、下方更宽敞就往下挪，框身一路往下长。
        主界面不在屏幕顶时不改判据，界面里的落点与原来一模一样。
        """
        above = self._room_above()
        if wanted <= above:
            return False
        below = self._room_below()
        if below <= above:
            return False
        return self._docked_top() or above < shape_min_body(self.shape)

    def _up(self):
        """尾巴该往哪头伸：云身翻在三虎下面时往上（第 29 期第 3 条）。

        向上翻的时候脸颊在云身上方，尾巴再从下边那条带子里挑出来就只能顶到画布上沿——离脸颊还差一整条云身，
        用户看到的就是「箭头没碰到三虎的脸」。这时带子改在上方（见 _shift）。"""
        return self._flipped()

    def _shift(self):
        """云身在画布里的纵向偏移：尾巴带在下时为 0，在上时为 TAIL。"""
        return TAIL if self._up() else 0

    def _body_ceiling(self):
        """云身高度上限（第 42 期第 2 条）。

        平时收在 MAX_BODY（第 30 期第 4 条那一档，再长交给滚轮）；主界面贴着屏幕顶、整朵被迫翻到
        三虎下面时，下面那一整屏都是空的，用户要的「把框下移显示更多内容」就落在这里——上限放宽到
        MAX_BODY_DOWN，框身长到刚好装下这条内容为止（内容短还是原来那么小，不会无端变胖）。
        """
        if self._flipped() and self._docked_top():
            return MAX_BODY_DOWN
        return MAX_BODY

    def _fit_body(self, wanted):
        """云身高度：放得下就按内容，放不下就压到能放的高度（其余内容靠滚轮看）。"""
        if self._can_align_top(min(wanted, MAX_BODY_DOWN)):
            self._down = False
            return int(min(wanted, MAX_BODY_DOWN))
        self._down = self._wants_down(wanted)      # 第 36 期第 7 条：先定朝向，再按那一侧算余量
        room = self._room_below() if self._flipped() else self._room_above()
        ceiling = self._body_ceiling()             # 第 42 期第 2 条：翻到下面时允许长过 MAX_BODY
        floor = int(min(shape_min_body(self.shape), max(60, room)))
        return int(max(floor, min(int(wanted), max(floor, min(ceiling, room)))))

    def _avoid_pet(self, left, top):
        """云身不许压住三虎（第 24 期第 9 条）：真压上了就往左／往上让开最少的距离。

        用户的原话是「可以遮挡界面的文字，不能遮挡三虎」，而且「尽量不要移动太远」——
        所以这里只挪到刚好不压着猫为止（先往左让，界面左边不够再往上），不重新挑落点。
        没压着就一个像素都不动，直接返回原落点。

        拿来比的是**云身**那一块方框，不含右边留尾巴的那条空档：那根尖角是「指到脸颊上」
        的指针（见 _tip），按用户第 24 期的要求本来就顶着三虎的脸——把它也算进来，云身
        就得为它再退开一整个尾巴的长度，尖角反而缩回空档里、指不到脸了。
        """
        rect = self._patch_rect()
        patch_left = rect[0] - PET_GAP
        patch_top = rect[1] - PET_GAP
        patch_right = rect[0] + max(8.0, rect[2]) + PET_GAP
        patch_bottom = rect[1] + max(8.0, rect[3]) + PET_GAP
        width, height = self.width(), self._body
        shift = self._shift()
        body_top = float(top) + shift
        if (left + width <= patch_left or left >= patch_right
                or body_top + height <= patch_top or body_top >= patch_bottom):
            return (left, top)                       # 没压着：落点一个像素都不动
        left = left + (patch_left - (left + width))  # 往左让：让出的正好是压住的那一条
        edge_left = self._work_left()
        if left < edge_left + MARGIN:
            left = edge_left + MARGIN
            if self._up():
                top = max(top, patch_bottom - shift)     # 云身在下：往下让，从三虎下面开始
            else:
                top = max(self._work_top(), min(top, patch_top - height))   # 云身在上：左边让不开就往上让
        return (int(left), int(top))

    def _near_pet(self, left, top):
        """云身离三虎太远就往回收（第 25 期第 4 条）：最多留 MAX_GAP 那么宽一条空档。

        什么时候会太远：屏幕边不够、或者整朵在屏幕外摆不下被 _inside_window 挪进助手界面里，
        落点会被推得很开——对话框看着就跟猫没关系了（用户报的「不能离三虎太远」）。
        这里只拉这一条空档：拉回来压到三虎身上时就不拉（不压住猫是硬要求，见 _avoid_pet），
        屏幕挤得拉不回来也不拉（宁远离，不越界）。尾巴尖照旧钉在脸颊上，见 _tip。
        """
        width, height = float(self.width()), float(self._body)
        rect = self._patch_rect()
        patch_left = float(rect[0])
        patch_top = float(rect[1]) - PET_GAP
        patch_bottom = float(rect[1]) + max(8.0, rect[3]) + PET_GAP
        body_top = float(top) + self._shift()
        if body_top + height <= patch_top or body_top >= patch_bottom:
            return (int(left), int(top))            # 云身跟三虎不在同一条横带上：不掺和
        gap = patch_left - (left + width)
        if gap <= MAX_GAP:
            return (int(left), int(top))            # 已经在近处：一个像素都不动
        pulled = left + (gap - MAX_GAP)
        floor = self._anchor()[0] - (self.total_width() - 2)   # 再往右，尾巴尖就顶出画布了
        pulled = max(pulled, floor)
        if pulled <= left:
            return (int(left), int(top))            # 画布就这么宽，提不动：保持原样
        right = self._work_right()
        if right > 0 and pulled + self.total_width() + MARGIN > right:
            return (int(left), int(top))            # 拉不进屏幕里就别拉
        if pulled + width > patch_left - PET_GAP:
            return (int(left), int(top))            # 拉回来会压住猫：不拉
        return (int(pulled), int(top))

    def _pet_horizontal_anchor(self, left, top):
        """判定三虎在气泡右侧还是下方/偏左，并返回 (on_right, target_x, local_x)。"""
        rect = self._patch_rect()
        cheek_x, _cheek_y = self._anchor()
        body_right = float(left) + float(self.width())
        on_right = (float(cheek_x) >= body_right - PET_GAP
                    or float(rect[0]) >= body_right - PET_GAP)
        target_x = float(rect[0]) + max(8.0, float(rect[2])) * 0.5
        return on_right, target_x, target_x - float(left)

    def _pet_docked_left(self):
        """三虎是否停靠在窗口左侧或贴近屏幕左边，导致气泡无法摆在三虎左侧。"""
        rect = self._patch_rect()
        cheek_x, _cheek_y = self._anchor()
        pw = max(8.0, float(rect[2]))
        expected_cheek = float(rect[0]) + pw * CHEEK_X
        if abs(float(cheek_x) - expected_cheek) > max(32.0, pw):
            return False
        width = float(self.width())
        win_rect = self._window_rect()
        if win_rect is not None:
            x0 = float(win_rect[0])
            if float(rect[0]) >= x0 - 4.0 and (float(rect[0]) - x0) < width:
                return True
        return float(rect[0]) - PET_GAP - width < float(self._work_left()) + MARGIN

    def _origin(self):
        """浮窗左上角（屏幕坐标）：左下角停靠时摆在三虎正上方并贴合窗口左内边；
        经典右侧布局仍站在三虎左边、下沿与它对齐，尾巴指到脸颊。
        """
        total = self.total_width()
        right = self._work_right()
        edge_left = self._work_left()
        edge_top = self._work_top()
        if self._pet_docked_left():
            rect = self._patch_rect()
            win_rect = self._window_rect()
            base_left = (win_rect[0] + MARGIN) if win_rect is not None else (edge_left + MARGIN)
            if right - edge_left > total + 2 * MARGIN:
                left = max(edge_left + MARGIN, min(int(base_left), right - total - MARGIN))
            else:
                left = max(edge_left + MARGIN, int(base_left))
            patch_top = rect[1] - PET_GAP
            patch_bottom = rect[1] + max(8.0, rect[3]) + PET_GAP
            if self._up():
                top = int(patch_bottom - self._shift())
            else:
                top = int(patch_top - self._body)
            top = max(edge_top + MARGIN, top)
            screen = self._screen_height()
            if screen > 0:
                top = min(top, max(edge_top + MARGIN, screen - MARGIN - (self._body + TAIL)))
            return (int(left), int(top))
        anchor_x, _anchor_y = self._anchor()
        left = int(anchor_x - (total - TIP_IN))
        if right - edge_left > total + 2 * MARGIN:
            left = max(edge_left + MARGIN, min(left, right - total - MARGIN))
        if self._can_align_top():
            top = int(self._patch_rect()[1])
        elif self._flipped():
            # 第 29 期第 3 条：翻到三虎下面时，尾巴带在云身**上方**，带子的尖头就落在脸颊上——
            # 以前下边那条带子是白留的，尖头被夹在画布里，顶多只能顶到画布上沿，
            # 脸颊在上面一整条云身的地方——用户看到的就是「箭头没碰到脸」。
            top = int(self._anchor()[1] - (TAIL - TIP_IN))
        else:
            top = int(self._bottom() - (self._body + TAIL))
        # 第 22 期：整朵在屏幕外摆不下（顶到屏幕边／露不全）就挪进助手界面里。
        inside = self._inside_window(left, top)
        spot = self._avoid_pet(*(inside if inside is not None else (left, top)))
        return self._near_pet(*spot)

    def _tip(self):
        """画布坐标下的尾巴尖：三虎在右侧时指右颊；在左下/下方时动态指向三虎头像中心。"""
        left, top = self._origin()
        cheek_x, cheek_y = self._anchor()
        on_right, _target_x, local_x = self._pet_horizontal_anchor(left, top)
        if on_right:
            x = min(max(int(cheek_x - left), int(self.width() * 0.75)), self.total_width() - 2)
            if self._up():
                y = min(max(int(cheek_y - top), 2), TAIL - 2)      # 带子在上：尖头进不了下面去
            else:
                y = min(max(int(cheek_y - top), 8), self._body + TAIL - 2)
            return (x, y)
        x = min(max(int(round(local_x)), MARGIN), max(MARGIN, self.width() - MARGIN))
        if self._up():
            y = min(max(int(cheek_y - top), 2), TAIL - 2)
        else:
            y = min(max(int(cheek_y - top), self._body + 6), self._body + TAIL - 2)
        return (x, y)

    def _tail_polygon(self):
        """尾巴＝一根尖角折线：底边藏在云身里，根部与尖端按三虎真实方位动态同步指向。"""
        tip_x, tip_y = self._tip()
        left, top = self._origin()
        on_right, _target_x, _local_x = self._pet_horizontal_anchor(left, top)
        root_x, root_y = shape_root(self.shape, self.width(), self._body)
        half = TAIL_BASE * 0.5
        if on_right:
            if self._up():
                base_y = float(TAIL) + root_y               # 根还在云身里（被云身盖住），尖头朝上
                return ('poly', tail_points((root_x - half, base_y - 2.0), (root_x + half, base_y + 2.0),
                                            (float(tip_x), float(tip_y))))
            return ('poly', tail_points((root_x - half, root_y + 2.0), (root_x + half, root_y - 2.0),
                                        (float(tip_x), float(tip_y))))
        min_rx = float(TAIL_BASE + MARGIN)
        max_rx = float(max(min_rx, self.width() - TAIL_BASE - MARGIN))
        root_x = min(max(float(tip_x), min_rx), max_rx)
        if self._up():
            base_y = float(TAIL) + float(self._body) * (1.0 - TAIL_SPAN_Y)
            return ('poly', tail_points((root_x - half, base_y), (root_x + half, base_y),
                                        (float(tip_x), float(tip_y))))
        return ('poly', tail_points((root_x - half, root_y), (root_x + half, root_y),
                                    (float(tip_x), float(tip_y))))

    def _reset_position_state(self):
        """定位重试登记的初值（父窗口尚未完成布局时的受限延迟重试）；只有本 Mixin 写这三个字段。"""
        self._position_job = None
        # Tk 只保存回调对应的 Tcl 命令名；若不保留 Python 闭包，GC 会先删命令，
        # 留下 after 队列在窗口销毁前报 ``invalid command name ...retry``。
        self._position_callback = None
        self._position_retries = 0

    def _take_position_job(self):
        """清掉重试登记并交出旧的 after 句柄（没有则 None）；取消由调用方做。"""
        job, self._position_job = self._position_job, None
        self._position_callback = None
        return job

    def _arm_position_retry(self):
        """父窗口还没布局好：在上限内排一张延迟重试票（同一时刻最多一张）。"""
        if self._position_retries < POSITION_RETRY_MAX and self._position_job is None:
            try:
                self._position_retries += 1
                # 用闭包保持 Cloud 到回调实际执行／取消为止；直接登记绑定方法时，
                # Cloud 先被回收会令 Tcl 留下 ``..._place_window`` 无效命令。
                def retry(cloud=self):
                    if cloud._position_job is None:
                        return None
                    # 只有这一张已排队的票真正开始执行时才清登记。同步触发的
                    # follow/_place_window 不能清它，否则 Tcl 仍握着旧回调、
                    # Python 却已不再持有该回调。
                    cloud._take_position_job()
                    try:
                        if not cloud.parent.winfo_exists():
                            return None
                    except Exception:
                        return None
                    return cloud._place_window()
                # after() 自身只挂 Tcl 命令名；字段持有闭包直到触发／取消，
                # 防止局部变量离开作用域后 Tk 留下悬空命令。
                self._position_callback = retry
                self._position_job = self.parent.after(POSITION_RETRY_MS, retry)
            except Exception as exc:
                self.errors.append(('place.retry', str(exc)))

    def _place_window(self):
        """按三虎贴片锚点摆浮窗；父窗或贴片未映射时每 50ms 重试，最多十次。"""
        if self.win is None:
            return None
        try:
            parent_rect = (self.parent.winfo_rootx(), self.parent.winfo_rooty(),
                           self.parent.winfo_width(), self.parent.winfo_height())
        except Exception as exc:
            self.errors.append(('place', str(exc)))
            return None
        if (int(parent_rect[2]) <= 1 or int(parent_rect[3]) <= 1
                or not self._position_anchor_ready()):
            self._arm_position_retry()
            return None
        self._position_retries = 0
        # 云朵的语义是「三虎在说话」：落点必须来自贴片脸颊，而不能是父窗口中心。
        # _origin 会同时处理副屏坐标、屏幕边界钳制以及不遮住三虎的间距。
        left, top = self._origin()
        try:
            self.win.geometry('+%d+%d' % (int(left), int(top)))
        except Exception as exc:
            self.errors.append(('place', str(exc)))
            return None
        return left, top

    def _position_anchor_ready(self):
        """贴片屏幕坐标已稳定才允许定位，避免第一次映射时把 (0, 0) 当真。"""
        try:
            canvas = self.pet.canvas
            width, height = float(canvas.winfo_width()), float(canvas.winfo_height())
            left, top = float(canvas.winfo_rootx()), float(canvas.winfo_rooty())
        except Exception:
            # 仅供无贴片的轻量测试桩使用；真实 Cloud 一定持有 pet.canvas。
            return not hasattr(self, 'pet')
        return self._patch_is_trustworthy(canvas, left, top, width, height)
