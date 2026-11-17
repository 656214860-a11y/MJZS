"""三虎窗口的绘制、动画、菜单与点击。

从 ``pet_ui.Pet`` 原样迁出（R1506）：方法体未改，``self`` 语义不变，``Pet`` 通过继承
``PetViewMixin`` 获得；用到的模块级名字来自 ``pet_ui_support``。
"""
import pet_agent
import contract.pet_bus as pet_bus
import ui.pet_cloud as pet_cloud
from tkinter import TclError
from ui_tokens import BUTTON_BORDER_WIDTH, COLORS, DESKTOP_LAYOUT, PET_LAYOUT, SPACING
from ui_widgets import ContextMenu
from pet_ui_support import ACTIVE_MS, BUSY_TAPS, BUSY_WINDOW, CANVAS_BG, CAPTION_Y, CHAT_MUTE_SECONDS, DETAIL_MENU_LABEL, DOCK_CAPTION_GAP, DOCK_CAPTION_ROOM, DOCK_CLUSTER_W, DOCK_PAD_BOTTOM, DOCK_PAD_TOP, DOCK_PAD_X, DOCK_PAW_RIGHT, DOCK_ROOM, IDLE_MS, PANEL_DIVIDER, PANEL_HEAD, PANEL_MENU_LABEL, PANEL_SECTIONS, PATCH_X, PAW_ARC, PAW_COL_HEIGHT, PAW_COL_WIDTH, PAW_COL_X, PAW_COLORS, PAW_GAP, PAW_HOVER, PAW_IDLE, PAW_LEVELS, PAW_HIT_SIZE, PAW_HIT_X, PAW_SIZE, PAW_STEP, QUIT_LABEL, SETTINGS_ENTRIES, SETTINGS_LABEL, SIZE, SNOOZE_SECONDS, paint, paw_dy, paw_parts


