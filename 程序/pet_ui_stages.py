"""三虎的阶段推进、自动流程与一键制作。

从 ``pet_ui.Pet`` 原样迁出（R1506）：方法体未改，``self`` 语义不变，``Pet`` 通过继承
``PetStagesMixin`` 获得；用到的模块级名字来自 ``pet_ui_support``。
"""
import pet_agent
import pet_bus
import pet_cloud
import stage_flow
import stage_handler_registry
import stage_parallel
from tkinter import TclError
from ui_widgets import ask_confirmation, ask_string
from pet_ui_support import ADVANCE_SECONDS, AUTO_STAGE_VARIABLES, AUTO_VARIABLE_NAMES, CONFIRM_NEED, CONFIRM_TITLE, FALLBACK_ASK, LEVEL_SWITCH_NOTES, ONE_CLICK_ASK, ONE_CLICK_TITLE, PAGE_ASKS, PAW_LEVELS, SANHU_MODES, STAGE_ASK_SECONDS, _BooleanFlag, accepts_keyword


class PetStagesMixin:
    """Pet 的阶段推进方法集（见模块说明）。"""
    def _completion_evidence(self, stage):
        """返回某阶段是否已有可核验的落盘成果及未通过原因。

        自动任务的 ``ok`` 只代表调用没有抛异常：它可能只是提交了远端任务、生成了
        一段提示词，或者页面仍在等待用户采用。三虎只能把可复核的项目产物标成完成。
        没有项目的轻量宿主（旧插件和自检替身）不持久化阶段状态，保留其原有行为。
        """
        import stage_completion_service
        studio = getattr(self.desktop, 'studio', None)
        return stage_completion_service.completion_evidence(
            getattr(self.desktop, 'root', None), stage,
            getattr(studio, 'auto_edit_ready', None))
    def _complete_if_verified(self, stage, text):
        """唯一的自动完成出口；缺少产物时只停止运行态，绝不推进自动链。"""
        import stage_completion_service
        studio = getattr(self.desktop, 'studio', None)
        ok, detail, emitted = stage_completion_service.emit_verified_completion(
            getattr(self.desktop, 'root', None), stage, text, self._emit,
            getattr(studio, 'auto_edit_ready', None))
        if ok:
            return emitted
        self.last_status = '%s（待校验：%s）' % (text, detail)
        return self._emit('stage.paused', stage=stage, text=self.last_status)
    # ── 接缝：自动任务队列 / 状态栏 / 页面按钮 ─────────────────────────────
    def drain(self, stage, item):
        """接缝②：自动任务这一轮的结果 → 阶段事件；失败交给父 Agent 分级。"""
        try:
            ok, value = item[0], item[1]
        except (TypeError, IndexError, KeyError):
            return None
        text = str(value)
        self.last_status = text
        self._tick_texts.add(text)
        if ok:
            self.attempts[stage] = 0
            return self._complete_if_verified(stage, text)
        plan = self.agent.fail(stage, text, attempt=self.attempts.get(stage, 0))
        self.attempts[stage] = plan['next_attempt'] if plan['allow'] else 0
        return plan
    def _auto_stage_completed(self, item):
        """自动链只在成功收场后推进，并预告下一阶段给心跳安全启动。"""
        stage = str((item or {}).get('stage') or '')
        self.auto.done(stage, True)
        if self.mode != 'auto' or not self.auto.armed or self.auto.paused:
            return None
        pending = self.auto.pending()
        if not pending:
            return None
        next_stage = pending[0]
        self.bstate.reset_advance()
        name = pet_bus.STAGE_NAMES.get(next_stage, next_stage)
        self.broadcast('【下一阶段】%s - 自动开始' % name)
        return next_stage
    def _auto_stage_failed(self, item):
        """任一阶段失败均阻塞自动链，直到用户修复后手动恢复或重试。"""
        stage = str((item or {}).get('stage') or '')
        error = ' '.join(str((item or {}).get('error') or '').split())
        self.auto.done(stage, False, error)
        name = pet_bus.STAGE_NAMES.get(stage, stage or '当前阶段')
        detail = error or '该阶段未完成，等待用户处理'
        self.broadcast('【阻塞】%s 未完成，自动执行已停止：%s' % (name, detail))
        return None
    def report_done(self, stage, text, at=None):
        """接缝⑤：某一步的手工制作收了尾 → 三虎当场说一句（第 47 期第 5 条）。

        与自动任务那条 StageQueue 通道的区别在那条通道的节拍上：它要等下一次播报窗口
        （忙时 40 秒、闲时 180 秒，见 tick_broadcast），用户盯着页面等成品时这一句必须马上说，
        所以这里走 announce（与「用户按了东西」同一条出口）。

        「稍后再说」期间只记账不冒泡——那是用户自己点名要的安静；失败照旧由失败清单分级处理，
        不走这里。同一句话连着说两次由 broadcast 自己挡掉（bstate.last_broadcast）。
        """
        text = ' '.join(str(text or '').split())
        if not text:
            return ''
        try:
            import stage_completion_service
            # 自动链先由 script.completed 武装，再消费同一次的 stage.completed。
            # 反过来发会让队长尚未 armed 就吞掉完成事件，停在剧本阶段。
            studio = getattr(self.desktop, 'studio', None)
            verified, detail, _emitted = stage_completion_service.emit_verified_completion(
                getattr(self.desktop, 'root', None), stage, text, self._emit,
                getattr(studio, 'auto_edit_ready', None),
                (lambda: self._emit('script.completed', stage='script', text=text))
                if str(stage or '') == 'script' else None)
            if not verified:
                self.last_status = '%s（待校验：%s）' % (text, detail)
                self._emit('stage.paused', stage=str(stage or ''), text=self.last_status)
                return self.announce(self.last_status, at=at)
        except Exception as exc:
            self.errors.append(('report', str(exc)))
        if self.snoozing():
            self.notice = text
            return text
        return self.announce(text, at=at)
    def tune_advance(self, state=None, at=None):
        """自动推进（第 23 期）：等级允许时，把「下一步该做的那一步」提前叫醒一轮。

        Agent.advance() 一直在算「下一步是哪一步」，却从来没人用（只有用例在调）——自动化的
        最后一段路是断的。这里把它接上心跳：不代按任何按钮，只把这一步对应的无人值守轮询的
        due 拉到当前（跑不跑仍然由那一步自己的开关和退避说了算）。

        什么时候不推：只提醒档（advance 自己会返回 None）、忙、暂停、静默、有对话框露着、
        距上次推进不到 ADVANCE_SECONDS。换了一步才说一句，同一阶段不重复念。

        第 44 期（默认档改成半自动之后补的一条）：**开机第一拍只把活叫醒，不冒云**——原来第一次
        推进就会说一句，而默认半自动之后这必然发生在开机那一拍，正好撞上用户第 22 期报过的
        「开机闪一下云朵框」。叫醒照旧（这一步的轮询该跑就跑），只是那一句留到下一次换步再说。
        """
        try:
            now = float(self.clock() if at is None else at)
            if self.quiet(at=at):
                return ''                  # 第 68 期任务 11：招呼刚说完，推进那一步的话也留到安静期之后
            if self.bstate.advance_throttled(now, ADVANCE_SECONDS):
                return ''
            if self.cloud_visible() or self.muted(at=at) or self.snoozing() or self.agent.paused:
                return ''
            state = state if state else self.snapshot(at=at)
            if self.busy(state=state):
                return ''
            stage = self.auto_stage()
            first_beat = self.bstate.advance_at is None
            self.bstate.mark_advance(now)             # 到这一拍为止都算推过：没阶段可推也别每 150ms 问一遍
            if not stage:
                return self.gate_note(at=at)   # 第 63 期任务 3.2：被门禁停住就说一句
            # 第 67 期任务 5：自动档下不只把这一步叫醒——能自己派的就派下去、该打开的无人值守
            # 开关替他打开（见 start_stage）；放行不了的那几步照旧只叫醒。
            text = self.start_stage(stage, at=at)
            if first_beat:
                return ''                     # 开机第一拍：只叫醒不念（下一拍这一步仍会被念一次）
            if not text or text == self._last_advance:
                return ''
            self._last_advance = text
            return self.announce(text, at=at)
        except Exception as exc:
            self.errors.append(('advance.tune', str(exc)))
            return ''
    def retry_failures(self):
        """失败清单交给链路自己重跑（无人值守链路的下游节流清零），宠物只负责记账。"""
        count = len(self.agent.failures)
        kick = getattr(self.desktop, 'kick_unattended', None)
        if callable(kick):
            try:
                kick('pet')
            except Exception as exc:
                self.errors.append(('kick', str(exc)))
        self.agent.clear_failures()
        self.notice = ('已重试失败项：%d 项已交回链路重跑，无人值守会按原顺序继续' % count if count
                       else '现在没有待确认的项，不用重试')
        return True
    def skip_failure(self, item=None):
        """「跳过这张」：把一条待确认从清单里摘掉——用户显式跳过就是不再等它了。

        摘掉之后清单指纹变化，剩下那些仍然会被气泡提醒一次；清单本来就空就说明一句，
        不做任何别的事（跳过不等于重试，也不动状态机）。
        """
        entry = None
        try:
            entry = self.agent.skip_failure(item)
        except Exception as exc:
            self.errors.append(('skip', str(exc)))
        if entry is None:
            self.notice = '现在没有待确认的项，不用跳过'
            return ''
        stage = str(entry.get('stage') or '')
        category = str(entry.get('category') or '')
        self.notice = '已跳过一条待确认：%s · %s（还剩 %d 项）' % (
            pet_bus.STAGE_NAMES.get(stage, stage or '某阶段'),
            pet_agent.CATEGORY_NAMES.get(category, category or '未分类'), len(self.agent.failures))
        return self.notice
    # ── 对话落地：把「听懂了」变成「真的做了」（第 23 期）───────────────────
    def goto(self, stage, at=None):
        """切到某一页：真的把那一页翻开。

        原来对话里回一句「切到对应页面。」——页面一动不动，用户还得自己找。现在走宿主的
        pet_goto 真翻页；翻不动（没项目／认不出这一步）也老实说一句，不装作做过。
        """
        name = pet_bus.STAGE_NAMES.get(stage, '')
        if not name:
            self.notice = '这句话里没听出要切到哪一步，可以说「打开首帧管理」。'
            return self.notice
        go = getattr(self.desktop, 'pet_goto', None)
        page = ''
        if callable(go):
            try:
                page = str(go(stage) or '')
            except Exception as exc:
                self.errors.append(('goto', str(exc)))
        self.notice = ('已切到「%s」页' % name) if page else ('没能替您翻到「%s」页，自己点一下也行' % name)
        return self.notice
    def stage_states(self):
        """项目里每一步现在是什么状态（读不出来给空表＝一律当没做完）。"""
        try:
            return {stage: (entry or {}).get('state') for stage, entry in self.machine.stages.items()}
        except Exception as exc:
            self.errors.append(('states', str(exc)))
            return {}
    def arm_auto(self):
        """第 67 期任务 5：用户切到自动档之后，不必再做一次剧本——剧本做完了就按现状武装。

        第 54 期起那条链只在「剧本完成」这一条事件上武装；用户在早就做完剧本的项目里切到全自动，
        那一条事件不会再来，自动档于是一直什么都不开始。这里按项目现状补上（见 Auto.arm_from）：
        已经收场的那几步跳过，队长从第一个没做完的阶段接手。
        """
        level = self.agent.level
        if level not in stage_flow.AUTO_LEVELS:
            return False
        states = self.stage_states()
        # 用户可能在切换三虎自动档之前，已经通过「手动制作结构剧本」产出了正稿。
        # 那条手动工作流的历史事件不一定还在状态机里，不能因此把自动链卡在旧的
        # script / script_structure 状态。以真实落盘的正稿为准，并顺手登记到初步
        # 分镜的选择中；后者保证 storyboard_batch 立即有输入可派发，后续自动采用
        # 则会继续把生成的分镜同步给资产、首帧等页面。
        project = getattr(self.desktop, 'root', None)
        ready = self.has_structured_script(project)
        if ready:
            states = dict(states)
            # 旧项目只缺状态记录或仍是初始 pending 时，已有正稿可作为已完成依据；
            # 但本轮若已明确 failed/running/retrying，目录里残留的旧正稿不能掩盖
            # 这次失败，否则自动链会错误跳过结构剧本直接开始分镜。
            for stage in ('script', 'script_structure'):
                if str(states.get(stage) or '') in ('', 'pending'):
                    states[stage] = 'success'
            try:
                from storyboard_selection import sync_structured_script
                sync_structured_script(project)
            except (OSError, ValueError, TypeError) as exc:
                self.errors.append(('structured_script.sync', str(exc)))
                self.broadcast('【警告】结构剧本已存在，但同步分镜输入失败：%s；请稍后重试。' % exc)
        if str(states.get('script') or '') not in stage_flow.DONE_STATES:
            return False
        return self.auto.arm_from(level, states)
    @staticmethod
    def has_structured_script(project):
        """真实的结构剧本是否已落盘（兼容历史状态机没有记录的旧项目）。"""
        try:
            from script_contract import structured_script_path
            structured = structured_script_path(project) if project else None
            return bool(structured and structured.is_file() and structured.stat().st_size > 0)
        except (OSError, TypeError, ValueError):
            return False
    def start_stage(self, stage, at=None):
        """第 67 期任务 5：自动档下「自动开始每个阶段的任务」。

        能免费自己派的（分镜、首帧）走「手动制作XX」那一条准备链；其余各步交给宿主把这一步的
        无人值守开关打开并立刻起跑。半自动档会花钱的那几步只叫醒、等他点一下确认（与 approve
        同一条口径），hint 档一个字都不做。宿主没有这条接缝、或这一步不放行时，退回原来的
        「只叫醒轮询」。
        """
        if self.agent.level not in stage_flow.AUTO_LEVELS:
            # 第 67 期任务 4：只提醒档只看着——连「提前叫醒一轮」都不做，一个阶段都不替他开。
            return ''
        kick = getattr(self.desktop, 'pet_start', None)
        allowed = False
        if callable(kick):
            try:
                allowed = bool(self.agent.approve('stage.run', paid=stage in stage_flow.PAID_STAGES)['run'])
            except Exception as exc:
                self.errors.append(('start', str(exc)))
                allowed = False
        if allowed:
            # 所有阶段都必须经过宿主的 L3 命令入口。此前这里为结构剧本／分镜／首帧
            # 直接调用了三个批处理接缝，既绕过注册器，也使手动与自动拥有两套状态路径。
            # L3 再按阶段选择批处理或无人值守轮询；Pet 只负责授权与观察终态。
            started = ''
            try:
                started = str(kick(stage) or '')
            except Exception as exc:
                self.errors.append(('start', str(exc)))
                # L3 入口抛错也必须给 active 阶段一个终态，不能退回
                # advance_stage 后把“派发失败”伪装成仅仅提前叫醒。
                prefix = {
                    'script_structure': '剧本结构未派发：',
                    'storyboard': '分镜批次未派发：',
                    'keyframe': '首帧批次未派发：',
                }.get(stage, '阶段未派发：')
                started = prefix + str(exc)
            if started:
                # 三个本地批处理接缝会把异常转换成人可读文字。此前这里把那种
                # 非空错误文字误认成「已经启动」，自动链的 active 永远得不到终态事件。
                # 只识别本模块固定前缀，正常宿主返回的任意中文提示仍照旧透传。
                failed_prefix = {
                    'script_structure': '剧本结构未派发：',
                    'storyboard': '分镜批次未派发：',
                    'keyframe': '首帧批次未派发：',
                }.get(stage, '')
                if failed_prefix and started.startswith(failed_prefix):
                    self._emit('stage.failed', stage=stage, error=started)
                return started
        advanced = self.advance_stage(stage, at=at)
        if advanced:
            return advanced
        # 自动队长已经在 next_stage() 中把本阶段置为 active。宿主既没有可派发
        # 的批处理、也没有可提前叫醒的轮询时，继续静默返回会永久显示“自动执行中”。
        # 这不是成功；明确阻塞，让用户手动完成后再恢复自动链。
        if self.auto.armed and self.auto.active == stage:
            error = '当前版本没有「%s」的自动执行入口，请手动完成后再恢复自动流程' % (
                pet_bus.STAGE_NAMES.get(stage, stage))
            self._emit('stage.failed', stage=stage, error=error)
            return error
        return ''
    def auto_stage(self):
        """这一拍该推哪一步（附件四）：自动推进那条链武装了就按它走，否则退回状态机。

        hint（只提醒）档、暂停、链走完都会落到 agent.advance() 上——那一条本来就会返回
        None。第 67 期任务 5：链改由「用户切档」那一下按项目现状武装、切回只提醒时停手
        （见 arm_auto 与 Pet.set_level）；这里不再自己补——补了就等于每拍让链抢在状态机
        前面吃掉一格，「同一阶段连着叫醒几次」的老规矩会当场失效。
        """
        try:
            if self.auto.armed and not self.auto.paused:
                stage = self.auto.next_stage()
                if stage:
                    return stage
                if self.auto.blocked:
                    return None            # 第 63 期任务 3.2：被门禁停住就别去推别的阶段
        except Exception as exc:
            self.errors.append(('auto', str(exc)))
        return self.agent.advance()
    def log_stage(self, stage, status, detail='', release=False):
        """某一步的一个事件按统一格式落进 logs/（第 63 期任务 3.3）。

        只记账：写不进去、还号失败都绝不影响正在跑的那一步。released=True 的几个收场事件
        顺带把这一步手上的并发号还了——不还，闸门会一直当它还在跑。
        """
        try:
            self.agent.log_stage(stage, 'stage', status, detail)
        except Exception as exc:
            self.errors.append(('log', str(exc)))
        if release:
            try:
                self.agent.release_stage(stage)
            except Exception as exc:
                self.errors.append(('release', str(exc)))
    def gate_reason(self, stage):
        """这一步的上游门禁（第 63 期任务 3.2）：挡住了给一句人话，没挡住给空串。

        O24：把「正式自动生产」和「浏览／补录／旧项目兼容」分开——自动链在推（无人值守）时
        用正式生产口径：上游「还没开始」也当前置条件缺失拦住，除非用户显式把那一步标成
        「已跳过」；链没在推时沿用旧的浏览口径，旧项目不会因为严格门禁打不开。
        """
        # 结构剧本是分镜唯一的文件级上游。历史项目可能有成品却未留
        # script_structure.completed 事件；该情况下不要让状态机的旧账阻断
        # 自动派发，后面的阶段仍照常由各自真实产物门禁控制。
        if stage == 'storyboard' and self.has_structured_script(getattr(self.desktop, 'root', None)):
            return ''
        chain = getattr(self, 'auto', None)
        mode = (stage_parallel.PRODUCTION if getattr(chain, 'armed', False)
                else stage_parallel.BROWSE)
        try:
            return str(self.agent.blocked_reason(stage, mode=mode) or '')
        except Exception as exc:
            self.errors.append(('gate', str(exc)))
            return ''
    def parallel_snapshot(self):
        """并发现状（第 63 期任务 3.3）：在跑几个、降速几次、各阶段各几个。"""
        try:
            return self.agent.parallel_snapshot()
        except Exception as exc:
            self.errors.append(('parallel', str(exc)))
            return {'limit': 8, 'running': 0, 'slowed': 0, 'stages': {}, 'tickets': ()}
    def gate_note(self, at=None):
        """被门禁停住时补的一句：同一句只说一次，暂停或忙的时候不打扰用户。"""
        held = getattr(self.auto, 'blocked', None)
        if not held or self.auto.paused or self.agent.paused:
            self._gate_said = ''
            return ''
        reason = str(held[1] or '')
        if not reason or reason == self._gate_said:
            return ''
        self._gate_said = reason
        return self.announce(reason, at=at)
    def pause_running_stage(self):
        """暂停自动：正在跑的那一步按钮恢复「手动制作XX」（附件四第 7 条）。返回那几步。"""
        stages = [stage for stage in stage_flow.OWN_ORDER if stage_flow.running(stage)]
        for stage in stages:
            self._emit('stage.paused', stage=stage)
        return stages
    def advance_stage(self, stage, at=None):
        """让某一步的无人值守轮询提前跑一轮；返回宿主给的那句人话，没有这条路返回空串。

        只有宿主知道那一步有没有轮询、用户在页面上勾没勾开关，所以这里只负责问一句。
        """
        kick = getattr(self.desktop, 'pet_advance', None)
        if not callable(kick) or not stage:
            return ''
        try:
            return str(kick(stage) or '')
        except Exception as exc:
            self.errors.append(('advance', str(exc)))
            return ''
    def generate(self, stage, at=None):
        """「批量生成某一步」：能免费跑的立刻派单，跑不了的说清楚要用户在哪按。

        首帧走本机 ComfyUI 那条免费通道（与「一键执行」同一个入口）；其余几步要么花钱、
        要么得先有素材，一律不代按——最多把用户带到那一页，或者把用户勾过的无人值守开关
        提前叫醒一轮（叫醒之后跑不跑，仍然由那一步自己的开关说了算）。
        """
        name = pet_bus.STAGE_NAMES.get(stage, stage or '这一步')
        if stage == 'keyframe':
            self.notice = self.firstframe_batch() or '现在没有缺首帧的镜头，不用派单'
            return self.notice
        if stage == 'storyboard':
            # 第 62 期任务 2：三虎也能自己把分镜做起来（与「手动制作分镜」同一条准备链）。
            # 没有要做的新分镜时退回老路子——把「自动采用」那一轮提前叫醒。
            text = self.storyboard_batch()
            if text:
                self.notice = text
                return self.notice
            text = self.advance_stage(stage)
            self.notice = text or '分镜这一步现在没有要做的事：先去「初步分镜」页选好剧本。'
            return self.notice
        text = self.advance_stage(stage)
        if text:
            self.notice = text
            return self.notice
        paid = stage in ('assets', 'video', 'audio')
        if paid:
            self.goto(stage)
            self.notice = '「%s」这一步会花钱，三虎不代按：已经带您到那一页，按页面上的按钮就行' % name
            return self.notice
        self.notice = '「%s」这一步还没有能自动跑的路子，可以在页面上手动做' % name
        return self.notice
    def export_delivery(self, at=None):
        """「导出交付」：把用户带到「质检与交付」页——导出按钮在那儿，三虎不代按。"""
        self.goto('delivery')
        self.notice = '交付导出在「质检与交付」页：按「导出」就出清单（这一步三虎不代按）'
        return self.notice
    def run_plan(self, result, at=None):
        """把对话里那句「听懂了」真的落到处（第 23 期）。

        dispatch 在后台线程只出结论（纯读状态机与台账、不碰 Tk）；结论随云朵的队列回到心跳，
        由这里在界面线程办事。没登记的意图一律不动手——宁可什么都不做，也不能替用户按错按钮。
        返回一句「做了什么」的人话；没做就返回空串。
        """
        try:
            plan = (result or {}).get('plan') or {}
            decision = (result or {}).get('decision') or {}
            if not decision.get('run'):
                return ''                     # 没放行：理由已经在对话里说过了
            intent = str(plan.get('intent') or '')
            stage = plan.get('stage')
            if intent == 'goto':
                return self.goto(stage, at=at)
            if intent == 'generate':
                return self.generate(stage, at=at)
            if intent == 'skill':
                return self.run_skill(plan, at=at)
            if intent == 'export':
                return self.export_delivery(at=at)
            if intent in ('progress', 'panel', 'usage'):
                self.show_panel()
                return self.notice
            if intent == 'silence':
                self.click('snooze', at=at)
                return self.notice
            if intent == 'oneclick':
                # 用户在气泡里答过「好」的话（params.confirmed）就不再弹第二次确认窗。
                return self.one_click(at=at, confirm=not bool((plan.get('params') or {}).get('confirmed')))
            if intent in ('retry', 'skip', 'pause', 'resume', 'model', 'details'):
                self.click(intent, at=at)     # 与气泡／菜单共用同一份实现，不再各写一遍
                return self.notice
            if intent == 'level':
                target = (plan.get('params') or {}).get('level')
                if target is None:
                    return ''
                self.set_level(target, at=at)
                return self.notice
            if intent == 'projects':
                # 第 37 期第 1 条：「有哪些项目」「项目都怎么样了」——照着盘上的登记表念一遍。
                self.notice = self.projects_text(at=at)
                return self.notice
            if intent == 'report':
                _data, path = self.daily_report(at=at)
                self.notice = '日报已生成：' + (path.name if path else '（未落盘）')
                return self.notice
            if intent == 'weekly':
                path, _totals = self.weekly_report(at=at)
                self.notice = '周报已生成：' + (path.name if path else '（还没攒够数据）')
                return self.notice
            if intent == 'test':
                return self.run_test_mode(plan.get('params') or {}, at=at)
            if intent == 'performance':
                return self.run_performance_mode(at=at)
            if intent == 'performance_list':
                return self.run_performance_mode(kind='long_list', at=at)
            return ''                         # 没登记的意图不动手
        except Exception as exc:
            self.errors.append(('run_plan', str(exc)))
            # 对话已经承诺执行时，不能只在内部错误列表留下痕迹；否则云朵会显示
            # “听懂了”却没有任何完成或失败反馈。异常详情留在既有错误记录中，界面
            # 仅给出可操作的降级提示，避免把内部路径或凭据片段回显给用户。
            self.notice = '操作未完成，请稍后重试。'
            return self.notice
    def run_skill(self, plan, at=None):
        """「跑 SKILL」这条路上真的动手（第 28 期第 7 条）：读阶段配置 → 编排器跑 → 汇报。

        规格要的四件事都在这里接上：按 project.skillConfig[stage] 挑 SKILL、多个 SKILL 交给
        skill_orchestrator 分层执行、付费的并成一个气泡问一次、结果统一汇报给三虎说出去。
        """
        import skill_panel
        import skill_registry
        import skill_templates
        import stage_config
        params = plan.get('params') or {}
        stage = plan.get('stage')
        project = getattr(self.desktop, 'root', None)
        if project is None:
            self.notice = '还没打开项目——先建一个项目，我才好按 SKILL 动手。'
            self.show_progress(self.notice)
            return self.notice
        registry = skill_registry.default_registry()
        names = [str(item) for item in (params.get('skills') or [])]
        if not names and stage:
            names = [item.name for item in registry.getByStage(stage)]
        if stage:
            chosen = set(stage_config.get(project, stage, registry=registry)['skills'] or [])
            picked = [name for name in names if name in chosen]
            if not picked:
                self.notice = '「%s」这一阶段的 SKILL 都被您取消勾选了——先到阶段配置里勾上再说。' % stage
                self.show_progress(self.notice)
                return self.notice
            names = picked
        if not names:
            self.notice = '我没听出要跑哪几个 SKILL，说具体点？'
            self.show_progress(self.notice)
            return self.notice
        # 与「手动制作XX」走同一份上下文：单次（这句话里点名的模型）＞ 项目 ＞ 全局。
        context = skill_panel.stage_context(self.desktop, stage,
                                           extra={'model': str(params.get('model') or '')})
        orch = skill_panel.build_orchestrator(self.desktop, project)
        # 新项目会持有状态文件，但尚未写入 checkpoint；统一为空字典，恢复分支无需特判。
        checkpoint = ((orch.status.get('checkpoint') or {})
                      if isinstance(orch.status, dict) else {})
        resume_from = 1
        if stage and checkpoint.get('stage') == stage:
            resume_from = self._recovery_from[1] if self._recovery_from and self._recovery_from[0] == stage else 0
            if not resume_from:
                resume_from = orch.recover_from_checkpoint(
                    wait_for_user=self.recovery_choice,
                    broadcast=lambda text: self.broadcast(text, at=at, shape=pet_cloud.SHAPE_CLOUD))
            if resume_from:
                self._recovery_from = None
        # 第 54 期附件二第 6 条：手动与自动共用同一台编排器，只有 trigger 不同。
        # 这一条路是三虎自己动手，所以按「自动」记——正在跑的那一步按钮就写「自动执行中」。
        try:
            template = skill_templates.load_template(stage)
            template_answer = params.get('template_confirmation')
            wait_for_template = (lambda text: template_answer) if template_answer is not None else self.template_choice
            run = orch.run_stage_with_template(
                stage, context, names=names,
                # 「全自动」既可能从三虎模式切换进入，也可能从三虎等级菜单进入；两者都不能
                # 在模板门禁处重新弹窗。半自动仍由 template_choice 等用户确认。
                mode='auto' if (self.should_auto_run(template.process_id or stage)
                                or self.level() == 'auto') else 'manual',
                wait_for_user=wait_for_template,
                broadcast=lambda text: self.broadcast(text, at=at, shape=pet_cloud.SHAPE_CLOUD),
                start_step=resume_from or 1,
            )
        except (OSError, ValueError):
            run = orch.run(names, context, trigger='auto')
        pending = list(run.get('pending') or [])
        if pending:
            run = self.settle_paid(orch, run, pending, context)
        self.notice = str(run.get('text') or '').strip() or '这一批没跑出结果。'
        self.show_progress(self.notice)
        self.refresh(at=at)
        return self.notice
    def template_choice(self, text):
        """手动模板门禁：由用户确认生成类步骤；不可交互时保守跳过。"""
        try:
            return str(ask_string(self.win, '确认三虎步骤', text) or '').strip()
        except Exception as exc:
            self.errors.append(('template.ask', str(exc)))
            return ''
    def run_test_mode(self, params, at=None):
        """启动增量自检；真实完成由既有 pump 心跳汇报，绝不阻塞 Tk。"""
        if self._test_session is not None:
            self.notice = '增量自检正在运行，完成后会汇报结果。'
            return self.notice
        project = getattr(self.desktop, 'root', None)
        if project is None:
            self.notice = '还没打开项目，无法写入测试台账。'
            return self.notice
        try:
            self._test_session = stage_handler_registry.start(
                self.desktop, 'pet_test', trigger='manual', text=str(params.get('text') or ''))
            self.notice = '增量自检已启动，完成后汇报成功率与失败用例。'
        except Exception as exc:
            self.errors.append(('test.start', str(exc)))
            self.notice = '增量自检启动失败：' + str(exc)
        return self.notice
    def poll_test_mode(self, at=None):
        """复用 150ms pump 观察测试子进程；不创建额外线程或 Tk 定时器。"""
        if self._test_session is None:
            return ''
        try:
            result = stage_handler_registry.poll_pet_test(
                self._test_session, self.desktop.root, at=at)
            if result is None or result.get('running'):
                return ''
            self._test_session = None
            self.notice = str(result.get('text') or '')
            return self.announce(self.notice, at=at)
        except Exception as exc:
            self.errors.append(('test.poll', str(exc)))
            self._test_session = None
            self.notice = '增量自检失败：' + str(exc)
            return self.announce(self.notice, at=at)
    def run_performance_mode(self, kind='startup', at=None):
        """按用户指令启动短离线基准；只写当前项目的运行报告。"""
        if self._performance_session is not None:
            self.notice = '优化检查正在运行，完成后会汇报结果。'
            return self.notice
        project = getattr(self.desktop, 'root', None)
        if project is None:
            self.notice = '还没打开项目，无法写入优化检查台账。'
            return self.notice
        try:
            self._performance_session = stage_handler_registry.start(
                self.desktop, 'pet_performance', trigger='manual', kind=kind)
            label = '长列表优化检查' if kind == 'long_list' else '优化检查'
            self.notice = label + '已启动，完成后只汇报超过阈值的耗时退化。'
        except Exception as exc:
            self.errors.append(('performance.start', str(exc)))
            self.notice = '优化检查启动失败：' + str(exc)
        return self.notice
    def poll_performance_mode(self, at=None):
        """复用 pump 轮询短基准；不额外创建线程或 Tk 定时器。"""
        if self._performance_session is None:
            return ''
        try:
            result = stage_handler_registry.poll_pet_performance(
                self._performance_session, at=at)
            if result is None:
                return ''
            self._performance_session = None
            self.notice = str(result.get('text') or '')
            return self.announce(self.notice, at=at)
        except Exception as exc:
            self.errors.append(('performance.poll', str(exc)))
            self._performance_session = None
            self.notice = '优化检查失败：' + str(exc)
            return self.announce(self.notice, at=at)
    def recovery_choice(self, text):
        """等待用户从继续、跳过、重做中选一项；不可交互时不擅自恢复。"""
        asker = self.recovery_asker
        if callable(asker):
            try:
                return str(asker(text) or '').strip()
            except Exception as exc:
                self.errors.append(('recovery.ask', str(exc)))
                return ''
        try:
            return str(ask_string(self.win, '恢复三虎任务', text) or '').strip()
        except Exception as exc:
            self.errors.append(('recovery.ask', str(exc)))
            return ''
    def recover_project_checkpoint(self):
        """三虎启动时检查当前项目，并把用户选择留给下一次阶段执行。"""
        project = getattr(self.desktop, 'root', None)
        if project is None:
            return False
        try:
            import skill_panel
            orch = skill_panel.build_orchestrator(self.desktop, project)
            stage = (orch.status.get('checkpoint') or {}).get('stage')
            step = orch.recover_from_checkpoint(
                wait_for_user=self.recovery_choice,
                broadcast=lambda text: self.broadcast(text, shape=pet_cloud.SHAPE_CLOUD))
            if stage and step:
                self._recovery_from = (stage, step)
                return step
        except Exception as exc:
            self.errors.append(('recovery.start', str(exc)))
        return False
    def settle_paid(self, orch, run, pending, context):
        """付费 SKILL 合并确认：一个气泡问完，用户点头就接着把这几件做完。"""
        merged = '、'.join(row.get('name') or row['skill'] for row in pending)
        if any(row.get('queued') for row in pending):
            self.confirm('这几个要花钱的活先排着队（现在不打扰您）：' + merged)
            return run
        if not self.confirm_start('确认付费步骤', '这几个要花钱：%s（%s）\n\n现在做吗？'
                                  % (merged, '共 %d 件' % len(pending))):
            orch.confirm_all(False)
            return run
        orch.confirm_all(True)
        again = orch.run([row['skill'] for row in pending], context, trigger='auto')
        run['text'] = str(run.get('text') or '') + '\n' + str(again.get('text') or '')
        run['results'] = list(run.get('results') or []) + list(again.get('results') or [])
        run['failed'] = list(run.get('failed') or []) + list(again.get('failed') or [])
        return run
    def start_level(self):
        """开机那一档（第 67 期任务 4）：一律「只提醒」，用户上一次选的档不沿用。

        第 44 期把用户选的档写进了配置、下一次开机照它来；用户现在要的是「开机就是提示档」，
        所以这里只把这一刻的等级摁回默认那一档——配置里那把键照旧留着（他下次切档时会重写）。
        不冒云、不报错：开机那一下不打扰用户。

        这一档管**整次运行**：换项目会把内核整体重建（core 会重读盘上的设置），所以这里把档位
        记进 session_level，core 建完新 Agent 再照它设一遍——不记的话，一打开项目就把存档里
        那把旧档位读回来，「开机一律只提醒」等于没做。
        """
        self.session_level = pet_agent.DEFAULT_LEVEL
        self.mode = 'manual'
        try:
            self.agent.set_level(self.session_level)
        except Exception as exc:
            self.errors.append(('level', str(exc)))
        self.auto.armed = False
        self.auto.paused = False
        return self.level()
    def auto_variable(self, name):
        """返回三虎唯一创建的自动制作变量；页面不得自行创建或写入。"""
        if name not in AUTO_VARIABLE_NAMES:
            raise ValueError('未知自动制作变量：%s' % name)
        variable = self._auto_variables.get(name)
        if variable is None:
            if self.win is None:
                variable = _BooleanFlag(False)
            else:
                import tkinter as tk
                variable = tk.BooleanVar(master=self.win, value=False)
            self._auto_variables[name] = variable
            setattr(self, name, variable)
            # 兼容页面既有的属性读取；对象归属仍是三虎。
            setattr(self.desktop, name, variable)
        return variable
    def _set_all_auto_actions(self, enabled):
        """把项目中登记的全部自动制作开关统一设为同一个值。

        项目设置仅作持久化兼容；活动变量由三虎创建和写入，页面只读同一对象。
        """
        project = getattr(self.desktop, 'root', None)
        if project is None:
            return ()
        import project_settings
        failures = []
        for key in project_settings.DEFAULTS:
            setter = getattr(project_settings, 'set_' + key, None)
            if not callable(setter):
                failures.append(key)
                continue
            try:
                setter(project, bool(enabled))
            except (OSError, ValueError, KeyError, TypeError):
                failures.append(key)
        for name in AUTO_VARIABLE_NAMES:
            try:
                self.auto_variable(name).set(bool(enabled))
            except (AttributeError, TypeError, RuntimeError):
                failures.append(name)
        return tuple(failures)
    def enable_all_auto_actions(self):
        """全自动模式入口：打开当前项目的全部自动制作开关。"""
        return self._set_all_auto_actions(True)
    def disable_all_auto_actions(self):
        """手动模式入口：关闭当前项目的全部自动制作开关。"""
        return self._set_all_auto_actions(False)
    def set_mode(self, mode, at=None):
        """切换三虎手动／全自动模式，并统一接管页面自动制作开关。"""
        if mode not in SANHU_MODES:
            return None
        # 已有阶段在执行时，重复点“全自动”只是重复确认模式，不能重新 arm_auto()
        # 把 active 清空；否则下面的立即派发会把同一阶段再提交一次。
        keep_active = (mode == 'auto' and self.mode == 'auto' and self.auto.armed
                       and bool(self.auto.active))
        self.mode = mode
        try:
            if self.mode_var is not None:
                self.mode_var.set(mode)
        except TclError:
            # 仅允许窗口销毁竞态静默；变量类型或调用线程错误必须继续暴露。
            pass
        # 复用既有审批与自动推进链：手动＝只提醒，全自动＝全自动等级。
        if not keep_active:
            self.set_level('auto' if mode == 'auto' else 'hint', at=at)
        failed = self.enable_all_auto_actions() if mode == 'auto' else self.disable_all_auto_actions()
        label = '全自动' if mode == 'auto' else '手动'
        self.broadcast('【模式】已切换到%s模式' % label, at=at)
        self.broadcast('【模式】已%s全部自动制作开关' % ('打开' if mode == 'auto' else '关闭'), at=at)
        # 上面两句模式反馈会打开三虎气泡；若只等 tune_advance，气泡可见这一项
        # 门禁又会把刚武装的链路挡住，表现为用户切到全自动却没有任何制作开始。
        # 因此切换成功时立刻派发第一项；之后仍由正常心跳推进后续阶段。
        if mode == 'auto' and not keep_active and self.auto.armed and not self.auto.paused:
            try:
                stage = self.auto_stage()
                if stage:
                    started = self.start_stage(stage, at=at)
                    if started:
                        self.notice = started
            except Exception as exc:
                self.errors.append(('mode.start', str(exc)))
        if failed:
            self.broadcast('【警告】未能同步自动制作开关：' + '、'.join(failed), at=at)
        self.refresh_menu_labels()
        return self.mode
    def set_paw_level(self, level, at=None):
        """猫爪是唯一自动化入口：全自动同步开启，其他两档回到手动控制面。"""
        if level not in PAW_LEVELS:
            return None
        self.set_mode('auto' if level == 'auto' else 'manual', at=at)
        return self.set_level(level, at=at)
    def should_auto_run(self, stage_id):
        """按阶段 ID 读取三虎变量；全自动以外一律不自动执行。"""
        if self.mode != 'auto':
            return False
        try:
            name = AUTO_STAGE_VARIABLES.get(str(stage_id or '').strip())
            return bool(name and self.auto_variable(name).get())
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return False
    def set_level(self, level, at=None):
        """直接切到某一档自动化等级：切完必须把「现在是哪一档」说出来。

        第 19 期：猫爪按钮与右键菜单都走这里，提醒改用圆形气泡，猫爪的填色与头像颜色都立刻跟着变。
        """
        if level not in pet_agent.LEVELS:
            return None
        self.session_level = level         # 第 67 期任务 4：这一次运行照用户刚选的这一档
        try:
            self.agent.set_level(level)
        except Exception as exc:
            self.errors.append(('level', str(exc)))
            return None
        # 第 44 期：用户选的档写进全局配置——下一次开机照他选的这一档来，不再每次都退回出厂那档。
        try:
            pet_agent.save_settings({'level': level}, self.program)
        except Exception as exc:
            self.errors.append(('settings.level', str(exc)))
        # 第 67 期任务 5：切到半自动／全自动就按项目现状把那条链武装起来——剧本早就做完的
        # 项目里，script.completed 那条事件不会再来，不补这一下自动档会一直什么都不开始。
        if level in stage_flow.AUTO_LEVELS:
            try:
                if self.arm_auto():
                    # 切到自动档是明确的「现在开始」操作，不能被上一轮心跳留下的
                    # 推进节流挡住；下一个 UI 心跳应立即派发当前待办阶段。
                    self.bstate.reset_advance()
            except Exception as exc:
                self.errors.append(('level.arm', str(exc)))
        else:
            self.auto.armed = False        # 退回只提醒档：那条链立刻停手，一个阶段都不再开
        self.draw_paws(level)              # 猫爪按钮的填色＝当前档（不等下一帧）
        self.draw()                        # 头像颜色＝等级：这一下要立刻变色，不等下一帧
        text = LEVEL_SWITCH_NOTES.get(level, '已切换自动化等级')
        self.notice = text
        return self.whisper(text, at=at) or self.agent.level
    def one_click(self, at=None, confirm=True):
        """一键执行：把今天该收的尾一次做完——有失败项先重试，缺口交本地引擎补，再出一份当日日报。

        只做三件不花钱的事：重试记账、本地 ComfyUI 补首帧、日报落盘。凡是会产生费用的
        （Seedream 首帧、云端视频、配音），一律留给用户在各页面自己按，这里绝不代按。
        confirm=False 是给「用户已经在气泡里答了好」那条路用的（第 25 期第 3 条）：不再弹第二次。
        返回写进 self.notice 的那句话，出错也照样给一句话。
        """
        if confirm and not self.confirm_start():
            self.notice = '一键执行已取消：您按了「否」，这次什么都没做'
            self.show_progress(self.notice)
            self.refresh(at=at)
            return self.notice
        steps = []
        self.show_progress('一键执行中：重试失败项 → 本地补首帧 → 日报（进度就写在这里）')
        try:
            if self.agent.failures:
                self.retry_failures()
                steps.append('已重试失败项')
        except Exception as exc:
            self.errors.append(('one_click.retry', str(exc)))
        try:
            batch = self.firstframe_batch()
            if batch:
                steps.append(batch)
        except Exception as exc:
            self.errors.append(('one_click.firstframe', str(exc)))
        try:
            _data, path = self.daily_report(at=at)
            steps.append('日报已生成 ' + (path.name if path else '（未落盘）'))
        except Exception as exc:
            self.errors.append(('one_click.report', str(exc)))
        try:
            counts = self.counts()
            missing = int(counts['shots']) - int(counts['frames'])
            if missing > 0:
                steps.append('首帧还差 %d 个镜头' % missing)
        except Exception as exc:
            self.errors.append(('one_click.counts', str(exc)))
        self.notice = '一键执行：' + ('；'.join(steps) if steps else '没有可以自动收尾的事')
        self.show_progress(self.notice)
        self.refresh(at=at)
        return self.notice
    def storyboard_batch(self):
        """分镜缺口接进自动链路（第 62 期任务 2）：把「手动制作分镜」那条准备链交给宿主真的跑一遍。

        与 firstframe_batch 同一套：真正的派发在宿主（Desktop.pet_storyboard_batch）里做——
        那里才知道当前勾了哪些剧本／分镜、有没有正在跑的 Agent。宠物只负责把这件事说出来。
        宿主要么返回一句中文结果，要么返回空串（没有要做的分镜）。
        """
        dispatch = getattr(self.desktop, 'pet_storyboard_batch', None)
        if not callable(dispatch):
            return ''
        try:
            # 宿主需要知道这是自动链的派发：没有输入、或所有输入均已采用时，
            # 它才能给 active 的 storyboard 一个确定的终态事件。保留无参数
            # 接缝兼容，避免旧版宿主／自检替身被这次参数扩展打断；先认签名，只派发一次。
            return str((dispatch(trigger='auto') if accepts_keyword(dispatch, 'trigger') else dispatch()) or '')
        except Exception as exc:
            self.errors.append(('storyboard', str(exc)))
            return '分镜批次未派发：' + str(exc)
    def script_structure_batch(self):
        """把剧本结构阶段交给宿主执行，避免自动链停在没有轮询的确定性步骤。"""
        dispatch = getattr(self.desktop, 'pet_script_structure_batch', None)
        if not callable(dispatch):
            return ''
        try:
            return str(dispatch() or '')
        except Exception as exc:
            self.errors.append(('script_structure', str(exc)))
            return '剧本结构未派发：' + str(exc)
    def firstframe_batch(self, trigger='manual'):
        """首帧缺口接进自动链路：本地 ComfyUI 就绪时，按分镜顺序补一批缺首帧的镜头。

        真正的派发在宿主（Desktop.pet_frame_batch）里做——那里才知道当前分镜、批次忙不忙、
        本地引擎配没配好。宠物只负责「把缺口这件事说出来」，一个按钮都不替用户按；
        宿主要么返回一句中文结果，要么返回空串（没有缺口／没有项目）。
        """
        dispatch = getattr(self.desktop, 'pet_frame_batch', None)
        if not callable(dispatch):
            return ''
        try:
            # 自动链已经先把 keyframe 标成 active。将触发来源传给宿主，才能把
            # 「无分镜／没有缺口／暂时无法派发」收成明确阶段事件；无参数接缝仍兼容。
            # 先认签名、只派发一次：宿主内部抛的 TypeError 不能当成签名不符，再无参派发一遍。
            return str((dispatch(trigger=trigger) if accepts_keyword(dispatch, 'trigger') else dispatch()) or '')
        except Exception as exc:
            self.errors.append(('firstframe', str(exc)))
            return '首帧批次未派发：' + str(exc)
    def confirm_start(self, title=ONE_CLICK_TITLE, text=ONE_CLICK_ASK):
        """一键执行前的确认弹窗（第 18 期）：要自动制图，先问一句，别一按就跑起来。

        asker 可注入；默认经统一确认窗口，自检可换成假函数而不弹真窗。
        无界面或弹窗失败一律不放行，避免在未获确认时启动自动制作。
        """
        asker, parent = self.asker, None
        if asker is None:
            try:
                return bool(ask_confirmation(self.win, title, text, dangerous=True))
            except Exception as exc:
                self.errors.append(('ask', str(exc)))
                return False
        try:
            if parent is None:
                return bool(asker(title, text))
            return bool(asker(title, text, parent=parent))
        except Exception as exc:
            self.errors.append(('ask', str(exc)))
            return True
    def confirm(self, text, title=CONFIRM_TITLE):
        """三虎判断某件事要用户点头时说一句（第 16 期）。

        第 22 期：自绘气泡删了，要用户点头的事统一走云朵框——先写进记录，再当场播报出来；
        安静时段（「稍后再说」）只记账不说话。title 参数留着不删，旧调用点不用改。
        """
        text = ' '.join(str(text or '').split())
        if not text:
            return ''
        cloud = self.cloud()
        if cloud is not None:
            try:
                cloud.append(self._record_output('%s：%s（%s）' % (pet_agent.PET_NAME, text, CONFIRM_NEED)))
            except Exception as exc:
                self.errors.append(('confirm.cloud', str(exc)))
        if self.snoozing():
            return text
        # 第 26 期第 5 条：问用户「要不要办这件事」统一用绿色对话框——一眼就和播报分得开
        self.announce(text, shape=pet_cloud.SHAPE_CLOUD)
        return text
    def show_progress(self, text):
        """把「正在做什么」写到主界面状态栏：一键执行这类活儿跑在页面之外，用户找不到进度。

        状态栏拿不到才退回云朵框（self.notice），总之不许一点动静都没有。
        """
        text = ' '.join(str(text or '').split())
        if not text:
            return ''
        status = getattr(self.desktop, 'status', None)
        if status is not None:
            try:
                status.set(text)
                return text
            except Exception as exc:
                self.errors.append(('progress', str(exc)))
        self.notice = text
        return text
    def is_page_ask(self, line):
        """这一句是不是三虎在问「要不要做这一页的事」（换页时旧的那一句要让位）。

        第 37 期第 6 条「及时清理」落到实处的一条判据：只认自己问出去的那几句（PAGE_ASKS ＋
        兜底那一句），用户自己说的话、别的播报一个字都不动。
        """
        body = str(line or '')
        # 进页半自动会把当前进度与问句合并为同一条，换页时仍要识别并清理末行问句。
        if '\n' in body:
            body = body.rsplit('\n', 1)[-1]
        prefix = pet_agent.PET_NAME + '：'
        if not body.startswith(prefix):
            return False
        question = body[len(prefix):]
        return any(question == ask for ask, _command in PAGE_ASKS + (FALLBACK_ASK,))
    def page_name(self, page=None):
        """这一页叫什么（「08  首帧管理」这种）：从宿主的页表里读，读不到就退回序号。

        第 36 期第 6 条起名字以宿主的页表为准（desktop.PAGES），拿不到也不编。第 37 期第 5 条
        之后换页那句问句不再报页码，这里留着给别的入口（菜单、用例）用同一份口径。
        """
        try:
            index = int(getattr(self.desktop, 'page_index', 0) if page is None else page)
        except (TypeError, ValueError):
            return ''
        pages = list(getattr(self.desktop, 'PAGES', None) or [])
        if 0 <= index < len(pages):
            return ' '.join(str(pages[index]).split())
        return '第 %d 页' % (index + 1)
    def page_stage(self, index):
        """页序号 → 制作阶段：页表与 pet_bus.STAGES 一一对应。"""
        try:
            index = int(index)
        except (TypeError, ValueError):
            return ''
        stages = list(getattr(pet_bus, 'STAGES', ()) or ())
        return stages[index] if 0 <= index < len(stages) else ''
    def stage_failures(self, stage):
        """这一阶段上还等着用户点头的那些项（条数直接来自台账，不编）。"""
        try:
            return [item for item in self.agent.failures
                    if isinstance(item, dict) and str(item.get('stage') or '') == str(stage)]
        except Exception as exc:
            self.errors.append(('stage.failures', str(exc)))
            return []
    def stage_needs_user(self, index, at=None):
        """第 45 期：换到这一页，用户到底需不需要三虎开口——判据只有「有没有非他不可的事」。

        用户报的是「用户一换页三虎就弹对话框」，要改成「三虎自己判断」：纯粹翻页看看，一个字都
        不说；只有这一阶段真压着「失败待确认」（等他点个头才能接着往下走）时才开口。暂停期间也
        不打扰——那会儿三虎本来就不动手，问了也做不成。额度用光的提醒走预算播报那条路，
        不在这里重复一遍。
        """
        if getattr(self.agent, 'paused', False):
            return False
        stage = self.page_stage(index)
        return bool(stage) and bool(self.stage_failures(stage))
    def stage_entry_status(self, index):
        """进入制作页时的一句状态：只报当前阶段与进度，不创建新的助手窗口。"""
        stage = self.page_stage(index)
        name = pet_bus.STAGE_NAMES.get(stage, '当前阶段')
        try:
            raw_state = str(self.stage_states().get(stage) or 'pending')
            state = {
                'pending': '未开始', 'running': '进行中', 'success': '已完成',
                'failed': '待处理', 'blocked': '已阻塞', 'skipped': '已跳过',
            }.get(raw_state, raw_state)
        except Exception:
            state = '状态待读取'
        return '【阶段 %d/%d】%s：当前进度 %s' % (int(index) + 1, len(pet_bus.STAGES), name, state)
    def enter_stage(self, page=None, at=None):
        """统一进页规则：有待办才开口（R1948），提示档报进度，半自动征询，全自动按已选 SKILL 执行。"""
        try:
            index = int(getattr(self.desktop, 'page_index', 0) if page is None else page)
        except (TypeError, ValueError):
            return ''
        stage = self.page_stage(index)
        if not stage or not self.stage_has_todo(index):
            return ''
        status = self.stage_entry_status(index)
        level = self.level()
        if level == 'hint' or getattr(self.agent, 'paused', False):
            return self.broadcast(status, at=at)
        if level == 'semi':
            # 进度与确认合在同一朵云，避免状态云把确认云顶掉。
            return self.note_stage(index, at=at, force_prompt=True, intro=status)
        if level != 'auto':
            return self.broadcast(status, at=at)
        marker = (str(getattr(self.desktop, 'root', '') or ''), stage)
        self.broadcast(status, at=at)
        if marker in self._stage_auto_started:
            return status
        self._stage_auto_started.add(marker)
        # 分镜／结构／首帧各有文件级完成条件，不能把通用 SKILL 的“已派发”当成
        # 阶段完成。它们必须走与页面手动按钮相同的专用入口：由产物轮询、采用或
        # 本地校验发出 completed，才允许自动链进入下一阶段。
        if stage in ('script_structure', 'storyboard', 'keyframe'):
            result = self.start_stage(stage, at=at)
        else:
            # 其余阶段沿用既有模板／SKILL 编排器；不会打开或并发创建新的 Agent 窗口。
            result = self.run_skill({'stage': stage, 'params': {'skills': [], 'template_confirmation': '确认'}}, at=at)
        # 全自动可以代为产出剧本，但剧本内容仍由用户确认后再进入分镜。
        if stage == 'script' and result:
            self.confirm('确认剧本信息后，可继续制作分镜。')
        return result or status
    def script_downloaded(self, path=None, at=None):
        """已下载的真实剧本可完成阶段；模型首次回复仍不触发弹窗。"""
        try:
            from pathlib import Path
            saved = Path(path) if path else None
            source = saved if saved and saved.is_file() and saved.stat().st_size else None
        except (OSError, TypeError, ValueError):
            source = None
        if source is not None:
            # 同一轮先让自动队长武装，再结束 script；否则 completed 会被未武装的
            # 自动队长吞掉，保存成功仍无法进入结构剧本阶段。
            verified, detail = self._completion_evidence('script')
            if verified:
                self._emit('script.completed', stage='script', source=str(source))
                self._complete_if_verified('script', '剧本文档已下载')
            else:
                self._emit('stage.paused', stage='script',
                           text='剧本文档已下载（待校验：%s）' % detail)
        self.broadcast('【完成】剧本文档已下载', at=at)
        return self.confirm('【下一阶段】剧本已下载。现在制作分镜吗？')
    def note_stage(self, page=None, at=None, force_prompt=False, intro=''):
        """第 36 期第 6 条：用户换到别的阶段，三虎看一眼「这一步要不要我自动做」。

        旧的普通换页入口仍只给一句问句；进页协调器传入 intro 时会把「当前进度」与问句合并，
        既不另开窗口，也不会让状态提示把用户确认顶掉。
        对话框正开着的时候不另冒一朵：新的问句接着排进同一个框里（顺手清一清旧话），
        框里于是永远只有当前这一页的事。回车要做的那件事照旧 propose 给回复框。

        第 45 期：换页本身不再等于「该说话了」——先问 stage_needs_user（有没有非等用户点头的
        事），没有就安静地记下这一页。同一页重复问要隔 STAGE_ASK_SECONDS；暂停／静音／人不在
        界面里都不问——这时候再冒一个框只会更吵。返回问出去的那句话（没问返回空串）。
        """
        try:
            index = int(getattr(self.desktop, 'page_index', 0) if page is None else page)
        except (TypeError, ValueError):
            return ''
        try:
            now = float(self.clock() if at is None else at)
        except Exception as exc:
            self.errors.append(('stage.clock', str(exc)))
            return ''
        first_entry = self._stage_page is None
        if first_entry:
            self._stage_page, self._stage_at = index, now
            if not force_prompt:
                return ''                              # 旧入口：开机落在哪一页不算「换阶段」
        if index == self._stage_page and self._stage_at is not None \
                and (now - float(self._stage_at)) < STAGE_ASK_SECONDS \
                and not (force_prompt and first_entry):
            return ''                                  # 刚问过这一页：不重复问
        self._stage_page, self._stage_at = index, now
        try:
            if self.muted(at=at) or not self.can_pop():
                return ''
            if not force_prompt and not self.stage_needs_user(index, at=at):
                return ''                  # 第 45 期：没什么非等用户点头的事，这句就咽下去
            ask, command = self.chat_task(index)
            line = ('%s\n%s：%s' % (str(intro).strip(), pet_agent.PET_NAME, ask)) if intro else '%s：%s' % (pet_agent.PET_NAME, ask)
            chat = self.chat
            if chat is not None and getattr(chat, 'visible', False) and getattr(chat, 'pinned', False):
                # 对话框开着：这一页的问句接着排进去，框里跟着换页更新（不另冒一朵、不打断用户）。
                if command and hasattr(chat, 'propose'):
                    try:
                        chat.propose(command)
                    except Exception as exc:
                        self.errors.append(('stage.propose', str(exc)))
                if chat.lines and self.is_page_ask(chat.lines[-1]):
                    # 上一页问过的那一句让位：框里永远只有「当前这一页要不要做」，
                    # 换十页也不会攒成十句问句（第 37 期第 6 条）。
                    chat.pop()
                chat.append(line)
                chat.trim()                # 再顺手收一收：只留最近几段
                return line
            if self.cloud_visible():
                return ''                  # 已经有别的贴纸露着：不叠一个
            cloud = self.cloud()
            if cloud is not None and command and hasattr(cloud, 'propose'):
                try:
                    cloud.propose(command)
                except Exception as exc:
                    self.errors.append(('stage.propose', str(exc)))
            return self.broadcast(line, at=at, shape=pet_cloud.SHAPE_CLOUD)
        except Exception as exc:
            self.errors.append(('stage.ask', str(exc)))
            return ''