class PetPatchLayoutMixin:
    """贴片簇布局：头像＋小字左列、猫爪列右列，簇区恒为正方形（第 R2946 期）。

    正方形边长 ``side=max(DOCK_CLUSTER_W, 内容高+上下边距)``；内容在 side 内水平垂直
    居中，``patch_room``＝side 由宿主 align_header 写成 pet_dock 高。小字一行／两行
    换行、dock 宽度变化时由 ``_align_paws`` 重算全部 place 坐标（状态只经本类写
    ``self.patch_room``）。
    """
    def _dock_widget(self):
        """簇的承载层：pet_layer → pet_dock → title_row → 根窗（与 _build_canvas 同链）。"""
        return (getattr(self.desktop, 'pet_layer', None)
                or getattr(self.desktop, 'pet_dock', None)
                or getattr(self.desktop, 'title_row', None) or self.win)
    def _caption_height(self):
        """小字实测高；未映射或取不到时退回按 token 行高估的两行。"""
        caption = getattr(self, 'caption', None)
        try:
            height = int(caption.winfo_reqheight()) if caption is not None else 0
        except (TclError, ValueError):
            height = 0
        return height if height > 0 else 2 * PET_LAYOUT['caption_height']
    def _cluster_layout(self):
        """算出正方形边长与全部 place 坐标；dock 未映射时宽度退回侧栏内宽估值。"""
        dock = self._dock_widget()
        try:
            dock_w = int(dock.winfo_width())
        except (TclError, ValueError, AttributeError):
            dock_w = 0
        if dock_w <= 0:
            dock_w = DESKTOP_LAYOUT['sidebar_width'] - SPACING['xs']
        group_h = SIZE + DOCK_CAPTION_GAP + self._caption_height()
        count = len(PAW_LEVELS)
        col_rel = (group_h - PAW_COL_HEIGHT) / 2.0
        last = count - 1
        hit_bottom_rel = (col_rel + last * PAW_STEP + PAW_SIZE // 2
                          + paw_dy(last) + PAW_HIT_SIZE // 2)
        hit_top_rel = col_rel + PAW_SIZE // 2 + paw_dy(0) - PAW_HIT_SIZE // 2
        inner_top = min(0.0, hit_top_rel)
        inner_bottom = max(float(group_h), hit_bottom_rel)
        inner_h = inner_bottom - inner_top
        side = max(float(DOCK_CLUSTER_W), DOCK_PAD_TOP + inner_h + DOCK_PAD_BOTTOM)
        content_left = max(0.0, (dock_w - DOCK_CLUSTER_W) / 2.0)
        avatar_x = content_left + DOCK_PAD_X
        avatar_y = ((side - DOCK_PAD_TOP - DOCK_PAD_BOTTOM - inner_h) / 2.0
                    + DOCK_PAD_TOP - inner_top)
        caption_y = avatar_y + SIZE + DOCK_CAPTION_GAP
        paw_col_y = avatar_y + (group_h - PAW_COL_HEIGHT) / 2.0
        paw_right = content_left + DOCK_CLUSTER_W - DOCK_PAW_RIGHT
        paw_x = paw_right - dock_w
        # 承接区比猫爪宽：右沿可能探出 dock 一点，钳在 dock 内不压正文（仍盖住整只爪）。
        hit_right = min(paw_right - PAW_COL_WIDTH // 2 + PAW_HIT_SIZE // 2, float(dock_w))
        hit_x = hit_right - dock_w
        hit_ys = [paw_col_y + i * PAW_STEP + PAW_SIZE // 2 + paw_dy(i)
                  - PAW_HIT_SIZE // 2 for i in range(count)]
        return {'side': side, 'avatar_x': avatar_x, 'avatar_y': avatar_y,
                'caption_y': caption_y, 'paw_col_y': paw_col_y,
                'paw_x': paw_x, 'hit_x': hit_x, 'hit_ys': hit_ys}
    def _paw_col_top(self):
        """猫爪列顶边＝_cluster_layout 的 paw_col_y（保留方法名给既有调用与测试）。"""
        return self._cluster_layout()['paw_col_y']
    def _align_cluster(self):
        """把头像画布、小字、猫爪列与全部命中区 place 到正方形布局算出的坐标。"""
        layout = self._cluster_layout()
        canvas = getattr(self, 'canvas', None)
        if canvas is not None:
            try:
                canvas.place_configure(x=layout['avatar_x'], y=layout['avatar_y'])
            except TclError:
                pass
        caption = getattr(self, 'caption', None)
        if caption is not None:
            try:
                caption.place_configure(x=layout['avatar_x'], y=layout['caption_y'],
                                        width=DOCK_CAPTION_ROOM)
            except TclError:
                pass
        paws = getattr(self, 'paws', None)
        if paws is not None:
            try:
                paws.place_configure(x=layout['paw_x'], y=layout['paw_col_y'])
                for hit, top in zip(getattr(self, 'paw_hits', ()), layout['hit_ys']):
                    hit.place_configure(x=layout['hit_x'], y=top)
            except TclError:
                pass
        return layout
    def _align_paws(self, event=None):
        """小字换行（一行↔两行）或 dock 尺寸变化后重算整簇 place 坐标并同步底栏高度。"""
        try:
            layout = self._align_cluster()
        except Exception:
            return None
        self._sync_patch_room()
        return layout['paw_col_y']
    def _sync_patch_room(self):
        """底栏要留的高度＝簇区正方形边长 side；变了就让宿主重排一次。"""
        room = int(self._cluster_layout()['side'] + 0.999)
        if room == getattr(self, 'patch_room', None):
            return room
        self.patch_room = room
        try:
            align = getattr(self.desktop, 'align_header', None)
            if callable(align):
                align()
        except Exception as exc:
            self.errors.append(('room', str(exc)))
        return room
    def _build_paws(self):
        """三虎右侧那列猫爪：原图形不变，每只外加一块键盘／鼠标承接区（命中区尺寸不变）。"""
        import tkinter as tk
        parent = self._dock_widget()
        for old_hit in getattr(self, 'paw_hits', ()):
            try:
                old_hit.destroy()
            except TclError:
                pass
        self.paw_hits = []
        layout = self._cluster_layout()
        ring = BUTTON_BORDER_WIDTH * 2
        for index in range(len(PAW_LEVELS)):
            # 承接区：列内每爪一个，右沿比列中心再出头半个承接区，整列命中区右沿贴 dock 右沿。
            top = layout['hit_ys'][index]
            hit = tk.Canvas(parent, width=PAW_HIT_SIZE - ring * 2,
                            height=PAW_HIT_SIZE - ring * 2, bd=0,
                            highlightthickness=ring,
                            highlightbackground=CANVAS_BG, highlightcolor=COLORS['focus'],
                            bg=CANVAS_BG, cursor='hand2', takefocus=1)
            hit.place(relx=1.0, rely=0.0, anchor='ne', x=layout['hit_x'], y=top)
            hit.bind('<Button-1>', lambda event, i=index: self.paw_choose_event(event, i))
            hit.bind('<Enter>', lambda event, i=index: self.paw_hover_at(i))
            hit.bind('<Leave>', self.paw_leave)
            hit.bind('<FocusIn>', lambda event, i=index: self.paw_focus_at(i))
            hit.bind('<FocusOut>', self.paw_blur)
            hit.bind('<Return>', lambda event, i=index: self.paw_choose(i))
            hit.bind('<Key-space>', lambda event, i=index: self.paw_choose(i))
            self.paw_hits.append(hit)
        self.paws = tk.Canvas(parent, width=PAW_COL_WIDTH, height=PAW_COL_HEIGHT, bd=0,
                              highlightthickness=0, bg=CANVAS_BG)
        self.paws.place(relx=1.0, rely=0.0, anchor='ne', x=layout['paw_x'], y=layout['paw_col_y'])
        self.paws.bind('<Button-1>', self.paw_click)
        self.paws.bind('<Button-3>', self.popup)
        # 第 23 期：鼠标扫过哪只爪就把哪只提亮——三档点哪一档，扫一眼就知道。
        self.paws.bind('<Motion>', self.paw_hover)
        self.paws.bind('<Leave>', self.paw_leave)
        self.draw_paws()
        self._sync_patch_room()
        return self.paws


class PetViewMixin(PetPatchLayoutMixin):
    """Pet 的窗口与交互方法集（见模块说明）。"""
    def tap(self, label):
        """接缝③：页面按钮成功后上报「用户点了什么」（原按钮逻辑不受影响）。

        第 60 期第 1 条：顺手记一笔「人刚才在按」——连着按太密就自己进免打扰（见 note_work）。
        """
        self.note_work()
        return self._emit('intent.command', text=str(label), source='button')
    def details_text(self):
        """待确认详情（纯文本）：一条一段，阶段 · 类目 · 原因 · 建议；没有就说明一句。"""
        try:
            failures = [item for item in self.agent.failures if isinstance(item, dict)]
        except Exception as exc:
            self.errors.append(('details', str(exc)))
            failures = []
        if not failures:
            return '现在没有待确认的项。'
        lines = ['待确认 %d 项：' % len(failures)]
        for index, item in enumerate(failures, 1):
            stage = str(item.get('stage') or '')
            category = str(item.get('category') or '')
            lines.append('%d. %s · %s' % (index, pet_bus.STAGE_NAMES.get(stage, stage or '某阶段'),
                                          pet_agent.CATEGORY_NAMES.get(category, category or '未分类')))
            for prefix, key in (('原因', 'error'), ('建议', 'hint')):
                value = ' '.join(str(item.get(key) or '').split())
                if value:
                    lines.append('   %s：%s' % (prefix, value))
        return '\n'.join(lines)
    def show_details(self):
        """「待确认项」：直接在三虎旁的提示框展示，不创建只读弹窗。"""
        text = self.details_text()
        self.notice = text
        self.progress_bubble(text=text)
        return text
    def tap_safe(self, intent, at=None):
        try:
            return self.click(intent, at=at)
        except Exception as exc:
            self.errors.append(('click', str(exc)))
            return None
    def act(self, action, at=None, speak=True):
        """右键菜单的统一出口：先把事做完，再把结果说给用户听。

        action 是动作 id（走 click，与气泡按钮同一批实现），也可以是菜单里的原方法。
        需要直接展示完整提示框的菜单项可传 speak=False，避免把多行内容再次压成一行播报。
        """
        if callable(action):
            self.note_work(at=at)          # 第 60 期第 1 条：这一路不经过 click，在这儿补记一笔
            try:
                result = action()
            except Exception as exc:
                self.errors.append(('act', str(exc)))
                result = None
        else:
            result = self.tap_safe(action, at=at)
        if not speak or (isinstance(action, str) and action in ('chat',)):
            return result
        self.speak(at=at)
        return result
    def hide_to_pet(self):
        """常驻模式第 22 期跟着独立窗一起删了：桌面.py 仍在问，这里一律答「不收」。

        desktop.pet_hides_instead_of_quitting() 拿 False 就走原来的关闭流程——关主窗口就是关程序，
        与用户要的「删掉独立小窗」一致。留着这个空壳是为了不再改桌面那条接缝。
        """
        return False
    def show_main(self):
        """把主窗口放回来，并把 Windows 的任务栏最小化状态彻底解除。"""
        hidden = True
        try:
            state = str(self.win.state()).lower()
            hidden = state in ('iconic', 'withdrawn') or not bool(self.win.winfo_viewable())
            # Windows/Tk 对任务栏图标化的恢复并不稳定：部分宿主必须先映射，
            # 再显式 normal；只做其中一步会留下一个看似可见、实际仍在任务栏的根窗口。
            self.win.deiconify()
            self.win.state('normal')
            self.win.update_idletasks()
            self.win.lift()
            # lift 在被别的顶层窗口遮挡时可能无效；短暂置顶仅用于交还焦点，
            # 空闲后立刻恢复，避免主界面长期压住其他应用。
            try:
                self.win.attributes('-topmost', True)
                # Use a bound method, not a throw-away lambda: Tk can dispatch
                # this idle task after a close and otherwise reports an invalid
                # Tcl command name to stderr.
                self._main_topmost_job = self.win.after_idle(self._release_main_topmost)
            except TclError:
                # 重复销毁是 Tk 生命周期竞态。
                pass
            try:
                self.win.focus_force()
            except Exception as exc:
                self.errors.append(('show_main.focus', str(exc)))
        except Exception as exc:
            self.errors.append(('show_main', str(exc)))
            return False
        self.notice = '主窗口已显示' if hidden else '主窗口本来就在屏幕上'
        return True
    def _release_main_topmost(self):
        """Release show_main's one-shot topmost flag if the root still exists."""
        self._main_topmost_job = None
        try:
            self.win.attributes('-topmost', False)
        except TclError:
            # The root may be destroyed between after_idle() and this callback.
            pass
    # ── 稍后再说（静默一段时间） ─────────────────────────────────────────────
    def snooze_left(self):
        """还剩多少秒不播报；时钟可注入，用例不必真等 15 分钟。"""
        try:
            return max(0.0, float(self.snooze_until) - float(self.clock()))
        except (TypeError, ValueError):
            return 0.0
    def snoozing(self):
        return self.snooze_left() > 0
    def snooze_label(self):
        """菜单文字直接反映还剩多久恢复，不另存一份状态。

        第 44 期：这一项按用户附件叫「免打扰」（原来是「稍后再说」）——同一件事的两种说法里，
        用户附件给的说法更直白：这一段时间别打扰我。
        """
        left = self.snooze_left()
        if left > 0:
            return '免打扰中：还有 %d 分钟恢复播报' % max(1, int((left + 59) // 60))
        return '免打扰（安静 %d 分钟）' % (SNOOZE_SECONDS // 60)
    def snooze(self, seconds=None):
        """「稍后再说」（第 22 期回到一级功能栏，紧挨在「暂停」下面）：安静一段时间不说话。

        到点之后同一批失败会**再提醒一次**——所以这里连同 already-announced 指纹与「同一句话
        不连着说两遍」那枚指纹一起清掉；只清前者的话，那句一模一样的提醒会被播报的判重吃掉，
        用户永远等不到第二次。
        """
        span = SNOOZE_SECONDS if seconds is None else max(0.0, float(seconds))
        self.snooze_until = float(self.clock()) + span
        self.bstate.forget_spoken()
        self._busy_taps = []              # 第 60 期第 1 条：这一轮数满了，下一轮重新攒
        self.refresh_menu_labels()
        return self.snooze_left()
    def unsnooze(self):
        """立刻恢复播报；同一批失败下一轮心跳就会重新说一次（判重指纹同上一起清）。"""
        self.snooze_until = 0.0
        self.bstate.forget_spoken()
        self._busy_taps = []              # 第 60 期第 1 条：刚恢复就别拿旧账立刻又把自己按静
        self.refresh_menu_labels()
        return self.snooze_left()
    def note_work(self, at=None):
        """第 60 期第 1 条：用户正忙着按个不停时，三虎自己进免打扰。

        每一下用户动作（页面按钮、气泡按钮、右键菜单）都在这儿记一笔；BUSY_WINDOW 秒里攒满
        BUSY_TAPS 下就说明人正忙在手上的活上——这时候再冒话就是打扰。于是照手按「免打扰」那
        条路安静 SNOOZE_SECONDS，并且把「先安静多久」这一句当场说出去（安静前最后一句）。
        已经在免打扰里、或者时钟读不出来时什么都不做：安静期间用户照样按个不停，那不算新的一轮。
        返回 True ＝这一拍真的进了免打扰。
        """
        if self.snoozing():
            return False
        try:
            now = float(self.clock() if at is None else at)
        except (TypeError, ValueError):
            return False
        self._busy_taps = [item for item in self._busy_taps if (now - item) <= BUSY_WINDOW]
        self._busy_taps.append(now)
        if len(self._busy_taps) < BUSY_TAPS:
            return False
        self.snooze()                      # 连同 _busy_taps 一起清掉
        self.announce('您在忙：三虎先安静 %d 分钟，过后再把待确认的项报给您' % (SNOOZE_SECONDS // 60),
                      at=at)
        return True
    def toggle_snooze(self):
        """菜单入口：安静着就恢复，否则安静一段时间；两个方向都不抛，也都留一句提示。"""
        if self.snoozing():
            self.unsnooze()
            self.notice = '已恢复播报：下一轮心跳就把待确认的项重新报一次'
        else:
            self.snooze()
            self.notice = '已安静 %d 分钟：这段时间失败项只记账，出安静期再报一次' % (SNOOZE_SECONDS // 60)
        return self.snooze_left()
    # ── 心情与动画 ──────────────────────────────────────────────────────────
    def mood(self, state=None):
        try:
            agent = self.agent
            if agent.paused:
                return 'paused'
            if agent.failures:
                return 'worry'
            state = state if state else self.snapshot()
            return 'busy' if state.get('stage') is not None else 'idle'
        except Exception:
            return 'idle'
    def interval(self, state=None):
        return ACTIVE_MS if self.mood(state) == 'busy' else IDLE_MS
    def level(self, state=None):
        """当前自动化等级：快照里有就用快照的，取不到退回父 Agent 自己记的那一档。"""
        try:
            value = (state if state is not None else self.snapshot()).get('level')
        except Exception:
            value = None
        if value in pet_agent.LEVELS:
            return value
        try:
            return self.agent.level
        except Exception:
            return pet_agent.DEFAULT_LEVEL
    def draw(self, index=None, state=None):
        """手绘一帧（共用 paint()，方案 B 的独立窗也用它，不另画一份）。

        第 15 期：颜色跟着自动化等级走——切等级那一下要立刻变，所以 click('level') 里会手画一帧。
        """
        if self.canvas is None:
            return 0
        state = state if state else self.snapshot()
        try:
            percent = state['percent']
        except Exception:
            percent = 0.0
        self.show_caption()                # 等级字样：切等级／暂停都要立刻反映，不等下一帧
        return paint(self.canvas, step=(self.frame if index is None else int(index)),
                     mood=self.mood(state), percent=percent, level=self.level(state),
                     pose=self.cat.pose)
    def step(self):
        """动画帧推进：忙时 8fps、闲置 2fps（一帧只采一次进度）。

        第 17 期：顺手推一下猫样——到点就换个动作（爬行／舔爪／打哈欠／摇尾巴／撒娇）。
        第 44 期：设置里把「贴片动画」关掉就停在那一帧（帧号与猫样都不动），照旧重画——
        进度、等级、暂停这些还会跟着变，只是猫不再换动作（关掉是为了省一点 CPU）。
        """
        state = self.snapshot()
        if self.animation_enabled():
            self.frame += 1
            self.cat.next(self.frame)
        self.draw(state=state)
        self._schedule(state)
        return self.frame
    def _schedule(self, state=None):
        if getattr(self.desktop, 'shutting_down', False):
            return None
        # 一次只准有一个在排队：build() 之后再手动 step()（自测里到处在用）会叠出第二个定时器，
        # 动画双倍频，关窗时也只取消得掉最后一个——剩下那个到期就报 invalid command name "…step"。
        self._cancel_animation_timer()
        try:
            self._timer = self.win.after(self.interval(state), self.step)
        except Exception as exc:
            self.errors.append(('after', str(exc)))
            self._timer = None
        return self._timer
    def _cancel_animation_timer(self):
        """动画重排只撤销旧帧，不影响聊天、单击和主窗恢复回调。"""
        if self._timer:
            try:
                self.win.after_cancel(self._timer)
            except TclError:
                # 计时器随窗口销毁。
                pass
            self._timer = None
    def stop(self, event=None):
        if event is not None and getattr(event, 'widget', None) is not self.win:
            return None
        self.cancel_click()                # 待唤出的下拉栏一并撤掉：窗口没了，它到点就是一句报错
        # 云朵的位置重试挂在主窗口 after 队列；主窗退出不会自然调用 Cloud.close()。
        # 先收云朵，才能撤销 ``_place_window`` 的挂起重试。
        cloud = getattr(self, '_cloud', None)
        closer = getattr(cloud, 'close', None)
        if callable(closer):
            closer()
        else:
            cancel = getattr(cloud, 'cancel_deferred_render', None)
            if callable(cancel):
                cancel()
        self._cancel_animation_timer()
        if self._main_topmost_job:
            try:
                self.win.after_cancel(self._main_topmost_job)
            except TclError:
                # The root already owns no Tcl timer during teardown.
                pass
            self._main_topmost_job = None
        return self._timer
    # ── 界面搭建 ────────────────────────────────────────────────────────────
    def build(self):
        """把贴片、猫爪、等级小字与右键菜单建出来（全部 place 在既有容器里，不动原布局代码）。"""
        self._build_canvas()
        self._build_paws()
        self._build_menu()
        self.build_gear()
        self._bind()
        self.draw()
        self.lift_patch()
        self._schedule()
        return self
    def _build_canvas(self):
        import tkinter as tk
        parent = (getattr(self.desktop, 'pet_layer', None)
                  or getattr(self.desktop, 'pet_dock', None)
                  or getattr(self.desktop, 'title_row', None) or self.win)
        self.canvas = tk.Canvas(parent, width=SIZE, height=SIZE, bd=0, highlightthickness=0, bg=CANVAS_BG)
        # 第 R2933 期：三虎簇进侧栏左下角固定底栏；第 R2946 期簇区收成正方形，
        # 头像／小字／猫爪的坐标统一由 _cluster_layout 细算（见 _align_cluster）。
        self.canvas.place(x=PATCH_X, y=DOCK_PAD_TOP, anchor='nw')
        # dock 宽高一变（侧栏宽度、patch_room 写入）整簇重算坐标。
        parent.bind('<Configure>', lambda event: self._align_paws())
        self._reserve_room(parent)
        # 第 16 期：单击＝收起云朵框＋唤出功能下拉栏（用户要的是「点一下就能唤出」）；
        # 双击仍然是云朵框（要说话就双击我）。
        self.canvas.bind('<Button-1>', self.pet_click)
        self.canvas.bind('<Double-Button-1>', self.double_click)
        self.canvas.bind('<Button-3>', self.popup)
        # 第 18 期：贴片旁边一行小字，说明现在是哪一档（正常／半自动／全自动，暂停时写「已暂停」）。
        # 用户报「模式不显示了」——它原来只体现在猫的颜色上，不写字就看不出来。
        try:
            from tkinter import ttk
            # 第 R2933 期：小字在头像正下方、左沿对齐；宽度钉死在 DOCK_CAPTION_ROOM 上，
            # 不钉宽度的话「待确认 N」那一行会把小字撑到猫爪命中区上（实测过）。
            self.caption = ttk.Label(parent, text='', style='Muted.TLabel',
                                     wraplength=DOCK_CAPTION_ROOM, justify='left', anchor='w')
            self.caption.place(x=DOCK_PAD_X, y=CAPTION_Y, anchor='nw', width=DOCK_CAPTION_ROOM)
            # 小字一行／两行换行、dock 尺寸变化时整簇重算（见 _align_paws／_cluster_layout）。
            self.caption.bind('<Configure>', lambda event: self._align_paws())
            self.show_caption()
        except Exception as exc:
            self.errors.append(('caption', str(exc)))
            self.caption = None
        self._align_cluster()
        return self.canvas
    def _reserve_room(self, parent, needed=True):
        """给贴片簇在宿主里留够高度（第 R2933 期沿用：底栏由宿主按 patch_room 管高度）。

        pet_dock 由桌面 align_header 按 pet.patch_room 定高，这里直接放行；
        没有该承载层的宿主（自检里的假桌面）退回给标题行／根窗一个固定高度，免得被裁。
        独立窗开着时贴片收起，这里再把高度还给宿主（pack_propagate 打开＝回到自然高度）。
        """
        if parent is None:
            return None
        # 主窗口提供的承载层由主窗口管理，避免贴片反向撑高标题区／底栏。
        if parent is getattr(self.desktop, 'pet_layer', None):
            return parent
        try:
            if needed:
                parent.pack_propagate(False)
                parent.configure(height=DOCK_ROOM)
            else:
                parent.pack_propagate(True)
                parent.configure(height=0)
        except Exception as exc:
            self.errors.append(('room', str(exc)))
        return parent
    def draw_paws(self, level=None, force=False):
        """按当前等级重画那排猫爪；键盘焦点用 COLORS['focus'] 画出可见方框。"""
        canvas = self.paws
        if canvas is None:
            return None
        try:
            level = self.level() if level is None else level
            key = (level, self._paw_hover, self._paw_focus)
            if not force and key == self._paws_key and canvas.find_withtag('paw'):
                return canvas
            self._paws_key = key
            canvas.delete('paw')
            canvas.delete('paw-focus')
            for index, name in enumerate(PAW_LEVELS):
                if name == level:
                    fill, edge = PAW_COLORS.get(name, PAW_IDLE)
                elif index == self._paw_hover:
                    fill, edge = PAW_HOVER
                else:
                    fill, edge = PAW_IDLE
                for part in paw_parts(0, index * PAW_STEP + paw_dy(index)):
                    _kind, cx, cy, radius = part
                    canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                       fill=fill, outline=edge, width=2, tags=('paw', 'paw-' + name))
            if self._paw_focus is not None:
                top = self._paw_focus * PAW_STEP + paw_dy(self._paw_focus)
                canvas.create_rectangle(0, top, PAW_SIZE, top + PAW_SIZE + PAW_ARC,
                                        outline=COLORS['focus'],
                                        width=BUTTON_BORDER_WIDTH * 2, tags=('paw-focus',))
        except Exception as exc:
            self.errors.append(('paws', str(exc)))
        return canvas
    def paw_choose(self, index):
        """命中外层承接区：焦点落到该爪，动作与点击原爪完全一致。"""
        try:
            index = int(index)
        except (TypeError, ValueError):
            return None
        if not 0 <= index < len(PAW_LEVELS) or not self.paw_hits:
            return None
        try:
            self.paw_hits[index].focus_set()
        except TclError:
            pass
        return self.set_paw_level(PAW_LEVELS[index])
    def paw_choose_event(self, event=None, fallback=None):
        """鼠标点击按指针位置取最近的一只爪；坐标拿不到时才退回被点控件自己的档位。"""
        index = self.paw_nearest_at_root(getattr(event, 'y_root', None))
        if index is None:
            index = fallback
        if index is None:
            return None
        return self.paw_choose(index)
    def paw_nearest_at_root(self, y_root):
        """屏幕纵坐标最近的猫爪序号；承接区重叠时由这里决定谁接这一下。"""
        canvas = self.paws
        if canvas is None:
            return None
        try:
            y_root = float(y_root)
        except (TypeError, ValueError):
            return None
        top = canvas.winfo_rooty()
        centre = PAW_SIZE / 2
        return min(range(len(PAW_LEVELS)),
                   key=lambda index: abs(y_root - (top + index * PAW_STEP + centre)))
    def paw_hover_at(self, index):
        """承接区悬停：与画布上的 Motion 共用同一提亮状态。"""
        if index == self._paw_hover:
            return index
        self._paw_hover = index
        self.draw_paws()
        return index
    def paw_focus_at(self, index):
        self._paw_focus = index
        self.draw_paws()
        return index
    def paw_blur(self, event=None):
        if self._paw_focus is None:
            return None
        self._paw_focus = None
        self.draw_paws()
        return self._paw_focus
    def paw_at(self, y):
        """纵坐标离第几只爪最近（不在整列上返回 None）。"""
        try:
            y = float(y)
        except (TypeError, ValueError):
            return None
        if not 0 <= y < PAW_COL_HEIGHT:
            return None
        centre = PAW_SIZE / 2
        return min(range(len(PAW_LEVELS)),
                   key=lambda index: abs(y - (index * PAW_STEP + centre)))
    def paw_hover(self, event=None):
        """鼠标扫过那排爪：停在谁身上就把谁提亮，扫出去了就恢复。"""
        index = self.paw_at(getattr(event, 'y', None))
        if index == self._paw_hover:
            return index
        self._paw_hover = index
        self.draw_paws()
        return index
    def paw_leave(self, event=None):
        """鼠标离开那排爪：恢复成没停的样子。"""
        if self._paw_hover is None:
            return None
        self._paw_hover = None
        self.draw_paws()
        return self._paw_hover
    def paw_click(self, event=None):
        """点某个猫爪＝切到那一档（一次点到位，不用一轮一轮按）。"""
        index = self.paw_at(getattr(event, 'y', None))
        if index is None:
            return None
        return self.set_paw_level(PAW_LEVELS[index])
    def lift_patch(self):
        """三虎永远在最上层（第 19 期）：贴片、猫爪、等级小字各抬一次，别被内容框压住。"""
        for widget in (self.canvas, self.paws, self.caption):
            if widget is None:
                continue
            try:
                # 不能用 widget.lift()：Canvas 把 lift 覆写成了 tag_raise（抬手画布里的图元），
                # 无参调用只会报 wrong # args。直接走 Tcl 的 raise <窗口路径> 才是把窗口抬上去。
                widget.tk.call('raise', widget._w)
            except Exception as exc:
                self.errors.append(('lift', str(exc)))
        return self.canvas
    def _build_menu(self):
        """三虎的功能下拉栏（第 22 期／第 44 期）：越靠上越常按；等级仍由三虎身旁那排猫爪管。

        第 22 期按用户要求重排：① 独立小窗、② 自绘气泡两条彻底从功能栏拿掉；
        「暂停自动执行」改名「暂停」、「稍后再说」放回一级栏紧挨在它下面；
        「进度面板」回到功能栏（第 19 期被圆气泡顶替过），点开就是那十几行明细——
        第 24 期第 10 条：用户自己点开的这段时间里，三虎不再弹进度气泡。

        第 44 期照用户附件再对一遍：面板那一项叫「打开三虎面板」；「三虎设置」改名「设置」，
        下面四格＝基础功能／模型配置／自动化等级／预算（附件里的 SKILL 管理这一轮不做）；
        「稍后再说」改名「免打扰」；附件要的「退出」放回最后一行（按下去会先问一句）。

        第 59 期第 10 条：右键「设置」子菜单与齿轮那扇窗的分页同步（见 SETTINGS_ENTRIES）——名字一模一样。
        第 50 期第 3 条：用户报「三虎头像右键界面列表有点乱」——原来只有两条分隔线，
        十一项连成一大片。现在按用途分五块，块间用分隔线拉开：
        ① 和三虎说话（提问、一键收尾）；② 进度与待确认（面板、重试、详情、跳过）；
        ③ 设置与模型（设置、切换模型）；④ 运行状态（暂停／继续、免打扰）；⑤ 退出程序（单独一块，
        省得手一拖就点到）。块内次序照旧是「越靠上越常按」，所以只加线、不动顺序。

        第 60 期第 2 条：光有分隔线还是看不出「这一块是干什么的」——中间那三块各加一行灰色
        小标题（见 _add_section），用户扫一眼就知道该去哪一块找。头尾两块一眼就懂，不加。
        """
        import tkinter as tk
        self.menu = ContextMenu(self.win)
        # ① 和三虎说话：提问、一键收尾。
        self.menu.command('向三虎提问', lambda: self.act('chat'))
        self._add_menu('一键执行（重试＋补首帧＋日报）', lambda: self.act('oneclick'))
        self.menu.separator()
        # ② 进度与待确认的事：面板、重试、详情、跳过。
        self._add_section('进度与待确认')
        self._add_menu(PANEL_MENU_LABEL, lambda: self.act(self.show_panel, speak=False), name='panel')
        self._add_menu('重试失败项', lambda: self.act('retry'))
        self._add_menu(DETAIL_MENU_LABEL, lambda: self.act(self.show_details, speak=False))
        self._add_menu('跳过这张', lambda: self.act('skip'))
        self.menu.separator()
        # ③ 设置与模型：两子菜单。
        self._add_section('设置与模型')
        self._build_settings_menu()
        self._build_model_menu()
        self.menu.separator()
        # ④ 运行状态：自动化入口只保留猫爪，右键不再重复提供手动／全自动。
        self._add_section('运行状态')
        self._add_menu(self.pause_label(), lambda: self.act(self.pause_action), name='pause')
        self._add_menu(self.snooze_label(), lambda: self.act(self.toggle_snooze), name='snooze')
        self.menu.separator()
        # ⑤ 退出程序：单独一块（点错了真会关掉）。
        self._add_menu(QUIT_LABEL, lambda: self.act(self.quit_app), name='quit')
        return self.menu
    def pause_action(self):
        """「暂停 / 继续」按下去做什么：现在是哪一头就翻到另一头。"""
        return self.act('resume' if self.agent.paused else 'pause')
    def panel_text(self):
        """面板正文：按节分块、逐行编号（第 26 期第 4 条）。

        原来一行一条「名字：值」连着十几条，看不出哪些是「现在在做什么」、哪些是配额——
        用户报的就是「文字排版差、难阅读」。这里照 PANEL_SECTIONS 分三节，节名单独一行，
        每行「编号. 名字 · 值」；没列进分节表的新行也不会丢，统一落到最后一节。
        """
        rows = list(self.rows())
        known = {name for _title, names in PANEL_SECTIONS for name in names}
        blocks = [PANEL_HEAD]        # 第 36 期第 10 条：用户要的抬头「当前进度：」
        index = 0
        for title, names in PANEL_SECTIONS:
            picked = [(name, value) for name, value in rows if name in names]
            if not picked:
                continue
            lines = []
            for name, value in picked:
                index += 1
                lines.append('%d.%s%s%s%s' % (index, pet_cloud.NUMBER_GAP, name, PANEL_DIVIDER, value))
            blocks.append('【%s】\n%s' % (title, '\n'.join(lines)))
        rest = [(name, value) for name, value in rows if name not in known]
        if rest:
            lines = []
            for name, value in rest:
                index += 1
                lines.append('%d.%s%s%s%s' % (index, pet_cloud.NUMBER_GAP, name, PANEL_DIVIDER, value))
            blocks.append('【其它】\n%s' % '\n'.join(lines))
        return '\n'.join(blocks)
    def show_panel(self):
        """「进度面板」：在三虎旁的提示框展示分节后的完整进度，不创建弹窗。"""
        text = self.panel_text()
        self.notice = text
        self.note_panel()                      # 这次已主动查看完整进度，自动播报先让路
        self.progress_bubble(text=text)
        return text
    def pause_label(self):
        """菜单文字直接反映现在是哪一头（第 22 期：用户要的名字就是「暂停」）。"""
        return '继续' if self.agent.paused else '暂停'
    def mode_label(self):
        """控制面板入口文字始终反映三虎当前模式。"""
        return '模式：' + ('全自动' if self.mode == 'auto' else '手动')
    def _build_model_menu(self):
        """「切换模型」子菜单（第 43 期）：自动 ＋ 池里每一条（当前那条前面打 ✓）＋ 新增模型…。

        第 18 期起整栏重建一次就跟着变；第 43 期起条目来自模型池（模型管理），不再硬编码档位。
        """
        import tkinter as tk
        sub = self.menu.submenu()
        self.menu_tier = sub
        self._fill_model_menu()
        self._add_cascade(self.model_label(), sub, name='model')
        return sub
    def _build_settings_menu(self):
        """「设置」子菜单（第 44 期）：基础功能／三虎模型配置／自动化等级／预算／开发信息，
        每一格开的就是齿轮那扇窗的同一页（第 59 期第 10 条：两边同步，名字也一模一样）。

        附件里还有一格「SKILL 管理」——用户这一轮说不用做，所以这里不摆，也不留空占位。
        """
        import tkinter as tk
        sub = self.menu.submenu()
        self.menu_settings = sub
        for tab, label in SETTINGS_ENTRIES:
            sub.command(label, lambda key=tab: self.act(lambda: self.open_settings(key)))
        self._add_cascade(SETTINGS_LABEL, sub, name='settings')
        return sub
    def _add_section(self, title):
        """右键栏的分块小标题：灰色的、点不动，只用来告诉用户「这一块是干什么的」。

        第 60 期第 2 条。它不记序号——事后改文字（refresh_menu_labels）只认 model／pause／snooze
        那几项，标题永远不动，也就不会被算错。
        """
        self.menu.disabled('【%s】' % title)
        return title
    def _add_cascade(self, label, menu, name=None):
        """加一个子菜单并记下它的序号（序号用来事后改文字，不用 Tk 变量）。"""
        index = self.menu.index('end')
        self.menu.cascade(label, menu)
        index = 0 if index is None else index + 1
        if name:
            self.menu_index[name] = index
        return index
    def _add_menu(self, label, command, name=None):
        """加一个菜单项并记下它的序号（序号用来事后改文字，不用 Tk 变量）。"""
        index = self.menu.index('end')
        self.menu.command(label, command)
        index = 0 if index is None else index + 1
        if name:
            self.menu_index[name] = index
        return index
    def _bind(self):
        try:
            self.win.bind('<Destroy>', self.stop, add='+')
            # stop 清理退出资源；close_chat 另负责清空聊天引用，保持绑定顺序。
            # 自绘气泡也跟着主窗口走：主窗口没了，气泡留在屏幕上就是没人管的孤儿窗。
            # 云朵框同理：主窗口没了，浮层与它的定时器都要跟着停。
            self.win.bind('<Destroy>', self.close_chat, add='+')
        except Exception as exc:
            self.errors.append(('bind', str(exc)))
    def pet_click(self, event=None):
        """左键点三虎＝开／关云朵框（第 19 期：单击直接切换，不再借道下拉栏）。

        为什么还等 CLICK_MS：第二下（双击）该由 double_click 接管，单击才真的切一次；
        下拉栏改成只跟右键，不再跟弹出的菜单抢那一下点击（“再点一下关不掉”就是这么来的）。
        """
        return self._chat_interaction.request_single()
    def cloud_visible(self, sticker_only=False):
        """云朵框这会儿是不是真露着（含云朵框／圆／标签这些贴纸形态）。

        第 23 期：把原来那个「现在露着的是不是贴纸」并进来——两处问的其实是同一件事，
        分开写迟早走偏。sticker_only=True 只认贴纸（云朵对话框不算）：播报要能接着往
        对话里写，而「随口一句」不该把用户正在看的对话窗换掉。
        """
        cloud = self._cloud
        if cloud is None or not cloud.visible:
            return False
        return (cloud.shape != pet_cloud.SHAPE_CLOUD) if sticker_only else True
    def flip_chat(self, at=None):
        """单击的落点：云朵框开着就收起（并且安静一会儿），关着就打开。"""
        return self._chat_interaction.flip(at=at)
    def mute(self, seconds=CHAT_MUTE_SECONDS, at=None):
        """安静一会儿：这段时间里自动播报与进度气泡不再往外顶（用户刚把云点掉）。"""
        try:
            now = float(self.clock() if at is None else at)
            self._mute_until = max(self._mute_until, now + max(0.0, float(seconds)))
        except (TypeError, ValueError) as exc:
            self.errors.append(('mute', str(exc)))
        return self._mute_until
    def muted(self, at=None):
        """现在是不是在「刚点掉云朵框」的安静期里。"""
        try:
            return float(self.clock() if at is None else at) < float(self._mute_until)
        except (TypeError, ValueError):
            return False
    def cancel_click(self):
        """双击与退出共用协调 module 的待单击取消入口。"""
        return self._chat_interaction.cancel_pending()
    @property
    def _click_at(self):
        """保留既有观察口径，待点击只由协调 module 写入。"""
        return self._chat_interaction.pending
    def _cancel_chat_click(self, job):
        """Tk 调度 adapter：只吞掉已经销毁的 Tcl 任务。"""
        try:
            self.win.after_cancel(job)
        except TclError:
            # 延迟任务已被 Tk 清理。
            pass
    def double_click(self, event=None):
        """双击贴片＝直接和三虎说话（云朵框以对话形态打开）。"""
        return self._chat_interaction.request_double()
    def popup_at(self, x=None, y=None):
        """把功能下拉栏弹在鼠标处；拿不到鼠标坐标（键盘／程序触发）就落在贴片下沿。"""
        if self.menu is None:
            return None
        if x is None or y is None:
            try:
                x = self.canvas.winfo_rootx()
                y = self.canvas.winfo_rooty() + self.canvas.winfo_height()
            except Exception:
                x = y = 0
        # 第 47 期第 4 条：下拉栏显示期间三虎不弹聊天框／云朵框（见 broadcast 里那道闸）；
        # 栏里那几项自己开的界面（比如「向三虎提问」）照旧，不受这道闸影响。
        self._menu_open = True
        try:
            self.menu.popup_at(int(x), int(y))
        finally:
            self._menu_open = False
            self.say_held()
        return self.menu
    def say_held(self):
        """下拉栏／弹窗收起之后，把压住的那一句补上（没有就空操作）。

        云已经露着（栏里刚点开的对话／贴纸，或者刚被弹窗赶走、正在淡出）就先留着：
        用户正看着的那一朵不该被顶掉。第 59 期第 8 条：原来这里把压住的话直接丢了（那句话其实
        连记录都没进）；现在只是再等一下，下一次心跳等云收了再补说。
        """
        text = self.bstate.held_broadcast
        if not text or self.cloud_visible():
            return ''
        self.bstate.take_held()
        return self.broadcast(text)
    def popup(self, event=None):
        """右键贴片：同一张下拉栏（左键单击也走它）。"""
        return self.popup_at(getattr(event, 'x_root', None), getattr(event, 'y_root', None))
    def refresh(self, at=None, state=None):
        """重绘等级小字与猫爪，并把贴片抬到最上层（动画帧由定时器自己推进）。"""
        state = state if state else self.snapshot(at=at)
        try:
            self.show_caption()
            self.draw_paws()
            now = float(self.clock() if at is None else at)
            if self._lifted_at is None or (now - self._lifted_at) >= 1.0:
                self._lifted_at = now
                self.lift_patch()
        except Exception as exc:
            self.errors.append(('refresh', str(exc)))
        return self
